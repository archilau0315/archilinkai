"""工程量分组汇总（V0.16，算量第 2 步）。

aggregate() 串起：query_engine 查 GUID（自动翻页取全量）
→ property_service 取量 → _group() 纯函数分组求和。
分组维度：type（构件类型）、story（楼层）、任意属性名。
"""

from __future__ import annotations

from typing import Any

import code_table
import formula_eval
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
        "description": "混凝土体积：按楼层汇总墙/柱/梁/板的净体积（含 3% 损耗）",
        "quantity": "General_NetVolume",
        "group_by": ["story"],
        "element_types": ["Wall", "Column", "Beam", "Slab"],
        "waste_factor": 0.03,
        "with_code": True,
    },
    "wall_area": {
        "description": "墙体面积：按楼层汇总所有墙的表面积",
        "quantity": "General_SurfaceArea",
        "group_by": ["story"],
        "element_types": ["Wall"],
        "with_code": True,
    },
    "wall_length": {
        "description": "墙体长度：按楼层汇总所有墙的 3D 长度",
        "quantity": "General_3DLength",
        "group_by": ["story"],
        "element_types": ["Wall"],
        "with_code": True,
    },
    "slab_area": {
        "description": "楼板面积：按楼层汇总板的净顶面积",
        "quantity": "General_NetTopSurfaceArea",
        "group_by": ["story"],
        "element_types": ["Slab"],
        "with_code": True,
    },
    "door_window_area": {
        "description": "门窗洞口面积：按类型统计门和窗的洞口面积（宽×高，GB 50500 规则）",
        "formula": "General_Width * General_Height",
        "formula_name": "洞口面积",
        "formula_unit": "m²",
        "group_by": ["type"],
        "element_types": ["Door", "Window"],
        "with_code": True,
    },
    "door_area": {
        "description": "门洞口面积：按楼层汇总门的洞口面积（宽×高）",
        "formula": "General_Width * General_Height",
        "formula_name": "洞口面积",
        "formula_unit": "m²",
        "group_by": ["story"],
        "element_types": ["Door"],
        "with_code": True,
    },
    "window_area": {
        "description": "窗洞口面积：按楼层汇总窗的洞口面积（宽×高）",
        "formula": "General_Width * General_Height",
        "formula_name": "洞口面积",
        "formula_unit": "m²",
        "group_by": ["story"],
        "element_types": ["Window"],
        "with_code": True,
    },
    "zone_area": {
        "description": "房间面积：按楼层汇总房间区域的计算面积",
        "quantity": "Zone_CalculatedArea",
        "group_by": ["story"],
        "element_types": ["Zone"],
        "with_code": True,
    },
    "column_count": {
        "description": "柱计数：按楼层统计柱的数量",
        "quantity": "General_Height",
        "group_by": ["story"],
        "element_types": ["Column"],
        "with_code": True,
    },
    "mep_length": {
        "description": "机电管线长度：按专业汇总风管/水管/桥架的长度",
        "quantity": "General_3DLength",
        "group_by": ["type"],
        "element_types": ["MEPRoutingElement"],
        "with_code": True,
    },
    "wall_summary": {
        "description": "墙体综合：体积+面积+长度按楼层同时出表",
        "quantities": ["General_NetVolume", "General_SurfaceArea", "General_3DLength"],
        "group_by": ["story"],
        "element_types": ["Wall"],
    },
    "wall_paint_area": {
        "description": "墙面涂刷面积：表面积*2（双面），公式法演示",
        "formula": "General_SurfaceArea * 2",
        "formula_name": "涂刷面积",
        "formula_unit": "m²",
        "group_by": ["story"],
        "element_types": ["Wall"],
    },
    "wall_composite_layers": {
        "description": "复合墙分层算量：内饰面面积/外饰面面积/核心层体积（V0.27 修正）",
        "quantities": ["Wall_NetInsideSurfaceArea", "Wall_NetOutsideSurfaceArea", "General_NetVolume"],
        "group_by": ["story"],
        "element_types": ["Wall"],
        "with_code": True,
    },
    "wall_insulation_area": {
        "description": "墙保温层面积：贴外墙外侧，按外饰面面积算（V0.27 修正）",
        "quantity": "Wall_NetOutsideSurfaceArea",
        "group_by": ["story"],
        "element_types": ["Wall"],
        "with_code": True,
    },
    "wall_core_volume": {
        "description": "墙核心层体积：净体积-内层-外层，结构层体积（V0.27 公式法）",
        "formula": "General_NetVolume - Wall_InsideSkinVolume - Wall_OutsideSkinVolume",
        "formula_name": "核心层体积",
        "formula_unit": "m³",
        "group_by": ["story"],
        "element_types": ["Wall"],
        "with_code": True,
    },
    "curtain_wall_area": {
        "description": "幕墙面积：按楼层汇总幕墙表面积（V0.28，幕墙无体积属性）",
        "quantity": "General_SurfaceArea",
        "group_by": ["story"],
        "element_types": ["CurtainWall"],
        "with_code": True,
    },
    "railing_length": {
        "description": "栏杆长度：按楼层汇总栏杆 3D 长度（V0.29，GB 50500 栏杆按 m 计）",
        "quantity": "General_3DLength",
        "group_by": ["story"],
        "element_types": ["Railing"],
        "with_code": True,
    },
    "concrete_volume_by_grade": {
        "description": "混凝土体积分强度：按楼层+类型+强度等级汇总（V0.30，概算分 C25/C30/C35/C40）",
        "quantity": "General_NetVolume",
        "group_by": ["story", "type", "General_ConcreteGrade"],
        "element_types": ["Wall", "Column", "Beam", "Slab"],
        "waste_factor": 0.03,
        "with_code": True,
    },
    "roller_shutter_area": {
        "description": "卷帘门面积：按楼层汇总防火卷帘门洞口面积（V0.30，GB 50500 规则）",
        "formula": "General_Width * General_Height",
        "formula_name": "洞口面积",
        "formula_unit": "m²",
        "group_by": ["story"],
        "element_types": ["Door"],
        "with_code": True,
    },
    "rebar_estimate": {
        "description": "钢筋估算：按混凝土体积×含钢率估算（V0.30，框架结构 0.12-0.18t/m³，默认 0.15）",
        "formula": "General_NetVolume * 0.15",
        "formula_name": "钢筋估算",
        "formula_unit": "t",
        "group_by": ["story", "type"],
        "element_types": ["Wall", "Column", "Beam", "Slab"],
        "with_code": True,
    },
    "formwork_area": {
        "description": "模板面积：按混凝土表面积×0.8 估算（V0.30，扣除底面/顶面不支模部分）",
        "formula": "General_SurfaceArea * 0.8",
        "formula_name": "模板面积",
        "formula_unit": "m²",
        "group_by": ["story", "type"],
        "element_types": ["Wall", "Column", "Beam", "Slab"],
        "with_code": True,
    },
    "facade_paint_area": {
        "description": "外墙真石漆面积：按外饰面面积算（V0.31，概算外檐工程）",
        "quantity": "Wall_NetOutsideSurfaceArea",
        "group_by": ["story"],
        "element_types": ["Wall"],
        "with_code": True,
        "code_override": {"code": "011406001", "name": "墙面喷刷涂料", "unit": "m²"},
    },
    "masonry_volume": {
        "description": "砌体体积：按楼层汇总砌体墙净体积（V0.31，需配合 filters 筛选砌体墙）",
        "quantity": "General_NetVolume",
        "group_by": ["story"],
        "element_types": ["Wall"],
        "with_code": True,
        "code_override": {"code": "010402001", "name": "砖砌体", "unit": "m³"},
    },
    "roof_waterproof_area": {
        "description": "屋面防水面积：按楼层汇总屋顶表面积（V0.35，GB 50500 屋面卷材防水）",
        "quantity": "General_SurfaceArea",
        "group_by": ["story"],
        "element_types": ["Roof"],
        "with_code": True,
        "code_override": {"code": "010902001", "name": "屋面卷材防水", "unit": "m²"},
    },
    "stair_concrete_volume": {
        "description": "楼梯混凝土体积：按楼层汇总楼梯净体积（V0.35）",
        "quantity": "General_NetVolume",
        "group_by": ["story"],
        "element_types": ["Stair"],
        "with_code": True,
        "code_override": {"code": "010506001", "name": "现浇混凝土楼梯", "unit": "m³"},
    },
    "column_concrete_volume": {
        "description": "柱混凝土体积：按楼层汇总柱净体积（V0.35，含 3% 损耗）",
        "quantity": "General_NetVolume",
        "group_by": ["story"],
        "element_types": ["Column"],
        "waste_factor": 0.03,
        "with_code": True,
        "code_override": {"code": "010502001", "name": "现浇混凝土矩形柱", "unit": "m³"},
    },
    "beam_concrete_volume": {
        "description": "梁混凝土体积：按楼层汇总梁净体积（V0.35，含 3% 损耗）",
        "quantity": "General_NetVolume",
        "group_by": ["story"],
        "element_types": ["Beam"],
        "waste_factor": 0.03,
        "with_code": True,
        "code_override": {"code": "010505001", "name": "现浇混凝土梁", "unit": "m³"},
    },
    "ceiling_area": {
        "description": "天棚抹灰面积：按楼层汇总板净底面面积（V0.35）",
        "quantity": "General_NetBottomSurfaceArea",
        "group_by": ["story"],
        "element_types": ["Slab"],
        "with_code": True,
        "code_override": {"code": "011301001", "name": "天棚抹灰", "unit": "m²"},
    },
    "floor_finish_area": {
        "description": "楼地面面层面积：按楼层汇总板净顶面面积（V0.35）",
        "quantity": "General_NetTopSurfaceArea",
        "group_by": ["story"],
        "element_types": ["Slab"],
        "with_code": True,
        "code_override": {"code": "011101001", "name": "水泥砂浆楼地面", "unit": "m²"},
    },
}


