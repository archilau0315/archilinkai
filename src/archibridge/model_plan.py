"""建模计划模块。

只做一件事：描述并校验"建模计划 JSON"。
- 自然语言、图片两条输入路径最终都生成这份计划
- 校验只针对计划自身的结构与数据合理性，不依赖真机
- 各构件的具体校验拆在 plan_framing / plan_openings / plan_special，
  基础数值校验在 plan_values

计划示例（单位：米）：
{
  "instance": "ac29-1",
  "elements": [
    {"type": "Wall", "start": {"x": 0, "y": 0}, "end": {"x": 6, "y": 0}},
    {"type": "Column", "x": 0, "y": 0}
  ]
}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from archibridge.errors import InvalidArgumentError
from archibridge import plan_framing
from archibridge import plan_openings
from archibridge import plan_special

#: 当前支持的构件类型
SUPPORTED_TYPES = frozenset({"Wall", "Column", "Beam", "Slab",
                             "Door", "Window",
                             "Stair", "Roof", "Morph",
                             "Object", "Lamp",
                             "Mesh", "Opening", "Zone", "MEPRoute"})

#: 必须挂墙的构件（门窗），用于墙引用校验
WALL_BASED = frozenset({"Door", "Window"})

#: 依赖宿主、需在宿主建成后再建的构件（V0.12 加 Opening）
HOST_BASED = frozenset({"Door", "Window", "Opening"})

#: 独立洞口允许挂的宿主类型
OPENING_HOSTS = frozenset({"Wall", "Slab", "Beam", "Mesh"})

#: 单次计划构件上限
MAX_ELEMENTS = 200

#: 构件类型 → 校验函数（构件字段、序号 → 补全默认值后的字段）
_BUILDERS: dict[str, Callable[[dict[str, Any], int], dict[str, Any]]] = {
    "Wall": plan_framing.build_wall,
    "Column": plan_framing.build_column,
    "Beam": plan_framing.build_beam,
    "Slab": plan_framing.build_slab,
    "Door": plan_openings.build_door,
    "Window": plan_openings.build_window,
    "Stair": plan_special.build_stair,
    "Roof": plan_special.build_roof,
    "Morph": plan_special.build_morph,
    "Object": plan_special.build_object,
    "Lamp": plan_special.build_object,
    "Mesh": plan_special.build_mesh,
    "Opening": plan_special.build_opening,
    "Zone": plan_special.build_zone,
    "MEPRoute": plan_special.build_mep_route,
}


@dataclass
class PlanElement:
    """计划中的单个构件。data 为补全默认值后的字段。"""

    type: str
    data: dict[str, Any]
    index: int  # 在计划中的序号（从 0 开始）

    def to_dict(self) -> dict[str, Any]:
        out = {"index": self.index, "type": self.type}
        out.update(self.data)
        return out


@dataclass
class ModelPlan:
    """一份完整的建模计划。"""

    elements: list[PlanElement] = field(default_factory=list)
    instance: str | None = None

    @classmethod
    def from_dict(cls, source: dict[str, Any]) -> "ModelPlan":
        """解析、校验并补全默认值。校验不过抛 InvalidArgumentError。"""
        if not isinstance(source, dict):
            raise InvalidArgumentError("plan", type(source).__name__, "应为对象")
        raw_elements = source.get("elements")
        if not isinstance(raw_elements, list) or not raw_elements:
            raise InvalidArgumentError("elements", raw_elements,
                                       "至少包含 1 个构件")
        if len(raw_elements) > MAX_ELEMENTS:
            raise InvalidArgumentError(
                "elements", f"{len(raw_elements)}个",
                f"单次最多 {MAX_ELEMENTS} 个，请分批",
            )
        elements = [
            _build_element(raw, i)
            for i, raw in enumerate(raw_elements)
        ]
        _check_references(elements)
        instance = source.get("instance")
        return cls(elements=elements, instance=instance or None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance": self.instance,
            "elements": [e.to_dict() for e in self.elements],
        }

    def types_used(self) -> list[str]:
        """计划中实际用到的构件类型（去重、按首次出现排序）。"""
        seen: list[str] = []
        for e in self.elements:
            if e.type not in seen:
                seen.append(e.type)
        return seen


# --- 单构件解析 -------------------------------------------------------------


def _build_element(raw: Any, index: int) -> PlanElement:
    if not isinstance(raw, dict):
        raise InvalidArgumentError(f"elements[{index}]", raw, "应为对象")
    element_type = raw.get("type")
    if element_type not in SUPPORTED_TYPES:
        allowed = ", ".join(sorted(SUPPORTED_TYPES))
        raise InvalidArgumentError(
            f"elements[{index}].type", element_type, f"仅支持：{allowed}"
        )
    data = {k: v for k, v in raw.items() if k != "type"}
    data = _BUILDERS[element_type](data, index)
    return PlanElement(type=element_type, data=data, index=index)


def _check_references(elements: list[PlanElement]) -> None:
    """交叉校验：序号引用的目标必须存在且类型允许。

    - 门/窗 wall：必须是本计划中的墙
    - 洞口 host：必须是墙、板、梁、网面
    """
    for e in elements:
        if e.type in WALL_BASED and isinstance(e.data["wall"], int):
            ref = e.data["wall"]
            if ref >= len(elements) or elements[ref].type != "Wall":
                raise InvalidArgumentError(
                    f"elements[{e.index}].wall", ref,
                    f"该序号不是墙（计划共 {len(elements)} 个构件）",
                )
        elif e.type == "Opening" and isinstance(e.data["host"], int):
            ref = e.data["host"]
            if ref >= len(elements):
                raise InvalidArgumentError(
                    f"elements[{e.index}].host", ref,
                    f"序号超出计划范围（共 {len(elements)} 个构件）",
                )
            if elements[ref].type not in OPENING_HOSTS:
                raise InvalidArgumentError(
                    f"elements[{e.index}].host", ref,
                    "洞口只能挂在墙、板、梁、网面上",
                )
