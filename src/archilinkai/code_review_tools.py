"""规范审查工具注册（V0.42）。

注册 run_code_review 工具，调用 code_review_service 执行强条审查。
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from archilinkai import instance_manager
from archilinkai.code_review_service import DEFAULT_LIMITS, run_review
from archilinkai.schemas import success_result


def register(mcp: FastMCP, safe) -> None:
    """注册规范审查工具。safe 为 server._safe（统一异常包装）。"""

    @mcp.tool()
    def run_code_review(
        rules: list[str] | None = None,
        limits: dict[str, float] | None = None,
        building_type: str = "multi",
        high_rise: bool = False,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """建筑规范强条审查，返回违规清单。

        rules 可选子集：wall_thickness（墙厚）/ openings（门窗洞口）/
        headroom（净高）/ collisions（碰撞）/ fire_zone_area（防火分区面积）/
        stair_width（楼梯宽度）/ railing_height（栏杆高度），默认全部。
        building_type: high/multi（影响防火分区面积限值）；
        high_rise: 是否高层（影响栏杆高度限值）。
        limits 覆盖规范限值（单位 m），常用键见 list_code_review_limits。
        返回：per_rule（各规则违规数）、violations（违规明细）、
        total_violations、passed。
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            result = run_review(
                rules, limits, instance,
                building_type=building_type, high_rise=high_rise)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=result["total_violations"], data=result,
            )
        return safe(instance, _run)

    @mcp.tool()
    def list_code_review_limits() -> dict[str, Any]:
        """返回规范审查默认限值（可用于 run_code_review 的 limits 参数）。"""
        return {"limits": dict(DEFAULT_LIMITS)}
