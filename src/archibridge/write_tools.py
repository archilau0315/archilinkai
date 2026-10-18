"""P1 安全写入工具注册（V0.3 从 server.py 拆出，控制入口行数）。

只做一件事：向 FastMCP 注册 8 个写入工具。
通过 register(mcp, safe) 调用，复用 server 的统一异常包装。
所有写入工具都需 confirm=true 才真正执行。
"""

from __future__ import annotations

from typing import Any

from archibridge import create_service
from archibridge import gdl_service
from archibridge import instance_manager
from archibridge import operation_service
from mcp.server.fastmcp import FastMCP
from archibridge.schemas import success_result
from archibridge.tapir_adapter import adapter as _tapir


def register(mcp: FastMCP, safe) -> None:
    """注册写入工具。safe 为 server._safe（统一异常包装）。"""

    @mcp.tool()
    def preview_property_change(
        element_guids: list[str],
        property_name: str,
        value: Any,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """预览属性修改：当前值、目标值、不可改元素、风险。

        类型未知或不符时直接报错，不进入执行。
        """
        def _run() -> dict[str, Any]:
            preview = operation_service.operations.preview_property_change(
                element_guids, property_name, value, instance
            )
            info = _info(instance)
            return success_result(
                instance=info.instance_id if info else None,
                project=info.project_name if info else None,
                data=preview.to_dict(),
            )
        return safe(instance, _run)

    @mcp.tool()
    def set_element_properties(
        element_guids: list[str],
        property_name: str,
        value: Any,
        confirm: bool = False,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """批量设置元素属性值（走 Tapir）。

        confirm=true 时才执行；Tapir 写入内部已含撤销单元，Ctrl+Z 可撤销。
        完成后自动 Verify 并返回 operation_id。
        """
        def _run() -> dict[str, Any]:
            return operation_service.operations.execute_property_change(
                element_guids, property_name, value, confirm, instance
            )
        return safe(instance, _run)

    @mcp.tool()
    def set_gdl_parameters(
        element_guids: list[str],
        parameter_name: str,
        value: Any,
        confirm: bool = False,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """批量修改 GDL 对象参数（L1）。

        confirm=true 时才执行；Tapir 写入可撤销。
        """
        def _run() -> dict[str, Any]:
            return gdl_service.service.set_parameters(
                element_guids, parameter_name, value, confirm, instance
            )
        return safe(instance, _run)

    @mcp.tool()
    def preview_classification(
        element_guids: list[str],
        item_name: str,
        system_name: str | None = None,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """预览分类挂接：目标分类、各元素当前分类、风险。不写入。"""
        def _run() -> dict[str, Any]:
            preview = operation_service.operations.preview_classification_change(
                element_guids, item_name, system_name, instance
            )
            info = _info(instance)
            return success_result(
                instance=info.instance_id if info else None,
                project=info.project_name if info else None,
                data=preview,
            )
        return safe(instance, _run)

    @mcp.tool()
    def attach_classification(
        element_guids: list[str],
        item_name: str,
        system_name: str | None = None,
        confirm: bool = False,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """批量给元素挂分类项（如把墙挂到"标准墙"）。

        item_name 为分类树里的项名称（精确匹配，可挂子项）；
        system_name 为分类系统名，项目只有一个系统时可省略。
        confirm=false 只读校验不入库；confirm=true 执行并自动验证（Ctrl+Z 可撤销）。
        """
        def _run() -> dict[str, Any]:
            return operation_service.operations.execute_classification_change(
                element_guids, item_name, system_name, confirm, instance
            )
        return safe(instance, _run)

    @mcp.tool()
    def highlight_elements(
        element_guids: list[str], instance: str | None = None
    ) -> dict[str, Any]:
        """高亮指定元素（经 Tapir HighlightElements）。"""
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            n = len(element_guids)
            # Tapir 实测需颜色配置：elements + highlightedColors
            # + wireframe3D + nonHighlightedColor，颜色为 RGBA（0-255）
            params = {
                "elements": [
                    {"elementId": {"guid": str(g)}} for g in element_guids
                ],
                "highlightedColors": [[50, 255, 100, 100] for _ in range(n)],
                "wireframe3D": True,
                "nonHighlightedColor": [0, 0, 255, 128],
            }
            _tapir.execute("HighlightElements", params, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=n,
                data={"message": f"已高亮 {n} 个元素。"},
            )
        return safe(instance, _run)

    @mcp.tool()
    def create_layers(
        layer_data: list[dict[str, Any]],
        overwrite_existing: bool = False,
        confirm: bool = False,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """创建或覆盖图层（经 Tapir CreateLayers）。

        layer_data 每项至少含 name，可选 isHidden/isLocked/isWireframe/intersectionGroupNr。
        confirm=true 时才执行；overwrite_existing=true 时同名图层会被覆盖。
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            if not confirm:
                return success_result(
                    instance=info.instance_id, project=info.project_name,
                    count=len(layer_data),
                    data={"message": f"预览：将创建/覆盖 {len(layer_data)} 个图层。",
                          "layer_data": layer_data, "overwrite_existing": overwrite_existing},
                )
            result = _tapir.create_layers(layer_data, overwrite_existing, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(layer_data),
                data={"message": f"已创建/覆盖 {len(layer_data)} 个图层。", "result": result},
            )
        return safe(instance, _run)

    @mcp.tool()
    def delete_attributes(
        attributes_to_delete: list[dict[str, Any]],
        confirm: bool = False,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """删除属性（经 Tapir DeleteAttributes）。

        attributes_to_delete 每项含 attributeType + attributeId。
        confirm=true 时才执行。
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            if not confirm:
                return success_result(
                    instance=info.instance_id, project=info.project_name,
                    count=len(attributes_to_delete),
                    data={"message": f"预览：将删除 {len(attributes_to_delete)} 个属性。",
                          "attributes_to_delete": attributes_to_delete},
                )
            result = _tapir.delete_attributes(attributes_to_delete, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(attributes_to_delete),
                data={"message": f"已删除 {len(attributes_to_delete)} 个属性。", "result": result},
            )
        return safe(instance, _run)

    @mcp.tool()
    def apply_favorites(
        favorites_to_apply: list[dict[str, Any]],
        apply_settings: bool = True,
        apply_classifications: bool = True,
        apply_categories: bool = True,
        apply_properties: bool = True,
        confirm: bool = False,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """把收藏夹应用到已有元素（经 Tapir ApplyFavoritesToElements）。

        favorites_to_apply 每项含 elementId + favorite（收藏夹名称）。
        只改设置类参数，不改几何。confirm=true 时才执行。
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            if not confirm:
                return success_result(
                    instance=info.instance_id, project=info.project_name,
                    count=len(favorites_to_apply),
                    data={"message": f"预览：将应用 {len(favorites_to_apply)} 个收藏夹。",
                          "favorites_to_apply": favorites_to_apply},
                )
            result = _tapir.apply_favorites_to_elements(
                favorites_to_apply, apply_settings, apply_classifications,
                apply_categories, apply_properties, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(favorites_to_apply),
                data={"message": f"已应用 {len(favorites_to_apply)} 个收藏夹。", "result": result},
            )
        return safe(instance, _run)

    @mcp.tool()
    def set_element_details(
        elements_with_details: list[dict[str, Any]],
        confirm: bool = False,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """改元素楼层/图层/绘制顺序等（经 Tapir SetDetailsOfElements）。

        elements_with_details 每项含 elementId + details（floorIndex/layerIndex/drawIndex）。
        confirm=true 时才执行。
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            if not confirm:
                return success_result(
                    instance=info.instance_id, project=info.project_name,
                    count=len(elements_with_details),
                    data={"message": f"预览：将修改 {len(elements_with_details)} 个元素的详情。",
                          "elements_with_details": elements_with_details},
                )
            result = _tapir.set_details_of_elements(elements_with_details, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(elements_with_details),
                data={"message": f"已修改 {len(elements_with_details)} 个元素的详情。", "result": result},
            )
        return safe(instance, _run)

    @mcp.tool()
    def update_zones(
        keep_stamp_position: bool = True,
        undo_top_trim: bool = False,
        undo_bottom_trim: bool = False,
        confirm: bool = False,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """重算全部 Zone 的几何/标签/关联元素（经 Tapir UpdateZones）。confirm=true 时才执行。"""
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            if not confirm:
                return success_result(
                    instance=info.instance_id, project=info.project_name,
                    data={"message": "预览：将重算全部 Zone 的几何/标签/关联元素。",
                          "keep_stamp_position": keep_stamp_position,
                          "undo_top_trim": undo_top_trim,
                          "undo_bottom_trim": undo_bottom_trim},
                )
            result = _tapir.update_zones(
                keep_stamp_position, undo_top_trim, undo_bottom_trim, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                data={"message": "已重算全部 Zone。", "result": result},
            )
        return safe(instance, _run)

    @mcp.tool()
    def move_elements(
        element_guids: list[str],
        dx: float,
        dy: float,
        dz: float = 0.0,
        copy: bool = False,
        confirm: bool = False,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """按向量批量移动元素（经 Tapir MoveElements）。

        dx/dy/dz 为移动向量（米）；copy=true 时移动副本（原元素保留）。
        confirm=true 时才执行。
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            vec = {"x": dx, "y": dy, "z": dz}
            if not confirm:
                return success_result(
                    instance=info.instance_id, project=info.project_name,
                    count=len(element_guids),
                    data={"message": f"预览：将移动 {len(element_guids)} 个元素。",
                          "move_vector": vec, "copy": copy,
                          "element_guids": element_guids},
                )
            payload = [
                {"elementId": {"guid": g}, "moveVector": vec, "copy": copy}
                for g in element_guids
            ]
            result = _tapir.move_elements(payload, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(element_guids),
                data={"message": f"已移动 {len(element_guids)} 个元素。",
                      "move_vector": vec, "copy": copy, "result": result},
            )
        return safe(instance, _run)

    @mcp.tool()
    def rotate_elements(
        element_guids: list[str],
        origin: dict[str, float],
        begin_point: dict[str, float],
        end_point: dict[str, float],
        copy: bool = False,
        confirm: bool = False,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """绕参考点批量旋转元素（经 Tapir RotateElements）。

        origin 为旋转中心，begin_point→end_point 定义旋转弧（均含 x/y）。
        copy=true 时旋转副本。confirm=true 时才执行。
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            rot = {"beginPoint": begin_point, "endPoint": end_point,
                   "origin": origin}
            if not confirm:
                return success_result(
                    instance=info.instance_id, project=info.project_name,
                    count=len(element_guids),
                    data={"message": f"预览：将旋转 {len(element_guids)} 个元素。",
                          "rotation": rot, "copy": copy,
                          "element_guids": element_guids},
                )
            payload = [
                {"elementId": {"guid": g}, "rotation": rot, "copy": copy}
                for g in element_guids
            ]
            result = _tapir.rotate_elements(payload, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(element_guids),
                data={"message": f"已旋转 {len(element_guids)} 个元素。",
                      "rotation": rot, "copy": copy, "result": result},
            )
        return safe(instance, _run)

    @mcp.tool()
    def create_layer_combinations(
        layer_combination_data: list[dict[str, Any]],
        overwrite_existing: bool = False,
        confirm: bool = False,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """创建或覆盖图层组合（经 Tapir CreateLayerCombinations）。

        layer_combination_data 每项含 name + layers；layers 每项含
        attributeId（图层 guid）+ isHidden/isLocked/isWireframe/intersectionGroupNr。
        confirm=true 时才执行；overwrite_existing=true 时同名组合会被覆盖。
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            if not confirm:
                return success_result(
                    instance=info.instance_id, project=info.project_name,
                    count=len(layer_combination_data),
                    data={"message": f"预览：将创建/覆盖 {len(layer_combination_data)} 个图层组合。",
                          "layer_combination_data": layer_combination_data,
                          "overwrite_existing": overwrite_existing},
                )
            result = _tapir.create_layer_combinations(
                layer_combination_data, overwrite_existing, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(layer_combination_data),
                data={"message": f"已创建/覆盖 {len(layer_combination_data)} 个图层组合。",
                      "result": result},
            )
        return safe(instance, _run)

    @mcp.tool()
    def preview_model_plan(
        plan: dict[str, Any], instance: str | None = None
    ) -> dict[str, Any]:
        """预览建模计划：要建哪些构件、数量、墙总长、逐构件明细。不创建。

        计划格式（单位米）：
        {"elements":[
          {"type":"Wall","start":{"x":0,"y":0},"end":{"x":6,"y":0}},
          {"type":"Column","x":0,"y":0},
          {"type":"Beam","start":{"x":0,"y":0},"end":{"x":6,"y":0},"z":3.0},
          {"type":"Slab","polygon":[{"x":0,"y":0},{"x":6,"y":0},{"x":6,"y":4},{"x":0,"y":4}],
           "holes":[[{"x":2,"y":1},{"x":4,"y":1},{"x":4,"y":3},{"x":2,"y":3}]]},
          {"type":"Window","wall":0,"offset":3.0},
          {"type":"Door","wall":"已有墙GUID","offset":1.0},
          {"type":"Stair","start":{"x":0,"y":0},"end":{"x":4,"y":0},"z":0},
          {"type":"Stair","path":[{"x":0,"y":0},{"x":4,"y":0},{"x":4,"y":3}],"z":0},
          {"type":"Roof","polygon":[{"x":0,"y":0},{"x":6,"y":0},{"x":6,"y":4}],"slope":30,
           "holes":[[{"x":2,"y":1},{"x":4,"y":1},{"x":4,"y":3},{"x":2,"y":3}]]},
          {"type":"Morph","position":{"x":0,"y":0,"z":0},"size":{"x":1,"y":1,"z":1}}
        ]}
        门、窗的 wall：填数字=挂在计划里第几面墙（如 0），
        填字符串=挂在项目中已有墙的 GUID。门窗只支持直墙。
        Slab/Roof 可选 holes 开洞列表，每个洞是多边形顶点列表；
        多平面屋顶不支持 holes（会报错）。
        Stair=楼梯：start+end=直梯；path（≥2点列表）=L形/多段折线梯；
        可给 steps 踏步数。Roof=屋顶（给 slope 度=单坡，
        转轴默认多边形第1边，可用 pivot 覆盖；不给=多平面）；
        Morph=变形体方块（任意形状暂不支持）。
        默认值：墙高 3m 厚 0.2m；柱高 3m；梁截面 0.2×0.3m 顶标高 0；
        板顶标高 0 厚 0.2m；窗洞口 1.2×1.5m 窗台 0.9m；
        门洞口 1.0×2.1m 门槛 0；门窗默认距墙起点 1m；
        楼梯总高 3m 梯宽 1.2m；屋顶底标高 0 厚 0.3m；
        变形体默认 1m 方块。均可覆盖。
        通道不支持某构件时（如旧版 Tapir）此步即拦截。
        """
        return safe(
            instance,
            lambda: create_service.service.preview(plan, instance),
        )

    @mcp.tool()
    def create_from_plan(
        plan: dict[str, Any],
        confirm: bool = False,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """按建模计划创建构件：confirm=false 不创建；true 时创建并读回验证。

        计划格式同 preview_model_plan。创建走可撤销命令，AC 中 Ctrl+Z 可撤销。
        返回 operation_id、已创建构件（含 GUID）、失败项和验证结果。
        """
        return safe(
            instance,
            lambda: create_service.service.execute(plan, confirm, instance),
        )


def _info(instance: str | None):
    """取实例信息用于结果填充（不抛异常给上层工具）。"""
    try:
        return instance_manager.manager.get_info(instance)
    except Exception:
        return None
