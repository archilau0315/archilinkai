"""只读工具子模块：元信息 / 属性字典 / 楼层 / 预览图（V0.52 从 read_tools.py 拆出）。

只做一件事：向 FastMCP 注册元信息类只读工具。
通过 register(mcp, safe) 调用，复用 server 的统一异常包装。
"""

from __future__ import annotations

from typing import Any

from archilinkai import instance_manager
from mcp.server.fastmcp import FastMCP
from archilinkai.schemas import success_result
from archilinkai.tapir_adapter import _to_dict, adapter as _tapir


def register(mcp: FastMCP, safe) -> None:
    """注册元信息类只读工具。safe 为 server._safe（统一异常包装）。"""

    @mcp.tool()
    def list_instances() -> dict[str, Any]:
        """列出所有已连接的 ArchiCAD 实例：实例 ID、端口、版本、项目名。

        English: List all connected ArchiCAD instances: instance ID, port, version, project name.
        """
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
        """项目概览：元素总数、可用属性数量。

        English: Project overview: total element count and available property count.
        """
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
    def list_floors(instance: str | None = None) -> dict[str, Any]:
        """列出项目楼层（经 Tapir GetStories）。

        English: List project floors (via Tapir GetStories).
        """
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
        """列出项目可用的分类系统与分类项。

        English: List available classification systems and their items in the project.
        """
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

        English: List project attributes by type (via Tapir GetAttributes).
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

        English: List available library parts in the project (via Tapir GetAvailableLibraryParts).
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
    def list_favorites(
        element_type: str, instance: str | None = None,
    ) -> dict[str, Any]:
        """列指定构件类型的收藏夹名称（经 Tapir GetFavoritesByType）。

        English: List favorite names for a given element type (via Tapir GetFavoritesByType).
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            rows = _tapir.get_favorites_by_type(element_type, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(rows), element_type=element_type, items=rows,
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

        English: Read layer combination details (via Tapir GetLayerCombinations).
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
        """列楼层：索引、标高、楼层名（经 Tapir GetStories）。

        English: List stories: index, elevation, name (via Tapir GetStories).
        """
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
    def list_all_properties(instance: str | None = None) -> dict[str, Any]:
        """列全部属性定义+属性组（经 Tapir GetAllProperties）。

        算量时属性名拼错排查用。

        English: List all property definitions and groups (via Tapir GetAllProperties).
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
        """读项目计算单位：长度/面积/体积的单位与精度（经 Tapir GetCalculationUnits）。

        English: Read project calculation units: unit and precision for length/area/volume.
        """
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

        English: Read the navigator tree (via Tapir GetNavigatorItemTree).
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
    def get_building_material_properties(
        attribute_ids: list[str], instance: str | None = None,
    ) -> dict[str, Any]:
        """读建筑材料物理性能（经 Tapir GetBuildingMaterialPhysicalProperties）。

        attribute_ids 为建筑材料 attributeId.guid 列表。

        English: Read building material physical properties (via Tapir GetBuildingMaterialPhysicalProperties).
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

        English: Get an element preview image (via Tapir GetElementPreviewImage); returns a base64 string.
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
