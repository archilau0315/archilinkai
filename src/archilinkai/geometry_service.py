"""几何信息规整模块（V0.3 完整几何信息补充）。

只做一件事：把 Tapir GetDetailsOfElements 的原始详情 dict
转成人类/LLM 易读的规整几何：尺寸摘要、起止点、高程、包围盒。

纯函数、无连接逻辑，便于单元测试。
坐标约定：x/y 为项目坐标；z 相对元素所在楼层。
"""

from __future__ import annotations

import math
from typing import Any


def _wall_length(d: dict) -> float | None:
    """直墙取起止点距离；曲墙（geometryType 非 Straight）不猜弧长，返回 None。"""
    if d.get("geometryType") not in (None, "Straight"):
        return None
    beg, end = d.get("begCoordinate"), d.get("endCoordinate")
    if not beg or not end:
        return None
    return round(math.hypot(end["x"] - beg["x"], end["y"] - beg["y"]), 4)


def _all_polygon_points(detail: dict) -> list[dict]:
    """汇总 floorPlanPolygons 全部 2D 顶点（含洞口切分后的各多边形）。"""
    pts: list[dict] = []
    for poly in detail.get("floorPlanPolygons", []) or []:
        pts.extend(poly.get("coordinates", []) or [])
    return pts


def _bounding_box(detail: dict, d: dict) -> dict[str, Any] | None:
    """平面投影包围盒取自全部多边形顶点；z 范围取楼层相对底/顶。

    无多边形时（如带 profile 的墙 Tapir 不返回 floorPlanPolygons），
    用起止点±厚度/2 的矩形角点兜底推算。
    """
    pts = _all_polygon_points(detail)
    if not pts:
        pts = _fallback_wall_points(d)
    if not pts:
        return None
    xs = [float(p["x"]) for p in pts]
    ys = [float(p["y"]) for p in pts]
    z0 = float(d.get("zCoordinate", 0) or 0)
    z1 = round(z0 + float(d.get("height", 0) or 0), 4)
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    return {
        "min": {"x": round(minx, 4), "y": round(miny, 4), "z": round(z0, 4)},
        "max": {"x": round(maxx, 4), "y": round(maxy, 4), "z": z1},
        "size": {
            "x": round(maxx - minx, 4),
            "y": round(maxy - miny, 4),
            "z": round(z1 - z0, 4),
        },
        "note": "z 相对所在楼层；x/y 为项目坐标。",
    }


def _fallback_wall_points(d: dict) -> list[dict]:
    """直墙兜底：参考线起止点沿法线方向各扩厚度/2，得墙体矩形 4 角点。"""
    if d.get("geometryType") not in (None, "Straight"):
        return []
    beg, end = d.get("begCoordinate"), d.get("endCoordinate")
    if not beg or not end:
        return []
    dx, dy = end["x"] - beg["x"], end["y"] - beg["y"]
    length = math.hypot(dx, dy)
    if length <= 0:
        return []
    thickness = float(d.get("begThickness", 0) or 0)
    nx, ny = -dy / length * thickness / 2, dx / length * thickness / 2
    return [
        {"x": beg["x"] + nx, "y": beg["y"] + ny},
        {"x": beg["x"] - nx, "y": beg["y"] - ny},
        {"x": end["x"] + nx, "y": end["y"] + ny},
        {"x": end["x"] - nx, "y": end["y"] - ny},
    ]


def summarize(detail: dict[str, Any]) -> dict[str, Any]:
    """一条 Tapir 原始详情 → 规整几何信息（字段缺失自动跳过，适配多元素类型）。"""
    d = detail.get("details", {}) or {}
    out: dict[str, Any] = {
        "guid": detail.get("guid"),
        "type": detail.get("type"),
        "id": detail.get("id"),
        "floor_index": detail.get("floorIndex"),
    }

    # 尺寸摘要：只放存在的字段
    summary: dict[str, Any] = {}
    length = _wall_length(d)
    if length is not None:
        summary["length"] = length
    for src, dst in (
        ("height", "height"),
        ("begThickness", "thickness_begin"),
        ("endThickness", "thickness_end"),
        ("structureType", "structure_type"),
    ):
        if src in d:
            summary[dst] = d[src]
    if summary:
        out["summary"] = summary

    # 起止点（3D，z 为楼层相对偏移）+ 底/顶高程
    beg, end = d.get("begCoordinate"), d.get("endCoordinate")
    z0 = float(d.get("zCoordinate", 0) or 0)
    if beg and end:
        out["base_point"] = {"x": beg["x"], "y": beg["y"], "z": z0}
        out["end_point"] = {"x": end["x"], "y": end["y"], "z": z0}
        out["elevation"] = {
            "bottom": z0,
            "top": round(z0 + float(d.get("height", 0) or 0), 4),
        }

    bbox = _bounding_box(detail, d)
    if bbox:
        out["bounding_box"] = bbox
        out["polygon_count"] = len(detail.get("floorPlanPolygons", []) or [])
    return out


def summarize_all(details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """批量规整。"""
    return [summarize(d) for d in details]
