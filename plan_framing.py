"""结构框架类构件的校验：墙、柱、梁、板。

每个函数入参（构件原始字段、序号），出参补全默认值后的字段。
"""

from __future__ import annotations

from typing import Any

from errors import InvalidArgumentError
import plan_values
from plan_values import coord_number, number, point, positive

#: 本族默认值（用户不填时使用）
_DEFAULTS: dict[str, dict[str, float]] = {
    "Wall": {"height": 3.0, "thickness": 0.2},
    "Column": {"height": 3.0},
    "Beam": {"height": 0.3, "width": 0.2, "z": 0.0},
    "Slab": {"level": 0.0, "thickness": 0.2},
}


def build_wall(data: dict[str, Any], index: int) -> dict[str, Any]:
    """墙：起止点 + 高 + 厚。"""
    prefix = f"elements[{index}]"
    start = point(data.get("start"), f"{prefix}.start")
    end = point(data.get("end"), f"{prefix}.end")
    if start == end:
        raise InvalidArgumentError(
            f"{prefix}.start/end", start, "墙的起止点不能相同（墙长为 0）"
        )
    height = positive(data.get("height", _DEFAULTS["Wall"]["height"]),
                      f"{prefix}.height")
    thickness = positive(data.get("thickness", _DEFAULTS["Wall"]["thickness"]),
                         f"{prefix}.thickness")
    return {"start": start, "end": end,
            "height": height, "thickness": thickness}


def build_column(data: dict[str, Any], index: int) -> dict[str, Any]:
    """柱：平面位置 x/y + 高。"""
    prefix = f"elements[{index}]"
    x = coord_number(data.get("x"), f"{prefix}.x")
    y = coord_number(data.get("y"), f"{prefix}.y")
    height = positive(data.get("height", _DEFAULTS["Column"]["height"]),
                      f"{prefix}.height")
    return {"x": x, "y": y, "height": height}


def build_beam(data: dict[str, Any], index: int) -> dict[str, Any]:
    """梁：起止点 + 截面宽/高 + 梁顶标高 z。"""
    prefix = f"elements[{index}]"
    start = point(data.get("start"), f"{prefix}.start")
    end = point(data.get("end"), f"{prefix}.end")
    if start == end:
        raise InvalidArgumentError(
            f"{prefix}.start/end", start, "梁的起止点不能相同（梁长为 0）"
        )
    height = positive(data.get("height", _DEFAULTS["Beam"]["height"]),
                      f"{prefix}.height")
    width = positive(data.get("width", _DEFAULTS["Beam"]["width"]),
                     f"{prefix}.width")
    # z 是标高，可为负（地下），只查数值合法
    z = number(data.get("z", _DEFAULTS["Beam"]["z"]), f"{prefix}.z")
    return {"start": start, "end": end,
            "height": height, "width": width, "z": z}


def build_slab(data: dict[str, Any], index: int) -> dict[str, Any]:
    """板：闭合多边形顶点（≥3）+ 顶面标高 + 厚度；可选 holes 开洞列表。"""
    prefix = f"elements[{index}]"
    raw_poly = data.get("polygon")
    if not isinstance(raw_poly, list) or len(raw_poly) < 3:
        raise InvalidArgumentError(
            f"{prefix}.polygon", raw_poly, "板至少需要 3 个顶点"
        )
    polygon = [point(p, f"{prefix}.polygon[{i}]")
               for i, p in enumerate(raw_poly)]
    level = number(data.get("level", _DEFAULTS["Slab"]["level"]),
                   f"{prefix}.level")
    thickness = positive(data.get("thickness", _DEFAULTS["Slab"]["thickness"]),
                         f"{prefix}.thickness")
    out: dict[str, Any] = {"polygon": polygon, "level": level,
                           "thickness": thickness}
    if "holes" in data:
        out["holes"] = plan_values.hole_polygons(
            data["holes"], f"{prefix}.holes"
        )
    return out
