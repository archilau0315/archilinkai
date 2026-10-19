"""属性名别名解析模块（V0.50）

问题：各模块直接写死 ArchiCAD 属性名（如 General_Thickness），
换项目 / 换 ArchiCAD 版本后属性名不存在，读取静默返回 None。

方案：语义键 → 候选属性名列表；运行时按顺序取第一个真实存在的属性名，
结果按 (instance, 名称) 缓存。调用方仍用原属性名索引，无感兼容。
"""
from __future__ import annotations

from typing import Any

from archilinkai import instance_manager
from archilinkai.errors import PropertyNotFoundError
from archilinkai import property_service

# 语义键 → 候选属性名（按优先级，前为最优）
PROPERTY_ALIASES: dict[str, list[str]] = {
    # 墙
    "wall_thickness": [
        "General_Thickness", "Wall_Thickness",
        "Wall_CompositeThickness", "General_WallThickness",
    ],
    # 门窗洞口
    "opening_width": [
        "General_Width", "Door_Width", "Window_Width", "Opening_Width",
    ],
    "opening_height": [
        "General_Height", "Door_Height", "Window_Height", "Opening_Height",
    ],
    "sill_height": [
        "Window_SillHeight", "General_SillHeight", "Window_Sill",
        "General_Sill",
    ],
    # 梁 / 板
    "beam_height": ["Beam_Height", "General_Height", "Beam_Height_"],
    "slab_thickness": [
        "Slab_Thickness", "General_Thickness", "Slab_Thickness_",
    ],
    # 楼梯
    "stair_flight_width": [
        "Stair_FlightWidth", "Stair_Width", "Stair_GoingWidth",
    ],
    "stair_riser_height": [
        "Stair_DefaultRiserHeight", "Stair_RiserHeight", "Stair_Riser",
    ],
    "stair_going": [
        "Stair_DefaultGoing", "Stair_TreadDepth", "Stair_Going",
    ],
    "stair_riser_count": [
        "Stair_NumberOfRisers", "Stair_RiserCount", "Stair_Risers",
        "Stair_Number_Of_Risers",
    ],
    # 栏杆
    "railing_height": ["Railing_Height", "General_Height", "Railing_Height_"],
    # 面积 / 体积
    "zone_area": [
        "General_NetArea", "General_Area", "Zone_CalculatedArea",
    ],
    "element_area": ["General_Area", "General_NetArea"],
    "element_volume": ["General_Volume", "General_NetVolume"],
    "wall_volume": ["General_NetVolume", "General_Volume"],
    # 翻新状态（内置属性，固定英文名）
    "renovation_status": ["Category_RenovationStatus"],
}


def candidates_for(name: str) -> list[str]:
    """名称 → 候选列表。

    - name 是语义键：返回该键的候选列表
    - name 是候选之一：返回所属键的候选列表（name 提到最前）
    - 其他：返回 [name]
    """
    if name in PROPERTY_ALIASES:
        return list(PROPERTY_ALIASES[name])
    for key, cands in PROPERTY_ALIASES.items():
        if name in cands:
            rest = [c for c in cands if c != name]
            return [name, *rest]
    return [name]


class AliasResolver:
    """属性名解析器：把请求名解析为真实存在的属性名，带缓存。"""

    def __init__(self, mgr: instance_manager.InstanceManager) -> None:
        self._mgr = mgr
        # {(instance, name): 真实属性名 or None}
        self._cache: dict[tuple, str | None] = {}

    def _exists(self, name: str, instance: str | None) -> bool:
        try:
            property_service.service.get_property_id(name, instance)
            return True
        except PropertyNotFoundError:
            return False

    def resolve(self, name: str, instance: str | None = None) -> str | None:
        """返回第一个真实存在的候选名；全都不存在返回 None。"""
        ck = (instance, name)
        if ck in self._cache:
            return self._cache[ck]
        found: str | None = None
        for cand in candidates_for(name):
            if self._exists(cand, instance):
                found = cand
                break
        self._cache[ck] = found
        return found

    def resolve_many(
        self, names: list[str], instance: str | None = None,
    ) -> dict[str, str | None]:
        """批量解析：{请求名: 真实名 or None}。"""
        return {n: self.resolve(n, instance) for n in names}

    def describe(
        self, names: list[str] | None = None, instance: str | None = None,
    ) -> dict[str, Any]:
        """返回别名解析报告：每个键的候选、实际命中。"""
        keys = names or list(PROPERTY_ALIASES.keys())
        out: dict[str, Any] = {}
        for key in keys:
            cands = candidates_for(key)
            hit = self.resolve(key, instance)
            out[key] = {
                "candidates": cands,
                "resolved": hit,
                "fallback_used": hit not in (None, cands[0]),
            }
        return out


# 模块级单例
resolver = AliasResolver(instance_manager.manager)
