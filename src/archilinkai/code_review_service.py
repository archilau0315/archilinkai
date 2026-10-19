"""建筑规范强条审查服务（V0.42）。

规则集：墙厚、门窗洞口、净高、碰撞。
每条规则返回违规列表，由 run_code_review 汇总。
"""

from __future__ import annotations

from typing import Any

from archilinkai import instance_manager
from archilinkai import property_service
from archilinkai.query_engine import QueryRequest, engine

# 规范限值（可被参数覆盖，单位：m）
DEFAULT_LIMITS: dict[str, float] = {
    "wall_min_thickness": 0.09,        # 隔墙最小厚度
    "wall_bearing_min": 0.18,          # 承重墙最小厚度
    "door_min_height": 2.0,            # 门洞最小高度
    "door_min_width": 0.8,             # 门洞最小宽度
    "door_exit_min_width": 0.9,        # 疏散门最小宽度
    "window_sill_min": 0.9,            # 外窗窗台最小高度
    "headroom_corridor": 2.2,          # 走道最小净高
    "headroom_room": 2.4,              # 房间最小净高
    "headroom_stair": 2.2,             # 楼梯最小净高
    "headroom_garage": 2.2,            # 车库最小净高
    # ---- V0.43 增强 ----
    "fire_zone_max_area_high": 1500.0,  # 高层防火分区最大面积(㎡)
    "fire_zone_max_area_multi": 2500.0, # 多层防火分区最大面积(㎡)
    "stair_min_width": 1.1,             # 楼梯梯段最小宽度(m)
    "railing_min_height": 1.05,         # 栏杆最小高度(m)
    "railing_high_height": 1.10,        # 临空高度>24m 栏杆最小高度(m)
    # ---- V0.44 增强 ----
    "riser_max_public": 0.175,          # 公共建筑踏步最大高度(m)
    "riser_max_residential": 0.15,      # 住宅踏步最大高度(m)
    "tread_min_public": 0.28,           # 公共建筑踏步最小深度(m)
    "tread_min_residential": 0.26,      # 住宅踏步最小深度(m)
    "window_floor_ratio_residential": 0.1429,  # 居住房间窗地比 1/7
    "window_floor_ratio_office": 0.125,        # 办公房间窗地比 1/8
    # ---- V0.45 门框余量 ----
    "door_frame_allowance": 0.10,     # 门洞两侧门框合计宽度(m)，净宽=洞口宽-此值
    "door_head_allowance": 0.05,      # 门上框高度(m)，净高=洞口高-此值
    # ---- V0.46 楼梯扶手扣除 ----
    "stair_handrail_deduction_per_side": 0.06,  # 单侧扶手扣除宽度(m)
    "stair_handrail_count": 2,        # 默认扶手数量（双侧）
    # ---- V0.47 疏散距离 ----
    "evacuation_distance_office": 40.0,       # 办公建筑疏散距离限值(m)
    "evacuation_distance_office_sprinkler": 50.0,  # 有喷淋时
    "evacuation_distance_residential": 22.0,  # 住宅疏散距离限值(m)
}


def _fetch_elements(element_type: str, instance: str | None) -> list[dict[str, Any]]:
    """用 query_engine 取指定类型元素（含 guid/story_index）。"""
    page = engine.query(QueryRequest(element_type=element_type, limit=10000))
    return page.items


def _get_props(
    guids: list[str], names: list[str], instance: str | None,
) -> dict[str, dict[str, Any]]:
    if not guids:
        return {}
    return property_service.service.get_values(guids, names, instance)


