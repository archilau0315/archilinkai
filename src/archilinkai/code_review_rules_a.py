"""规范审查规则 A 组（V0.53 拆分）。

规则 1-4：墙厚、门窗洞口、净高、碰撞；
V0.53 新增：楼板厚度、承重/外墙厚度。
每条规则返回违规列表，由 run_review 汇总。
"""

from __future__ import annotations

from typing import Any

from archilinkai import i18n
from archilinkai import instance_manager
from archilinkai.code_review_common import (
    DEFAULT_LIMITS,
    _beam_horizontal_span,
    _fetch_beam_details,
    _fetch_elements,
    _get_props,
    _num,
)

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
                "rule": i18n.t("review.wall_thickness.rule", "墙厚不足"),
                "value": round(t, 3),
                "limit": lim["wall_min_thickness"],
                "message": i18n.t(
                    "review.wall_thickness.msg",
                    f"墙厚 {t:.3f}m 小于最小限值 {lim['wall_min_thickness']:.2f}m",
                    t=f"{t:.3f}", limit=f"{lim['wall_min_thickness']:.2f}"),
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
                        "story": d.get("story_index"),
                        "rule": i18n.t("review.door_headroom.rule", "门洞净高不足"),
                        "value": round(clear_h, 3), "limit": lim["door_min_height"],
                        "message": i18n.t(
                            "review.door_headroom.msg",
                            f"门洞净高 {clear_h:.2f}m（洞口 {rough_h:.2f}m "
                            f"- 上框 {head_h:.2f}m）小于 "
                            f"{lim['door_min_height']:.1f}m",
                            clear_h=f"{clear_h:.2f}", rough_h=f"{rough_h:.2f}",
                            head_h=f"{head_h:.2f}",
                            limit=f"{lim['door_min_height']:.1f}"),
                    })
            if rough_w is not None:
                clear_w = rough_w - frame_w
                if clear_w < lim["door_min_width"]:
                    violations.append({
                        "guid": d["guid"], "name": d.get("name", ""),
                        "story": d.get("story_index"),
                        "rule": i18n.t("review.door_width.rule", "门洞净宽不足"),
                        "value": round(clear_w, 3), "limit": lim["door_min_width"],
                        "message": i18n.t(
                            "review.door_width.msg",
                            f"门洞净宽 {clear_w:.2f}m（洞口 {rough_w:.2f}m "
                            f"- 门框 {frame_w:.2f}m）小于 "
                            f"{lim['door_min_width']:.1f}m",
                            clear_w=f"{clear_w:.2f}", rough_w=f"{rough_w:.2f}",
                            frame_w=f"{frame_w:.2f}",
                            limit=f"{lim['door_min_width']:.1f}"),
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
                    "story": w.get("story_index"),
                    "rule": i18n.t("review.sill_height.rule", "窗台高度不足"),
                    "value": round(sill, 3), "limit": lim["window_sill_min"],
                    "message": i18n.t(
                        "review.sill_height.msg",
                        f"窗台高 {sill:.2f}m 小于 {lim['window_sill_min']:.1f}m",
                        sill=f"{sill:.2f}",
                        limit=f"{lim['window_sill_min']:.1f}"),
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
                "rule": i18n.t("review.headroom.rule", "净高不足"),
                "value": round(headroom, 3),
                "limit": lim["headroom_room"],
                "message": i18n.t(
                    "review.headroom.msg",
                    f"第 {st} 层净高 {headroom:.2f}m 小于 "
                    f"{lim['headroom_room']:.1f}m",
                    st=st, headroom=f"{headroom:.2f}",
                    limit=f"{lim['headroom_room']:.1f}"),
            })
    return violations


# ---- 规则 4：碰撞检查 ---------------------------------------------------

