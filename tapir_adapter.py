"""Tapir 命令统一封装模块（V0.3 8.2）。

所有 Tapir 命令调用经此模块，统一：
- 经官方 ExecuteAddOnCommand 转发给 Tapir Add-On
- 区分"Tapir 未加载"与"Tapir 命令执行失败"
- 绑定实例（通过 instance_manager）

官方 Python API 命令（如 GetAllElements/GetSelectedElements/GetProductInfo）
不走本模块，直接 conn.commands.xxx 调用。
"""

from __future__ import annotations

import enum
import uuid
from typing import Any

import archicad

import instance_manager
from errors import TapirCommandFailedError, TapirNotLoadedError

# Tapir Add-On 的命令前缀，所有 Tapir 命令经此 AddOnCommandId 加载
_TAPIR_ADDON_NAME = "TapirCommand"


class TapirAdapter:
    """Tapir 命令统一封装器。"""

    def __init__(self, mgr: instance_manager.InstanceManager) -> None:
        self._mgr = mgr

    # --- 核心：统一调用 ---------------------------------------------------

    def execute(
        self,
        command_name: str,
        parameters: dict[str, Any] | None = None,
        instance: str | None = None,
    ) -> Any:
        """统一调用 Tapir 命令。

        Args:
            command_name: Tapir 命令名（如 GetProjectInfo）
            parameters: 命令参数 dict（可空）
            instance: 目标实例 ID；None 时由 manager 决定

        Returns:
            Tapir 命令返回值（dict 或对象）

        Raises:
            TapirNotLoadedError: Add-On 未加载或命令无法识别
            TapirCommandFailedError: 命令执行失败
        """
        conn = self._mgr.get_conn(instance)
        instance_id = self._resolve_instance_id(instance)
        try:
            command_id = conn.types.AddOnCommandId(
                _TAPIR_ADDON_NAME, command_name
            )
        except Exception as exc:
            # Add-On 未加载时构造 AddOnCommandId 通常不抛，但执行会抛
            raise TapirNotLoadedError(instance_id, command_name) from exc
        try:
            return conn.commands.ExecuteAddOnCommand(command_id, parameters)
        except Exception as exc:
            msg = str(exc).lower()
            # 仅在明确"找不到 Add-On/命令"时判未加载；
            # 参数错误（invalid command parameters）应算命令失败，避免误报
            addon_missing = (
                ("addon" in msg or "add-on" in msg)
                and ("not" in msg or "missing" in msg or "no " in msg)
            )
            if addon_missing or "command not found" in msg or "unknown command" in msg:
                raise TapirNotLoadedError(instance_id, command_name) from exc
            raise TapirCommandFailedError(instance_id, command_name, str(exc)) from exc

    def _resolve_instance_id(self, instance: str | None) -> str | None:
        """安全取实例 ID，不影响异常路径。"""
        try:
            return self._mgr.get_info(instance).instance_id
        except Exception:
            return instance

    # --- 便捷封装：常用 Tapir 命令 ---------------------------------------

    def get_project_info(self, instance: str | None = None) -> dict[str, Any]:
        """GetProjectInfo：项目名、路径等。"""
        result = self.execute("GetProjectInfo", None, instance)
        return _to_dict(result)

    def get_details_of_elements(
        self,
        element_guids: list[str],
        instance: str | None = None,
    ) -> list[dict[str, Any]]:
        """GetDetailsOfElements：楼层索引、元素类型、元素编号、几何等。

        实测入参结构：{"elements":[{"elementId":{"guid":...}}]}，
        返回 key：detailsOfElements。返回体不含元素自身 guid，
        这里按请求顺序回填 guid，供调用方对应元素。
        """
        params = {
            "elements": [
                {"elementId": {"guid": str(g)}} for g in element_guids
            ]
        }
        result = self.execute("GetDetailsOfElements", params, instance)
        details = _to_dict(result)
        rows = (
            list(details.get("detailsOfElements", []))
            if isinstance(details, dict) else list(details)
        )
        for g, row in zip(element_guids, rows):
            if isinstance(row, dict):
                row["guid"] = str(g)
        return rows

    # Tapir GetAttributes 支持的属性类型（读用；不同版本覆盖面略异）
    ATTRIBUTE_TYPES = (
        "Layer", "Line", "Pen", "BuildingMaterial", "Composite",
        "Surface", "ZoneCategory", "Profile", "City", "Fill",
        "LayerCombination", "MEPSystem",
    )

    def get_attributes(
        self,
        attribute_type: str,
        instance: str | None = None,
    ) -> list[dict[str, Any]]:
        """GetAttributes：按类型读项目属性列表（Layer/Pen/材料/复合结构等）。

        实测入参：{"attributeType": "Layer"}，
        返回 key：attributes（每项含 attributeId.guid、name 等，
        具体字段随类型而异，统一转 dict 透传）。
        """
        result = self.execute(
            "GetAttributesByType", {"attributeType": attribute_type}, instance)
        data = _to_dict(result)
        if isinstance(data, dict):
            rows = data.get("attributes", [])
        else:
            rows = list(data or [])
        return rows

    # Tapir 库部件类型过滤值（filterByTypeId）
    LIBPART_TYPES = ("Door", "Window", "Object", "Lamp")

    def get_available_library_parts(
        self,
        filter_by_type_id: str | None = None,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """GetAvailableLibraryParts：列出项目可用库部件。

        入参可选 filterByTypeId（Door/Window/Object/Lamp），不传则返回全部。
        返回 dict：libraryParts（每项 guid/index/documentName/fileName/typeId）、
        skippedCount（读取失败数）、skippedSample（前 5 个失败项含 index/code）。
        """
        params = {}
        if filter_by_type_id:
            params["filterByTypeId"] = filter_by_type_id
        result = self.execute("GetAvailableLibraryParts", params, instance)
        data = _to_dict(result)
        if not isinstance(data, dict):
            return {"libraryParts": [], "skippedCount": 0, "skippedSample": []}
        return data

    def get_subelements_of_hierarchical(
        self,
        guids: list[str],
        instance: str | None = None,
    ) -> dict[str, Any]:
        """GetSubelementsOfHierarchicalElements：取层级构件的子构件。

        入参 guids（幕墙/楼梯等父构件 GUID 列表），
        返回 dict：subelements（按类型分组，如 cWallSegments/cWallFrames/
        stairTreads/stairRisers/stairStructures）。
        """
        params = {
            "elements": [{"elementId": {"guid": g}} for g in guids],
        }
        result = self.execute(
            "GetSubelementsOfHierarchicalElements", params, instance)
        data = _to_dict(result)
        if not isinstance(data, dict):
            return {"subelements": []}
        return data

    def set_property_values_of_elements(
        self,
        element_property_values: list[dict[str, Any]],
        instance: str | None = None,
    ) -> Any:
        """SetPropertyValuesOfElements：批量设置属性值（走 Tapir 写入）。"""
        params = {"elementPropertyValues": element_property_values}
        return self.execute("SetPropertyValuesOfElements", params, instance)

    def set_gdl_parameters_of_elements(
        self,
        elements_with_gdl_parameters: list[dict[str, Any]],
        instance: str | None = None,
    ) -> Any:
        """SetGDLParametersOfElements：批量修改 GDL 对象参数（L1）。"""
        params = {"elementsWithGDLParameters": elements_with_gdl_parameters}
        return self.execute("SetGDLParametersOfElements", params, instance)


def _to_dict(value: Any) -> Any:
    """把 Tapir 返回的对象（可能是 namedtuple/dataclass）转成 dict/list。

    archicad 包返回值常见为带属性的对象，转 dict 便于序列化与本地过滤。
    """
    if value is None:
        return None
    # 已是基础类型
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {k: _to_dict(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_dict(v) for v in value]
    # UUID 转字符串（guid 期望形态）；Enum 转值（避免枚举内部自指递归）
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, enum.Enum):
        return _to_dict(value.value)
    # 对象：尝试 __dict__ 或 fields
    if hasattr(value, "__dict__") and value.__dict__:
        return {k: _to_dict(v) for k, v in value.__dict__.items()}
    # __slots__ 对象（archicad 类型常用，__dict__ 为空）
    slots = getattr(value, "__slots__", None)
    if slots:
        if isinstance(slots, str):
            slots = (slots,)
        out = {
            k: _to_dict(getattr(value, k))
            for k in slots if hasattr(value, k)
        }
        if out:
            return out
    # dataclass
    if hasattr(value, "__dataclass_fields__"):
        return {
            k: _to_dict(getattr(value, k))
            for k in value.__dataclass_fields__
        }
    # 兜底：str
    return str(value)


# 模块级单例
adapter = TapirAdapter(instance_manager.manager)
