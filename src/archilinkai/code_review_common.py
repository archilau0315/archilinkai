"""规范审查公共模块（V0.53 拆分）。

含规范限值 DEFAULT_LIMITS 与三条公共 helper：
_fetch_elements / _get_props / _num。
各规则模块从这里 import，保持单一数据源。
"""

from __future__ import annotations

import math
from typing import Any

from archilinkai import property_service
from archilinkai.query_engine import QueryRequest, engine

# 规范限值（可被参数覆盖，单位：m）
DEFAULT_LIMITS: dict[str, float] = {
    "wall_min_thickness": 0.09,        # 隔墙最小厚度
    "wall_bearing_min": 0.18,          # 承重墙最小厚度
    "slab_min_thickness": 0.10,        # 楼板最小厚度
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
    # ---- V0.48 层高 + 踏步级数 ----
    "floor_height_min_office": 3.0,      # 办公建筑最小层高(m)
    "floor_height_min_residential": 2.8, # 住宅最小层高(m)
    "stair_max_riser_count": 18,         # 楼梯最大踏步级数（超过需设平台）
    # ---- V0.49 碰撞过滤 ----
    "collision_min_volume": 0.001,      # 最小碰撞体积(m³)，当前 Tapir 无此字段，保留备用
    "collision_body_only": True,        # 只报实体碰撞(hasBodyCollision)，忽略间隙碰撞
    # ---- V0.54 柱/梁 ----
    "column_min_side": 0.30,            # 框架柱截面最小边长(m)
    # ---- V0.55 钢结构梁 + 柱长细比 ----
    "beam_span_h_ratio_concrete": 12.0,   # 混凝土跨高比上限 span/h ≤ 12
    "beam_span_h_ratio_steel": 60.0,      # 钢结构简支梁 span/h ≤ 60（GB 50017）
    "beam_span_h_ratio_continuous": 40.0, # 钢结构连续梁/受约束 span/h ≤ 40
    "column_slenderness_max": 20.0,       # 混凝土柱高/截面宽 ≤ 20（简化长细比限值）
    # ---- V0.57 钢结构柱长细比 ----
    # GB 50017 受压构件 λ≤150，λ=L0/i，H 型钢 i≈0.289W → H/W≤43
    "column_slenderness_max_steel": 43.0,
    "fake_column_max_height": 0.5,        # 假柱高度阈值(m)：< 此值视为锚栓标记跳过
    # ---- V0.63 墙高厚比 ----
    # 墙高/墙厚 ≤ 限值（GB 50003 允许高厚比简化；未细分承重/砂浆，取宽松值降误报）
    "wall_slenderness_max": 30.0,
}


def _fetch_elements(element_type: str, instance: str | None) -> list[dict[str, Any]]:
    """用 query_engine 取指定类型元素（含 guid/story_index）。"""
    page = engine.query(QueryRequest(
        element_type=element_type, limit=10000, instance=instance))
    return page.items


def _get_props(
    guids: list[str], names: list[str], instance: str | None,
) -> dict[str, dict[str, Any]]:
    """按请求名读取属性；请求名不存在时自动尝试别名候选（V0.50）。

    返回 {guid: {请求名: 值}}，调用方仍用原请求名索引，别名解析透明。
    """
    if not guids:
        return {}
    from archilinkai.property_alias import resolver
    # 请求名 → 实际命中的真实属性名
    actual_map: dict[str, str] = {}
    for n in names:
        actual = resolver.resolve(n, instance)
        if actual:
            actual_map[n] = actual
    if not actual_map:
        return {g: {} for g in guids}
    raw = property_service.service.get_values(
        guids, list(actual_map.values()), instance)
    out: dict[str, dict[str, Any]] = {g: {} for g in guids}
    for g in guids:
        row = raw.get(g, {})
        for requested, actual in actual_map.items():
            if actual in row:
                out[g][requested] = row[actual]
    return out


def _num(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _fetch_beam_details(
    guids: list[str], instance: str | None,
) -> dict[str, dict[str, Any]]:
    """取梁的 Tapir 详情，返回 {guid: detail}；失败返回空 dict（不阻塞规则）。"""
    if not guids:
        return {}
    from archilinkai.tapir_adapter import adapter
    try:
        rows = adapter.get_details_of_elements(list(guids), instance)
    except Exception:
        return {}
    return {r.get("guid"): r for r in rows if isinstance(r, dict) and r.get("guid")}


def _beam_horizontal_span(
    detail: dict[str, Any] | None,
    fallback_len: float | None,
    instance: str | None = None,
) -> float | None:
    """梁水平投影跨度 = √((x2-x1)²+(y2-y1)²)。

    detail 为 Tapir 梁详情（取 details.begCoordinate/endCoordinate，
    仅含 x/y，即天然的水平投影，斜梁不含竖向分量）。
    拿不到起止点时用 fallback_len（General_3DLength）兜底。
    instance 为保留形参，当前未使用。
    """
    d = detail if isinstance(detail, dict) else {}
    # 兼容传入整条详情（含 details 子对象）或直接传入 details 字典
    d = d.get("details") or d
    beg, end = d.get("begCoordinate"), d.get("endCoordinate")
    if beg and end:
        try:
            span = math.hypot(
                float(end["x"]) - float(beg["x"]),
                float(end["y"]) - float(beg["y"]),
            )
            if span > 0:
                return span
        except (KeyError, TypeError, ValueError):
            pass
    return fallback_len
