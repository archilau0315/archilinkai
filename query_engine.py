"""BIM 条件查询引擎（V0.3 8.4）+ 分页（V0.3 8.8）。

执行顺序：
    Element Type → Story/basic details → Classification →
    Property ID resolution → Property values → Local filtering →
    Pagination → Structured result

禁止默认进行全模型的无条件属性/几何读取。
属性条件必须走本地比对（Tapir FilterElements 不支持按属性值搜索）。
"""

from __future__ import annotations

import base64
import json
from typing import Any

import instance_manager
import property_service
from errors import PaginationInvalidError
from schemas import (
    ElementSummary,
    Filter,
    Operator,
    PageResult,
    QueryRequest,
)
from tapir_adapter import adapter as _tapir

# 单次返回元素数量默认上限，避免大量 BIM 数据灌入 LLM 上下文
DEFAULT_LIMIT = 100
MAX_LIMIT = 1000


def apply_operator(actual: Any, operator: Operator, target: Any) -> bool:
    """对单个过滤条件做本地比对。

    数值比较时尽量转 float；字符串比较时大小写不敏感（contains/starts_with）。
    无法比较时返回 False（保守过滤，避免误返回）。
    """
    try:
        if operator == Operator.EQ:
            return _normalize(actual) == _normalize(target)
        if operator == Operator.NE:
            return _normalize(actual) != _normalize(target)
        if operator in (Operator.GT, Operator.GE, Operator.LT, Operator.LE):
            a = _to_number(actual)
            t = _to_number(target)
            if a is None or t is None:
                return False
            return {
                Operator.GT: a > t,
                Operator.GE: a >= t,
                Operator.LT: a < t,
                Operator.LE: a <= t,
            }[operator]
        if operator == Operator.CONTAINS:
            return str(target).lower() in str(actual).lower()
        if operator == Operator.STARTS_WITH:
            return str(actual).lower().startswith(str(target).lower())
        if operator == Operator.IN:
            targets = target if isinstance(target, (list, tuple)) else [target]
            return _normalize(actual) in {_normalize(t) for t in targets}
    except Exception:
        return False
    return False


def _normalize(value: Any) -> Any:
    """归一化比较值：数值统一 float，字符串去空白。"""
    if isinstance(value, str):
        s = value.strip()
        n = _to_number(s)
        return n if n is not None else s.lower()
    return value


def _to_number(value: Any) -> float | None:
    """尝试转 float；失败返回 None。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return None


# --- 分页游标（base64 编码的 offset，避免暴露内部细节） -------------------


def encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"o": offset}).encode()).decode()


def decode_cursor(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        offset = int(payload.get("o", 0))
        if offset < 0:
            raise ValueError
        return offset
    except Exception as exc:
        raise PaginationInvalidError(f"cursor 解析失败：{cursor}") from exc


class QueryEngine:
    """查询引擎。"""

    def __init__(self, mgr: instance_manager.InstanceManager) -> None:
        self._mgr = mgr

    def query(self, request: QueryRequest) -> PageResult:
        """执行查询，返回分页结果。

        步骤：
          1. 按类型缩小范围（GetElementsByType / GetAllElements）
          2. 取详情（Tapir GetDetailsOfElements），按楼层/名称过滤
          3. 按属性值过滤（GetPropertyIds → GetPropertyValuesOfElements → 本地比对）
          4. 分页
        """
        limit = self._validate_limit(request.limit)
        offset = decode_cursor(request.cursor)

        # 1. 按类型缩小范围，得到 GUID 列表
        guids = self._get_guids_by_type(request.element_type, request.instance)
        if not guids:
            return PageResult(items=[], count=0, next_cursor=None)

        # 2. 取详情，按楼层/名称过滤
        summaries = self._filter_by_details(
            guids, request.stories, request.instance
        )
        if not summaries:
            return PageResult(items=[], count=0, next_cursor=None)

        # 3. 按属性值过滤
        if request.filters:
            summaries = self._filter_by_properties(
                summaries, request.filters, request.instance
            )

        # 4. 分页
        return self._paginate(summaries, offset, limit)

    # --- 步骤实现 ---------------------------------------------------------

    def _validate_limit(self, limit: int) -> int:
        if limit <= 0:
            raise PaginationInvalidError(f"limit 必须 > 0，收到 {limit}")
        if limit > MAX_LIMIT:
            return MAX_LIMIT
        return limit

    def _get_guids_by_type(
        self, element_type: str | None, instance: str | None
    ) -> list[str]:
        """按类型获取元素 GUID。未指定类型时用 GetAllElements。"""
        conn = self._mgr.get_conn(instance)
        if element_type:
            # archicad 原生 API：elementType 是字符串枚举
            # AC29 支持 'All'，AC28 不支持（schema 验证会失败 → 兜底 GetAllElements）
            try:
                elements = conn.commands.GetElementsByType(element_type)
            except Exception:
                # 类型名无效，或 AC28 拒绝 'All'，回退到全部元素
                elements = conn.commands.GetAllElements()
        else:
            elements = conn.commands.GetAllElements()
        # 统一转字符串：下游 Tapir 参数需 JSON 序列化，UUID 对象会失败
        return [str(e.elementId.guid) for e in elements]

    def _filter_by_details(
        self,
        guids: list[str],
        stories: list[int] | None,
        instance: str | None,
    ) -> list[ElementSummary]:
        """取详情，按楼层过滤；guid 由 adapter 按顺序回填。"""
        if not guids:
            return []
        details = _tapir.get_details_of_elements(guids, instance)
        summaries: list[ElementSummary] = []
        for d in details:
            # 注意 floorIndex 可能为 0，不能用 `or`（会把 0 误判成空）
            story_idx = d.get("floorIndex", d.get("storyIndex"))
            if stories is not None and story_idx not in stories:
                continue
            summaries.append(
                ElementSummary(
                    guid=d.get("guid"),
                    element_type=str(d.get("type", "Unknown")),
                    name=d.get("id"),
                    story_index=story_idx,
                )
            )
        return summaries

    def _filter_by_properties(
        self,
        summaries: list[ElementSummary],
        filters: list[Filter],
        instance: str | None,
    ) -> list[ElementSummary]:
        """按属性值本地过滤。

        直接复用 property_service 已验证的 get_values（含 BuiltIn/UserDefined
        属性解析与 enum displayValue 处理），不在本模块重复取数逻辑。
        """
        if not summaries or not filters:
            return summaries
        field_names = list({f.field for f in filters})
        guids = [str(s.guid) for s in summaries]
        value_map = property_service.service.get_values(
            guids, field_names, instance
        )
        result: list[ElementSummary] = []
        for s, g in zip(summaries, guids):
            values = value_map.get(g, {})
            if all(apply_operator(values.get(f.field), f.operator, f.value)
                   for f in filters):
                result.append(s)
        return result

    def _paginate(
        self,
        summaries: list[ElementSummary],
        offset: int,
        limit: int,
    ) -> PageResult:
        total = len(summaries)
        end = offset + limit
        page = summaries[offset:end]
        next_cursor = encode_cursor(end) if end < total else None
        return PageResult(
            items=[s.to_dict() for s in page],
            count=len(page),
            next_cursor=next_cursor,
        )


# 模块级单例
engine = QueryEngine(instance_manager.manager)
