"""建模计划的基础数值校验。

只做一件事：把计划里的数字、坐标校验并转成规范的 float。
各构件校验模块共用这里的函数，不各自重复实现。
"""

from __future__ import annotations

import math
from typing import Any

from errors import InvalidArgumentError

#: 坐标允许范围（防 LLM 多写 0）
COORD_LIMIT = 100000.0


def number(raw: Any, field_name: str) -> float:
    """转成数字。bool 是 int 子类，但坐标不接受 true/false。"""
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise InvalidArgumentError(field_name, raw, "应为数字")
    return float(raw)


def coord_number(raw: Any, field_name: str) -> float:
    """有界坐标：±COORD_LIMIT 以内。"""
    value = number(raw, field_name)
    if not math.isfinite(value) or abs(value) > COORD_LIMIT:
        raise InvalidArgumentError(
            field_name, raw, f"应在 ±{COORD_LIMIT:g} 米以内"
        )
    return value


def positive(raw: Any, field_name: str) -> float:
    value = number(raw, field_name)
    if not math.isfinite(value) or value <= 0:
        raise InvalidArgumentError(field_name, raw, "应为正数")
    return value


def non_negative(raw: Any, field_name: str) -> float:
    """允许等于 0（如门窗正好在墙起点）。"""
    value = number(raw, field_name)
    if not math.isfinite(value) or value < 0:
        raise InvalidArgumentError(field_name, raw, "应为 0 或正数")
    return value


def point(raw: Any, field_name: str) -> dict[str, float]:
    """2D 坐标点（x、y）。"""
    if not isinstance(raw, dict):
        raise InvalidArgumentError(field_name, raw, "应为带 x、y 的坐标对象")
    return {
        "x": coord_number(raw.get("x"), f"{field_name}.x"),
        "y": coord_number(raw.get("y"), f"{field_name}.y"),
    }


def point3d(raw: Any, field_name: str,
            defaults: dict[str, float]) -> dict[str, float]:
    """3D 点；raw 为 None 时用 defaults 的 x/y/z。"""
    if raw is None:
        return {"x": defaults["x"], "y": defaults["y"], "z": defaults["z"]}
    if not isinstance(raw, dict):
        raise InvalidArgumentError(field_name, raw, "应为带 x、y、z 的坐标对象")
    return {
        "x": coord_number(raw.get("x"), f"{field_name}.x"),
        "y": coord_number(raw.get("y"), f"{field_name}.y"),
        "z": number(raw.get("z"), f"{field_name}.z"),
    }


def hole_polygons(raw: Any, field_name: str) -> list[list[dict[str, float]]]:
    """洞列表校验：每个洞是 ≥3 个顶点的闭合多边形（点不重复）。"""
    if not isinstance(raw, list) or not raw:
        raise InvalidArgumentError(field_name, raw, "应为非空洞列表")
    out: list[list[dict[str, float]]] = []
    for i, hole in enumerate(raw):
        if not isinstance(hole, list) or len(hole) < 3:
            raise InvalidArgumentError(
                f"{field_name}[{i}]", hole, "每个洞至少 3 个顶点"
            )
        out.append([point(p, f"{field_name}[{i}][{j}]")
                    for j, p in enumerate(hole)])
    return out


def point3z(raw: Any, field_name: str) -> dict[str, float]:
    """3D 点：x/y 必填，z 缺省按 0（用于网面、洞口）。"""
    if not isinstance(raw, dict):
        raise InvalidArgumentError(field_name, raw, "应为带 x、y、z 的坐标对象")
    return {
        "x": coord_number(raw.get("x"), f"{field_name}.x"),
        "y": coord_number(raw.get("y"), f"{field_name}.y"),
        "z": number(raw.get("z", 0.0), f"{field_name}.z"),
    }


def hole_polygons3d(raw: Any, field_name: str) -> list[list[dict[str, float]]]:
    """3D 洞列表：每个洞是 ≥3 个 3D 顶点的闭合多边形。"""
    if not isinstance(raw, list) or not raw:
        raise InvalidArgumentError(field_name, raw, "应为非空洞列表")
    out: list[list[dict[str, float]]] = []
    for i, hole in enumerate(raw):
        if not isinstance(hole, list) or len(hole) < 3:
            raise InvalidArgumentError(
                f"{field_name}[{i}]", hole, "每个洞至少 3 个顶点"
            )
        out.append([point3z(p, f"{field_name}[{i}][{j}]")
                    for j, p in enumerate(hole)])
    return out
