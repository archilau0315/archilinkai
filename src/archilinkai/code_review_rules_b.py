"""规范审查规则 B 组（V0.53 拆分）。

规则 5-12：防火分区面积、楼梯宽度、栏杆高度、踏步尺寸、
窗地比、疏散距离、层高、踏步级数。
每条规则返回违规列表，由 run_review 汇总。
"""

from __future__ import annotations

from typing import Any

from archilinkai import i18n
from archilinkai import instance_manager
from archilinkai.code_review_common import (
    DEFAULT_LIMITS,
    _fetch_elements,
    _get_props,
    _num,
)

# ---- 规则 5：防火分区面积检查 ------------------------------------------

def check_fire_zone_area(
    instance: str | None,
    limits: dict[str, float] | None = None,
    building_type: str = "multi",
) -> list[dict[str, Any]]:
    """防火分区面积≤限值。

    building_type: high(高层, 1500㎡) / multi(多层, 2500㎡)。
    用 Zone 面积；无 Zone 时返回空。
    """
    lim = {**DEFAULT_LIMITS, **(limits or {})}
    max_area = (lim["fire_zone_max_area_high"]
                if building_type == "high"
                else lim["fire_zone_max_area_multi"])
    zones = _fetch_elements("Zone", instance)
    if not zones:
        return []
    guids = [z["guid"] for z in zones]
    props = _get_props(
        guids, ["General_NetArea", "General_Area"], instance)
    violations: list[dict[str, Any]] = []
    for z in zones:
        p = props.get(z["guid"], {})
        area = _num(p.get("General_NetArea")) or _num(p.get("General_Area"))
        if area is None:
            continue
        if area > max_area:
            violations.append({
                "guid": z["guid"], "name": z.get("name", ""),
                "story": z.get("story_index"),
                "rule": i18n.t("review.fire_zone_area.rule", "防火分区面积超限"),
                "value": round(area, 2), "limit": max_area,
                "message": i18n.t(
                    "review.fire_zone_area.msg",
                    f"防火分区面积 {area:.1f}㎡ 超过限值 {max_area:.0f}㎡",
                    area=f"{area:.1f}", limit=f"{max_area:.0f}"),
            })
    return violations


# ---- 规则 6：楼梯宽度检查 ----------------------------------------------

