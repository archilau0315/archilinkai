"""operation_service.py 单元测试：_values_match + _verify_status 纯函数。

四阶段流程需 archicad 连接，留给集成测试；
分类挂接的 confirm 拦截不触发连接，可直接测。
"""

import pytest

from archilinkai.errors import ConfirmRequiredError
from archilinkai.operation_service import _values_match, _verify_status, operations


# --- _values_match ------------------------------------------------------


def test_match_equal_strings():
    assert _values_match("A", "A") is True


def test_match_case_insensitive():
    assert _values_match("A", "a") is True
    assert _values_match("Fire", "FIRE") is True


def test_match_numeric_string():
    assert _values_match("600", "600") is True
    assert _values_match(600, "600") is True


def test_match_strips_whitespace():
    assert _values_match("  A  ", "A") is True


def test_no_match_different():
    assert _values_match("A", "B") is False


def test_none_actual_returns_false():
    """实际值为 None（无可读值）必判失败，避免 None==字符串误匹配。"""
    assert _values_match(None, "A") is False


def test_none_expected_returns_false():
    assert _values_match("A", None) is False


def test_exception_returns_false():
    """无法比较时不抛异常，保守返回 False。"""

    class Weird:
        def __str__(self):
            raise RuntimeError("boom")

    assert _values_match(Weird(), "A") is False


# --- _verify_status ----------------------------------------------------


def test_verify_status_success():
    assert _verify_status(36, 36) == "success"


def test_verify_status_failed():
    assert _verify_status(36, 0) == "failed"


def test_verify_status_partial():
    assert _verify_status(36, 34) == "partial_success"


def test_verify_status_single_element_success():
    assert _verify_status(1, 1) == "success"


def test_verify_status_single_element_failed():
    assert _verify_status(1, 0) == "failed"


def test_verify_status_zero_requested():
    """请求数为 0 时视为 success（无操作）。"""
    assert _verify_status(0, 0) == "success"


# --- 分类挂接：confirm 拦截（不触发连接）-----------------------------------


def test_classification_confirm_required():
    """confirm=False 必须抛 ConfirmRequiredError，且在任何连接调用之前。"""
    with pytest.raises(ConfirmRequiredError) as exc_info:
        operations.execute_classification_change(
            ["00000000-0000-0000-0000-000000000000"],
            "标准墙", None, confirm=False, instance=None,
        )
    assert exc_info.value.code.value == "CONFIRM_REQUIRED"


def test_classification_confirm_required_details():
    """拦截异常应标注工具名，便于 LLM 引导用户确认。"""
    with pytest.raises(ConfirmRequiredError) as exc_info:
        operations.execute_classification_change(
            ["g"], "标准墙", None, confirm=False, instance=None,
        )
    assert exc_info.value.details["tool"] == "attach_classification"
