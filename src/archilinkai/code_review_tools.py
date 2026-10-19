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
        has_sprinkler: bool = False,
        structure_type: str = "concrete",
        instance: str | None = None,
    ) -> dict[str, Any]:
        """建筑规范强条审查，返回违规清单。

        rules 可选子集：wall_thickness（墙厚）/ openings（门窗洞口）/
        headroom（净高）/ collisions（碰撞）/ fire_zone_area（防火分区面积）/
        stair_width（楼梯净宽）/ railing_height（栏杆高度）/
        stair_tread（踏步尺寸）/ window_floor_ratio（窗地比）/
        evacuation_distance（疏散距离估算）/ floor_height（层高）/
        stair_riser_count（踏步级数）/ slab_thickness（楼板厚度）/
        bearing_wall_thickness（承重/外墙厚）/ column_section（柱截面）/
        beam_span_ratio（梁跨高比）/ column_slenderness（柱长细比）/
        wall_slenderness（墙高厚比）/ evacuation_door_width（疏散门净宽）/
        beam_section_width（梁截面宽度，仅混凝土）/
        beam_aspect_ratio（梁截面高宽比，仅混凝土）/
        fire_door_rating（防火门耐火等级缺失），默认全部。
        building_type: high/multi（影响防火分区面积限值）；
        high_rise: 是否高层（影响栏杆高度限值）；
        has_sprinkler: 是否有自动喷淋（影响疏散距离限值）；
        structure_type: concrete/steel/continuous/any（影响梁跨高比限值；
        梁截面宽度/高宽比两条规则仅 concrete 生效，钢结构请传 steel 以免误报）。
        limits 覆盖规范限值（单位 m），常用键见 list_code_review_limits。
        返回：per_rule（各规则违规数）、violations（违规明细）、
        total_violations、passed。

        English: Building code mandatory-rule review; returns a violation list.
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            result = run_review(
                rules, limits, instance,
                building_type=building_type, high_rise=high_rise,
                has_sprinkler=has_sprinkler, structure_type=structure_type)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=result["total_violations"], data=result,
            )
        return safe(instance, _run)

    @mcp.tool()
    def list_code_review_limits() -> dict[str, Any]:
        """返回规范审查默认限值（可用于 run_code_review 的 limits 参数）。

        English: Return the default code review limit values (usable as run_code_review's limits).
        """
        return {"limits": dict(DEFAULT_LIMITS)}
