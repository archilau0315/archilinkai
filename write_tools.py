"""P1 安全写入工具注册（V0.3 从 server.py 拆出，控制入口行数）。

只做一件事：向 FastMCP 注册 8 个写入工具。
通过 register(mcp, safe) 调用，复用 server 的统一异常包装。
所有写入工具都需 confirm=true 才真正执行。
"""

from __future__ import annotations

from typing import Any

import create_service
import gdl_service
import instance_manager
import operation_service
from mcp.server.fastmcp import FastMCP
from schemas import success_result
from tapir_adapter import adapter as _tapir


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
