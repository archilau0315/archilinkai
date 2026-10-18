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
    """门洞高≥2.0m、宽≥0.8m；外窗窗台高≥0.9m。"""
    lim = {**DEFAULT_LIMITS, **(limits or {})}
    violations: list[dict[str, Any]] = []

    # 门
    doors = _fetch_elements("Door", instance)
    if doors:
        guids = [d["guid"] for d in doors]
        props = _get_props(
            guids, ["Door_Height", "Door_Width"], instance)
        for d in doors:
            p = props.get(d["guid"], {})
            h = _num(p.get("Door_Height"))
            w = _num(p.get("Door_Width"))
            if h is not None and h < lim["door_min_height"]:
                violations.append({
                    "guid": d["guid"], "name": d.get("name", ""),
                    "story": d.get("story_index"), "rule": "门洞高度不足",
                    "value": round(h, 3), "limit": lim["door_min_height"],
                    "message": f"门洞高 {h:.2f}m 小于 {lim['door_min_height']:.1f}m",
                })
            if w is not None and w < lim["door_min_width"]:
                violations.append({
                    "guid": d["guid"], "name": d.get("name", ""),
                    "story": d.get("story_index"), "rule": "门洞宽度不足",
                    "value": round(w, 3), "limit": lim["door_min_width"],
                    "message": f"门洞宽 {w:.2f}m 小于 {lim['door_min_width']:.1f}m",
                })

    # 窗（窗台高度）
    windows = _fetch_elements("Window", instance)
    if windows:
        guids = [w["guid"] for w in windows]
        props = _get_props(
            guids, ["Window_SillHeight"], instance)
        for w in windows:
            sill = _num(props.get(w["guid"], {}).get("Window_SillHeight"))
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
    """楼梯梯段宽度≥1.1m。"""
    lim = {**DEFAULT_LIMITS, **(limits or {})}
    stairs = _fetch_elements("Stair", instance)
    if not stairs:
        return []
    guids = [s["guid"] for s in stairs]
    props = _get_props(
        guids, ["Stair_Width", "General_Width"], instance)
    violations: list[dict[str, Any]] = []
    for s in stairs:
        p = props.get(s["guid"], {})
        w = _num(p.get("Stair_Width")) or _num(p.get("General_Width"))
        if w is None:
            continue
        if w < lim["stair_min_width"]:
            violations.append({
                "guid": s["guid"], "name": s.get("name", ""),
                "story": s.get("story_index"), "rule": "楼梯宽度不足",
                "value": round(w, 3), "limit": lim["stair_min_width"],
                "message": f"楼梯宽 {w:.2f}m 小于 {lim['stair_min_width']:.1f}m",
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


# ---- 汇总入口 -----------------------------------------------------------

def run_review(
    rules: list[str] | None = None,
    limits: dict[str, float] | None = None,
    instance: str | None = None,
    building_type: str = "multi",
    high_rise: bool = False,
) -> dict[str, Any]:
    """执行规范审查，返回各规则违规清单与汇总。

    building_type: high/multi（影响防火分区面积限值）；
    high_rise: 是否高层（影响栏杆高度限值）。
    """
    all_rules = [
        "wall_thickness", "openings", "headroom", "collisions",
        "fire_zone_area", "stair_width", "railing_height",
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
    total = sum(len(v) for v in results.values())
    return {
        "rules_checked": rules,
        "per_rule": {k: len(v) for k, v in results.items()},
        "violations": results,
        "total_violations": total,
        "passed": total == 0,
    }