def check_stair_width(
    instance: str | None,
    limits: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """楼梯梯段**净宽**≥1.1m。

    净宽 = 构造宽度（Stair_FlightWidth）- 扶手扣除。
    扶手在踏面边缘上方时，按 stair_handrail_deduction_per_side ×
    stair_handrail_count 扣除（默认 0.06×2=0.12m）。
    """
    lim = {**DEFAULT_LIMITS, **(limits or {})}
    deduct = (lim["stair_handrail_deduction_per_side"]
              * lim["stair_handrail_count"])
    stairs = _fetch_elements("Stair", instance)
    if not stairs:
        return []
    guids = [s["guid"] for s in stairs]
    props = _get_props(
        guids, ["Stair_FlightWidth"], instance)
    violations: list[dict[str, Any]] = []
    for s in stairs:
        p = props.get(s["guid"], {})
        structural_w = _num(p.get("Stair_FlightWidth"))
        if structural_w is None:
            continue
        clear_w = structural_w - deduct
        if clear_w < lim["stair_min_width"]:
            violations.append({
                "guid": s["guid"], "name": s.get("name", ""),
                "story": s.get("story_index"),
                "rule": i18n.t("review.stair_width.rule", "楼梯净宽不足"),
                "value": round(clear_w, 3), "limit": lim["stair_min_width"],
                "message": i18n.t(
                    "review.stair_width.msg",
                    f"楼梯净宽 {clear_w:.2f}m（构造宽 {structural_w:.2f}m "
                    f"- 扶手 {deduct:.2f}m）小于 "
                    f"{lim['stair_min_width']:.1f}m",
                    clear_w=f"{clear_w:.2f}", structural_w=f"{structural_w:.2f}",
                    deduct=f"{deduct:.2f}",
                    limit=f"{lim['stair_min_width']:.1f}"),
            })
    return violations


# ---- 规则 7：栏杆高度检查 ----------------------------------------------

def check_railing_height(
    instance: str | None,
    limits: dict[str, float] | None = None,
    high_rise: bool = False,
) -> list[dict[str, Any]]:
    """栏杆高度≥1.05m；高层/临空>24m 时≥1.10m。"""
    lim = {**DEFAULT_LIMITS, **(limits or {})}
    min_h = lim["railing_high_height"] if high_rise else lim["railing_min_height"]
    railings = _fetch_elements("Railing", instance)
    if not railings:
        return []
    guids = [r["guid"] for r in railings]
    props = _get_props(
        guids, ["Railing_Height", "General_Height"], instance)
    violations: list[dict[str, Any]] = []
    for r in railings:
        p = props.get(r["guid"], {})
        h = _num(p.get("Railing_Height")) or _num(p.get("General_Height"))
        if h is None:
            continue
        if h < min_h:
            violations.append({
                "guid": r["guid"], "name": r.get("name", ""),
                "story": r.get("story_index"),
                "rule": i18n.t("review.railing_height.rule", "栏杆高度不足"),
                "value": round(h, 3), "limit": min_h,
                "message": i18n.t(
                    "review.railing_height.msg",
                    f"栏杆高 {h:.2f}m 小于 {min_h:.2f}m",
                    h=f"{h:.2f}", limit=f"{min_h:.2f}"),
            })
    return violations


# ---- 规则 8：楼梯踏步尺寸检查 ------------------------------------------

def check_stair_tread(
    instance: str | None,
    limits: dict[str, float] | None = None,
    building_type: str = "multi",
) -> list[dict[str, Any]]:
    """踏步高 ≤ 限值、踏步深 ≥ 限值。

    building_type: public(公共) / residential(住宅)。
    """
    lim = {**DEFAULT_LIMITS, **(limits or {})}
    is_public = building_type in ("public", "office", "multi", "high")
    riser_max = (lim["riser_max_public"] if is_public
                 else lim["riser_max_residential"])
    tread_min = (lim["tread_min_public"] if is_public
                 else lim["tread_min_residential"])
    stairs = _fetch_elements("Stair", instance)
    if not stairs:
        return []
    guids = [s["guid"] for s in stairs]
    props = _get_props(
        guids,
        ["Stair_DefaultRiserHeight", "Stair_DefaultGoing"],
        instance)
    violations: list[dict[str, Any]] = []
    for s in stairs:
        p = props.get(s["guid"], {})
        riser = _num(p.get("Stair_DefaultRiserHeight"))
        tread = _num(p.get("Stair_DefaultGoing"))
        if riser is not None and riser > riser_max:
            violations.append({
                "guid": s["guid"], "name": s.get("name", ""),
                "story": s.get("story_index"),
                "rule": i18n.t("review.stair_riser.rule", "踏步高度超限"),
                "value": round(riser, 3), "limit": riser_max,
                "message": i18n.t(
                    "review.stair_riser.msg",
                    f"踏步高 {riser:.3f}m 超过 {riser_max:.3f}m",
                    riser=f"{riser:.3f}", limit=f"{riser_max:.3f}"),
            })
        if tread is not None and tread < tread_min:
            violations.append({
                "guid": s["guid"], "name": s.get("name", ""),
                "story": s.get("story_index"),
                "rule": i18n.t("review.stair_tread.rule", "踏步深度不足"),
                "value": round(tread, 3), "limit": tread_min,
                "message": i18n.t(
                    "review.stair_tread.msg",
                    f"踏步深 {tread:.3f}m 小于 {tread_min:.3f}m",
                    tread=f"{tread:.3f}", limit=f"{tread_min:.3f}"),
            })
    return violations


# ---- 规则 9：窗地比检查 -------------------------------------------------

def check_window_floor_ratio(
    instance: str | None,
    limits: dict[str, float] | None = None,
    building_type: str = "office",
) -> list[dict[str, Any]]:
    """按楼层汇总：总窗面积 / 总房间面积 ≥ 限值。

    简化实现：按 story_index 分组，窗面积用 Window_Height×Window_Width
    或 General_NetArea，房间面积用 Zone 的 General_NetArea。
    无 Zone 的楼层跳过。
    """
    lim = {**DEFAULT_LIMITS, **(limits or {})}
    ratio_min = (lim["window_floor_ratio_residential"]
                 if building_type == "residential"
                 else lim["window_floor_ratio_office"])

    zones = _fetch_elements("Zone", instance)
    windows = _fetch_elements("Window", instance)
    if not zones or not windows:
        return []

    # 每层 Zone 总面积
    zprops = _get_props(
        [z["guid"] for z in zones], ["General_NetArea"], instance)
    story_floor_area: dict[int, float] = {}
    for z in zones:
        st = z.get("story_index")
        area = _num(zprops.get(z["guid"], {}).get("General_NetArea"))
        if st is None or area is None:
            continue
        story_floor_area[int(st)] = story_floor_area.get(int(st), 0.0) + area

    # 每层窗总面积
    wprops = _get_props(
        [w["guid"] for w in windows],
        ["General_NetArea", "Window_Height", "Window_Width"], instance)
    story_window_area: dict[int, float] = {}
    for w in windows:
        st = w.get("story_index")
        if st is None:
            continue
        p = wprops.get(w["guid"], {})
        area = _num(p.get("General_NetArea"))
        if area is None:
            h = _num(p.get("Window_Height"))
            wd = _num(p.get("Window_Width"))
            if h is not None and wd is not None:
                area = h * wd
        if area is None:
            continue
        story_window_area[int(st)] = story_window_area.get(int(st), 0.0) + area

    violations: list[dict[str, Any]] = []
    for st, floor_area in story_floor_area.items():
        if floor_area <= 0:
            continue
        win_area = story_window_area.get(st, 0.0)
        ratio = win_area / floor_area
        if ratio < ratio_min:
            violations.append({
                "story": st,
                "rule": i18n.t("review.window_floor_ratio.rule", "窗地比不足"),
                "value": round(ratio, 4),
                "limit": ratio_min,
                "message": i18n.t(
                    "review.window_floor_ratio.msg",
                    f"第 {st} 层窗地比 {ratio:.3f} "
                    f"小于 {ratio_min:.3f}"
                    f"（窗 {win_area:.1f}㎡ / 地面 {floor_area:.1f}㎡）",
                    st=st, ratio=f"{ratio:.3f}", limit=f"{ratio_min:.3f}",
                    win_area=f"{win_area:.1f}", floor_area=f"{floor_area:.1f}"),
            })
    return violations


# ---- 规则 10：疏散距离估算检查 ------------------------------------------

def check_evacuation_distance(
    instance: str | None,
    limits: dict[str, float] | None = None,
    building_type: str = "office",
    has_sprinkler: bool = False,
) -> list[dict[str, Any]]:
    """疏散距离估算：用 Zone 面积估算最大疏散距离。

    简化算法（无精确几何时）：
    - 最大疏散距离 ≈ sqrt(Zone_Area) × 1.5（保守系数）
    - 限值：办公 40m（有喷淋 50m）、住宅 22m

    注意：这是估算值，精确计算需要 Zone 边界几何和疏散门位置，
    当前 Tapir 的 GetZoneBoundaries 参数格式不支持。
    """
    import math
    lim = {**DEFAULT_LIMITS, **(limits or {})}
    if building_type == "residential":
        max_dist = lim["evacuation_distance_residential"]
    elif has_sprinkler:
        max_dist = lim["evacuation_distance_office_sprinkler"]
    else:
        max_dist = lim["evacuation_distance_office"]

    zones = _fetch_elements("Zone", instance)
    if not zones:
        return []
    guids = [z["guid"] for z in zones]
    props = _get_props(
        guids, ["General_Area", "Zone_CalculatedArea"], instance)
    violations: list[dict[str, Any]] = []
    for z in zones:
        p = props.get(z["guid"], {})
        area = _num(p.get("General_Area")) or _num(p.get("Zone_CalculatedArea"))
        if area is None or area <= 0:
            continue
        # 估算最大疏散距离：sqrt(面积) × 1.5（保守）
        est_dist = math.sqrt(area) * 1.5
        if est_dist > max_dist:
            violations.append({
                "guid": z["guid"], "name": z.get("name", ""),
                "story": z.get("story_index"),
                "rule": i18n.t("review.evacuation_distance.rule", "疏散距离超限(估算)"),
                "value": round(est_dist, 2), "limit": max_dist,
                "message": i18n.t(
                    "review.evacuation_distance.msg",
                    f"Zone 面积 {area:.1f}㎡，估算疏散距离 "
                    f"{est_dist:.1f}m 超过限值 {max_dist:.0f}m"
                    f"（估算值，精确计算需 Zone 边界几何）",
                    area=f"{area:.1f}", est=f"{est_dist:.1f}",
                    limit=f"{max_dist:.0f}"),
            })
    return violations


# ---- 规则 11：层高检查 --------------------------------------------------

def check_floor_height(
    instance: str | None,
    limits: dict[str, float] | None = None,
    building_type: str = "office",
) -> list[dict[str, Any]]:
    """各层层高 ≥ 限值（办公 3.0m / 住宅 2.8m）。

    层高 = 相邻楼层标高差；顶层用本层最高楼板标高 - 楼层标高。
    """
    lim = {**DEFAULT_LIMITS, **(limits or {})}
    min_h = (lim["floor_height_min_office"]
             if building_type in ("office", "multi", "high", "public")
             else lim["floor_height_min_residential"])
    conn = instance_manager.manager.get_conn(instance)
    try:
        stories = conn.commands.GetStories()
    except Exception:
        return []
    story_elev: dict[int, float] = {}
    for idx, s in enumerate(getattr(stories, "stories", stories) or []):
        story_elev[idx] = float(getattr(s, "elevation", 0.0))
    # 计算层高
    heights: dict[int, float] = {}
    for st, elev in story_elev.items():
        next_elev = story_elev.get(st + 1)
        if next_elev is not None:
            heights[st] = next_elev - elev
        else:
            # 顶层：取本层最高楼板标高 - 楼层标高
            slabs = _fetch_elements("Slab", instance)
            slab_props = _get_props(
                [s["guid"] for s in slabs],
                ["Slab_Thickness", "General_Thickness"], instance)
            max_top = elev
            for s in slabs:
                if s.get("story_index") != st:
                    continue
                t = _num(slab_props.get(s["guid"], {}).get("Slab_Thickness")) \
                    or _num(slab_props.get(s["guid"], {}).get("General_Thickness"))
                if t:
                    max_top = max(max_top, elev + t)
            heights[st] = max_top - elev

    violations: list[dict[str, Any]] = []
    for st, h in heights.items():
        if h < min_h:
            violations.append({
                "story": st,
                "rule": i18n.t("review.floor_height.rule", "层高不足"),
                "value": round(h, 3),
                "limit": min_h,
                "message": i18n.t(
                    "review.floor_height.msg",
                    f"第 {st} 层层高 {h:.2f}m 小于 {min_h:.1f}m",
                    st=st, h=f"{h:.2f}", limit=f"{min_h:.1f}"),
            })
    return violations


# ---- 规则 12：踏步级数限制 ----------------------------------------------

def check_stair_riser_count(
    instance: str | None,
    limits: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """楼梯踏步级数 ≤ 18 级（超过需设平台）。

    注意：ArchiCAD 的 Stair_NumberOfRisers 属性不存在，
    此规则当前无法生效，返回空列表。
    """
    lim = {**DEFAULT_LIMITS, **(limits or {})}
    max_count = int(lim.get("stair_max_riser_count", 18))
    stairs = _fetch_elements("Stair", instance)
    if not stairs:
        return []
    guids = [s["guid"] for s in stairs]
    props = _get_props(
        guids, ["Stair_NumberOfRisers"], instance)
    violations: list[dict[str, Any]] = []
    for s in stairs:
        p = props.get(s["guid"], {})
        count = _num(p.get("Stair_NumberOfRisers"))
        if count is None:
            continue
        if count > max_count:
            violations.append({
                "guid": s["guid"], "name": s.get("name", ""),
                "story": s.get("story_index"),
                "rule": i18n.t("review.stair_riser_count.rule", "踏步级数超限"),
                "value": int(count), "limit": max_count,
                "message": i18n.t(
                    "review.stair_riser_count.msg",
                    f"踏步级数 {int(count)} 超过 {max_count} 级（需设平台）",
                    count=int(count), limit=max_count),
            })
    return violations
