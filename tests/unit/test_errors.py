"""errors.py 单元测试：异常 to_dict、错误码、兜底函数。"""

import pytest

from errors import (
    ArchicadMCPError,
    ConfirmRequiredError,
    ErrorCode,
    InstanceNotFoundError,
    InstanceDisconnectedError,
    MultipleInstancesError,
    NoInstanceAvailableError,
    PropertyNotFoundError,
    PropertyTypeMismatchError,
    PropertyTypeUnknownError,
    TapirCommandFailedError,
    TapirNotLoadedError,
    VerifyFailedError,
    to_error_dict,
)


def test_error_code_count():
    """V0.3 定义的错误码应齐全。"""
    assert len(ErrorCode) >= 22


def test_base_to_dict_contains_required_fields():
    err = ArchicadMCPError(
        code=ErrorCode.INTERNAL_ERROR,
        message="测试错误",
        instance="ac29-1",
        retryable=True,
    )
    d = err.to_dict()
    assert d["status"] == "error"
    assert d["error_code"] == "INTERNAL_ERROR"
    assert d["message"] == "测试错误"
    assert d["instance"] == "ac29-1"
    assert d["retryable"] is True
    # details 不应进入 LLM 上下文
    assert "details" not in d


def test_instance_not_found_lists_available():
    err = InstanceNotFoundError("ac29-9", ["ac28-1", "ac29-1"])
    d = err.to_dict()
    assert d["error_code"] == "INSTANCE_NOT_FOUND"
    assert "ac28-1" in d["message"]
    assert d["retryable"] is True


def test_instance_disconnected_retryable():
    err = InstanceDisconnectedError("ac29-1")
    assert err.code == ErrorCode.INSTANCE_DISCONNECTED
    assert err.to_dict()["retryable"] is True


def test_multiple_instances_not_retryable():
    err = MultipleInstancesError(["ac28-1", "ac29-1"])
    d = err.to_dict()
    assert d["error_code"] == "MULTIPLE_INSTANCES"
    assert d["retryable"] is False


def test_no_instance_available_has_troubleshooting():
    err = NoInstanceAvailableError()
    msg = err.to_dict()["message"]
    assert "ArchiCAD" in msg and "Tapir" in msg


def test_tapir_not_loaded_carries_command():
    err = TapirNotLoadedError("ac29-1", "GetProjectInfo")
    assert err.to_dict()["error_code"] == "TAPIR_NOT_LOADED"
    assert "GetProjectInfo" in err.to_dict()["message"]


def test_tapir_command_failed():
    err = TapirCommandFailedError("ac29-1", "SetPropertyValuesOfElements", "boom")
    d = err.to_dict()
    assert d["error_code"] == "TAPIR_COMMAND_FAILED"
    assert "boom" in d["message"]


def test_property_not_found():
    err = PropertyNotFoundError("Fire Rating")
    assert "Fire Rating" in err.to_dict()["message"]


def test_property_type_mismatch():
    err = PropertyTypeMismatchError("Area", "float", "boolean")
    d = err.to_dict()
    assert d["error_code"] == "PROPERTY_TYPE_MISMATCH"


def test_property_type_unknown_rejects():
    err = PropertyTypeUnknownError("Mystery")
    assert err.to_dict()["retryable"] is False


def test_confirm_required_message():
    err = ConfirmRequiredError("set_element_properties")
    assert "confirm" in err.to_dict()["message"].lower()


def test_verify_failed_has_counts():
    err = VerifyFailedError("OP-20260923-00001", 36, 34)
    d = err.to_dict()
    assert d["error_code"] == "VERIFY_FAILED"
    assert d["retryable"] is True


def test_to_error_dict_wraps_unknown_exception():
    """非 ArchicadMCPError 的异常应兜底为 INTERNAL_ERROR。"""
    d = to_error_dict(ValueError("boom"), instance="ac29-1")
    assert d["status"] == "error"
    assert d["error_code"] == "INTERNAL_ERROR"
    assert d["instance"] == "ac29-1"
    assert "boom" in d["message"]


def test_to_error_dict_passes_through_custom():
    err = InstanceNotFoundError("ac29-9")
    d = to_error_dict(err, instance="ac28-1")
    assert d["error_code"] == "INSTANCE_NOT_FOUND"
    # 原异常已带 instance，不应被覆盖
    assert d["instance"] == "ac29-9"


def test_exception_is_catchable_as_exception():
    """子类可被 except Exception 捕获，便于 server._safe 统一处理。"""
    try:
        raise ConfirmRequiredError("set_gdl_parameters")
    except Exception as exc:
        assert isinstance(exc, ArchicadMCPError)
