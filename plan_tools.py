"""计划辅助工具注册（V0.10，P2 图片识别主线起点）。

只做一件事：向 FastMCP 注册 lint_model_plan（离线校验建模计划）。
不连 ArchiCAD、不查通道能力，让 LLM 生成计划后可零成本迭代。
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from model_plan import ModelPlan
from schemas import success_result


def register(mcp: FastMCP, safe) -> None:
    """注册计划辅助工具。safe 为 server._safe（统一异常包装）。"""

    @mcp.tool()
    def lint_model_plan(plan: dict[str, Any]) -> dict[str, Any]:
        """离线校验建模计划，不连接 ArchiCAD。识图生成计划后先跑它自检。

        返回 ok=True + 构件统计（各类数量）；失败返回结构化错误
        （error_code/message 指出具体字段问题），修正后再调本工具。
        通道能力（如旧版 Tapir 不支持门窗）在 preview_create_plan 时才校验。
        """
        def _run() -> dict[str, Any]:
            model = ModelPlan.from_dict(plan)
            counts: dict[str, int] = {}
            for e in model.elements:
                counts[e.type] = counts.get(e.type, 0) + 1
            return success_result(count=len(model.elements),
                                  data={"ok": True, "types": counts})
        return safe(None, _run)
