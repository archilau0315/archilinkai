"""构件删除工具注册（V0.7）。

两个工具：
- preview_delete_plan：读回构件类型/编号，列出将删除清单，不写入
- delete_from_plan：confirm=true 才真正删除，删完读回确认已消失

注册模式与其它工具模块一致：register(mcp, safe)。
"""

from __future__ import annotations

from archilinkai.delete_service import service


def register(mcp, safe) -> None:
    """向 FastMCP 注册构件删除工具。"""

    @mcp.tool()
    def preview_delete_plan(
        plan: dict, instance: str | None = None
    ) -> dict:
        """预览构件删除：读回每个构件的类型/编号，列出将删除清单。不写入。

        plan 形如：{"guids": ["GUID1", "GUID2"]}
        """
        return safe(instance, service.preview, plan, instance)

    @mcp.tool()
    def delete_from_plan(
        plan: dict, confirm: bool = False, instance: str | None = None
    ) -> dict:
        """按删除计划删除已有构件。

        必须 confirm=true 才真正执行；执行后自动读回确认每个构件已消失，
        返回 deleted/failed 明细和验证结果。删错可在 ArchiCAD 里 Ctrl+Z。
        """
        return safe(instance, service.execute, plan, confirm, instance)
