"""集成测试公共装置：把注册到 FastMCP 的工具抓成普通可调用字典。

背景：工具函数定义在各 *_tools.register() 内部，模块外部拿不到；
这里用一个假 mcp 重新注册一遍，按函数名收集，测试里直接调用。
"""

from types import SimpleNamespace

import pytest

import server


class _Capturer:
    """伪装成 FastMCP：tool() 装饰器不注册，只把函数收进字典。"""

    def __init__(self) -> None:
        self.tools: dict = {}

    def tool(self):
        def deco(fn):
            self.tools[fn.__name__] = fn
            return fn
        return deco


def _collect() -> dict:
    cap = _Capturer()
    server.read_tools.register(cap, server._safe)
    server.write_tools.register(cap, server._safe)
    server.modify_tools.register(cap, server._safe)
    server.delete_tools.register(cap, server._safe)
    server.plan_tools.register(cap, server._safe)
    server.diagnostic_tools.register(cap, server._safe)
    return cap.tools


@pytest.fixture(scope="session")
def mcp_tools() -> SimpleNamespace:
    """全部工具的属性式访问：mcp_tools.get_elements_by_type(...)。"""
    return SimpleNamespace(**_collect())
