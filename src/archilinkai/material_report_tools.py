"""材料统计 MCP 工具（V0.49）。

注册 generate_material_report / export_material_excel 工具。
"""
from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from archilinkai import instance_manager
from archilinkai import material_report
from archilinkai.schemas import success_result


def _ensure_output_dir() -> str:
    out = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(out, exist_ok=True)
    return out


def _ts() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def register(mcp: FastMCP, safe) -> None:
    """注册材料统计工具。safe 为 server._safe（统一异常包装）。"""

    @mcp.tool()
    def generate_material_report(
        element_types: list[str] | None = None,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """生成材料统计报告。

        element_types 可选：Wall/Beam/Column/Slab/Stair/Roof，默认全部。
        返回材料汇总、按构件类型统计、明细列表。
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            report = material_report.generate_material_report(
                element_types, instance)
            return success_result(
                instance=info.instance_id,
                project=info.project_name,
                count=len(report["details"]),
                data=report,
            )
        return safe(instance, _run)

    @mcp.tool()
    def export_material_excel(
        element_types: list[str] | None = None,
        filename: str | None = None,
        instance: str | None = None,
    ) -> str:
        """生成材料统计报告并导出为 Excel。

        element_types 可选：Wall/Beam/Column/Slab/Stair/Roof，默认全部。
        filename 输出文件名，默认自动生成。
        返回 Excel 文件路径。
        """
        def _run() -> str:
            report = material_report.generate_material_report(
                element_types, instance)
            if not filename:
                fname = f"material_report_{_ts()}.xlsx"
            else:
                fname = filename
            filepath = os.path.join(_ensure_output_dir(), fname)
            return material_report.export_material_excel(report, filepath)
        return safe(instance, _run)
