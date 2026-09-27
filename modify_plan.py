"""构件修改计划模块（V0.4）。

只做一件事：描述并校验"修改计划 JSON"。
- 每项用 GUID 锁定一个已有构件，只写要改的字段
- 校验只看计划自身，不连真机
- 真机当前值由 modify_service 读回做对照

计划示例（单位：米）：
{
  "instance": "ac29-1",
  "items": [
    {"type": "Wall", "guid": "A1B2...", "height": 4.0},
    {"type": "Column", "guid": "C3D4...", "x": 3.0, "y": 4.0},
    {"type": "Window", "guid": "E5F6...", "width": 1.5}
  ]
}

各类型能改什么：
- Wall：start/end（端点，给就给全 x、y）、height、thickness
- Column：x/y（两个一起给，即平移）、height、width、depth
- Beam：start/end（端点）、width、height（截面）
- Slab：level（绝对标高）、thickness、holes（开洞列表，全量替换）
- Roof：thickness、eavesOverhang（檐出）；只支持多平面屋顶（开洞不支持）
- Door/Window：width、height、sill（窗台/门槛高）

梁、屋顶的"相对楼层位移"不开放：用户难算，真机容易挪错层。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from errors import InvalidArgumentError

#: V0.4 开放修改的构件类型
SUPPORTED_TYPES = frozenset({
    "Wall", "Column", "Beam", "Slab", "Roof", "Door", "Window"
})

#: 字段数值规则：point=2D点 / coord=有界数 / positive=正数 / nonneg=非负数
FIELD_RULES: dict[str, dict[str, str]] = {
    "Wall": {"start": "point", "end": "point",
             "height": "positive", "thickness": "positive"},
    "Column": {"x": "coord", "y": "coord",
               "height": "positive",
               "width": "positive", "depth": "positive"},
    "Beam": {"start": "point", "end": "point",
             "width": "positive", "height": "positive"},
    "Slab": {"level": "coord", "thickness": "positive", "holes": "holes"},
    "Roof": {"thickness": "positive", "eavesOverhang": "coord"},
    "Door": {"width": "positive", "height": "positive", "sill": "nonneg"},
    "Window": {"width": "positive", "height": "positive", "sill": "nonneg"},
}

MAX_ITEMS = 200              # 单次修改构件上限
COORD_LIMIT = 100000.0       # 坐标允许范围（防 LLM 多写 0）


@dataclass
class ModifyItem:
    """计划中对单个构件的修改。changes 只含要改的字段。"""

    type: str
    guid: str
    changes: dict[str, Any]
    index: int  # 在计划中的序号（从 0 开始）

    def to_dict(self) -> dict[str, Any]:
        out = {"index": self.index, "type": self.type, "guid": self.guid}
        out.update(self.changes)
        return out


@dataclass
class ModifyPlan:
    """一份完整的构件修改计划。"""

    items: list[ModifyItem]
    instance: str | None = None

    @classmethod
    def from_dict(cls, source: dict[str, Any]) -> "ModifyPlan":
        """解析、校验。校验不过抛 InvalidArgumentError。"""
        if not isinstance(source, dict):
            raise InvalidArgumentError("plan", type(source).__name__, "应为对象")
        raw_items = source.get("items")
        if not isinstance(raw_items, list) or not raw_items:
            raise InvalidArgumentError("items", raw_items, "至少包含 1 项修改")
        if len(raw_items) > MAX_ITEMS:
            raise InvalidArgumentError(
                "items", f"{len(raw_items)}项",
                f"单次最多 {MAX_ITEMS} 项，请分批",
            )
        items = [_build_item(raw, i) for i, raw in enumerate(raw_items)]
        instance = source.get("instance")
        return cls(items=items, instance=instance or None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance": self.instance,
            "items": [it.to_dict() for it in self.items],
        }

    def types_used(self) -> list[str]:
        """实际用到的构件类型（去重、按首次出现排序）。"""
        seen: list[str] = []
        for it in self.items:
            if it.type not in seen:
                seen.append(it.type)
        return seen


# --- 单项解析与校验 ---------------------------------------------------------


def _build_item(raw: Any, index: int) -> ModifyItem:
    prefix = f"items[{index}]"
    if not isinstance(raw, dict):
        raise InvalidArgumentError(prefix, raw, "应为对象")
    element_type = raw.get("type")
    if element_type not in SUPPORTED_TYPES:
        allowed = ", ".join(sorted(SUPPORTED_TYPES))
        raise InvalidArgumentError(
            f"{prefix}.type", element_type, f"V0.4 仅支持：{allowed}"
        )
    guid = raw.get("guid")
    if not isinstance(guid, str) or not guid.strip():
        raise InvalidArgumentError(f"{prefix}.guid", guid, "应为非空 GUID 字符串")

    rules = FIELD_RULES[element_type]
    unknown = [k for k in raw if k not in ("type", "guid") and k not in rules]
    if unknown:
        raise InvalidArgumentError(
            f"{prefix}", unknown,
            f"{element_type} 不支持修改这些字段",
        )

    changes: dict[str, Any] = {}
    for name, rule in rules.items():
        if name not in raw:
            continue
        if rule == "point":
            changes[name] = _full_point(raw[name], f"{prefix}.{name}")
        elif rule == "holes":
            changes[name] = _hole_polygons(raw[name], f"{prefix}.{name}")
        else:
            changes[name] = _scalar(raw[name], f"{prefix}.{name}", rule)
    if not changes:
        raise InvalidArgumentError(prefix, raw, "至少给出 1 个要改的字段")

    if element_type == "Column":
        _check_column_pair(changes, prefix)
    if (element_type in ("Wall", "Beam")
            and "start" in changes and "end" in changes
            and changes["start"] == changes["end"]):
        raise InvalidArgumentError(
            f"{prefix}.start/end", changes["start"],
            f"{element_type} 的起止点不能相同（长度为 0）"
        )
    return ModifyItem(type=element_type, guid=guid.strip(),
                      changes=changes, index=index)


def _check_column_pair(changes: dict[str, Any], prefix: str) -> None:
    """柱：x/y 必须成对。

    Tapir 只认完整 origin，缺的分量按 0 处理，
    只给一个会把柱挪到坐标轴上。
    """
    if ("x" in changes) != ("y" in changes):
        raise InvalidArgumentError(
            f"{prefix}.x/y", None,
            "柱子平移时 x、y 必须一起给（另一个方向填原值即可）",
        )


# --- 基础数值校验 -----------------------------------------------------------


def _full_point(raw: Any, field_name: str) -> dict[str, float]:
    """2D 点；x、y 必须都给，缺一个直接拒绝（理由同柱 x/y）。"""
    if not isinstance(raw, dict):
        raise InvalidArgumentError(field_name, raw, "应为带 x、y 的坐标对象")
    if "x" not in raw or "y" not in raw:
        raise InvalidArgumentError(field_name, raw, "x、y 必须都给")
    return {"x": _coord_number(raw.get("x"), f"{field_name}.x"),
            "y": _coord_number(raw.get("y"), f"{field_name}.y")}


def _scalar(raw: Any, field_name: str, rule: str) -> float:
    value = _number(raw, field_name)
    if rule == "coord":
        if not math.isfinite(value) or abs(value) > COORD_LIMIT:
            raise InvalidArgumentError(
                field_name, raw, f"应在 ±{COORD_LIMIT:g} 米以内"
            )
    elif rule == "positive":
        if not math.isfinite(value) or value <= 0:
            raise InvalidArgumentError(field_name, raw, "应为正数")
    elif rule == "nonneg":
        if not math.isfinite(value) or value < 0:
            raise InvalidArgumentError(field_name, raw, "应为 0 或正数")
    return value


def _coord_number(raw: Any, field_name: str) -> float:
    value = _number(raw, field_name)
    if not math.isfinite(value) or abs(value) > COORD_LIMIT:
        raise InvalidArgumentError(
            field_name, raw, f"应在 ±{COORD_LIMIT:g} 米以内"
        )
    return value


def _number(raw: Any, field_name: str) -> float:
    # bool 是 int 的子类，但数值不接受 true/false
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise InvalidArgumentError(field_name, raw, "应为数字")
    return float(raw)


def _hole_polygons(raw: Any, field_name: str) -> list[list[dict[str, float]]]:
    """洞列表校验：每个洞是 ≥3 个顶点的闭合多边形。"""
    if not isinstance(raw, list) or not raw:
        raise InvalidArgumentError(field_name, raw, "应为非空洞列表")
    out: list[list[dict[str, float]]] = []
    for i, hole in enumerate(raw):
        if not isinstance(hole, list) or len(hole) < 3:
            raise InvalidArgumentError(
                f"{field_name}[{i}]", hole, "每个洞至少 3 个顶点"
            )
        out.append([_full_point(p, f"{field_name}[{i}][{j}]")
                    for j, p in enumerate(hole)])
    return out
