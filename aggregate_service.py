"""工程量分组汇总（V0.16，算量第 2 步）。

aggregate() 串起：query_engine 查 GUID（自动翻页取全量）
→ property_service 取量 → _group() 纯函数分组求和。
分组维度：type（构件类型）、story（楼层）、任意属性名。
"""

from __future__ import annotations

from typing import Any

import instance_manager
import property_service
from query_engine import engine, MAX_LIMIT
from tapir_adapter import _to_dict, adapter as _tapir
from schemas import Filter, Operator, QueryRequest

# 构件类型英→中映射
_TYPE_CN: dict[str, str] = {
    "Wall": "墙", "Column": "柱", "Beam": "梁", "Slab": "板",
    "Door": "门", "Window": "窗", "Stair": "楼梯", "Roof": "屋顶",
    "Morph": "变形体", "Mesh": "网面", "Opening": "洞口",
    "Zone": "房间区域", "Object": "对象", "Lamp": "灯具",
    "CurtainWall": "幕墙", "Railing": "栏杆", "Shell": "壳体",
    "Skylight": "天窗", "MEPRoutingElement": "机电管线",
}


def _fetch_story_names(instance: str | None) -> dict[int, str]:
    """取楼层 index→name 映射，失败返回空 dict。"""
    try:
        result = _tapir.execute("GetStories", None, instance)
        data = _to_dict(result)
        stories = data.get("stories", []) if isinstance(data, dict) else []
        return {s["index"]: s["name"] for s in stories if "index" in s and "name" in s}
    except Exception:
        return {}



# 字段与 aggregate() 参数一一对应；description 供人/模型理解用途
QUANTITY_TEMPLATES: dict[str, dict[str, Any]] = {
    "concrete_volume": {
        "description": "混凝土体积：按楼层汇总墙/柱/梁/板的净体积",
        "quantity": "General_NetVolume",
        "group_by": ["story"],
        "element_types": ["Wall", "Column", "Beam", "Slab"],
    },
    "wall_area": {
        "description": "墙体面积：按楼层汇总所有墙的表面积",
        "quantity": "General_SurfaceArea",
        "group_by": ["story"],
        "element_types": ["Wall"],
    },
    "wall_length": {
        "description": "墙体长度：按楼层汇总所有墙的 3D 长度",
        "quantity": "General_3DLength",
        "group_by": ["story"],
        "element_types": ["Wall"],
    },
    "slab_area": {
        "description": "楼板面积：按楼层汇总板的净顶面积",
        "quantity": "General_NetTopSurfaceArea",
        "group_by": ["story"],
        "element_types": ["Slab"],
    },
    "door_count": {
        "description": "门窗计数：按类型统计门和窗的数量",
        "quantity": "General_3DLength",
        "group_by": ["type"],
        "element_types": ["Door", "Window"],
    },
    "zone_area": {
        "description": "房间面积：按楼层汇总房间区域的计算面积",
        "quantity": "Zone_CalculatedArea",
        "group_by": ["story"],
        "element_types": ["Zone"],
    },
    "column_count": {
        "description": "柱计数：按楼层统计柱的数量",
        "quantity": "General_Height",
        "group_by": ["story"],
        "element_types": ["Column"],
    },
    "mep_length": {
        "description": "机电管线长度：按专业汇总风管/水管/桥架的长度",
        "quantity": "General_3DLength",
        "group_by": ["type"],
        "element_types": ["MEPRoutingElement"],
    },
}


def get_template(name: str) -> dict[str, Any]:
    """按名取模板，找不到返回 None。"""
    return QUANTITY_TEMPLATES.get(name)


def _fetch_all(request: QueryRequest, instance: str | None) -> list:
    """循环翻页取全部匹配元素（query 单次最多 MAX_LIMIT）。"""
    out, cursor = [], None
    while True:
        request.instance = instance
        request.cursor = cursor
        page = engine.query(request)
        out.extend(page.items)
        cursor = page.next_cursor
        if not cursor:
            return out


