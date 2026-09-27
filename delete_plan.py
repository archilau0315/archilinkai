"""构件删除计划模块（V1.7）。

只做一件事：描述并校验"删除计划 JSON"。
- 用 GUID 锁定要删的已有构件
- 校验只看计划自身，不连真机
- 真机是否存在由 delete_service 读回预检

计划示例：
{
  "instance": "ac29-1",
  "guids": ["A1B2...", "C3D4..."]
}

删除不可在对话里恢复（ArchiCAD 里可 Ctrl+Z），故同样走先预览后确认。
"""

from __future__ import annotations

from dataclasses import dataclass

from errors import InvalidArgumentError

#: 单次删除构件上限
MAX_GUIDS = 200


@dataclass
class DeletePlan:
    """一份删除计划。guids 已去重、非空。"""

    guids: list[str]
    instance: str | None = None

    @classmethod
    def from_dict(cls, source: dict) -> "DeletePlan":
        if not isinstance(source, dict):
            raise InvalidArgumentError("plan", type(source).__name__, "应为对象")
        raw = source.get("guids")
        if not isinstance(raw, list) or not raw:
            raise InvalidArgumentError("guids", raw, "至少包含 1 个构件 GUID")
        if len(raw) > MAX_GUIDS:
            raise InvalidArgumentError(
                "guids", f"{len(raw)}个",
                f"单次最多 {MAX_GUIDS} 个，请分批",
            )
        guids = [
            _check_guid(g, i) for i, g in enumerate(raw)
        ]
        # 去重但保留首次出现顺序
        guids = list(dict.fromkeys(guids))
        instance = source.get("instance")
        return cls(guids=guids, instance=instance or None)

    def to_dict(self) -> dict:
        return {"instance": self.instance, "guids": list(self.guids)}


def _check_guid(raw: object, index: int) -> str:
    """每项必须是非空字符串。"""
    if not isinstance(raw, str) or not raw.strip():
        raise InvalidArgumentError(
            f"guids[{index}]", raw, "应为非空的构件 GUID 字符串"
        )
    return raw.strip()
