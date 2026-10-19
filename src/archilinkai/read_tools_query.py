"""只读工具子模块：元素查询 / 属性读取 / 搜索 / 碰撞 / 几何（V0.52 拆出）。

只做一件事：向 FastMCP 注册元素查询类只读工具。
通过 register(mcp, safe) 调用，复用 server 的统一异常包装。
"""

from __future__ import annotations

from typing import Any

from archilinkai import geometry_service
from archilinkai import instance_manager
from archilinkai import property_service
from archilinkai import query_engine
from mcp.server.fastmcp import FastMCP
from archilinkai.schemas import Filter, Operator, QueryRequest, success_result
from archilinkai.tapir_adapter import adapter as _tapir


def register(mcp: FastMCP, safe) -> None:
    """注册元素查询类只读工具。safe 为 server._safe（统一异常包装）。"""

    @mcp.tool()
    def get_selected_elements(instance: str | None = None) -> dict[str, Any]:
        """读取当前选中元素：元素类型 + GUID。

        English: Read currently selected elements: element type + GUID.
        """
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
        """按元素类型获取元素列表（GUID + 类型）。

        English: Get elements by type (GUID + type).
        """
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
        """读取指定元素的指定属性。

        English: Read the specified properties of the given elements.
        """
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

        English: Combined search by type/story/property filters, with pagination.
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

        English: Collision check between two element GUID groups (via Tapir GetCollisions).
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
    def get_element_geometry_info(
        element_guids: list[str], instance: str | None = None
    ) -> dict[str, Any]:
        """读取元素完整几何：长度/高度/厚度、起止点坐标、高程、包围盒。

        经 Tapir GetDetailsOfElements 取数，geometry_service 规整输出。
        坐标：x/y 为项目坐标，z 相对元素所在楼层。

        English: Read full geometry: length/height/thickness, endpoints, elevation, bounding box.
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