def get_template(name: str) -> dict[str, Any]:
    """按名取预设模板，找不到返回 None。"""
    return QUANTITY_TEMPLATES.get(name)


def validate_template(tpl: dict[str, Any]) -> None:
    """校验自定义模板字段，不合法抛 ValueError。

    必须含 quantity/quantities 或 formula 三者之一。
    可选 with_code（True 时按 GB 50500 清单编码附加 code 列）。
    """
    has_qty = "quantity" in tpl or "quantities" in tpl
    if not has_qty and "formula" not in tpl:
        raise ValueError("模板缺少 quantity/quantities 或 formula 字段")
    if "group_by" not in tpl:
        raise ValueError("模板缺少 group_by 字段")
    if "element_types" not in tpl:
        raise ValueError("模板缺少 element_types 字段")
    qty = tpl.get("quantities", tpl.get("quantity"))
    if isinstance(qty, str):
        tpl.setdefault("quantity", qty)
    elif isinstance(qty, list):
        tpl["quantities"] = qty


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
    rows: list[dict[str, Any]], group_by: list[str],
    quantity: str | list[str],
) -> list[dict[str, Any]]:
    """纯函数分组求和。rows 每项含维度字段 + 量值。

    quantity 支持 str（单量）或 list[str]（多量）。
    单量：每组 sum/avg/skipped_none
    多量：每组 sum_{qty}/avg_{qty}/skipped_none_{qty} + count
    """
    is_multi = isinstance(quantity, list)
    quantities = quantity if is_multi else [quantity]
    groups: dict[tuple, dict[str, Any]] = {}
    for row in rows:
        key = tuple(row.get(dim) for dim in group_by)
        g = groups.setdefault(
            key,
            {"group": dict(zip(group_by, key)), "count": 0},
        )
        g["count"] += 1
        for qty in quantities:
            v = row.get(qty)
            if is_multi:
                g.setdefault(f"sum_{qty}", 0.0)
                g.setdefault(f"skipped_none_{qty}", 0)
            else:
                g.setdefault("sum", 0.0)
                g.setdefault("skipped_none", 0)
            if isinstance(v, (int, float)):
                if is_multi:
                    g[f"sum_{qty}"] += v
                else:
                    g["sum"] += v
            else:
                if is_multi:
                    g[f"skipped_none_{qty}"] += 1
                else:
                    g["skipped_none"] += 1
    for g in groups.values():
        for qty in quantities:
            if is_multi:
                denom = g["count"] - g[f"skipped_none_{qty}"]
                g[f"avg_{qty}"] = round(g[f"sum_{qty}"] / denom, 4) \
                    if denom > 0 else None
                g[f"sum_{qty}"] = round(g[f"sum_{qty}"], 4)
            else:
                denom = g["count"] - g["skipped_none"]
                g["avg"] = (g["sum"] / denom) if denom > 0 else None
                g["sum"] = round(g["sum"], 4)
                if isinstance(g["avg"], float):
                    g["avg"] = round(g["avg"], 4)
    return sorted(groups.values(), key=lambda g: str(g["group"]))


