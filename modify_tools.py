"""构件修改工具注册（V0.4）。

两个工具：
- preview_modify_plan：读回当前值，列出每项 旧值→新值，不写入
- modify_from_plan：confirm=true 才真正修改，改完读回逐字段验证

注册模式与 read_tools/write_tools 一致：register(mcp, safe)。
"""

from __future__ import annotations

from modify_service import service


def register(mcp, safe) -> None:
    """向 FastMCP 注册构件修改工具。"""

    @mcp.tool()
    def preview_modify_plan(
        plan: dict, instance: str | None = None
    ) -> dict:
        """预览构件修改：读回当前值，逐项列出 旧值→新值。不写入。

        plan 形如：
        {"items": [
          {"type": "Wall", "guid": "...", "height": 4.0},
          {"type": "Slab", "guid": "...", "holes": [[{"x":1,"y":1},{"x":2,"y":1},{"x":2,"y":2}]]}
        ]}
        能改：墙（端点/高/厚）、柱（平移/高/截面）、门和窗（洞口/窗台）、
        板（标高/厚/开洞 holes）、屋顶（厚/檐出）。
        注意：屋顶开洞仅支持单坡屋顶创建时；多平面屋顶和既有屋顶暂不支持开洞。
        """
        return safe(instance, service.preview, plan, instance)

    @mcp.tool()
    def modify_from_plan(
        plan: dict, confirm: bool = False, instance: str | None = None
    ) -> dict:
        """按修改计划调整已有构件。

        必须 confirm=true 才真正执行；执行后自动读回逐字段验证，
        返回 modified/failed 明细和验证结果。改错了可在 ArchiCAD 里 Ctrl+Z。
        """
        return safe(instance, service.execute, plan, confirm, instance)
