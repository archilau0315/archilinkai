"""输入/输出数据结构模块（V0.3 8.2–8.9）。

统一用 dataclass 描述跨模块的数据契约，避免在 server.py 里散落字典结构。
所有结构提供 to_dict()，便于 FastMCP 工具直接返回结构化数据。
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# 8.3 实例信息
# ---------------------------------------------------------------------------


class InstanceStatus(str, Enum):
    """实例生命周期状态（V0.3 8.3）。"""

    DISCOVERED = "discovered"        # 已发现，尚未验证
    CONNECTED = "connected"          # 已连接
    HEALTHY = "healthy"              # 已连接且健康检查通过
    DISCONNECTED = "disconnected"    # 已断开，待重连
    REFRESHING = "refreshing"        # 正在刷新
    DEAD = "dead"                     # 已失效，应移除


@dataclass
class InstanceInfo:
    """单个 ArchiCAD 实例的运行期信息。

    instance_id 形如 ac29-1，是运行期 ID，不作为永久身份。
    project_identity 用于在写操作前核对项目身份（V0.3 8.3）。
    """

    instance_id: str
    port: int
    version: int
    build: int
    language: str
    project_name: str = "未命名项目"
    project_identity: str | None = None
    session_id: str | None = None
    status: InstanceStatus = InstanceStatus.DISCOVERED

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "port": self.port,
            "version": self.version,
            "build": self.build,
            "language": self.language,
            "project_name": self.project_name,
            "project_identity": self.project_identity,
            "session_id": self.session_id,
            "status": self.status.value,
        }


# ---------------------------------------------------------------------------
# 8.4 查询引擎：QueryRequest / Filter / Operator
# ---------------------------------------------------------------------------


class Operator(str, Enum):
    """V0.3 8.4 第一阶段支持的操作符。"""

    EQ = "="
    NE = "!="
    GT = ">"
    GE = ">="
    LT = "<"
    LE = "<="
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    IN = "in"


@dataclass
class Filter:
    """单个过滤条件。field 为属性名或特殊字段名。"""

    field: str
    operator: Operator
    value: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "operator": self.operator.value,
            "value": self.value,
        }


@dataclass
class QueryRequest:
    """统一查询模型（V0.3 8.4）。

    element_type 缩小类型范围；stories 按楼层索引过滤；
    filters 按属性值本地比对；limit/cursor 分页。
    """

    instance: str | None = None
    element_type: str | None = None
    stories: list[int] | None = None
    filters: list[Filter] = field(default_factory=list)
    limit: int = 100
    cursor: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance": self.instance,
            "element_type": self.element_type,
            "stories": self.stories,
            "filters": [f.to_dict() for f in self.filters],
            "limit": self.limit,
            "cursor": self.cursor,
        }


# ---------------------------------------------------------------------------
# 8.8 分页结果
# ---------------------------------------------------------------------------


@dataclass
class PageResult:
    """分页结果。next_cursor 为 None 表示已到末尾。"""

    items: list[dict[str, Any]]
    count: int
    next_cursor: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": self.items,
            "count": self.count,
            "next_cursor": self.next_cursor,
        }


# ---------------------------------------------------------------------------
# 元素摘要
# ---------------------------------------------------------------------------


@dataclass
class ElementSummary:
    """元素可读信息（GUID + 类型 + 名称 + 楼层索引）。"""

    guid: str
    element_type: str
    name: str | None = None
    story_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "guid": self.guid,
            "element_type": self.element_type,
            "name": self.name,
            "story_index": self.story_index,
        }


# ---------------------------------------------------------------------------
# 8.5 Preview / Verify
# ---------------------------------------------------------------------------


@dataclass
class PreviewResult:
    """写操作预览结果（V0.3 8.5）。

    unchangeable 元素无法修改，risk 描述潜在风险。
    """

    target_count: int
    target_guids: list[str]
    before_values: list[dict[str, Any]]
    target_value: Any
    unchangeable: list[str] = field(default_factory=list)
    risk: str | None = None
    estimated_change: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_count": self.target_count,
            "target_guids": self.target_guids,
            "before_values": self.before_values,
            "target_value": self.target_value,
            "unchangeable": self.unchangeable,
            "risk": self.risk,
            "estimated_change": self.estimated_change,
        }


@dataclass
class VerifyResult:
    """写操作验证结果（V0.3 8.5）。

    status ∈ {success, partial_success, failed}。
    """

    requested: int
    executed: int
    verified: int
    failed: int
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested": self.requested,
            "executed": self.executed,
            "verified": self.verified,
            "failed": self.failed,
            "status": self.status,
        }


# ---------------------------------------------------------------------------
# 8.9 Operation Log
# ---------------------------------------------------------------------------


@dataclass
class OperationLog:
    """单次写操作日志（V0.3 8.9）。

    operation_id 形如 OP-YYYYMMDD-NNNNN。
    """

    operation_id: str
    timestamp: str
    instance: str
    project: str
    tool: str
    target_count: int
    property: str | None = None
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] = field(default_factory=dict)
    execute_status: str = "pending"  # pending/success/failed
    verify_status: str | None = None  # success/partial_success/failed

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "timestamp": self.timestamp,
            "instance": self.instance,
            "project": self.project,
            "tool": self.tool,
            "target_count": self.target_count,
            "property": self.property,
            "before": self.before,
            "after": self.after,
            "execute_status": self.execute_status,
            "verify_status": self.verify_status,
        }


# ---------------------------------------------------------------------------
# 8.7 统一工具返回
# ---------------------------------------------------------------------------


@dataclass
class ToolResult:
    """V0.3 8.7 统一结构化返回。

    所有 MCP 工具应返回 ToolResult.to_dict()，
    或在出错时由 errors.to_error_dict() 兜底。
    """

    status: str = "success"  # success / error
    instance: str | None = None
    project: str | None = None
    count: int | None = None
    items: list[dict[str, Any]] | None = None
    data: dict[str, Any] | None = None   # 非列表型结果（如 Preview/Verify）
    error: dict[str, Any] | None = None  # 出错时填充

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"status": self.status}
        if self.instance is not None:
            out["instance"] = self.instance
        if self.project is not None:
            out["project"] = self.project
        if self.count is not None:
            out["count"] = self.count
        if self.items is not None:
            out["items"] = self.items
        if self.data is not None:
            out["data"] = self.data
        if self.error is not None:
            out["error"] = self.error
        return out


def success_result(
    instance: str | None = None,
    project: str | None = None,
    count: int | None = None,
    items: list[dict[str, Any]] | None = None,
    data: dict[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """便捷构造成功返回。额外关键字参数并入 data，避免调用方传自定义键报错。"""
    if extra:
        data = {**(data or {}), **extra}
    return ToolResult(
        status="success",
        instance=instance,
        project=project,
        count=count,
        items=items,
        data=data,
    ).to_dict()
