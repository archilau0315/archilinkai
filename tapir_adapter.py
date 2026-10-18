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

    # ---- P1 命令：碰撞 / 图层 / 收藏夹 / IFC / 区域边界 / 详情修改 ----

    def get_collisions(
        self,
        elements_group1: list[dict[str, Any]],
        elements_group2: list[dict[str, Any]],
        volume_tolerance: float = 0.001,
        perform_surface_check: bool = False,
        surface_tolerance: float = 0.001,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """GetCollisions：检测两组元素间的碰撞。

        settings 全部可选，缺省 volumeTolerance=0.001 / performSurfaceCheck=False /
        surfaceTolerance=0.001。返回 collisions（每项 elementId1/elementId2/
        hasBodyCollision/hasClearenceCollision）。
        """
        params = {
            "elementsGroup1": elements_group1,
            "elementsGroup2": elements_group2,
            "settings": {
                "volumeTolerance": volume_tolerance,
                "performSurfaceCheck": perform_surface_check,
                "surfaceTolerance": surface_tolerance,
            },
        }
        result = self.execute("GetCollisions", params, instance)
        data = _to_dict(result)
        if not isinstance(data, dict):
            return {"collisions": []}
        return data

    def get_layers(
        self,
        attribute_ids: list[str],
        fields: list[str] | None = None,
        instance: str | None = None,
    ) -> list[dict[str, Any]]:
        """GetLayers：读指定图层的详情（name/isHidden/isLocked/isWireframe/intersectionGroupNr）。

        attribute_ids：图层 attributeId.guid 列表。fields 可选，不传则返回全部字段。
        """
        params: dict[str, Any] = {
            "attributeIds": [{"attributeId": {"guid": g}} for g in attribute_ids]
        }
        if fields:
            params["fields"] = fields
        result = self.execute("GetLayers", params, instance)
        data = _to_dict(result)
        if isinstance(data, dict):
            rows = data.get("layers", [])
        else:
            rows = list(data or [])
        return rows

    def create_layers(
        self,
        layer_data_array: list[dict[str, Any]],
        overwrite_existing: bool = False,
        instance: str | None = None,
    ) -> Any:
        """CreateLayers：创建或覆盖图层。layerDataArray 每项至少含 name。"""
        params = {
            "layerDataArray": layer_data_array,
            "overwriteExisting": overwrite_existing,
        }
        return self.execute("CreateLayers", params, instance)

    def delete_attributes(
        self,
        attributes_to_delete: list[dict[str, Any]],
        instance: str | None = None,
    ) -> Any:
        """DeleteAttributes：删除属性。attributesToDelete 每项含 attributeType + attributeId。"""
        params = {"attributesToDelete": attributes_to_delete}
        return self.execute("DeleteAttributes", params, instance)

    def get_favorites_by_type(
        self,
        element_type: str,
        instance: str | None = None,
    ) -> list[str]:
        """GetFavoritesByType：列指定构件类型的收藏夹名称列表。"""
        params = {"elementType": element_type}
        result = self.execute("GetFavoritesByType", params, instance)
        data = _to_dict(result)
        if isinstance(data, dict):
            rows = data.get("favorites", [])
        else:
            rows = list(data or [])
        return rows

    def apply_favorites_to_elements(
        self,
        favorites_to_apply: list[dict[str, Any]],
        apply_settings: bool = True,
        apply_classifications: bool = True,
        apply_categories: bool = True,
        apply_properties: bool = True,
        instance: str | None = None,
    ) -> Any:
        """ApplyFavoritesToElements：把收藏夹应用到已有元素。

        favorites_to_apply 每项含 elementId + favorite（名称）。
        只改设置类参数，不改几何。
        """
        params: dict[str, Any] = {"favoritesToApply": favorites_to_apply}
        if not apply_settings:
            params["applySettings"] = False
        if not apply_classifications:
            params["applyClassifications"] = False
        if not apply_categories:
            params["applyCategories"] = False
        if not apply_properties:
            params["applyProperties"] = False
        return self.execute("ApplyFavoritesToElements", params, instance)

    def get_ifc_ids_of_elements(
        self,
        guids: list[str],
        instance: str | None = None,
    ) -> list[dict[str, Any]]:
        """GetIFCIdsOfElements：读元素的 IFC ID。"""
        params = {"elements": [{"elementId": {"guid": g}} for g in guids]}
        result = self.execute("GetIFCIdsOfElements", params, instance)
        data = _to_dict(result)
        if isinstance(data, dict):
            rows = data.get("elementIFCIds", [])
        else:
            rows = list(data or [])
        return rows

    def get_elements_by_ifc_ids(
        self,
        ifc_ids: list[str],
        instance: str | None = None,
    ) -> list[dict[str, Any]]:
        """GetElementsByIFCIds：按 IFC ID 反查元素。"""
        params = {"ifcIds": ifc_ids}
        result = self.execute("GetElementsByIFCIds", params, instance)
        data = _to_dict(result)
        if isinstance(data, dict):
            rows = data.get("elementsByIFCIds", [])
        else:
            rows = list(data or [])
        return rows

    def get_ifc_properties_of_elements(
        self,
        guids: list[str],
        instance: str | None = None,
    ) -> list[dict[str, Any]]:
        """GetIFCPropertiesOfElements：读元素的 IFC 属性。"""
        params = {"elements": [{"elementId": {"guid": g}} for g in guids]}
        result = self.execute("GetIFCPropertiesOfElements", params, instance)
        data = _to_dict(result)
        if isinstance(data, dict):
            rows = data.get("elementIFCProperties", [])
        else:
            rows = list(data or [])
        return rows

    def set_details_of_elements(
        self,
        elements_with_details: list[dict[str, Any]],
        instance: str | None = None,
    ) -> Any:
        """SetDetailsOfElements：改元素楼层/图层/绘制顺序等。

        elements_with_details 每项含 elementId + details（floorIndex/layerIndex/drawIndex/typeSpecificDetails）。
        """
        params = {"elementsWithDetails": elements_with_details}
        return self.execute("SetDetailsOfElements", params, instance)

    def get_zone_boundaries(
        self,
        zone_guids: list[str],
        instance: str | None = None,
    ) -> dict[str, Any]:
        """GetZoneBoundaries：读 Zone 的边界（关联元素/相邻 Zone 等）。

        zone_guids 为 Zone elementId.guid 列表。批量查询一次完成，比逐个查快。
        """
        params = {"zones": [{"elementId": {"guid": g}} for g in zone_guids]}
        result = self.execute("GetZoneBoundaries", params, instance)
        data = _to_dict(result)
        if not isinstance(data, dict):
            return {"zoneBoundaries": []}
        return data

    def update_zones(
        self,
        keep_stamp_position: bool = True,
        undo_top_trim: bool = False,
        undo_bottom_trim: bool = False,
        instance: str | None = None,
    ) -> Any:
        """UpdateZones：重算全部 Zone 的几何/标签/关联元素。"""
        params = {
            "keepStampPosition": keep_stamp_position,
            "undoTopTrim": undo_top_trim,
            "undoBottomTrim": undo_bottom_trim,
        }
        return self.execute("UpdateZones", params, instance)

    # ---- P0 命令：连接关系 / 移动旋转 / 预览图 / 材料物理性能 ----

    def get_connected_elements(
        self,
        guids: list[str],
        connected_element_type: str,
        instance: str | None = None,
    ) -> list[dict[str, Any]]:
        """GetConnectedElements：查宿主元素上挂的指定类型子元素。

        如墙上的门窗、幕墙的框架/面板、楼梯的踏踢板、栏杆的立柱/扶手。
        返回 connectedElements（按请求顺序与宿主对应）。
        """
        params = {
            "elements": [{"elementId": {"guid": g}} for g in guids],
            "connectedElementType": connected_element_type,
        }
        result = self.execute("GetConnectedElements", params, instance)
        data = _to_dict(result)
        if isinstance(data, dict):
            rows = data.get("connectedElements", [])
        else:
            rows = list(data or [])
        return rows

    def move_elements(
        self,
        elements_with_move_vectors: list[dict[str, Any]],
        instance: str | None = None,
    ) -> Any:
        """MoveElements：按向量移动元素。

        elements_with_move_vectors 每项：
        {"elementId": {"guid": ...}, "moveVector": {"x": .., "y": .., "z": ..},
         "copy": False(可选，True 时移动副本)}
        """
        params = {"elementsWithMoveVectors": elements_with_move_vectors}
        return self.execute("MoveElements", params, instance)

    def rotate_elements(
        self,
        elements_with_rotations: list[dict[str, Any]],
        instance: str | None = None,
    ) -> Any:
        """RotateElements：绕参考点旋转元素。

        elements_with_rotations 每项：
        {"elementId": {"guid": ...},
         "rotation": {"beginPoint": {"x","y"}, "endPoint": {"x","y"},
                      "origin": {"x","y"}},
         "copy": False(可选)}
        """
        params = {"elementsWithRotations": elements_with_rotations}
        return self.execute("RotateElements", params, instance)

    def get_element_preview_image(
        self,
        guid: str,
        image_type: str = "3D",
        image_format: str = "png",
        width: int = 128,
        height: int = 128,
        instance: str | None = None,
    ) -> str:
        """GetElementPreviewImage：取元素预览图，返回 base64 字符串。

        image_type: 2D / Section / 3D（默认 3D）；image_format: png / jpg。
        """
        params: dict[str, Any] = {
            "elementId": {"guid": guid},
            "imageType": image_type,
            "format": image_format,
            "width": width,
            "height": height,
        }
        result = self.execute("GetElementPreviewImage", params, instance)
        data = _to_dict(result)
        if isinstance(data, dict):
            return data.get("previewImage", "")
        return str(data or "")

    def get_building_material_physical_properties(
        self,
        attribute_ids: list[str],
        instance: str | None = None,
    ) -> list[dict[str, Any]]:
        """GetBuildingMaterialPhysicalProperties：读建筑材料物理性能。

        attribute_ids 为建筑材料 attributeId.guid 列表（包装成
        [{"attributeId": {"guid": ...}}]，与 GetLayers 同格式）。
        返回 properties 列表。
        """
        params = {
            "attributeIds": [{"attributeId": {"guid": g}} for g in attribute_ids]
        }
        result = self.execute(
            "GetBuildingMaterialPhysicalProperties", params, instance)
        data = _to_dict(result)
        if isinstance(data, dict):
            rows = data.get("properties", [])
        else:
            rows = list(data or [])
        return rows

    def get_layer_combinations(
        self,
        attribute_ids: list[str],
        instance: str | None = None,
    ) -> list[dict[str, Any]]:
        """GetLayerCombinations：读图层组合详情（含每层显隐/锁定/线框/交叉组）。

        注意入参 key 是 attributes（非 attributeIds）。列全部图层组合可用
        get_attributes("LayerCombination")。
        """
        params = {
            "attributes": [{"attributeId": {"guid": g}} for g in attribute_ids]
        }
        result = self.execute("GetLayerCombinations", params, instance)
        data = _to_dict(result)
        if isinstance(data, dict):
            rows = data.get("layerCombinations", [])
        else:
            rows = list(data or [])
        return rows

    def create_layer_combinations(
        self,
        layer_combination_data_array: list[dict[str, Any]],
        overwrite_existing: bool = False,
        instance: str | None = None,
    ) -> Any:
        """CreateLayerCombinations：创建或覆盖图层组合。

        每项含 name + layers；layers 每项含 attributeId + isHidden/isLocked/
        isWireframe/intersectionGroupNr（全必填）。
        """
        params = {
            "layerCombinationDataArray": layer_combination_data_array,
            "overwriteExisting": overwrite_existing,
        }
        return self.execute("CreateLayerCombinations", params, instance)


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
