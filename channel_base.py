"""建模通道抽象层（V1.0）。

把"业务建模计划"和"具体用谁执行"隔开：
- 上层（create_service）只认 ModelChannel 接口，不关心是 Tapir 还是未来的官方 MCP
- 新增通道时只需再写一个子类，上层业务逻辑一行不改

V1.0 已实现：tapir_channel.TapirChannel
预留：官方 MCP 通道、其它自动化通道
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class CreateResult:
    """单个构件的创建结果（按请求顺序对应计划中的元素）。"""

    ok: bool
    guid: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"ok": self.ok}
        if self.guid is not None:
            out["guid"] = self.guid
        if self.error is not None:
            out["error"] = self.error
        return out


class ModelChannel(ABC):
    """建模通道的统一接口。

    元素类型用业务名（与建模计划一致）："Wall"、"Column" 等，
    各通道自己负责把业务名翻译成自己的命令名。
    """

    #: 通道展示名，如 "Tapir 1.5.9"
    name: str = "abstract"

    @abstractmethod
    def get_version(self, instance: str | None = None) -> str:
        """返回通道版本号（无法获取时返回 'unknown'）。"""

    @abstractmethod
    def supports(self, element_type: str, instance: str | None = None) -> bool:
        """该实例上能否创建此类构件。只读，不写入。"""

    def check_supports(
        self, element_type: str, instance: str | None = None
    ) -> None:
        """不支持时直接抛 ChannelCapabilityError；支持则通过。"""
        from errors import ChannelCapabilityError

        if not self.supports(element_type, instance):
            raise ChannelCapabilityError(
                self.name, element_type,
                hint=f"可升级通道后重试（当前版本 {self.get_version(instance)}）",
                instance=instance,
            )

    @abstractmethod
    def create(
        self,
        element_type: str,
        items: list[dict[str, Any]],
        instance: str | None = None,
    ) -> list[CreateResult]:
        """批量创建同一类构件。

        items 为已通过计划校验、字段已补默认值的元素 data；
        返回与 items 等长、同序的结果列表。
        """

    def exists(
        self,
        element_type: str,
        guid: str,
        instance: str | None = None,
    ) -> bool:
        """按通道自己的方式确认构件当前存在。默认不支持，通道按需覆盖。"""
        raise NotImplementedError(
            f"{self.name} 通道未实现存在性查询"
        )

    # --- 修改（V1.4）------------------------------------------------------

    def supports_modify(
        self, element_type: str, instance: str | None = None
    ) -> bool:
        """该实例上能否修改此类构件。默认不支持，通道按需覆盖。"""
        return False

    def modify(
        self,
        element_type: str,
        items: list[dict[str, Any]],
        instance: str | None = None,
    ) -> list[CreateResult]:
        """批量修改同一类构件。

        每个 item 形如 {"guid": "...", "changes": {字段: 新值}}，
        字段已通过修改计划校验；返回与 items 等长、同序的结果列表。
        基类默认不支持，通道按需覆盖。
        """
        raise NotImplementedError(
            f"{self.name} 通道未实现构件修改"
        )

    # --- 删除（V1.7）------------------------------------------------------

    def supports_delete(self, instance: str | None = None) -> bool:
        """该实例上能否删除构件。默认不支持，通道按需覆盖。"""
        return False

    def delete(
        self,
        guids: list[str],
        instance: str | None = None,
    ) -> CreateResult:
        """批量删除构件，返回整批一个结果。

        guids 已通过删除计划校验；通道返回整批成功/失败。
        基类默认不支持，通道按需覆盖。
        """
        raise NotImplementedError(
            f"{self.name} 通道未实现构件删除"
        )
