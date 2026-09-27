"""统一异常与错误码模块（V0.3 8.10）。

所有模块抛出的异常都继承自 ArchicadMCPError，并通过 to_dict() 输出
V0.3 8.7 规定的结构化错误：
    {
      "status": "error",
      "error_code": "INSTANCE_NOT_FOUND",
      "message": "...",
      "instance": "ac29-1",
      "retryable": true
    }
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    """统一错误码。str 枚举便于序列化与日志检索。"""

    # 实例相关
    INSTANCE_NOT_FOUND = "INSTANCE_NOT_FOUND"
    INSTANCE_DISCONNECTED = "INSTANCE_DISCONNECTED"
    INSTANCE_VALIDATION_FAILED = "INSTANCE_VALIDATION_FAILED"
    MULTIPLE_INSTANCES = "MULTIPLE_INSTANCES"
    NO_INSTANCE_AVAILABLE = "NO_INSTANCE_AVAILABLE"

    # Tapir 相关
    TAPIR_NOT_LOADED = "TAPIR_NOT_LOADED"
    TAPIR_COMMAND_FAILED = "TAPIR_COMMAND_FAILED"

    # 属性相关
    PROPERTY_NOT_FOUND = "PROPERTY_NOT_FOUND"
    PROPERTY_TYPE_MISMATCH = "PROPERTY_TYPE_MISMATCH"
    PROPERTY_VALUE_INVALID = "PROPERTY_VALUE_INVALID"
    PROPERTY_TYPE_UNKNOWN = "PROPERTY_TYPE_UNKNOWN"

    # 元素相关
    ELEMENT_NOT_FOUND = "ELEMENT_NOT_FOUND"
    ELEMENT_TYPE_INVALID = "ELEMENT_TYPE_INVALID"

    # 分类相关
    CLASSIFICATION_NOT_FOUND = "CLASSIFICATION_NOT_FOUND"

    # 查询相关
    QUERY_FAILED = "QUERY_FAILED"
    PAGINATION_INVALID = "PAGINATION_INVALID"

    # 写操作相关
    CONFIRM_REQUIRED = "CONFIRM_REQUIRED"
    PROJECT_IDENTITY_CHANGED = "PROJECT_IDENTITY_CHANGED"
    VERIFY_FAILED = "VERIFY_FAILED"
    OPERATION_FAILED = "OPERATION_FAILED"
    PREVIEW_FAILED = "PREVIEW_FAILED"

    # 通用
    INTERNAL_ERROR = "INTERNAL_ERROR"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"

    # 建模通道相关
    CHANNEL_CAPABILITY_UNSUPPORTED = "CHANNEL_CAPABILITY_UNSUPPORTED"


@dataclass
class ArchicadMCPError(Exception):
    """所有自定义异常的基类。

    Attributes:
        code: ErrorCode 枚举值
        message: 给用户/LLM 看的可读说明
        instance: 关联的实例 ID（可选，便于多实例定位）
        retryable: 是否建议重试（如断线重连后可重试）
        details: 额外调试信息（不展示给 LLM）
    """

    code: ErrorCode = ErrorCode.INTERNAL_ERROR
    message: str = "内部错误"
    instance: str | None = None
    retryable: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # 让 Exception 能拿到 message，便于 traceback 与日志
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """转 V0.3 8.7 结构化错误返回。details 不进 LLM 上下文。"""
        result: dict[str, Any] = {
            "status": "error",
            "error_code": self.code.value,
            "message": self.message,
            "retryable": self.retryable,
        }
        if self.instance is not None:
            result["instance"] = self.instance
        return result


# --- 便捷子类：按错误类别抛出，调用方代码更清晰 ------------------------------


class InstanceError(ArchicadMCPError):
    """实例相关错误基类。"""


class InstanceNotFoundError(InstanceError):
    def __init__(self, instance: str | None, available: list[str] | None = None):
        avail = ", ".join(available) if available else "无"
        super().__init__(
            code=ErrorCode.INSTANCE_NOT_FOUND,
            message=f"没有找到实例 {instance or '<空>'}，当前可用：{avail}",
            instance=instance,
            retryable=True,
            details={"available": available or []},
        )


class InstanceDisconnectedError(InstanceError):
    def __init__(self, instance: str):
        super().__init__(
            code=ErrorCode.INSTANCE_DISCONNECTED,
            message=f"实例 {instance} 已断开连接，请先 refresh_instances 重连",
            instance=instance,
            retryable=True,
        )


class MultipleInstancesError(InstanceError):
    def __init__(self, instances: list[str]):
        super().__init__(
            code=ErrorCode.MULTIPLE_INSTANCES,
            message=f"检测到多个实例 {instances}，请通过 instance 参数指定",
            retryable=False,
            details={"instances": instances},
        )


class NoInstanceAvailableError(InstanceError):
    def __init__(self):
        super().__init__(
            code=ErrorCode.NO_INSTANCE_AVAILABLE,
            message=(
                "未发现任何 ArchiCAD 实例。请确认：1) ArchiCAD 已启动并打开项目；"
                "2) 工作环境-连接端口已启用；3) Tapir Add-On 已按版本安装。"
            ),
            retryable=True,
        )


class TapirError(ArchicadMCPError):
    """Tapir 相关错误基类。"""


class TapirNotLoadedError(TapirError):
    def __init__(self, instance: str | None, command: str = ""):
        super().__init__(
            code=ErrorCode.TAPIR_NOT_LOADED,
            message=(
                f"Tapir Add-On 未加载，无法执行命令 {command or '<unknown>'}。"
                "请通过 选项 → Add-On 管理器 加载对应版本 Tapir。"
            ),
            instance=instance,
            retryable=False,
            details={"command": command},
        )


class TapirCommandFailedError(TapirError):
    def __init__(self, instance: str | None, command: str, reason: str = ""):
        super().__init__(
            code=ErrorCode.TAPIR_COMMAND_FAILED,
            message=f"Tapir 命令 {command} 执行失败{': ' + reason if reason else ''}",
            instance=instance,
            retryable=False,
            details={"command": command, "reason": reason},
        )


class PropertyError(ArchicadMCPError):
    """属性相关错误基类。"""


class PropertyNotFoundError(PropertyError):
    def __init__(self, name: str, instance: str | None = None):
        super().__init__(
            code=ErrorCode.PROPERTY_NOT_FOUND,
            message=f"未找到属性 {name}，请确认属性名拼写与当前项目一致",
            instance=instance,
            retryable=False,
            details={"property_name": name},
        )


class PropertyTypeMismatchError(PropertyError):
    def __init__(self, name: str, expected: str, got: str, instance: str | None = None):
        super().__init__(
            code=ErrorCode.PROPERTY_TYPE_MISMATCH,
            message=f"属性 {name} 期望类型 {expected}，实际传入 {got}",
            instance=instance,
            retryable=False,
            details={"property_name": name, "expected": expected, "got": got},
        )


class PropertyTypeUnknownError(PropertyError):
    def __init__(self, name: str, instance: str | None = None):
        super().__init__(
            code=ErrorCode.PROPERTY_TYPE_UNKNOWN,
            message=f"属性 {name} 类型无法确定，拒绝执行以避免错误转换",
            instance=instance,
            retryable=False,
            details={"property_name": name},
        )


class ElementNotFoundError(ArchicadMCPError):
    def __init__(self, guids: list[str], instance: str | None = None):
        super().__init__(
            code=ErrorCode.ELEMENT_NOT_FOUND,
            message=f"未找到元素 {guids}",
            instance=instance,
            retryable=False,
            details={"guids": guids},
        )


class ClassificationNotFoundError(ArchicadMCPError):
    """分类系统或分类项按名称找不到。"""

    def __init__(self, name: str, kind: str = "分类项",
                 instance: str | None = None):
        super().__init__(
            code=ErrorCode.CLASSIFICATION_NOT_FOUND,
            message=f"未找到{kind} {name}，请确认名称与当前项目一致",
            instance=instance,
            retryable=False,
            details={"name": name, "kind": kind},
        )


class ConfirmRequiredError(ArchicadMCPError):
    """写操作未带 confirm=true。"""

    def __init__(self, tool: str, instance: str | None = None):
        super().__init__(
            code=ErrorCode.CONFIRM_REQUIRED,
            message=f"操作未执行：{tool} 需要将 confirm 设为 true 以确认写入",
            instance=instance,
            retryable=False,
            details={"tool": tool},
        )


class ProjectIdentityChangedError(ArchicadMCPError):
    """写入前发现项目身份（文件路径）与基线不一致。"""

    def __init__(self, instance: str, baseline: Any, current: Any):
        super().__init__(
            code=ErrorCode.PROJECT_IDENTITY_CHANGED,
            message=(
                f"实例 {instance} 的项目已变化（可能被关闭、另存为或切换）。"
                "为避免写错项目，操作已拦截；如确认要在当前项目继续，"
                "请先调用 refresh_instances 再重试。"
            ),
            instance=instance,
            retryable=True,
            details={"baseline": baseline, "current": current},
        )


class VerifyFailedError(ArchicadMCPError):
    def __init__(
        self,
        operation_id: str,
        requested: int,
        verified: int,
        instance: str | None = None,
    ):
        super().__init__(
            code=ErrorCode.VERIFY_FAILED,
            message=(
                f"操作 {operation_id} 验证失败：请求 {requested}，"
                f"实际验证通过 {verified}，请检查未通过元素"
            ),
            instance=instance,
            retryable=True,
            details={
                "operation_id": operation_id,
                "requested": requested,
                "verified": verified,
            },
        )


class PaginationInvalidError(ArchicadMCPError):
    def __init__(self, reason: str):
        super().__init__(
            code=ErrorCode.PAGINATION_INVALID,
            message=f"分页参数无效：{reason}",
            retryable=False,
        )


class InvalidArgumentError(ArchicadMCPError):
    def __init__(self, name: str, value: Any, reason: str = ""):
        super().__init__(
            code=ErrorCode.INVALID_ARGUMENT,
            message=f"参数 {name} 无效：{value}{': ' + reason if reason else ''}",
            retryable=False,
            details={"name": name, "value": str(value)},
        )


class ChannelCapabilityError(ArchicadMCPError):
    """目标实例的通道不支持创建某类构件（如旧版 Tapir 没有 CreateWindows）。"""

    def __init__(self, channel: str, element_type: str, hint: str = "",
                 instance: str | None = None):
        super().__init__(
            code=ErrorCode.CHANNEL_CAPABILITY_UNSUPPORTED,
            message=(
                f"当前{channel}通道不支持创建 {element_type}"
                f"{': ' + hint if hint else ''}。未创建任何元素。"
            ),
            instance=instance,
            retryable=False,
            details={"channel": channel, "element_type": element_type},
        )


def to_error_dict(exc: Exception, instance: str | None = None) -> dict[str, Any]:
    """把任意异常转成结构化错误 dict，兜底非 ArchicadMCPError 的异常。"""
    if isinstance(exc, ArchicadMCPError):
        out = exc.to_dict()
        if instance is not None and "instance" not in out:
            out["instance"] = instance
        return out
    # 未预期的异常
    return {
        "status": "error",
        "error_code": ErrorCode.INTERNAL_ERROR.value,
        "message": f"未预期的错误：{exc}",
        "instance": instance,
        "retryable": False,
    }
