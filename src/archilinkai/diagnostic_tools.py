"""P2 诊断 / 运维工具注册（V0.0 从 server.py 拆出，控制 server 行数）。

只做一件事：向 FastMCP 注册 4 个诊断工具。
通过 register(mcp, safe) 调用，复用 server 的统一异常包装。
"""

from __future__ import annotations

from typing import Any

from archilinkai import audit_log
from archilinkai import instance_manager
from mcp.server.fastmcp import FastMCP

from archilinkai.schemas import success_result


def register(mcp: FastMCP, safe) -> None:
    """注册诊断工具。safe 为 server._safe（统一异常包装）。"""

    @mcp.tool()
    def refresh_instances() -> dict[str, Any]:
        """重新扫描端口，刷新实例注册表。"""
        def _run() -> dict[str, Any]:
            infos = instance_manager.manager.refresh_instances()
            return success_result(
                count=len(infos),
                items=[i.to_dict() for i in infos.values()],
            )
        return safe(None, _run)

    @mcp.tool()
    def validate_instance(instance: str | None = None) -> dict[str, Any]:
        """验证实例仍有效（重新执行 GetProductInfo 核对版本/构建号）。"""
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.validate_instance(instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                data={"status": info.status.value, "build": info.build},
            )
        return safe(instance, _run)

    @mcp.tool()
    def get_operation_status(operation_id: str) -> dict[str, Any]:
        """查询某次写操作的状态（execute_status / verify_status）。"""
        op = audit_log.logger.get(operation_id)
        if op is None:
            return {
                "status": "error",
                "error_code": "OPERATION_NOT_FOUND",
                "message": f"未找到操作 {operation_id}",
                "retryable": False,
            }
        return success_result(data=op.to_dict())

    @mcp.tool()
    def get_operation_log(limit: int = 20) -> dict[str, Any]:
        """返回最近 N 条操作日志。"""
        recent = audit_log.logger.list_recent(limit)
        return success_result(
            count=len(recent), items=[op.to_dict() for op in recent],
        )
