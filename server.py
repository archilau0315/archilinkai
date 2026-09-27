"""ArchiCAD MCP Server 入口（FastMCP）。

只做三件事：建 FastMCP、统一异常包装、启动时发现实例。
工具按层拆到独立模块注册：
- read_tools：P0 只读（10 个）
- write_tools：P1 安全写入（8 个，均需 confirm）
- modify_tools：构件几何修改（2 个，V1.4）
- delete_tools：构件删除（2 个，V1.7）
- plan_tools：计划辅助（1 个，V1.10）
- diagnostic_tools：P2 诊断运维（4 个）

启动时尝试 discover_instances；无真机时允许启动，工具调用时报错。
"""

from __future__ import annotations

import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

import diagnostic_tools
import instance_manager
import modify_tools
import delete_tools
import plan_tools
import read_tools
import write_tools
from errors import ArchicadMCPError, to_error_dict

mcp = FastMCP("archicad-mcp")


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


# 启动时尝试发现实例；失败不阻塞启动（无真机时仍可启动 server）
# 注意：stdio 模式下 stdout 是 JSON-RPC 协议专用通道，日志必须走 stderr
try:
    instance_manager.manager.discover_instances()
    print(f"[archicad-mcp] 已发现实例："
          f"{list(instance_manager.manager._registry)}",
          file=sys.stderr, flush=True)
except Exception as exc:
    print(f"[archicad-mcp] 启动时未发现 ArchiCAD 实例：{exc}",
          file=sys.stderr, flush=True)
    print("[archicad-mcp] server 仍将启动，工具调用时将报告无可用实例。",
          file=sys.stderr, flush=True)


if __name__ == "__main__":
    mcp.run()
