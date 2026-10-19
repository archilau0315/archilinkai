"""P0 只读工具聚合入口（V0.52 拆分为 4 个子模块，控制单文件行数）。

只做一件事：按分组调用子模块的 register，向 FastMCP 注册全部只读工具。
子模块：read_tools_query / read_tools_meta / read_tools_interop /
read_tools_quantity。对外仍只暴露 register(mcp, safe)，调用方无需改动。
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from archilinkai import (
    read_tools_interop,
    read_tools_meta,
    read_tools_query,
    read_tools_quantity,
)


def register(mcp: FastMCP, safe) -> None:
    """注册全部只读工具（委托给 4 个子模块）。safe 为 server._safe。"""
    read_tools_query.register(mcp, safe)
    read_tools_meta.register(mcp, safe)
    read_tools_interop.register(mcp, safe)
    read_tools_quantity.register(mcp, safe)
