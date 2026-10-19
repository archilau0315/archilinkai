"""筑元智联 ArchiLinkAI MCP Server 入口（FastMCP）。

只做三件事：建 FastMCP、统一异常包装、启动时发现实例。
工具按层拆到独立模块注册：
- read_tools：只读查询/算量/估价
- write_tools：安全写入（均需 confirm）
- modify_tools：构件几何修改
- delete_tools：构件删除
- plan_tools：建模计划辅助
- diagnostic_tools：诊断运维
- code_review_tools：规范审查

启动时尝试 discover_instances；无真机时允许启动，工具调用时报错。
入口：archilinkai 命令 / python -m archilinkai / 根目录兼容薄壳 server.py。
"""

from __future__ import annotations

import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from archilinkai import __version__
from archilinkai import code_review_tools
from archilinkai import diagnostic_tools
from archilinkai import instance_manager
from archilinkai import material_report_tools
from archilinkai import modify_tools
from archilinkai import delete_tools
from archilinkai import plan_tools
from archilinkai import read_tools
from archilinkai import write_tools
from archilinkai.errors import ArchicadMCPError, to_error_dict

mcp = FastMCP("archilinkai")


def _safe(instance: str | None, fn, *args, **kwargs) -> dict[str, Any]:
    """统一异常包装：成功正常返回，失败返结构化错误。

    所有工具经此包装，保证 LLM 收到一致结构。
    """
    try:
        return fn(*args, **kwargs)
    except ArchicadMCPError as exc:
        return exc.to_dict()
    except Exception as exc:
        return to_error_dict(exc, instance)


# 注册四层工具（顺序无关，仅为可读性）
read_tools.register(mcp, _safe)
write_tools.register(mcp, _safe)
modify_tools.register(mcp, _safe)
delete_tools.register(mcp, _safe)
plan_tools.register(mcp, _safe)
diagnostic_tools.register(mcp, _safe)
code_review_tools.register(mcp, _safe)
material_report_tools.register(mcp, _safe)


# 启动时尝试发现实例；失败不阻塞启动（无真机时仍可启动 server）
# 注意：stdio 模式下 stdout 是 JSON-RPC 协议专用通道，日志必须走 stderr
def main() -> None:
    """启动入口：archilinkai 命令 / python -m archilinkai 共用。"""
    try:
        instance_manager.manager.discover_instances()
        print(f"[archilinkai v{__version__}] 已发现实例："
              f"{list(instance_manager.manager._registry)}",
              file=sys.stderr, flush=True)
    except Exception as exc:
        print(f"[archilinkai v{__version__}] 启动时未发现 ArchiCAD 实例：{exc}",
              file=sys.stderr, flush=True)
        print(f"[archilinkai v{__version__}] server 仍将启动，"
              "工具调用时将报告无可用实例。",
              file=sys.stderr, flush=True)
    mcp.run()


if __name__ == "__main__":
    main()
