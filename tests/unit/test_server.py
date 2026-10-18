"""server.py 单元测试：_safe 包装逻辑 + 工具注册完整性。

_instance_info 已随 P1 工具迁入 write_tools._info，在对应测试段覆盖。
工具函数本体需 archicad 连接，留给集成测试；
这里只测异常→结构化错误、成功→透传的包装契约。
"""

import pytest

from archibridge import server
from archibridge import write_tools
from archibridge.errors import (
    ArchicadMCPError,
    ConfirmRequiredError,
    ErrorCode,
    InstanceNotFoundError,
)
from archibridge.schemas import success_result


# --- _safe：成功路径透传 -----------------------------------------------


def test_safe_success_passthrough():
    def fn():
        return success_result(instance="ac29-1", count=3)
    out = server._safe("ac29-1", fn)
    assert out["status"] == "success"
    assert out["instance"] == "ac29-1"
    assert out["count"] == 3


def test_safe_success_returns_plain_dict():
    """非 success_result 的 dict 也应原样透传。"""
    def fn():
        return {"custom": "value", "n": 1}
    out = server._safe(None, fn)
    assert out == {"custom": "value", "n": 1}


def test_safe_passes_args_kwargs():
    """_safe 应把 *args / **kwargs 透传给被包装函数。"""
    def fn(a, b, c=0):
        return success_result(data={"sum": a + b + c})
    out = server._safe(None, fn, 1, 2, c=3)
    assert out["data"] == {"sum": 6}


# --- _safe：自定义异常转结构化 ----------------------------------------


def test_safe_archicad_error_to_dict():
    def fn():
        raise InstanceNotFoundError("ac99-1", ["ac29-1"])
    out = server._safe("ac99-1", fn)
    assert out["status"] == "error"
    assert out["error_code"] == "INSTANCE_NOT_FOUND"
    assert out["instance"] == "ac99-1"
    assert out["retryable"] is True


def test_safe_confirm_required_error():
    def fn():
        raise ConfirmRequiredError("set_element_properties")
    out = server._safe("ac29-1", fn)
    assert out["error_code"] == "CONFIRM_REQUIRED"
    assert "confirm" in out["message"].lower()


def test_safe_custom_error_keeps_instance():
    """异常自带 instance 时 to_dict 不被覆盖。"""
    def fn():
        raise InstanceNotFoundError("ac99-1")
    out = server._safe("ac29-1", fn)  # 传入 ac29-1，但异常记的是 ac99-1
    assert out["instance"] == "ac99-1"


# --- _safe：非自定义异常兜底 ------------------------------------------


def test_safe_value_error_becomes_internal():
    def fn():
        raise ValueError("boom")
    out = server._safe("ac29-1", fn)
    assert out["status"] == "error"
    assert out["error_code"] == ErrorCode.INTERNAL_ERROR.value
    assert out["instance"] == "ac29-1"
    assert out["retryable"] is False
    assert "boom" in out["message"]


def test_safe_runtime_error_no_instance():
    def fn():
        raise RuntimeError("oops")
    out = server._safe(None, fn)
    assert out["error_code"] == ErrorCode.INTERNAL_ERROR.value
    assert "instance" not in out or out.get("instance") is None


# --- write_tools._info：不抛异常 --------------------------------------


def test_instance_info_returns_info_when_available():
    """单实例时 _info 返回 info。"""
    from unittest.mock import MagicMock

    from archibridge.schemas import InstanceInfo, InstanceStatus

    info = InstanceInfo(
        instance_id="ac29-1", port=19723, version=29, build=3000,
        language="zh",
        status=InstanceStatus.CONNECTED, project_name="p",
    )
    entry = MagicMock()
    entry.info = info
    mgr = write_tools.instance_manager.manager
    mgr._registry = {"ac29-1": entry}
    try:
        result = write_tools._info(None)
        assert result is info
    finally:
        mgr._registry = {}


def test_instance_info_returns_none_on_error():
    """无实例或异常时不抛，返回 None（避免污染工具主流程）。"""
    mgr = write_tools.instance_manager.manager
    old = mgr._registry
    mgr._registry = {}
    try:
        assert write_tools._info(None) is None
        assert write_tools._info("ac99-1") is None
    finally:
        mgr._registry = old


# --- 工具注册完整性 ----------------------------------------------------


def test_all_expected_tools_registered():
    """V0.3 8.11 工具分层应全部注册。"""
    tools = set(server.mcp._tool_manager._tools.keys())
    expected = {
        # P0 只读
        "list_instances", "project_summary", "get_selected_elements",
        "get_elements_by_type", "get_element_properties",
        "search_elements_by_criteria", "get_gdl_parameters",
        "list_floors", "get_classifications", "get_element_geometry_info",
        # P1 写入
        "preview_property_change", "set_element_properties",
        "set_gdl_parameters", "highlight_elements",
        # P2 诊断
        "refresh_instances", "validate_instance",
        "get_operation_status", "get_operation_log",
    }
    missing = expected - tools
    assert not missing, f"缺失工具：{missing}"
