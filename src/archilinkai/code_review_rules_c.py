"""规范审查规则 C 组（V0.65 从 rules_a 拆出）。

规则 15-17：柱最小截面、梁跨高比、柱长细比；
规则 18-22：墙高厚比、疏散门净宽、梁截面宽度、梁截面高宽比、防火门耐火等级。
每条规则返回违规列表，由 run_review 汇总。
"""

from __future__ import annotations

from typing import Any

from archilinkai import i18n
from archilinkai.code_review_common import (
    DEFAULT_LIMITS,
    _beam_horizontal_span,
    _fetch_beam_details,
    _fetch_elements,
    _get_props,
    _num,
)


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