def _classification_guids(
    guids: list[str], item_name: str, instance: str | None
) -> set[str]:
    """按分类项名（分类树中的 id）筛出挂了该分类的元素 GUID。

    先全系统找 item 名 → 拿 item GUID，再批量读元素分类做匹配。
    """
    conn = instance_manager.manager.get_conn(instance)
    t = conn.types
    target: str | None = None
    for sys in conn.commands.GetAllClassificationSystems():
        sid = t.ClassificationSystemId(guid=sys.classificationSystemId.guid)
        stack = list(conn.commands.GetAllClassificationsInSystem(sid))
        while stack:
            it = stack.pop().classificationItem
            if it.id == item_name:
                target = str(it.classificationItemId.guid)
                break
            stack.extend(getattr(it, "children", None) or [])
        if target:
            break
    if target is None:
        raise ValueError(f"找不到分类项：{item_name}")
    elements = [t.ElementIdArrayItem(t.ElementId(guid=g)) for g in guids]
    system_ids = [
        t.ClassificationSystemIdArrayItem(
            t.ClassificationSystemId(guid=s.classificationSystemId.guid))
        for s in conn.commands.GetAllClassificationSystems()
    ]
    res = conn.commands.GetClassificationsOfElements(elements, system_ids)
    out = set()
    for g, r in zip(guids, res):
        for cid in getattr(r, "classificationIds", None) or []:
            item = getattr(cid.classificationId, "classificationItemId", None)
            if item and str(item.guid) == target:
                out.add(g)
    return out


def _group(
    rows: list[dict[str, Any]], group_by: list[str], quantity: str
) -> list[dict[str, Any]]:
    """纯函数分组求和。rows 每项含 guid/type/story/量值。

    返回 [{"group": {维度: 值}, "count": n, "sum": 和, "avg": 均}]，
    量值为 None 的元素计入 count 但不计入 sum（skipped_none 标注）。
    """
    groups: dict[tuple, dict[str, Any]] = {}
    for row in rows:
        key = tuple(row.get(dim) for dim in group_by)
        g = groups.setdefault(
            key,
            {"group": dict(zip(group_by, key)), "count": 0,
             "sum": 0.0, "skipped_none": 0},
        )
        g["count"] += 1
        v = row.get(quantity)
        if isinstance(v, (int, float)):
            g["sum"] += v
        else:
            g["skipped_none"] += 1
    for g in groups.values():
        g["avg"] = (g["sum"] / (g["count"] - g["skipped_none"])) \
            if g["count"] > g["skipped_none"] else None
        g["sum"] = round(g["sum"], 4)
        if isinstance(g["avg"], float):
            g["avg"] = round(g["avg"], 4)
    return sorted(groups.values(), key=lambda g: str(g["group"]))


def _flatten(groups: list[dict[str, Any]], quantity: str) -> list[dict[str, Any]]:
    """把嵌套 group 展平成一行一条，方便直接转表格。

    {"group": {"story": 1, "story_name": "二层"}, "count": 2, "sum": 5.0}
    → {"story": 1, "story_name": "二层", "count": 2, "sum": 5.0}
    """
    return [
        {
            **g["group"],
            "count": g["count"],
            "sum": g["sum"],
            "avg": g["avg"],
            "skipped_none": g["skipped_none"],
            "element_names": ", ".join(g.get("element_names", [])),
        }
        for g in groups
    ]