def check_collisions(
    instance: str | None,
    pairs: list[tuple[str, str]] | None = None,
    limits: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """结构与机电构件碰撞检查。

    只报实体碰撞(hasBodyCollision=True)，忽略间隙碰撞。
    同一对元素的碰撞只报一次（去重）。
    """
    from archilinkai.tapir_adapter import adapter
    lim = {**DEFAULT_LIMITS, **(limits or {})}
    body_only = lim.get("collision_body_only", True)

    # 保持精简：4 结构 × 1 机电汇总类型
    pairs = pairs or [
        ("Column", "MEPRoutingElement"),
        ("Beam", "MEPRoutingElement"),
        ("Wall", "MEPRoutingElement"),
        ("Slab", "MEPRoutingElement"),
    ]

    violations: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
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
            # 只报实体碰撞
            if body_only and not c.get("hasBodyCollision"):
                continue
            g1 = (c.get("elementId1") or {}).get("guid", "")
            g2 = (c.get("elementId2") or {}).get("guid", "")
            key = tuple(sorted([g1, g2]))
            if key in seen:
                continue
            seen.add(key)
            violations.append({
                "rule": i18n.t("review.collision.rule", "构件碰撞"),
                "pair": f"{t1} vs {t2}",
                "guid1": g1,
                "guid2": g2,
                "body_collision": c.get("hasBodyCollision"),
                "clearance_collision": c.get("hasClearenceCollision"),
                "message": i18n.t(
                    "review.collision.msg",
                    f"{t1} 与 {t2} 发生碰撞", t1=t1, t2=t2),
            })

    # 分组统计
    by_pair: dict[str, int] = {}
    for v in violations:
        key = v["pair"]
        by_pair[key] = by_pair.get(key, 0) + 1

    # 详细碰撞只保留前 100 条，其余用统计汇总
    detailed = violations[:100]
    detailed.append({
        "rule": i18n.t("review.collision_summary.rule", "碰撞统计"),
        "pair": "SUMMARY",
        "stats": by_pair,
        "total": len(violations),
        "detailed_shown": min(100, len(violations)),
        "message": i18n.t(
            "review.collision_summary.msg",
            f"碰撞总数 {len(violations)}，按类型：{by_pair}。"
            f"详细列出前 {min(100, len(violations))} 条",
            total=len(violations), stats=by_pair,
            shown=min(100, len(violations))),
    })
    return detailed


# ---- 规则 13：楼板厚度检查（V0.53 新增） --------------------------------

def check_slab_thickness(
    instance: str | None,
    limits: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """楼板厚度 ≥ slab_min_thickness（默认 0.10m）。"""
    lim = {**DEFAULT_LIMITS, **(limits or {})}
    slabs = _fetch_elements("Slab", instance)
    if not slabs:
        return []
    guids = [s["guid"] for s in slabs]
    props = _get_props(guids, ["General_Thickness"], instance)
    violations: list[dict[str, Any]] = []
    for s in slabs:
        t = _num(props.get(s["guid"], {}).get("General_Thickness"))
        if t is None:
            continue
        if t < lim["slab_min_thickness"]:
            violations.append({
                "guid": s["guid"],
                "name": s.get("name", ""),
                "story": s.get("story_index"),
                "rule": i18n.t("review.slab_thickness.rule", "楼板厚度不足"),
                "value": round(t, 3),
                "limit": lim["slab_min_thickness"],
                "message": i18n.t(
                    "review.slab_thickness.msg",
                    f"板厚 {t:.3f}m 小于最小限值 {lim['slab_min_thickness']:.2f}m",
                    t=f"{t:.3f}", limit=f"{lim['slab_min_thickness']:.2f}"),
            })
    return violations


# ---- 规则 14：承重/外墙厚度检查（V0.53 新增） ---------------------------

_EXTERNAL_TRUE_STRINGS = {"是", "外墙", "Yes", "yes", "true", "1"}


def _is_external(v: Any) -> bool:
    """判定外墙/承重属性值是否为真。

    bool True、数字非 0、或字符串 ∈ {"是","外墙","Yes","yes","true","1"}。
    """
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v.strip() in _EXTERNAL_TRUE_STRINGS
    return False


def check_bearing_wall_thickness(
    instance: str | None,
    limits: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """承重/外墙厚度 ≥ wall_bearing_min（默认 0.18m）。

    外墙判定：General_External / Wall_External 属性（别名解析透明）。
    属性全部缺失时返回空列表（不误报）。
    """
    lim = {**DEFAULT_LIMITS, **(limits or {})}
    walls = _fetch_elements("Wall", instance)
    if not walls:
        return []
    guids = [w["guid"] for w in walls]
    props = _get_props(
        guids, ["General_External", "Wall_External", "General_Thickness"],
        instance)
    violations: list[dict[str, Any]] = []
    for w in walls:
        p = props.get(w["guid"], {})
        ext_v = p.get("General_External", p.get("Wall_External"))
        if ext_v is None:
            continue
        if not _is_external(ext_v):
            continue
        t = _num(p.get("General_Thickness"))
        if t is None:
            continue
        if t < lim["wall_bearing_min"]:
            violations.append({
                "guid": w["guid"],
                "name": w.get("name", ""),
                "story": w.get("story_index"),
                "rule": i18n.t(
                    "review.bearing_wall.rule", "承重/外墙厚度不足"),
                "value": round(t, 3),
                "limit": lim["wall_bearing_min"],
                "message": i18n.t(
                    "review.bearing_wall.msg",
                    f"承重/外墙厚 {t:.3f}m 小于最小限值 "
                    f"{lim['wall_bearing_min']:.2f}m",
                    t=f"{t:.3f}", limit=f"{lim['wall_bearing_min']:.2f}"),
            })
    return violations


# ---- 规则 15：柱最小截面检查（V0.54 新增） -------------------------------

def check_column_section(
    instance: str | None,
    limits: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """柱截面边长 ≥ column_min_side（默认 0.30m）。

    AC28 真机验证：General_Width 是柱截面宽；General_Height 对柱是
    柱高（=General_3DLength）而非截面边，故只检宽度侧，另一边待确认。

    V0.55 过滤 story<0 或高度 < fake_column_max_height（默认 0.5m）
    的假柱（锚栓标记）。
    """
    lim = {**DEFAULT_LIMITS, **(limits or {})}
    cols = _fetch_elements("Column", instance)
    if not cols:
        return []
    guids = [c["guid"] for c in cols]
    props = _get_props(guids, ["General_Width", "General_Height"], instance)
    violations: list[dict[str, Any]] = []
    fake_h = lim.get("fake_column_max_height", 0.5)
    for c in cols:
        st = c.get("story_index")
        if st is not None and st < 0:
            continue
        p = props.get(c["guid"], {})
        h = _num(p.get("General_Height"))
        if h is not None and h < fake_h:
            continue
        side = _num(p.get("General_Width"))
        if side is None:
            continue
        if side < lim["column_min_side"]:
            violations.append({
                "guid": c["guid"],
                "name": c.get("name", ""),
                "story": st,
                "rule": i18n.t("review.column_section.rule", "柱截面不足"),
                "value": round(side, 3),
                "limit": lim["column_min_side"],
                "message": i18n.t(
                    "review.column_section.msg",
                    f"柱截面边长 {side:.3f}m 小于最小限值 "
                    f"{lim['column_min_side']:.2f}m",
                    side=f"{side:.3f}",
                    limit=f"{lim['column_min_side']:.2f}"),
            })
    return violations


# ---- 规则 16：梁跨高比检查（V0.54 → V0.55 框架化） -----------------------

def check_beam_span_ratio(
    instance: str | None,
    limits: dict[str, float] | None = None,
    structure_type: str | None = None,
) -> list[dict[str, Any]]:
    """梁跨高比 span/h 不应超限（V0.55 改为"跨高比"语义）。

    structure_type 决定限值：
      - "concrete"（默认）：span/h ≤ 12（混凝土梁 h ≥ span/12 反向表达）
      - "steel"     ：span/h ≤ 60（GB 50017-2017 H 型钢简支梁）
      - "continuous"：span/h ≤ 40（钢结构连续梁/受约束）
      - "any"       ：不做检查，直接返回空列表

    V0.57：跨度优先取梁 details 起止点算出的**水平投影**
    √((x2-x1)²+(y2-y1)²)（斜梁不含竖向分量，更贴近真实跨度），
    取不到起止点时用 General_3DLength 兜底。
    """
    st = (structure_type or "concrete").lower()
    if st == "any":
        return []
    lim = {**DEFAULT_LIMITS, **(limits or {})}
    key_map = {
        "concrete": "beam_span_h_ratio_concrete",
        "steel": "beam_span_h_ratio_steel",
        "continuous": "beam_span_h_ratio_continuous",
    }
    ratio_key = key_map.get(st, "beam_span_h_ratio_concrete")
    max_ratio = lim.get(ratio_key, 12.0)

    beams = _fetch_elements("Beam", instance)
    if not beams:
        return []
    guids = [b["guid"] for b in beams]
    props = _get_props(guids, ["General_Height", "General_3DLength"], instance)
    beam_details = _fetch_beam_details(guids, instance)
    violations: list[dict[str, Any]] = []
    for b in beams:
        p = props.get(b["guid"], {})
        h = _num(p.get("General_Height"))
        span_3d = _num(p.get("General_3DLength"))
        span = _beam_horizontal_span(beam_details.get(b["guid"]), span_3d)
        if h is None or span is None or h <= 0 or span <= 0:
            continue
        ratio = span / h
        if ratio > max_ratio:
            violations.append({
                "guid": b["guid"],
                "name": b.get("name", ""),
                "story": b.get("story_index"),
                "rule": i18n.t(
                    "review.beam_span_h_ratio.rule", "梁跨高比超限"),
                "value": round(ratio, 2),
                "limit": max_ratio,
                "message": i18n.t(
                    "review.beam_span_h_ratio.msg",
                    f"梁跨高比 {span:.2f}m / {h:.3f}m = "
                    f"{ratio:.1f} > 限值 {max_ratio:.0f} "
                    f"（{st}）",
                    span=f"{span:.2f}", h=f"{h:.3f}",
                    ratio=f"{ratio:.1f}",
                    limit=f"{max_ratio:.0f}", st=st),
            })
    return violations


# ---- 规则 17：柱长细比检查（V0.55 新增） ----------------------------------

def check_column_slenderness(
    instance: str | None,
    limits: dict[str, float] | None = None,
    structure_type: str | None = None,
) -> list[dict[str, Any]]:
    """柱高/截面宽 ≤ 限值。

    限值按结构类型细分（V0.57）：
      - concrete（默认）：20.0（GB 50011 框架柱 λ=150 简化 H/W≤20）
      - steel           ：43.0（GB 50017 受压构件 λ≤150，H 型钢 i≈0.289W）

    V0.55 过滤 story<0 或高度 < fake_column_max_height（默认 0.5m）
    的假柱（锚栓标记）。
    """
    stype = (structure_type or "concrete").lower()
    lim = {**DEFAULT_LIMITS, **(limits or {})}
    max_ratio = (lim["column_slenderness_max_steel"] if stype == "steel"
                 else lim["column_slenderness_max"])
    cols = _fetch_elements("Column", instance)
    if not cols:
        return []
    guids = [c["guid"] for c in cols]
    props = _get_props(
        guids, ["General_Height", "General_Width"], instance)
    violations: list[dict[str, Any]] = []
    fake_h = lim.get("fake_column_max_height", 0.5)
    for c in cols:
        st = c.get("story_index")
        if st is not None and st < 0:
            continue
        p = props.get(c["guid"], {})
        h = _num(p.get("General_Height"))
        w = _num(p.get("General_Width"))
        if h is None or w is None or w <= 0:
            continue
        if h < fake_h:
            continue
        ratio = h / w
        if ratio > max_ratio:
            violations.append({
                "guid": c["guid"],
                "name": c.get("name", ""),
                "story": st,
                "rule": i18n.t(
                    "review.column_slenderness.rule", "柱长细比过大"),
                "value": round(ratio, 2),
                "limit": max_ratio,
                "message": i18n.t(
                    "review.column_slenderness.msg",
                    f"柱高 {h:.2f}m / 截面宽 {w:.2f}m = "
                    f"{ratio:.1f} > 限值 {max_ratio:.0f}",
                    h=f"{h:.2f}", w=f"{w:.2f}",
                    ratio=f"{ratio:.1f}",
                    lim=f"{max_ratio:.0f}"),
            })
    return violations


# ---- 规则 18：墙高厚比检查（V0.63 新增） ----------------------------------

def check_wall_slenderness(
    instance: str | None,
    limits: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """墙高厚比 = 墙高 / 墙厚 ≤ wall_slenderness_max（默认 30，GB 50003 简化）。

    墙高取 Wall_MaximumHeight（只读长度属性），墙厚取 General_Thickness。
    简化版：未按承重/非承重、砂浆等级细分允许高厚比，默认限值取宽松值
    以降低误报；可用 limits 参数覆盖 wall_slenderness_max。
    """
    lim = {**DEFAULT_LIMITS, **(limits or {})}
    max_ratio = lim["wall_slenderness_max"]
    walls = _fetch_elements("Wall", instance)
    if not walls:
        return []
    guids = [w["guid"] for w in walls]
    props = _get_props(
        guids, ["Wall_MaximumHeight", "General_Thickness"], instance)
    violations: list[dict[str, Any]] = []
    for w in walls:
        p = props.get(w["guid"], {})
        h = _num(p.get("Wall_MaximumHeight"))
        t = _num(p.get("General_Thickness"))
        if h is None or t is None or h <= 0 or t <= 0:
            continue
        ratio = h / t
        if ratio > max_ratio:
            violations.append({
                "guid": w["guid"],
                "name": w.get("name", ""),
                "story": w.get("story_index"),
                "rule": i18n.t("review.wall_slenderness.rule", "墙高厚比超限"),
                "value": round(ratio, 2),
                "limit": max_ratio,
                "message": i18n.t(
                    "review.wall_slenderness.msg",
                    f"墙高 {h:.2f}m / 墙厚 {t:.3f}m = {ratio:.1f} "
                    f"大于限值 {max_ratio:.0f}",
                    h=f"{h:.2f}", t=f"{t:.3f}",
                    ratio=f"{ratio:.1f}", limit=f"{max_ratio:.0f}"),
            })
    return violations


# ---- 规则 19：疏散门净宽检查（V0.63 新增） --------------------------------

# 疏散门名称关键词（AC 无"疏散门"类型标记，按名称过滤避免误判普通房门）
_EVAC_DOOR_KEYWORDS = ("疏散", "安全出口", "逃生", "exit", "evac")


def check_evacuation_door_width(
    instance: str | None,
    limits: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """疏散门净宽 ≥ door_exit_min_width（默认 0.9m）。

    仅对名称含疏散/安全出口等关键词的门检查（普通门不参与，避免误报）。
    净宽 = 洞口宽 - door_frame_allowance（默认 0.10m）。
    """
    lim = {**DEFAULT_LIMITS, **(limits or {})}
    frame_w = lim["door_frame_allowance"]
    limit_w = lim["door_exit_min_width"]
    doors = _fetch_elements("Door", instance)
    if not doors:
        return []
    guids = [d["guid"] for d in doors]
    props = _get_props(guids, ["General_Width"], instance)
    violations: list[dict[str, Any]] = []
    for d in doors:
        name = str(d.get("name", "") or "")
        if not any(k in name for k in _EVAC_DOOR_KEYWORDS):
            continue
        rough_w = _num(props.get(d["guid"], {}).get("General_Width"))
        if rough_w is None:
            continue
        clear_w = rough_w - frame_w
        if clear_w < limit_w:
            violations.append({
                "guid": d["guid"],
                "name": name,
                "story": d.get("story_index"),
                "rule": i18n.t(
                    "review.evacuation_door.rule", "疏散门净宽不足"),
                "value": round(clear_w, 3),
                "limit": limit_w,
                "message": i18n.t(
                    "review.evacuation_door.msg",
                    f"疏散门净宽 {clear_w:.2f}m（洞口 {rough_w:.2f}m "
                    f"- 门框 {frame_w:.2f}m）小于 {limit_w:.1f}m",
                    clear_w=f"{clear_w:.2f}", rough_w=f"{rough_w:.2f}",
                    frame_w=f"{frame_w:.2f}", limit=f"{limit_w:.1f}"),
            })
    return violations


# ---- 规则 20/21 公共：假梁过滤（V0.64） -----------------------------------

def _is_fake_beam(
    p: dict[str, Any], lim: dict[str, float],
) -> bool:
    """装饰段/碎梁过滤：长度 < fake_beam_max_length 或高度 < fake_beam_min_height。"""
    length = _num(p.get("General_3DLength"))
    height = _num(p.get("General_Height"))
    if length is not None and length < lim["fake_beam_max_length"]:
        return True
    if height is not None and height < lim["fake_beam_min_height"]:
        return True
    return False


# ---- 规则 20：梁截面宽度检查（V0.64 新增，仅混凝土） ------------------------

def check_beam_section_width(
    instance: str | None,
    limits: dict[str, float] | None = None,
    structure_type: str | None = None,
) -> list[dict[str, Any]]:
    """梁截面宽度 ≥ beam_section_min_width（默认 0.20m，GB 50010 6.3.1）。

    仅 structure_type="concrete"（默认）生效；钢结构 H 梁窄翼缘属正常，
    steel/continuous/any 直接返回空列表避免误报。
    AC28 真机确证：Beam 的 General_Width = 截面宽度。
    假梁（装饰段）按 _is_fake_beam 过滤。
    """
    st = (structure_type or "concrete").lower()
    if st != "concrete":
        return []
    lim = {**DEFAULT_LIMITS, **(limits or {})}
    min_w = lim["beam_section_min_width"]
    beams = _fetch_elements("Beam", instance)
    if not beams:
        return []
    guids = [b["guid"] for b in beams]
    props = _get_props(
        guids, ["General_Width", "General_Height", "General_3DLength"],
        instance)
    violations: list[dict[str, Any]] = []
    for b in beams:
        p = props.get(b["guid"], {})
        if _is_fake_beam(p, lim):
            continue
        w = _num(p.get("General_Width"))
        if w is None:
            continue
        if w < min_w:
            violations.append({
                "guid": b["guid"],
                "name": b.get("name", ""),
                "story": b.get("story_index"),
                "rule": i18n.t(
                    "review.beam_section_width.rule", "梁截面宽度不足"),
                "value": round(w, 3),
                "limit": min_w,
                "message": i18n.t(
                    "review.beam_section_width.msg",
                    f"梁截面宽 {w:.3f}m 小于最小限值 {min_w:.2f}m",
                    w=f"{w:.3f}", limit=f"{min_w:.2f}"),
            })
    return violations


# ---- 规则 21：梁截面高宽比检查（V0.64 新增，仅混凝土） ----------------------

def check_beam_aspect_ratio(
    instance: str | None,
    limits: dict[str, float] | None = None,
    structure_type: str | None = None,
) -> list[dict[str, Any]]:
    """梁截面高宽比 h/b ≤ beam_aspect_ratio_max（默认 4.0，GB 50010 6.3.1）。

    仅 structure_type="concrete"（默认）生效。假梁按 _is_fake_beam 过滤。
    """
    st = (structure_type or "concrete").lower()
    if st != "concrete":
        return []
    lim = {**DEFAULT_LIMITS, **(limits or {})}
    max_ratio = lim["beam_aspect_ratio_max"]
    beams = _fetch_elements("Beam", instance)
    if not beams:
        return []
    guids = [b["guid"] for b in beams]
    props = _get_props(
        guids, ["General_Width", "General_Height", "General_3DLength"],
        instance)
    violations: list[dict[str, Any]] = []
    for b in beams:
        p = props.get(b["guid"], {})
        if _is_fake_beam(p, lim):
            continue
        w = _num(p.get("General_Width"))
        h = _num(p.get("General_Height"))
        if w is None or h is None or w <= 0 or h <= 0:
            continue
        ratio = h / w
        if ratio > max_ratio:
            violations.append({
                "guid": b["guid"],
                "name": b.get("name", ""),
                "story": b.get("story_index"),
                "rule": i18n.t(
                    "review.beam_aspect_ratio.rule", "梁截面高宽比超限"),
                "value": round(ratio, 2),
                "limit": max_ratio,
                "message": i18n.t(
                    "review.beam_aspect_ratio.msg",
                    f"梁截面高 {h:.3f}m / 宽 {w:.3f}m = {ratio:.1f} "
                    f"大于限值 {max_ratio:.0f}",
                    h=f"{h:.3f}", w=f"{w:.3f}",
                    ratio=f"{ratio:.1f}", limit=f"{max_ratio:.0f}"),
            })
    return violations


# ---- 规则 22：防火门耐火等级缺失检查（V0.64 新增） --------------------------

# 防火门名称关键词（AC 无"防火门"类型标记，按名称过滤避免误判普通门）
_FIRE_DOOR_KEYWORDS = ("防火", "fire")


def check_fire_door_rating(
    instance: str | None,
    limits: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """防火门应标注耐火等级（甲级/乙级/丙级，GB 50016）。

    仅对名称含 防火/fire 关键词的门检查：WindowDoor_FireRating
    为空（None/空串）判违规。属数据完整性检查，名称不过滤的普通门不参与。
    """
    doors = _fetch_elements("Door", instance)
    if not doors:
        return []
    targets = [d for d in doors
               if any(k in str(d.get("name", "") or "").lower()
                      for k in _FIRE_DOOR_KEYWORDS)]
    if not targets:
        return []
    guids = [d["guid"] for d in targets]
    props = _get_props(guids, ["WindowDoor_FireRating"], instance)
    violations: list[dict[str, Any]] = []
    for d in targets:
        rating = props.get(d["guid"], {}).get("WindowDoor_FireRating")
        if rating is not None and str(rating).strip() != "":
            continue
        name = str(d.get("name", "") or "")
        violations.append({
            "guid": d["guid"],
            "name": name,
            "story": d.get("story_index"),
            "rule": i18n.t(
                "review.fire_door_rating.rule", "防火门未标耐火等级"),
            "value": "",
            "limit": "甲/乙/丙级",
            "message": i18n.t(
                "review.fire_door_rating.msg",
                f"防火门 {name} 未标注耐火等级（应为甲级/乙级/丙级）",
                name=name),
        })
    return violations
