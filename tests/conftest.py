"""pytest 全局配置：把项目根加入 sys.path，便于测试导入模块。"""

import os
import sys

# 项目根 = conftest.py 所目录的上一级
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest


@pytest.fixture(autouse=True)
def _isolated_instance_registry():
    """每条测试前清空全局实例注册表（V0.65）。

    防止前序测试（如 test_cli 的 doctor 实例发现）留下的真实 AC 连接
    渗入后续测试：被模态弹窗阻塞的 AC 会让未 mock 的通道调用永久挂起。
    """
    from archilinkai import instance_manager as _im

    _im.manager._registry = {}
    yield
    _im.manager._registry = {}