def _num(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


# ---- 规则 1：墙厚检查 ---------------------------------------------------

def check_wall_thickness(
    instance: str | None,
    limits: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """墙厚≥隔墙限值；外墙（两面朝外）≥0.2m。"""
    lim = {**DEFAULT_LIMITS, **(limits or {})}
    walls = _fetch_elements("Wall", instance)
    if not walls:
        return []
    guids = [w["guid"] for w in walls]
    props = _get_props(guids, ["General_Thickness"], instance)
    violations: list[dict[str, Any]] = []
    for w in walls:
        t = _num(props.get(w["guid"], {}).get("General_Thickness"))
        if t is None:
            continue
        if t < lim["wall_min_thickness"]:
            violations.append({
                "guid": w["guid"],
                "name": w.get("name", ""),
                "story": w.get("story_index"),
                "rule": "墙厚不足",
                "value": round(t, 3),
                "limit": lim["wall_min_thickness"],
                "message": f"墙厚 {t:.3f}m 小于最小限值 {lim['wall_min_thickness']:.2f}m",
            })
    return violations


# ---- 规则 2：门窗洞口合规 ----------------------------------------------

def check_openings(
    instance: str | None,
    limits: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """门洞**净宽**≥0.8m、净高≥2.0m；外窗窗台高≥0.9m。

    ArchiCAD 只暴露洞口尺寸（General_Width/Height，含门框），
    净宽 = 洞口宽 - door_frame_allowance（默认两侧合计 0.10m），
    净高 = 洞口高 - door_head_allowance（默认上框 0.05m）。
    """
    lim = {**DEFAULT_LIMITS, **(limits or {})}
    frame_w = lim["door_frame_allowance"]
    head_h = lim["door_head_allowance"]
    violations: list[dict[str, Any]] = []

    # 门
    doors = _fetch_elements("Door", instance)
    if doors:
        guids = [d["guid"] for d in doors]
        props = _get_props(
            guids, ["General_Width", "General_Height"], instance)
        for d in doors:
            p = props.get(d["guid"], {})
            rough_w = _num(p.get("General_Width"))
            rough_h = _num(p.get("General_Height"))
            if rough_h is not None:
                clear_h = rough_h - head_h
                if clear_h < lim["door_min_height"]:
                    violations.append({
                        "guid": d["guid"], "name": d.get("name", ""),
                        "story": d.get("story_index"), "rule": "门洞净高不足",
                        "value": round(clear_h, 3), "limit": lim["door_min_height"],
                        "message": (f"门洞净高 {clear_h:.2f}m（洞口 {rough_h:.2f}m "
                                    f"- 上框 {head_h:.2f}m）小于 "
                                    f"{lim['door_min_height']:.1f}m"),
                    })
            if rough_w is not None:
                clear_w = rough_w - frame_w
                if clear_w < lim["door_min_width"]:
                    violations.append({
                        "guid": d["guid"], "name": d.get("name", ""),
                        "story": d.get("story_index"), "rule": "门洞净宽不足",
                        "value": round(clear_w, 3), "limit": lim["door_min_width"],
                        "message": (f"门洞净宽 {clear_w:.2f}m（洞口 {rough_w:.2f}m "
                                    f"- 门框 {frame_w:.2f}m）小于 "
                                    f"{lim['door_min_width']:.1f}m"),
                    })

    # 窗（窗台高度）
    windows = _fetch_elements("Window", instance)
    if windows:
        guids = [w["guid"] for w in windows]
        props = _get_props(
            guids, ["Window_SillHeight", "General_SillHeight"], instance)
        for w in windows:
            p = props.get(w["guid"], {})
            sill = (_num(p.get("Window_SillHeight"))
                    or _num(p.get("General_SillHeight")))
            if sill is not None and sill < lim["window_sill_min"]:
                violations.append({
                    "guid": w["guid"], "name": w.get("name", ""),
                    "story": w.get("story_index"), "rule": "窗台高度不足",
                    "value": round(sill, 3), "limit": lim["window_sill_min"],
                    "message": f"窗台高 {sill:.2f}m 小于 {lim['window_sill_min']:.1f}m",
                })
    return violations


# ---- 规则 3：净高检查 ---------------------------------------------------

def check_headroom(
    instance: str | None,
    limits: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """净高 = 上层楼板底标高 - 本层楼面标高。

    简化：取每层所有梁/板的最大底面标高作为该层可通行净高，
    与各空间限值比较。无梁板的楼层跳过。
    """
    lim = {**DEFAULT_LIMITS, **(limits or {})}
    # 楼层标高
    info = instance_manager.manager.get_info(instance)
    conn = instance_manager.manager.get_conn(instance)
    try:
        stories = conn.commands.GetStories()
    except Exception:
        return []
    story_elev: dict[int, float] = {}
    for idx, s in enumerate(getattr(stories, "stories", stories) or []):
        story_elev[idx] = float(getattr(s, "elevation", 0.0))

    # 取梁和板，按 story_index 分组，算底面标高
    beams = _fetch_elements("Beam", instance)
    slabs = _fetch_elements("Slab", instance)
    if not beams and not slabs:
        return []

    # 读梁高/板厚 + 底部偏移
    beam_props = _get_props(
        [b["guid"] for b in beams],
        ["Beam_Height", "General_Height"], instance)
    slab_props = _get_props(
        [s["guid"] for s in slabs],
        ["Slab_Thickness", "General_Thickness"], instance)

    # 每层最低底面标高 = min(楼层标高 + 偏移 - 高度)
    # 简化：底面标高 ≈ 楼层标高 - 构件高度（忽略偏移，偏保守）
    per_story_bottom: dict[int, float] = {}
    for b in beams:
        st = b.get("story_index")
        if st is None:
            continue
        h = _num(beam_props.get(b["guid"], {}).get("Beam_Height")) \
            or _num(beam_props.get(b["guid"], {}).get("General_Height"))
        elev = story_elev.get(int(st))
        if h is None or elev is None:
            continue
        bottom = elev - h
        per_story_bottom[int(st)] = min(
            per_story_bottom.get(int(st), bottom), bottom)
    for s in slabs:
        st = s.get("story_index")
        if st is None:
            continue
        t = _num(slab_props.get(s["guid"], {}).get("Slab_Thickness")) \
            or _num(slab_props.get(s["guid"], {}).get("General_Thickness"))
        elev = story_elev.get(int(st))
        if t is None or elev is None:
            continue
        bottom = elev - t
        per_story_bottom[int(st)] = min(
            per_story_bottom.get(int(st), bottom), bottom)

    violations: list[dict[str, Any]] = []
    for st, bottom in per_story_bottom.items():
        floor_elev = story_elev.get(st, 0.0)
        # 净高 = 上层楼面标高 - 本层最低底面标高；无上一层则用本层层高
        next_elev = story_elev.get(st + 1, floor_elev + 3.0)
        headroom = next_elev - bottom
        if headroom < lim["headroom_room"]:
            violations.append({
                "story": st,
                "rule": "净高不足",
                "value": round(headroom, 3),
                "limit": lim["headroom_room"],
                "message": (
                    f"第 {st} 层净高 {headroom:.2f}m 小于 "
                    f"{lim['headroom_room']:.1f}m"),
            })
    return violations


# ---- 规则 4：碰撞检查 ---------------------------------------------------

def check_collisions(
    instance: str | None,
    pairs: list[tuple[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """结构与机电/装饰构件碰撞检查。

    pairs：元素类型对列表，默认检查 结构(柱梁墙板) vs 机电(MEPRoutingElement)。
    """
    from archilinkai.tapir_adapter import adapter
    pairs = pairs or [
        ("Column", "MEPRoutingElement"),
        ("Beam", "MEPRoutingElement"),
        ("Wall", "MEPRoutingElement"),
        ("Slab", "MEPRoutingElement"),
    ]
    violations: list[dict[str, Any]] = []
    for t1, t2 in pairs:
        e1 = _fetch_elements(t1, instance)
        e2 = _fetch_elements(t2, instance)
        if not e1 or not e2:
            continue
        g1 = [{"elementId": {"guid": x["guid"]}} for x in e1]
        g2 = [{"elementId": {"guid": x["guid"]}} for x in e2]
        try:
            data = adapter.get_collisions(g1, g2, instance=instance)
        except Exception:
            continue
        colls = data.get("collisions", []) if isinstance(data, dict) else []
        for c in colls:
            violations.append({
                "rule": "构件碰撞",
                "pair": f"{t1} vs {t2}",
                "guid1": (c.get("elementId1") or {}).get("guid"),
                "guid2": (c.get("elementId2") or {}).get("guid"),
                "message": f"{t1} 与 {t2} 发生碰撞",
            })
    return violations


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
                "story": z.get("story_index"), "rule": "防火分区面积超限",
                "value": round(area, 2), "limit": max_area,
                "message": (f"防火分区面积 {area:.1f}㎡ 超过限值 "
                            f"{max_area:.0f}㎡"),
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
                "story": s.get("story_index"), "rule": "楼梯净宽不足",
                "value": round(clear_w, 3), "limit": lim["stair_min_width"],
                "message": (f"楼梯净宽 {clear_w:.2f}m（构造宽 {structural_w:.2f}m "
                            f"- 扶手 {deduct:.2f}m）小于 "
                            f"{lim['stair_min_width']:.1f}m"),
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
                "story": r.get("story_index"), "rule": "栏杆高度不足",
                "value": round(h, 3), "limit": min_h,
                "message": f"栏杆高 {h:.2f}m 小于 {min_h:.2f}m",
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
                "story": s.get("story_index"), "rule": "踏步高度超限",
                "value": round(riser, 3), "limit": riser_max,
                "message": f"踏步高 {riser:.3f}m 超过 {riser_max:.3f}m",
            })
        if tread is not None and tread < tread_min:
            violations.append({
                "guid": s["guid"], "name": s.get("name", ""),
                "story": s.get("story_index"), "rule": "踏步深度不足",
                "value": round(tread, 3), "limit": tread_min,
                "message": f"踏步深 {tread:.3f}m 小于 {tread_min:.3f}m",
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
                "rule": "窗地比不足",
                "value": round(ratio, 4),
                "limit": ratio_min,
                "message": (f"第 {st} 层窗地比 {ratio:.3f} "
                            f"小于 {ratio_min:.3f}"
                            f"（窗 {win_area:.1f}㎡ / 地面 {floor_area:.1f}㎡）"),
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
                "story": z.get("story_index"), "rule": "疏散距离超限(估算)",
                "value": round(est_dist, 2), "limit": max_dist,
                "message": (f"Zone 面积 {area:.1f}㎡，估算疏散距离 "
                            f"{est_dist:.1f}m 超过限值 {max_dist:.0f}m"
                            f"（估算值，精确计算需 Zone 边界几何）"),
            })
    return violations


# ---- 汇总入口 -----------------------------------------------------------

def run_review(
    rules: list[str] | None = None,
    limits: dict[str, float] | None = None,
    instance: str | None = None,
    building_type: str = "multi",
    high_rise: bool = False,
    has_sprinkler: bool = False,
) -> dict[str, Any]:
    """执行规范审查，返回各规则违规清单与汇总。

    building_type: high/multi（影响防火分区面积限值）；
    high_rise: 是否高层（影响栏杆高度限值）；
    has_sprinkler: 是否有自动喷淋（影响疏散距离限值）。
    """
    all_rules = [
        "wall_thickness", "openings", "headroom", "collisions",
        "fire_zone_area", "stair_width", "railing_height",
        "stair_tread", "window_floor_ratio", "evacuation_distance",
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
            results[r] = check_collisions(instance)
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
    total = sum(len(v) for v in results.values())
    return {
        "rules_checked": rules,
        "per_rule": {k: len(v) for k, v in results.items()},
        "violations": results,
        "total_violations": total,
        "passed": total == 0,
    }
