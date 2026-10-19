"""只读工具子模块：互操作 / IFC / MEP / GDL / 关联（V0.52 拆出）。

只做一件事：向 FastMCP 注册互操作类只读工具。
通过 register(mcp, safe) 调用，复用 server 的统一异常包装。
"""

from __future__ import annotations

from typing import Any

from archilinkai import instance_manager
from mcp.server.fastmcp import FastMCP
from archilinkai.schemas import success_result
from archilinkai.tapir_adapter import adapter as _tapir


def register(mcp: FastMCP, safe) -> None:
    """注册互操作类只读工具。safe 为 server._safe（统一异常包装）。"""

    @mcp.tool()
    def get_subelements_of_hierarchical(
        guids: list[str], instance: str | None = None
    ) -> dict[str, Any]:
        """取层级构件的子构件（经 Tapir GetSubelementsOfHierarchicalElements）。

        guids：幕墙/楼梯等父构件 GUID 列表。
        返回 subelements（按类型分组，如 cWallSegments/cWallFrames/
        stairTreads/stairRisers/stairStructures）。

        English: Get subelements of hierarchical elements (via Tapir GetSubelementsOfHierarchicalElements).
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
    def get_ifc_ids(
        guids: list[str], instance: str | None = None,
    ) -> dict[str, Any]:
        """读元素的 IFC ID（经 Tapir GetIFCIdsOfElements）。

        English: Read elements' IFC IDs (via Tapir GetIFCIdsOfElements).
        """
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
        """按 IFC ID 反查元素（经 Tapir GetElementsByIFCIds）。

        English: Look up elements by IFC ID (via Tapir GetElementsByIFCIds).
        """
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
        """读元素的 IFC 属性（经 Tapir GetIFCPropertiesOfElements）。

        English: Read elements' IFC properties (via Tapir GetIFCPropertiesOfElements).
        """
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
        """读 Zone 边界（经 Tapir GetZoneBoundaries）。zone_guids 为 Zone GUID 列表。

        English: Read Zone boundaries (via Tapir GetZoneBoundaries).
        """
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

        English: Get child elements of a given type attached to host elements (via Tapir GetConnectedElements).
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
    def get_gdl_parameters(
        guids: list[str], instance: str | None = None,
    ) -> dict[str, Any]:
        """读元素 GDL 参数（经 Tapir GetGDLParametersOfElements）。

        配合 set_gdl_parameters 写入前先读当前值。

        English: Read elements' GDL parameters (via Tapir GetGDLParametersOfElements).
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

        English: List all MEP elements in the project (via Tapir GetMEPElements).
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

        English: Read MEP routing element details (via Tapir GetMEPRoutingElements).
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
        """读 MEP 元素端口：位置/形状/尺寸/连接状态（经 Tapir GetMEPPorts，AC28+）。

        English: Read MEP element ports: location/shape/size/connection state (via Tapir GetMEPPorts, AC28+).
        """
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

        English: Read element relations such as host/connection (via Tapir GetRelationsOfElements).
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
