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
        quantity: str,
        group_by: list[str] | None = None,
        element_type: str | None = None,
        stories: list[int] | None = None,
        filters: list[dict] | None = None,
        instance: str | None = None,
        classification: str | None = None,
    ) -> dict[str, Any]:
        """按维度分组汇总工程量（count/sum/avg）。算量出表入口。

        quantity 为 BuiltIn 量名（如 General_NetVolume）；
        group_by 维度："type"（构件类型）、"story"（楼层）或属性名，可多选，
        缺省 ["type"]。例：按楼层汇总墙的净体积 →
        quantity="General_NetVolume", element_type="Wall", group_by=["story"]
        classification：只统计挂了该分类项的元素，如 "标准墙"。
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            data = aggregate_service.service.aggregate(
                quantity, group_by, element_type, stories, filters, instance,
                classification,
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

        template 须含：
        - quantity（单量 str）或 quantities（多量 list）
        - group_by：分组维度（type/story/属性名）
        - element_types：构件类型列表（如 ["Wall","Column"]）
        可选：description / waste_factor（损耗系数）

        示例：
        {"quantity":"General_NetVolume","group_by":["story"],
         "element_types":["Wall"],"waste_factor":0.05,
         "description":"墙体体积含5%损耗"}
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
    def export_table(
        rows: list[dict[str, Any]],
        filename: str = "export",
        fmt: str = "csv",
        instance: str | None = None,
    ) -> dict[str, Any]:
        """把算量结果（flat_rows）导出为文件，返回路径。

        rows 传 aggregate_quantities / aggregate_by_template 返回的 flat 数组。
        fmt 选 csv 或 xlsx（Excel），默认 csv。
        filename 不含扩展名，存到项目同级 output 目录。
        """
        import os
        import time

        def _run() -> dict[str, Any]:
            if not rows:
                raise errors.InvalidArgumentError("rows", "rows 为空，无可导出数据")
            out_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "output")
            os.makedirs(out_dir, exist_ok=True)
            safe_name = "".join(
                c for c in filename if c.isalnum() or c in "-_") or "export"
            ts = time.strftime("%Y%m%d_%H%M%S")
            fieldnames = list(rows[0].keys())
            if fmt == "xlsx":
                from openpyxl import Workbook
                path = os.path.join(out_dir, f"{safe_name}_{ts}.xlsx")
                wb = Workbook()
                ws = wb.active
                ws.title = safe_name[:31]
                ws.append(fieldnames)
                for row in rows:
                    ws.append([row.get(k) for k in fieldnames])
                # 表头加粗
                from openpyxl.styles import Font
                for cell in ws[1]:
                    cell.font = Font(bold=True)
                # 列宽自适应
                for i, col in enumerate(ws.columns, 1):
                    mx = max(len(str(c.value or "")) for c in col)
                    ws.column_dimensions[ws.cell(1, i).column_letter].width = min(mx + 4, 40)
                wb.save(path)
            else:
                import csv
                path = os.path.join(out_dir, f"{safe_name}_{ts}.csv")
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.DictWriter(f, fieldnames=fieldnames)
                    w.writeheader()
                    w.writerows(rows)
            return success_result(
                instance=instance,
                count=len(rows),
                data={"file_path": path, "rows": len(rows),
                      "format": fmt, "columns": fieldnames},
            )
        return safe(instance, _run)
