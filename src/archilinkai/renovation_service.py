"""翻新状态（拆除 / 新建 / 现有）读取与统计模块（V0.58）。

翻新状态是 ArchiCAD 内置属性，属性名固定为 Category_RenovationStatus，
取值四选一：Existing（现有）/ ToBeDemolished（要拆除）/ New（新建）/
Undefined（未定义）。本模块把该属性归一化、批量读取并按类型×状态计数，
供「拆除 / 新建分别算量」使用。
"""
from __future__ import annotations

from typing import Any

from archilinkai import i18n
from archilinkai import property_service
from archilinkai.schemas import QueryRequest
from archilinkai.query_engine import MAX_LIMIT

RENOVATION_PROP = "Category_RenovationStatus"
STATUSES = ("Existing", "ToBeDemolished", "New", "Undefined")

# 规范值 → 中文显示名
STATUS_CN = {
    "Existing": "已建",
    "ToBeDemolished": "拆除",
    "New": "新建",
    "Undefined": "未定义",
}

# 用户可传入的别名（小写键）→ 规范值
_INPUT_ALIASES = {
    "existing": "Existing", "现有": "Existing", "已建": "Existing", "现状": "Existing",
    "tobedemolished": "ToBeDemolished", "demolished": "ToBeDemolished",
    "拆除": "ToBeDemolished", "要拆除": "ToBeDemolished",
    "new": "New", "新建": "New",
    "undefined": "Undefined", "未定义": "Undefined",
}


def normalize_status(s: Any) -> str | None:
    """归一化入参为规范状态值。

    None / "all" / "" → None（表示不过滤）；非法值也返回 None。
    """
    if s is None:
        return None
    key = str(s).strip().lower()
    if key in ("", "all"):
        return None
    return _INPUT_ALIASES.get(key)


def get_status_map(
    guids: list[str], instance: str | None = None,
) -> dict[str, str]:
    """批量读翻新状态，返回 {guid: 状态}；缺失或非法值补 "Undefined"。"""
    if not guids:
        return {}
    values = property_service.service.get_values(guids, [RENOVATION_PROP], instance)
    out: dict[str, str] = {}
    for g in guids:
        v = values.get(g, {}).get(RENOVATION_PROP)
        out[g] = v if v in STATUSES else "Undefined"
    return out


def label(status: str, default_zh: str | None = None) -> str:
    """状态显示名（en 目录键 renovation.<状态>）。"""
    fallback = default_zh or STATUS_CN.get(status, status)
    return i18n.t(f"renovation.{status}", fallback)


def _fetch_summaries(
    element_types: list[str] | None, instance: str | None,
) -> list:
    """按类型取元素摘要；element_types 为空时取全部元素。"""
    from archilinkai.aggregate_service import _fetch_all
    types = element_types or [None]
    out: list = []
    for et in types:
        req = QueryRequest(element_type=et, limit=MAX_LIMIT)
        out.extend(_fetch_all(req, instance))
    return out


def summarize(
    element_types: list[str] | None = None, instance: str | None = None,
) -> dict[str, Any]:
    """按「类型 × 状态」统计元素数。

    返回 {"total": N, "by_status": {状态: n}, "by_type": {类型: {状态: n}},
    "element_count": {类型: n}}。
    """
    summaries = _fetch_summaries(element_types, instance)
    guids = [s["guid"] for s in summaries]
    status_map = get_status_map(guids, instance)
    by_status: dict[str, int] = {s: 0 for s in STATUSES}
    by_type: dict[str, dict[str, int]] = {}
    element_count: dict[str, int] = {}
    for s in summaries:
        st = status_map.get(s["guid"], "Undefined")
        et = s.get("element_type") or "Unknown"
        by_status[st] = by_status.get(st, 0) + 1
        bt = by_type.setdefault(et, {x: 0 for x in STATUSES})
        bt[st] = bt.get(st, 0) + 1
        element_count[et] = element_count.get(et, 0) + 1
    return {
        "total": len(summaries),
        "by_status": by_status,
        "by_type": by_type,
        "element_count": element_count,
    }
