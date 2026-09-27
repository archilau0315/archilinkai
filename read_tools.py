"""P0 只读工具注册（V0.3 从 server.py 拆出，控制入口行数）。

只做一件事：向 FastMCP 注册 10 个只读工具。
通过 register(mcp, safe) 调用，复用 server 的统一异常包装。
"""

from __future__ import annotations

from typing import Any

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
