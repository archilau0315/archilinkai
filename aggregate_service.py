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
from schemas import Filter, Operator, QueryRequest


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
    ) -> dict[str, Any]:
        """返回 {"unit": 单位, "rows": [_group 输出]}。

        group_by 维度："type"、"story" 或任意属性名（如 "结构类型"）。
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
                "type": s["element_type"],
                "story": s["story_index"],
                **{d: prop_vals.get(s["guid"], {}).get(d) for d in prop_dims},
                quantity: quantities.get(s["guid"], {}).get(quantity, {}).get("value"),
            }
            for s in summaries
        ]
        return {
            "unit": quantities.get(guids[0], {}).get(quantity, {}).get("unit")
            if guids else None,
            "rows": _group(rows, group_by, quantity),
        }


service = AggregateService()