def _flatten(groups: list[dict[str, Any]],
             quantity: str | list[str]) -> list[dict[str, Any]]:
    """把嵌套 group 展平成一行一条，方便直接转表格。"""
    is_multi = isinstance(quantity, list)
    quantities = quantity if is_multi else [quantity]
    out = []
    for g in groups:
        row = {**g["group"], "count": g["count"]}
        for qty in quantities:
            if is_multi:
                row[f"sum_{qty}"] = g.get(f"sum_{qty}")
                row[f"avg_{qty}"] = g.get(f"avg_{qty}")
                row[f"skipped_none_{qty}"] = g.get(f"skipped_none_{qty}")
                # 损耗系数列（V0.29 修复：flat_rows 也包含）
                if f"sum_with_waste_{qty}" in g:
                    row[f"sum_with_waste_{qty}"] = g[f"sum_with_waste_{qty}"]
            else:
                row["sum"] = g["sum"]
                row["avg"] = g["avg"]
                row["skipped_none"] = g["skipped_none"]
                # 损耗系数列（V0.29 修复：flat_rows 也包含）
                if "sum_with_waste" in g:
                    row["sum_with_waste"] = g["sum_with_waste"]
        row["element_names"] = ", ".join(g.get("element_names", []))
        out.append(row)
    return out


