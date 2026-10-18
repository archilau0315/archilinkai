"""P0 只读工具注册（V0.3 从 server.py 拆出，控制入口行数）。

只做一件事：向 FastMCP 注册 10 个只读工具。
通过 register(mcp, safe) 调用，复用 server 的统一异常包装。
"""

from __future__ import annotations

from typing import Any

import aggregate_service
import errors
import geometry_service
import gdl_service
import instance_manager
import property_service
import query_engine
from mcp.server.fastmcp import FastMCP
from schemas import Filter, Operator, QueryRequest, success_result
from tapir_adapter import _to_dict, adapter as _tapir


def register(mcp: FastMCP, safe) -> None:
    """注册只读工具。safe 为 server._safe（统一异常包装）。"""

    @mcp.tool()
    def list_instances() -> dict[str, Any]:
        """列出所有已连接的 ArchiCAD 实例：实例 ID、端口、版本、项目名。"""
        return safe(
            None,
            lambda: success_result(
                items=[e.to_dict()
                       for e in instance_manager.manager.list_instances()],
                count=len(instance_manager.manager.list_instances()),
            ),
        )

    @mcp.tool()
    def project_summary(instance: str | None = None) -> dict[str, Any]:
        """项目概览：元素总数、可用属性数量。"""
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            conn = instance_manager.manager.get_conn(instance)
            elements = conn.commands.GetAllElements()  # 只返回 GUID，轻量
            props = conn.commands.GetAllPropertyNames()
            return success_result(
                instance=info.instance_id,
                project=info.project_name,
                count=len(elements),
                data={"properties": len(props)},
            )
        return safe(instance, _run)

    @mcp.tool()
    def get_selected_elements(instance: str | None = None) -> dict[str, Any]:
        """读取当前选中元素：元素类型 + GUID。"""
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            conn = instance_manager.manager.get_conn(instance)
            selected = conn.commands.GetSelectedElements()
            if not selected:
                return success_result(
                    instance=info.instance_id, project=info.project_name,
                    count=0, items=[], data={"message": "当前没有选中元素。"},
                )
            elem_types = conn.commands.GetTypesOfElements(selected)
            items = [
                {"guid": e.elementId.guid, "type": t.type}
                for e, t in zip(selected, elem_types)
            ]
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(items), items=items,
            )
        return safe(instance, _run)

    @mcp.tool()
    def get_elements_by_type(
        element_type: str, instance: str | None = None
    ) -> dict[str, Any]:
        """按元素类型获取元素列表（GUID + 类型）。"""
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            conn = instance_manager.manager.get_conn(instance)
            try:
                # AC29 支持 'All'，AC28 不支持（失败→兜底 GetAllElements）
                elements = conn.commands.GetElementsByType(element_type)
            except Exception:
                # 类型名无效，或 AC28 拒绝 'All'，回退全部元素
                elements = conn.commands.GetAllElements()
            items = [{"guid": e.elementId.guid, "type": element_type}
                     for e in elements]
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(items), items=items,
            )
        return safe(instance, _run)

    @mcp.tool()
    def get_element_properties(
        element_guids: list[str],
        property_names: list[str],
        instance: str | None = None,
    ) -> dict[str, Any]:
        """读取指定元素的指定属性。"""
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            values = property_service.service.get_values(
                element_guids, property_names, instance
            )
            items = [{"guid": g, "properties": values.get(g, {})}
                     for g in element_guids]
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(items), items=items,
            )
        return safe(instance, _run)

    @mcp.tool()
    def search_elements_by_criteria(
        element_type: str | None = None,
        stories: list[int] | None = None,
        filters: list[dict[str, Any]] | None = None,
        limit: int = 100,
        cursor: str | None = None,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """组合搜索：按类型/楼层/属性值过滤，支持分页。

        filters 示例：[{"field":"Fire Rating","operator":"=","value":"A"}]
        operator ∈ =, !=, >, >=, <, <=, contains, starts_with, in
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            parsed_filters: list[Filter] = [
                Filter(field=f["field"], operator=Operator(f["operator"]),
                       value=f["value"])
                for f in (filters or [])
            ]
            request = QueryRequest(
                instance=instance,
                element_type=element_type,
                stories=stories,
                filters=parsed_filters,
                limit=limit,
                cursor=cursor,
            )
            page = query_engine.engine.query(request)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=page.count, items=page.items,
                data={"next_cursor": page.next_cursor},
            )
        return safe(instance, _run)

    @mcp.tool()
    def get_gdl_parameters(
        element_guids: list[str], instance: str | None = None
    ) -> dict[str, Any]:
        """读取已放置 GDL 对象的参数（经 Tapir）。"""
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            data = gdl_service.service.get_parameters(element_guids, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(element_guids),
                data={"gdl_parameters": data},
            )
        return safe(instance, _run)

    @mcp.tool()
    def list_floors(instance: str | None = None) -> dict[str, Any]:
        """列出项目楼层（经 Tapir GetStories）。"""
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            result = _tapir.execute("GetStories", None, instance)
            stories = _to_dict(result)
            if isinstance(stories, dict):
                stories = stories.get("stories", [])
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(stories) if isinstance(stories, list) else 0,
                data={"floors": stories},
            )
        return safe(instance, _run)

    @mcp.tool()
    def get_classifications(instance: str | None = None) -> dict[str, Any]:
        """列出项目可用的分类系统与分类项。"""
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            conn = instance_manager.manager.get_conn(instance)
            systems = conn.commands.GetAllClassificationSystems()
            items = [_to_dict(s) for s in systems]
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(items), items=items,
            )
        return safe(instance, _run)

    @mcp.tool()
    def list_attributes(
        attribute_type: str = "Layer", instance: str | None = None
    ) -> dict[str, Any]:
        """按类型列出项目属性（经 Tapir GetAttributes）。

        attribute_type 常用：Layer（图层）、Pen（画笔）、Line（线型）、
        BuildingMaterial（建筑材料）、Composite（复合结构）、Surface（表面材质）、
        ZoneCategory（区域类别）、Profile（截面）、Fill（填充）、
        LayerCombination（图层组合）、MEPSystem（机电系统）。
        每项含 attributeId.guid 与 name，具体字段随类型而异。
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            rows = _tapir.get_attributes(attribute_type, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(rows), attribute_type=attribute_type, items=rows,
            )
        return safe(instance, _run)

    @mcp.tool()
    def list_library_parts(
        type_id: str | None = None, instance: str | None = None
    ) -> dict[str, Any]:
        """列出项目可用库部件（经 Tapir GetAvailableLibraryParts）。

        type_id 可选：Door/Window/Object/Lamp，不传则返回全部。
        返回 libraryParts（每项 guid/index/documentName/fileName/typeId）、
        skippedCount（读取失败数）、skippedSample（前 5 个失败项）。
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            data = _tapir.get_available_library_parts(type_id, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(data.get("libraryParts", [])),
                type_id=type_id, **data,
            )
        return safe(instance, _run)

    @mcp.tool()
    def get_subelements_of_hierarchical(
        guids: list[str], instance: str | None = None
    ) -> dict[str, Any]:
        """取层级构件的子构件（经 Tapir GetSubelementsOfHierarchicalElements）。

        guids：幕墙/楼梯等父构件 GUID 列表。
        返回 subelements（按类型分组，如 cWallSegments/cWallFrames/
        stairTreads/stairRisers/stairStructures）。
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            data = _tapir.get_subelements_of_hierarchical(guids, instance)
            sub = data.get("subelements", [])
            total = sum(len(v) for v in sub if isinstance(v, list))
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=total, subelements=sub,
            )
        return safe(instance, _run)

    @mcp.tool()
    def get_collisions(
        guids1: list[str], guids2: list[str],
        volume_tolerance: float = 0.001,
        perform_surface_check: bool = False,
        surface_tolerance: float = 0.001,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """碰撞检查（经 Tapir GetCollisions）。

        guids1/guids2：两组元素 GUID 列表。
        volume_tolerance：体积容差（m³，默认 0.001）。
        perform_surface_check：是否启用表面碰撞检查。
        surface_tolerance：表面容差（m²，默认 0.001）。
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            data = _tapir.get_collisions(
                [{"elementId": {"guid": g}} for g in guids1],
                [{"elementId": {"guid": g}} for g in guids2],
                volume_tolerance, perform_surface_check, surface_tolerance,
                instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(data.get("collisions", [])), **data,
            )
        return safe(instance, _run)

    @mcp.tool()
    def list_favorites(
        element_type: str, instance: str | None = None,
    ) -> dict[str, Any]:
        """列指定构件类型的收藏夹名称（经 Tapir GetFavoritesByType）。"""
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            rows = _tapir.get_favorites_by_type(element_type, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(rows), element_type=element_type, items=rows,
            )
        return safe(instance, _run)

    @mcp.tool()
    def get_ifc_ids(
        guids: list[str], instance: str | None = None,
    ) -> dict[str, Any]:
        """读元素的 IFC ID（经 Tapir GetIFCIdsOfElements）。"""
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            rows = _tapir.get_ifc_ids_of_elements(guids, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(rows), items=rows,
            )
        return safe(instance, _run)

    @mcp.tool()
    def get_elements_by_ifc_ids(
        ifc_ids: list[str], instance: str | None = None,
    ) -> dict[str, Any]:
        """按 IFC ID 反查元素（经 Tapir GetElementsByIFCIds）。"""
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            rows = _tapir.get_elements_by_ifc_ids(ifc_ids, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(rows), items=rows,
            )
        return safe(instance, _run)

    @mcp.tool()
    def get_ifc_properties(
        guids: list[str], instance: str | None = None,
    ) -> dict[str, Any]:
        """读元素的 IFC 属性（经 Tapir GetIFCPropertiesOfElements）。"""
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            rows = _tapir.get_ifc_properties_of_elements(guids, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(rows), items=rows,
            )
        return safe(instance, _run)

    @mcp.tool()
    def get_zone_boundaries(
        zone_guids: list[str], instance: str | None = None,
    ) -> dict[str, Any]:
        """读 Zone 边界（经 Tapir GetZoneBoundaries）。zone_guids 为 Zone GUID 列表。"""
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            data = _tapir.get_zone_boundaries(zone_guids, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(data.get("zoneBoundaries", [])), **data,
            )
        return safe(instance, _run)

    @mcp.tool()
    def get_connected_elements(
        guids: list[str],
        connected_element_type: str,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """查宿主元素上挂的指定类型子元素（经 Tapir GetConnectedElements）。

        如墙上的门窗（connected_element_type="Window"/"Door"）、
        幕墙的框架/面板、楼梯的踏踢板、栏杆的立柱/扶手。
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            rows = _tapir.get_connected_elements(
                guids, connected_element_type, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(rows), connected_elements=rows,
            )
        return safe(instance, _run)

    @mcp.tool()
    def get_element_preview_image(
        guid: str,
        image_type: str = "3D",
        image_format: str = "png",
        width: int = 128,
        height: int = 128,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """取元素预览图（经 Tapir GetElementPreviewImage），返回 base64 字符串。

        image_type: 2D / Section / 3D；image_format: png / jpg。
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            b64 = _tapir.get_element_preview_image(
                guid, image_type, image_format, width, height, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=1 if b64 else 0,
                data={"guid": guid, "image_type": image_type,
                      "format": image_format, "preview_image": b64},
            )
        return safe(instance, _run)

    @mcp.tool()
    def get_building_material_properties(
        attribute_ids: list[str], instance: str | None = None,
    ) -> dict[str, Any]:
        """读建筑材料物理性能（经 Tapir GetBuildingMaterialPhysicalProperties）。

        attribute_ids 为建筑材料 attributeId.guid 列表。
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            rows = _tapir.get_building_material_physical_properties(
                attribute_ids, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(rows), properties=rows,
            )
        return safe(instance, _run)

    @mcp.tool()
    def get_layer_combination_details(
        attribute_ids: list[str], instance: str | None = None,
    ) -> dict[str, Any]:
        """读图层组合详情（经 Tapir GetLayerCombinations）。

        attribute_ids 为图层组合 attributeId.guid 列表（先用
        list_attributes("LayerCombination") 取全部组合的 id）。
        返回每层显隐/锁定/线框/交叉组。
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            rows = _tapir.get_layer_combinations(attribute_ids, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(rows), layer_combinations=rows,
            )
        return safe(instance, _run)

    @mcp.tool()
    def list_stories(instance: str | None = None) -> dict[str, Any]:
        """列楼层：索引、标高、楼层名（经 Tapir GetStories）。"""
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            data = _tapir.get_stories(instance)
            stories = data.get("stories", [])
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(stories) if isinstance(stories, list) else 0, **data,
            )
        return safe(instance, _run)

    @mcp.tool()
    def get_gdl_parameters(
        guids: list[str], instance: str | None = None,
    ) -> dict[str, Any]:
        """读元素 GDL 参数（经 Tapir GetGDLParametersOfElements）。

        配合 set_gdl_parameters 写入前先读当前值。
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            rows = _tapir.get_gdl_parameters_of_elements(guids, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(rows), gdl_parameters=rows,
            )
        return safe(instance, _run)

    @mcp.tool()
    def list_mep_elements(
        element_types: list[str] | None = None,
        domains: list[str] | None = None,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """列项目全部 MEP 元素（经 Tapir GetMEPElements）。

        element_types 可选（如 Duct/Pipe/CableCarrier）；domains 可选
        （Mechanical/Electrical/Piping/FireFighting/Telecom）。
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            rows = _tapir.get_mep_elements(element_types, domains, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(rows), elements=rows,
            )
        return safe(instance, _run)

    @mcp.tool()
    def get_mep_routing_elements(
        guids: list[str], instance: str | None = None,
    ) -> dict[str, Any]:
        """读 MEP 管线详情（经 Tapir GetMEPRoutingElements）。

        普通查询接口看不到 MEP 构建内容时用这个。
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            rows = _tapir.get_mep_routing_elements(guids, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(rows), routing_elements=rows,
            )
        return safe(instance, _run)

    @mcp.tool()
    def get_mep_ports(
        guids: list[str], instance: str | None = None,
    ) -> dict[str, Any]:
        """读 MEP 元素端口：位置/形状/尺寸/连接状态（经 Tapir GetMEPPorts，AC28+）。"""
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            rows = _tapir.get_mep_ports(guids, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(rows), element_ports=rows,
            )
        return safe(instance, _run)

    @mcp.tool()
    def get_element_relations(
        guids: list[str],
        other_element_type: str | None = None,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """读元素关系（宿主/连接等，经 Tapir GetRelationsOfElements）。

        other_element_type 可选，只返回与该类型元素的关系。
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            rows = _tapir.get_relations_of_elements(
                guids, other_element_type, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(rows), relations=rows,
            )
        return safe(instance, _run)

    @mcp.tool()
    def list_all_properties(instance: str | None = None) -> dict[str, Any]:
        """列全部属性定义+属性组（经 Tapir GetAllProperties）。

        算量时属性名拼错排查用。
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            data = _tapir.get_all_properties(instance)
            props = data.get("properties", [])
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(props) if isinstance(props, list) else 0, **data,
            )
        return safe(instance, _run)

    @mcp.tool()
    def get_calculation_units(instance: str | None = None) -> dict[str, Any]:
        """读项目计算单位：长度/面积/体积的单位与精度（经 Tapir GetCalculationUnits）。"""
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            data = _tapir.get_calculation_units(instance)
            return success_result(
                instance=info.instance_id, project=info.project_name, **data,
            )
        return safe(instance, _run)

    @mcp.tool()
    def get_navigator_tree(
        map_id: str = "ProjectMap",
        publisher_set_name: str | None = None,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """读导航树（经 Tapir GetNavigatorItemTree）。

        map_id: ProjectMap / PublicViewMap / LayoutBook / PublisherSets。
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            data = _tapir.get_navigator_item_tree(
                map_id, publisher_set_name, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name, **data,
            )
        return safe(instance, _run)

    @mcp.tool()
    def get_element_geometry_info(
        element_guids: list[str], instance: str | None = None
    ) -> dict[str, Any]:
        """读取元素完整几何：长度/高度/厚度、起止点坐标、高程、包围盒。

        经 Tapir GetDetailsOfElements 取数，geometry_service 规整输出。
        坐标：x/y 为项目坐标，z 相对元素所在楼层。
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            details = _tapir.get_details_of_elements(element_guids, instance)
            items = geometry_service.summarize_all(details)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(items), items=items,
            )
        return safe(instance, _run)

    #: 默认工程量清单（BuiltIn 属性名，AC29 真机验证可读）
    DEFAULT_QUANTITIES = [
        "General_3DLength", "General_Height", "General_Width",
        "General_Thickness", "General_GrossVolume", "General_NetVolume",
        "General_SurfaceArea", "General_Area",
        "General_GrossTopSurfaceArea", "General_NetTopSurfaceArea",
        "General_GrossEdgeSurfaceArea", "General_NetEdgeSurfaceArea",
        "General_GrossBottomSurfaceArea", "General_NetBottomSurfaceArea",
    ]

    @mcp.tool()
    def get_element_quantities(
        element_guids: list[str],
        quantities: list[str] | None = None,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """批量读取工程量（面积/体积/长度等），带单位标注。算量取数入口。

        quantities 缺省用默认 14 项通用量；也可传任意 BuiltIn 属性名，
        如 Wall_ReferenceLineLength、Slab_GrossTopSurfaceArea、
        Zone_CalculatedArea 等。元素不支持某项时该项 value 为 None。
        单位按项目默认公制：长度 m、面积 m²、体积 m³。
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            names = quantities or DEFAULT_QUANTITIES
            data = property_service.service.get_quantities(
                element_guids, names, instance
            )
            items = [
                {"guid": g, "quantities": data[g]} for g in element_guids
            ]
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(items), items=items,
            )
        return safe(instance, _run)

    @mcp.tool()
    def get_property_definition(
        property_name: str, instance: str | None = None
    ) -> dict[str, Any]:
        """查属性定义：类型/单位/分组/描述；枚举属性附带全部可选项。"""
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            d = property_service.service.get_property_definition(
                property_name, instance)
            if d is None:
                raise errors.PropertyNotFoundError(
                    property_name, instance,
                    suggestions=property_service.service
                    .suggest_property_names(property_name, instance),
                )
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=1, data=d,
            )
        return safe(instance, _run)

    @mcp.tool()
    def aggregate_quantities(
        quantity: str | None = None,
        group_by: list[str] | None = None,
        element_type: str | None = None,
        stories: list[int] | None = None,
        filters: list[dict] | None = None,
        instance: str | None = None,
        classification: str | None = None,
        formula: str | None = None,
        formula_name: str | None = None,
    ) -> dict[str, Any]:
        """按维度分组汇总工程量（count/sum/avg）。算量出表入口。

        quantity 为 BuiltIn 量名（如 General_NetVolume）；或用 formula 自定义公式
        （如 "General_NetVolume * 1.03"），需配 formula_name（结果列名）。
        group_by 维度："type"（构件类型）、"story"（楼层）或属性名，可多选，
        缺省 ["type"]。例：按楼层汇总墙的净体积 →
        quantity="General_NetVolume", element_type="Wall", group_by=["story"]
        classification：只统计挂了该分类项的元素，如 "标准墙"。
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            data = aggregate_service.service.aggregate(
                quantity, group_by, element_type, stories, filters, instance,
                classification, formula=formula, formula_name=formula_name,
            )
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(data["rows"]),
                data={"unit": data["unit"], "groups": data["rows"],
                      "flat": data["flat_rows"]},
            )
        return safe(instance, _run)

    @mcp.tool()
    def list_quantity_templates() -> dict[str, Any]:
        """列出所有预设算量规则模板名及说明，供 aggregate_by_template 调用。"""
        def _run() -> dict[str, Any]:
            items = [
                {"name": k, "description": v["description"]}
                for k, v in aggregate_service.QUANTITY_TEMPLATES.items()
            ]
            return success_result(count=len(items), items=items)
        return safe(None, _run)

    @mcp.tool()
    def aggregate_by_template(
        template_name: str, instance: str | None = None,
    ) -> dict[str, Any]:
        """按预设模板算量（如 concrete_volume 混凝土体积、wall_area 墙体面积）。
        用 list_quantity_templates 查看全部模板。"""
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            data = aggregate_service.service.aggregate_by_template(
                template_name, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(data["rows"]),
                data={"template": data["template"],
                      "description": data["description"],
                      "unit": data["unit"],
                      "groups": data["rows"],
                      "flat": data["flat_rows"]},
            )
        return safe(instance, _run)

    @mcp.tool()
    def aggregate_by_custom_template(
        template: dict[str, Any],
        instance: str | None = None,
    ) -> dict[str, Any]:
        """按自定义模板算量。

        template 须含（三选一）：
        - quantity（单量 str）或 quantities（多量 list）或 formula（规则公式 str）
        - group_by：分组维度（type/story/属性名）
        - element_types：构件类型列表（如 ["Wall","Column"]）
        可选：description / waste_factor（损耗系数）
              formula_name（公式结果列名）/ formula_unit（公式结果单位）

        示例1（普通量）：
        {"quantity":"General_NetVolume","group_by":["story"],
         "element_types":["Wall"],"waste_factor":0.05,
         "description":"墙体体积含5%损耗"}
        示例2（公式法）：
        {"formula":"General_NetVolume * 1.03","formula_name":"含损耗体积",
         "formula_unit":"m³","group_by":["story"],
         "element_types":["Wall","Column"],"description":"混凝土含3%损耗"}
        """
        def _run() -> dict[str, Any]:
            data = aggregate_service.service.aggregate_by_custom_template(
                template, instance)
            return success_result(
                instance=instance,
                count=len(data["rows"]),
                data={"rows": data["rows"],
                      "flat_rows": data["flat_rows"],
                      "unit" if "unit" in data else "units":
                          data.get("unit", data.get("units")),
                      "template": data["template"],
                      "description": data["description"]},
            )
        return safe(instance, _run)

    @mcp.tool()
    def estimate_cost(
        rows: list[dict[str, Any]],
        project_name: str,
        labor_price: float = 130.0,
        price_overrides: dict[str, float] | None = None,
        fee_overrides: dict[str, float] | None = None,
        region: str | None = None,
    ) -> dict[str, Any]:
        """成本估算细算：由算量 flat_rows 出人材机分解概算表。

        rows 传 aggregate_quantities / aggregate_by_template 的 flat 数组
        （须含 code/code_name/code_unit 列，即模板 with_code=true）。
        细算路径：消耗量 × 市场价 → 人工/材料/机械费 → 管理费/利润/税金 → 总价。
        labor_price 工日单价（默认 130 元）；price_overrides 覆盖材料市场价
        （如 {"C30 预拌混凝土": 400.0}）；fee_overrides 覆盖费率
        （如 {"management_fee": 0.06, "profit": 0.05, "tax": 0.09}）。
        未覆盖消耗量的条目不定价并在 notes 提示。
        """
        def _run() -> dict[str, Any]:
            from cost_estimator import estimate_from_flat_rows
            table = estimate_from_flat_rows(
                rows, project_name, labor_price, price_overrides,
                fee_overrides, region)
            s = table["summary"]
            return success_result(
                count=len(table["items"]),
                data={
                    "summary": s,
                    "items": table["items"],
                    "notes": table["notes"],
                    "fee_rates": table["fee_rates"],
                    "labor_price": table["labor_price"],
                    "region": table["region"],
                    "date": table["date"],
                },
            )
        return safe(None, _run)

    @mcp.tool()
    def export_table(
        rows: list[dict[str, Any]] | None = None,
        sheets: list[dict[str, Any]] | None = None,
        filename: str = "export",
        fmt: str = "csv",
        value_column: str | None = None,
        project_name: str | None = None,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """把算量结果导出为文件，返回路径。

        单表：传 rows（flat 数组），fmt 选 csv / xlsx / report，默认 csv。
        多表：传 sheets=[{"name":"表名","rows":[...]}, ...]，自动用 xlsx，
          一次写多张表到同一 Excel 文件。
        report：fmt=report 时按 GB 50500 工程量清单格式排版（标题/项目信息
          /表头/数据行/合计），rows 须含 code/code_name/code_unit 列
          （由模板 with_code=true 触发 aggregate 自动附加）；
          value_column 指定量值列名（缺省自动探测 sum/sum_xxx/formula_result）；
          project_name 写到报表项目信息行。
        filename 不含扩展名，存到项目同级 output 目录。
        """
        import os
        import time

        def _write_sheet(ws, sheet_rows: list[dict[str, Any]]) -> list[str]:
            """写一张表：表头+数据+加粗+列宽。返回列名列表。"""
            if not sheet_rows:
                return []
            fieldnames = list(sheet_rows[0].keys())
            ws.append(fieldnames)
            for row in sheet_rows:
                ws.append([row.get(k) for k in fieldnames])
            from openpyxl.styles import Font
            for cell in ws[1]:
                cell.font = Font(bold=True)
            for i, col in enumerate(ws.columns, 1):
                mx = max(len(str(c.value or "")) for c in col)
                ws.column_dimensions[ws.cell(1, i).column_letter].width = min(mx + 4, 40)
            return fieldnames

        def _run() -> dict[str, Any]:
            nonlocal fmt
            if sheets and fmt != "xlsx":
                fmt = "xlsx"  # 多表自动 xlsx
            if not rows and not sheets:
                raise errors.InvalidArgumentError(
                    "rows", "rows 和 sheets 均为空，无可导出数据")
            out_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "output")
            os.makedirs(out_dir, exist_ok=True)
            safe_name = "".join(
                c for c in filename if c.isalnum() or c in "-_") or "export"
            ts = time.strftime("%Y%m%d_%H%M%S")
            total_rows = 0
            columns: list[str] = []
            if fmt == "report":
                # GB 50500 工程量清单报表
                import report_service
                source_rows = rows or (sheets[0].get("rows", []) if sheets else [])
                path = report_service.build_report(
                    source_rows, value_column=value_column,
                    project_name=project_name, filename=safe_name,
                    out_dir=out_dir)
                total_rows = len(source_rows)
                columns = ["序号", "项目编码", "项目名称", "计量单位", "工程量"]
                return success_result(
                    instance=instance,
                    count=total_rows,
                    data={"file_path": path, "rows": total_rows,
                          "format": "report", "columns": columns,
                          "sheets": 1},
                )
            if fmt == "xlsx":
                from openpyxl import Workbook
                path = os.path.join(out_dir, f"{safe_name}_{ts}.xlsx")
                wb = Workbook()
                if sheets:
                    for i, sheet in enumerate(sheets):
                        ws = wb.active if i == 0 else wb.create_sheet()
                        ws.title = (sheet.get("name") or f"Sheet{i+1}")[:31]
                        sr = sheet.get("rows", [])
                        total_rows += len(sr)
                        if i == 0:
                            columns = _write_sheet(ws, sr)
                        else:
                            _write_sheet(ws, sr)
                else:
                    ws = wb.active
                    ws.title = safe_name[:31]
                    columns = _write_sheet(ws, rows)
                    total_rows = len(rows)
                wb.save(path)
            else:
                import csv
                path = os.path.join(out_dir, f"{safe_name}_{ts}.csv")
                columns = list(rows[0].keys())
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.DictWriter(f, fieldnames=columns)
                    w.writeheader()
                    w.writerows(rows)
                total_rows = len(rows)
            return success_result(
                instance=instance,
                count=total_rows,
                data={"file_path": path, "rows": total_rows,
                      "format": fmt, "columns": columns,
                      "sheets": len(sheets) if sheets else 1},
            )
        return safe(instance, _run)