class AggregateService:
    """对外：按维度汇总工程量。"""

    def aggregate(
        self,
        quantity: str,
        group_by: list[str] | None = None,
        element_type: str | None = None,
        stories: list[int] | None = None,
        filters: list[dict] | None = None,
        instance: str | None = None,
        classification: str | None = None,
    ) -> dict[str, Any]:
        """返回 {"unit": 单位, "rows": [_group 输出]}。

        group_by 维度："type"、"story" 或任意属性名（如 "结构类型"）。
        classification：只统计挂了该分类项的元素（算量归并维度）。
        """
        instance_manager.manager.get_info(instance)  # 实例不存在在此报错
        group_by = group_by or ["type"]
        flt = [
            Filter(f["field"], Operator(f.get("operator", "=")), f["value"])
            for f in (filters or [])
        ]
        req = QueryRequest(
            element_type=element_type, stories=stories,
            filters=flt, limit=MAX_LIMIT,
        )
        summaries = _fetch_all(req, instance)
        if classification:
            keep = _classification_guids(
                [s["guid"] for s in summaries], classification, instance)
            summaries = [s for s in summaries if s["guid"] in keep]
        guids = [s["guid"] for s in summaries]
        svc = property_service.service

        quantities = svc.get_quantities(guids, [quantity], instance)
        # 属性分组维度需另取属性值
        prop_dims = [d for d in group_by if d not in ("type", "story")]
        prop_vals = (
            svc.get_values(guids, prop_dims, instance) if prop_dims else {}
        )

        rows = [
            {
                "name": s.get("name") or "",
                "type": s.get("element_type"),
                "story": s.get("story_index"),
                **{d: prop_vals.get(s["guid"], {}).get(d) for d in prop_dims},
                quantity: quantities.get(s["guid"], {}).get(quantity, {}).get("value"),
            }
            for s in summaries
        ]
        groups = _group(rows, group_by, quantity)
        # 补全楼层名、类型中文名、构件名列表
        story_map = _fetch_story_names(instance) if "story" in group_by else {}
        name_map: dict[tuple, list[str]] = {}
        for row in rows:
            key = tuple(row.get(d) for d in group_by)
            name_map.setdefault(key, []).append(row.get("name", ""))
        for g in groups:
            key = tuple(g["group"].get(d) for d in group_by)
            g["element_names"] = name_map.get(key, [])
            if "story" in g["group"]:
                g["group"]["story_name"] = story_map.get(
                    g["group"]["story"], str(g["group"]["story"]))
            if "type" in g["group"]:
                g["group"]["type_name"] = _TYPE_CN.get(
                    g["group"]["type"], g["group"]["type"])
        return {
            "unit": quantities.get(guids[0], {}).get(quantity, {}).get("unit")
            if guids else None,
            "rows": groups,
            "flat_rows": _flatten(groups, quantity),
        }

    def aggregate_by_template(
        self,
        template_name: str,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """按预设模板算量。模板含 quantity/group_by/element_types。

        多 element_types 时分别汇总再合并（相同维度键的 sum 相加、count 相加）。
        """
        tpl = get_template(template_name)
        if tpl is None:
            available = ", ".join(QUANTITY_TEMPLATES)
            raise ValueError(f"未知算量模板：{template_name}，可选：{available}")
        element_types = tpl["element_types"]
        quantity = tpl["quantity"]
        group_by = tpl["group_by"]
        merged: dict[tuple, dict[str, Any]] = {}
        unit = None
        for et in element_types:
            r = self.aggregate(
                quantity=quantity, group_by=group_by,
                element_type=et, instance=instance,
            )
            unit = r.get("unit") or unit
            for row in r["rows"]:
                key = tuple(sorted(row["group"].items()))
                g = merged.setdefault(
                    key, {"group": row["group"], "count": 0,
                          "sum": 0.0, "skipped_none": 0,
                          "element_names": []})
                g["count"] += row["count"]
                g["sum"] += row["sum"]
                g["skipped_none"] += row.get("skipped_none", 0)
                g["element_names"].extend(row.get("element_names", []))
        for g in merged.values():
            denom = g["count"] - g["skipped_none"]
            g["avg"] = round(g["sum"] / denom, 4) if denom > 0 else None
            g["sum"] = round(g["sum"], 4)
        rows = sorted(merged.values(), key=lambda g: str(g["group"]))
        return {
            "unit": unit,
            "rows": rows,
            "flat_rows": _flatten(rows, quantity),
            "template": template_name,
            "description": tpl["description"],
        }


service = AggregateService()