class AggregateService:
    """对外：按维度汇总工程量。"""

    def aggregate(
        self,
        quantity: str | list[str] | None = None,
        group_by: list[str] | None = None,
        element_type: str | None = None,
        stories: list[int] | None = None,
        filters: list[dict] | None = None,
        instance: str | None = None,
        classification: str | None = None,
        waste_factor: float | None = None,
        quantities: list[str] | None = None,
        formula: str | None = None,
        formula_name: str | None = None,
        formula_unit: str | None = None,
        with_code: bool | None = None,
        code_override: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """返回 {"unit"/"units", "rows", "flat_rows"}。

        quantity: 单量名(str) 或 quantities: 多量名(list)。
        formula: 算量规则公式（如 "General_NetVolume * 1.03"），优先于 quantity。
          formula 需配 formula_name（结果列名）和 formula_unit（单位）。
        waste_factor: 损耗系数（如 0.03=3%），结果加 sum_with_waste 字段。
        with_code: True 时按 GB 50500 清单编码附加 code/code_name/code_unit 列。
          每组按 type 查 code_table.lookup，要求 group_by 含 type（缺则自动加）。
        code_override: 模板级清单编码覆盖（如 {"code": "011406001", "name": "墙面喷刷涂料", "unit": "m²"}），
          用于同一 element_type 不同用途（如 Wall 用于真石漆/砌体）时指定正确编码。
        """
        if quantities and not quantity:
            quantity = quantities
        # formula 模式：提取公式引用的量名，合成单量列
        use_formula = bool(formula)
        if use_formula:
            formula_name = formula_name or "formula_result"
            qty_list = formula_eval.formula_vars(formula)
            quantity = formula_name
            is_multi = False
        else:
            if not quantity:
                raise ValueError("quantity 或 quantities 或 formula 至少传一个")
            is_multi = isinstance(quantity, list)
            qty_list = quantity if is_multi else [quantity]
        instance_manager.manager.get_info(instance)
        group_by = group_by or ["type"]
        # with_code：要求按 type 分项，每组唯一 type 才能查清单编码
        if with_code and "type" not in group_by:
            group_by = [*group_by, "type"]
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

        qvals = svc.get_quantities(guids, qty_list, instance)
        prop_dims = [d for d in group_by if d not in ("type", "story")]
        prop_vals = (
            svc.get_values(guids, prop_dims, instance) if prop_dims else {}
        )

        rows = []
        for s in summaries:
            row = {
                "name": s.get("name") or "",
                "type": s.get("element_type"),
                "story": s.get("story_index"),
            }
            for d in prop_dims:
                row[d] = prop_vals.get(s["guid"], {}).get(d)
            if use_formula:
                vars_dict = {
                    q: qvals.get(s["guid"], {}).get(q, {}).get("value")
                    for q in qty_list
                }
                row[formula_name] = formula_eval.eval_formula(formula, vars_dict)
            else:
                for q in qty_list:
                    row[q] = qvals.get(s["guid"], {}).get(q, {}).get("value")
            rows.append(row)
        groups = _group(rows, group_by, quantity)
        # 损耗系数
        if waste_factor:
            for g in groups:
                if is_multi:
                    for q in qty_list:
                        raw = g.get(f"sum_{q}", 0) or 0
                        g[f"sum_with_waste_{q}"] = round(raw * (1 + waste_factor), 4)
                else:
                    raw = g.get("sum", 0) or 0
                    g["sum_with_waste"] = round(raw * (1 + waste_factor), 4)
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
                if with_code:
                    if code_override:
                        info = code_override
                    else:
                        info = code_table.lookup(g["group"]["type"])
                    if info:
                        g["group"]["code"] = info["code"]
                        g["group"]["code_name"] = info["name"]
                        # formula 模式用 formula_unit，否则用 code_table 清单单位
                        g["group"]["code_unit"] = (
                            formula_unit if use_formula else info["unit"])
        # 单位
        if use_formula:
            units = formula_unit
        elif is_multi:
            units = {q: qvals.get(guids[0], {}).get(q, {}).get("unit")
                     if guids else None for q in qty_list}
        else:
            units = qvals.get(guids[0], {}).get(quantity, {}).get("unit") \
                if guids else None
        # 质量告警：量值缺失的元素（求和时按 0 处理，需提示用户）
        warnings = []
        for q in qty_list:
            n_missing = sum(1 for r in rows if r.get(q) is None)
            if n_missing and rows:
                pct = round(n_missing / len(rows) * 100, 1)
                warnings.append(
                    f"量值「{q}」缺失 {n_missing}/{len(rows)} 个元素"
                    f"（{pct}%），求和按 0 计")
        return {
            "unit" if not is_multi else "units": units,
            "rows": groups,
            "flat_rows": _flatten(groups, quantity),
            "warnings": warnings,
        }

    def aggregate_by_template(
        self,
        template_name: str,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """按预设模板算量。模板含 quantity 或 quantities + group_by + element_types。

        多 element_types 时分别汇总再合并。支持 waste_factor（损耗系数）。
        """
        tpl = get_template(template_name)
        if tpl is None:
            available = ", ".join(QUANTITY_TEMPLATES)
            raise ValueError(f"未知算量模板：{template_name}，可选：{available}")
        element_types = tpl["element_types"]
        is_multi = "quantities" in tpl
        quantity = tpl.get("quantities", tpl.get("quantity"))
        group_by = tpl["group_by"]
        waste = tpl.get("waste_factor")
        with_code = tpl.get("with_code")
        # formula 模式：合成单量列
        formula = tpl.get("formula")
        formula_name = tpl.get("formula_name")
        formula_unit = tpl.get("formula_unit")
        code_override = tpl.get("code_override")
        if formula:
            quantity = formula_name or "formula_result"
            is_multi = False
        qty_list = quantity if is_multi else [quantity]
        merged: dict[tuple, dict[str, Any]] = {}
        units: dict[str, str | None] = {}
        template_warnings: list[str] = []
        for et in element_types:
            r = self.aggregate(
                quantity=quantity, group_by=group_by,
                element_type=et, instance=instance,
                waste_factor=waste,
                formula=formula, formula_name=formula_name,
                formula_unit=formula_unit,
                with_code=with_code, code_override=code_override,
            )
            if is_multi:
                units.update(r.get("units", {}))
            else:
                units["_default"] = r.get("unit") or units.get("_default")
            template_warnings.extend(r.get("warnings", []))
            for row in r["rows"]:
                key = tuple(sorted(row["group"].items()))
                g = merged.setdefault(
                    key, {"group": row["group"], "count": 0,
                          "element_names": []})
                g["count"] += row["count"]
                g["element_names"].extend(row.get("element_names", []))
                for q in qty_list:
                    if is_multi:
                        g.setdefault(f"sum_{q}", 0.0)
                        g.setdefault(f"skipped_none_{q}", 0)
                        g[f"sum_{q}"] += row.get(f"sum_{q}", 0) or 0
                        g[f"skipped_none_{q}"] += row.get(f"skipped_none_{q}", 0)
                        if waste:
                            g.setdefault(f"sum_with_waste_{q}", 0.0)
                            g[f"sum_with_waste_{q}"] += row.get(f"sum_with_waste_{q}", 0) or 0
                    else:
                        g.setdefault("sum", 0.0)
                        g.setdefault("skipped_none", 0)
                        g["sum"] += row.get("sum", 0) or 0
                        g["skipped_none"] += row.get("skipped_none", 0)
                        if waste:
                            g.setdefault("sum_with_waste", 0.0)
                            g["sum_with_waste"] += row.get("sum_with_waste", 0) or 0
        for g in merged.values():
            for q in qty_list:
                if is_multi:
                    denom = g["count"] - g[f"skipped_none_{q}"]
                    g[f"avg_{q}"] = round(g[f"sum_{q}"] / denom, 4) if denom > 0 else None
                    g[f"sum_{q}"] = round(g[f"sum_{q}"], 4)
                    if waste:
                        g[f"sum_with_waste_{q}"] = round(g[f"sum_with_waste_{q}"], 4)
                else:
                    denom = g["count"] - g["skipped_none"]
                    g["avg"] = round(g["sum"] / denom, 4) if denom > 0 else None
                    g["sum"] = round(g["sum"], 4)
                    if waste:
                        g["sum_with_waste"] = round(g["sum_with_waste"], 4)
        rows = sorted(merged.values(), key=lambda g: str(g["group"]))
        return {
            "units" if is_multi else "unit": units if is_multi else units.get("_default"),
            "rows": rows,
            "flat_rows": _flatten(rows, quantity),
            "template": template_name,
            "description": tpl["description"],
            "warnings": template_warnings,
        }

    def aggregate_by_custom_template(
        self,
        template: dict[str, Any],
        instance: str | None = None,
    ) -> dict[str, Any]:
        """用户自定义模板算量。template 须含 quantity/quantities/formula + group_by + element_types，
        可选 description / waste_factor / formula_name / formula_unit / with_code。"""
        validate_template(template)
        element_types = template["element_types"]
        is_multi = "quantities" in template
        quantity = template.get("quantities", template.get("quantity"))
        group_by = template["group_by"]
        waste = template.get("waste_factor")
        with_code = template.get("with_code")
        formula = template.get("formula")
        formula_name = template.get("formula_name")
        formula_unit = template.get("formula_unit")
        code_override = template.get("code_override")
        if formula:
            quantity = formula_name or "formula_result"
            is_multi = False
        merged: dict[tuple, dict[str, Any]] = {}
        units: dict[str, str | None] = {}
        template_warnings: list[str] = []
        for et in element_types:
            r = self.aggregate(
                quantity=quantity, group_by=group_by,
                element_type=et, instance=instance,
                waste_factor=waste,
                formula=formula, formula_name=formula_name,
                formula_unit=formula_unit,
                with_code=with_code, code_override=code_override,
            )
            if is_multi:
                units.update(r.get("units", {}))
            else:
                units["_default"] = r.get("unit") or units.get("_default")
            template_warnings.extend(r.get("warnings", []))
            for row in r["rows"]:
                key = tuple(sorted(row["group"].items()))
                g = merged.setdefault(
                    key, {"group": row["group"], "count": 0,
                          "element_names": []})
                g["count"] += row["count"]
                g["element_names"].extend(row.get("element_names", []))
                qty_list = quantity if is_multi else [quantity]
                for q in qty_list:
                    if is_multi:
                        g.setdefault(f"sum_{q}", 0.0)
                        g.setdefault(f"skipped_none_{q}", 0)
                        g[f"sum_{q}"] += row.get(f"sum_{q}", 0) or 0
                        g[f"skipped_none_{q}"] += row.get(f"skipped_none_{q}", 0)
                        if waste:
                            g.setdefault(f"sum_with_waste_{q}", 0.0)
                            g[f"sum_with_waste_{q}"] += row.get(f"sum_with_waste_{q}", 0) or 0
                    else:
                        g.setdefault("sum", 0.0)
                        g.setdefault("skipped_none", 0)
                        g["sum"] += row.get("sum", 0) or 0
                        g["skipped_none"] += row.get("skipped_none", 0)
                        if waste:
                            g.setdefault("sum_with_waste", 0.0)
                            g["sum_with_waste"] += row.get("sum_with_waste", 0) or 0
        for g in merged.values():
            qty_list = quantity if is_multi else [quantity]
            for q in qty_list:
                if is_multi:
                    denom = g["count"] - g[f"skipped_none_{q}"]
                    g[f"avg_{q}"] = round(g[f"sum_{q}"] / denom, 4) if denom > 0 else None
                    g[f"sum_{q}"] = round(g[f"sum_{q}"], 4)
                    if waste:
                        g[f"sum_with_waste_{q}"] = round(g[f"sum_with_waste_{q}"], 4)
                else:
                    denom = g["count"] - g["skipped_none"]
                    g["avg"] = round(g["sum"] / denom, 4) if denom > 0 else None
                    g["sum"] = round(g["sum"], 4)
                    if waste:
                        g["sum_with_waste"] = round(g["sum_with_waste"], 4)
        rows = sorted(merged.values(), key=lambda g: str(g["group"]))
        return {
            "units" if is_multi else "unit": units if is_multi else units.get("_default"),
            "rows": rows,
            "flat_rows": _flatten(rows, quantity),
            "template": template.get("description", "custom"),
            "description": template.get("description", "自定义模板"),
            "warnings": template_warnings,
        }


service = AggregateService()
