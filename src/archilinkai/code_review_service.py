"""建筑规范强条审查服务入口（V0.53 拆分后）。

本模块只保留 run_review 汇总入口；限值与公共 helper 在
code_review_common，规则实现在 code_review_rules_a / _b。
对外兼容：code_review_service.run_review / DEFAULT_LIMITS 仍可 import。
"""

from __future__ import annotations

from typing import Any

from archilinkai.code_review_common import DEFAULT_LIMITS  # noqa: F401 re-export
from archilinkai.code_review_rules_a import (
    check_beam_aspect_ratio,
    check_beam_section_width,
    check_beam_span_ratio,
    check_bearing_wall_thickness,
    check_collisions,
    check_column_section,
    check_column_slenderness,
    check_evacuation_door_width,
    check_fire_door_rating,
    check_headroom,
    check_openings,
    check_slab_thickness,
    check_wall_slenderness,
    check_wall_thickness,
)
from archilinkai.code_review_rules_b import (
    check_evacuation_distance,
    check_fire_zone_area,
    check_floor_height,
    check_railing_height,
    check_stair_riser_count,
    check_stair_tread,
    check_stair_width,
    check_window_floor_ratio,
)


def run_review(
    rules: list[str] | None = None,
    limits: dict[str, float] | None = None,
    instance: str | None = None,
    building_type: str = "multi",
    high_rise: bool = False,
    has_sprinkler: bool = False,
    structure_type: str | None = None,
) -> dict[str, Any]:
    """执行规范审查，返回各规则违规清单与汇总。

    building_type: high/multi（影响防火分区面积限值）；
    high_rise: 是否高层（影响栏杆高度限值）；
    has_sprinkler: 是否有自动喷淋（影响疏散距离限值）；
    structure_type: concrete/steel/continuous/any（影响梁跨高比限值）。
    """
    all_rules = [
        "wall_thickness", "openings", "headroom", "collisions",
        "fire_zone_area", "stair_width", "railing_height",
        "stair_tread", "window_floor_ratio", "evacuation_distance",
        "floor_height", "stair_riser_count",
        "slab_thickness", "bearing_wall_thickness",
        "column_section", "beam_span_ratio", "column_slenderness",
        "wall_slenderness", "evacuation_door_width",
        "beam_section_width", "beam_aspect_ratio", "fire_door_rating",
    ]
    rules = rules or all_rules
    results: dict[str, list[dict[str, Any]]] = {}
    for r in rules:
        if r == "wall_thickness":
            results[r] = check_wall_thickness(instance, limits)
        elif r == "openings":
            results[r] = check_openings(instance, limits)
        elif r == "headroom":
            results[r] = check_headroom(instance, limits)
        elif r == "collisions":
            results[r] = check_collisions(instance, limits=limits)
        elif r == "fire_zone_area":
            results[r] = check_fire_zone_area(instance, limits, building_type)
        elif r == "stair_width":
            results[r] = check_stair_width(instance, limits)
        elif r == "railing_height":
            results[r] = check_railing_height(instance, limits, high_rise)
        elif r == "stair_tread":
            results[r] = check_stair_tread(instance, limits, building_type)
        elif r == "window_floor_ratio":
            results[r] = check_window_floor_ratio(
                instance, limits, building_type)
        elif r == "evacuation_distance":
            results[r] = check_evacuation_distance(
                instance, limits, building_type, has_sprinkler)
        elif r == "floor_height":
            results[r] = check_floor_height(instance, limits, building_type)
        elif r == "stair_riser_count":
            results[r] = check_stair_riser_count(instance, limits)
        elif r == "slab_thickness":
            results[r] = check_slab_thickness(instance, limits)
        elif r == "bearing_wall_thickness":
            results[r] = check_bearing_wall_thickness(instance, limits)
        elif r == "column_section":
            results[r] = check_column_section(instance, limits)
        elif r == "beam_span_ratio":
            results[r] = check_beam_span_ratio(
                instance, limits, structure_type=structure_type)
        elif r == "column_slenderness":
            results[r] = check_column_slenderness(
                instance, limits, structure_type=structure_type)
        elif r == "wall_slenderness":
            results[r] = check_wall_slenderness(instance, limits)
        elif r == "evacuation_door_width":
            results[r] = check_evacuation_door_width(instance, limits)
        elif r == "beam_section_width":
            results[r] = check_beam_section_width(
                instance, limits, structure_type=structure_type)
        elif r == "beam_aspect_ratio":
            results[r] = check_beam_aspect_ratio(
                instance, limits, structure_type=structure_type)
        elif r == "fire_door_rating":
            results[r] = check_fire_door_rating(instance, limits)
    total = sum(len(v) for v in results.values())
    return {
        "rules_checked": rules,
        "per_rule": {k: len(v) for k, v in results.items()},
        "violations": results,
        "total_violations": total,
        "passed": total == 0,
    }
