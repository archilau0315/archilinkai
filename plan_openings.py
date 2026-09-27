"""门窗类构件的校验：门、窗（都必须挂墙）。

wall 两种写法：
- 整数：本计划中墙的序号（引用将新建的墙）
- 字符串：项目中已有墙的 GUID
"""

from __future__ import annotations

from typing import Any

from errors import InvalidArgumentError
from plan_values import non_negative, positive

#: 本族默认值
_DEFAULTS: dict[str, dict[str, float]] = {
    "Door": {"width": 1.0, "height": 2.1, "sill": 0.0, "offset": 1.0},
    "Window": {"width": 1.2, "height": 1.5, "sill": 0.9, "offset": 1.0},
}


def build_door(data: dict[str, Any], index: int) -> dict[str, Any]:
    return _build_opening(data, index, "Door")


def build_window(data: dict[str, Any], index: int) -> dict[str, Any]:
    return _build_opening(data, index, "Window")


def _build_opening(data: dict[str, Any], index: int,
                   element_type: str) -> dict[str, Any]:
    """挂哪面墙 + 沿墙位置 offset + 洞口宽高 + 窗台/门槛高 sill。"""
    prefix = f"elements[{index}]"
    wall = data.get("wall")
    # bool 是 int 子类但不能当序号
    if isinstance(wall, bool) or (
        not isinstance(wall, int) and not isinstance(wall, str)
    ):
        raise InvalidArgumentError(
            f"{prefix}.wall", wall,
            "应为计划内墙的序号（如 0）或已有墙的 GUID 字符串",
        )
    if isinstance(wall, str) and not wall.strip():
        raise InvalidArgumentError(
            f"{prefix}.wall", wall, "GUID 不能为空字符串"
        )

    d = _DEFAULTS[element_type]
    offset = non_negative(data.get("offset", d["offset"]),
                          f"{prefix}.offset")
    width = positive(data.get("width", d["width"]), f"{prefix}.width")
    height = positive(data.get("height", d["height"]), f"{prefix}.height")
    sill = non_negative(data.get("sill", d["sill"]), f"{prefix}.sill")
    return {"wall": wall, "offset": offset,
            "width": width, "height": height, "sill": sill}
