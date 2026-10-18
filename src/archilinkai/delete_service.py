"""构件删除服务（V0.7）：删除计划 → 读回核对构件 → 通道删除 → 再读回确认。

只做调度，不直接拼命令：
- 计划解析/校验：delete_plan
- 能不能删（版本闸门）：ModelChannel.supports_delete
- 真正删除：ModelChannel.delete（整批一个结果）
- 删除前后核对：GetDetailsOfElements

安全沿用创建/修改链路：confirm=false 不删；删前核对项目身份与构件存在；
删后读回确认每个 GUID 已消失；全程记 operation 日志。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
import time

from archilinkai import audit_log
from archilinkai import instance_manager
from archilinkai.delete_plan import DeletePlan
from archilinkai.errors import (ChannelCapabilityError, ConfirmRequiredError,
                    InvalidArgumentError)
from archilinkai.schemas import OperationLog
from archilinkai.tapir_adapter import _to_dict, adapter as _tapir
from archilinkai.tapir_channel import channel as _default_channel

#: 删后核对发现"没删掉"时的最多尝试次数
MAX_DELETE_ATTEMPTS = 3


class DeleteService:
    """按删除计划删除已有构件的调度服务。"""

    def __init__(self, mgr=None, logger=None, channel=None) -> None:
        self._mgr = mgr or instance_manager.manager
        self._logger = logger or audit_log.logger
        self._channel = channel or _default_channel

    # --- 预览 -------------------------------------------------------------

    def preview(
        self, source: dict[str, Any], instance: str | None = None
    ) -> dict[str, Any]:
        """读回每个构件的类型/编号，列出将删除清单。不写入。"""
        plan = self._parse(source, instance)
        info = self._mgr.validate_instance(plan.instance)
        self._check_capability(plan)

        rows = self._read_rows(plan.guids, plan.instance)
        items: list[dict[str, Any]] = []
        missing: list[str] = []
        for i, guid in enumerate(plan.guids):
            row = rows.get(guid.lower())
            if not self._present(row):
                missing.append(guid)
                continue
            items.append({"index": i, "guid": guid,
                          "type": row.get("type"), "id": row.get("id")})
        result = {
            "instance": info.instance_id, "project": info.project_name,
            "item_count": len(items), "items": items,
            "risk": "删除后对话里无法恢复，ArchiCAD 中可按 Ctrl+Z 撤销",
        }
        if missing:
            result["warnings"] = [
                f"构件当前项目中读不到（可能已删除）：{g}" for g in missing
            ]
        return result

    # --- 执行 -------------------------------------------------------------

    def execute(
        self,
        source: dict[str, Any],
        confirm: bool = False,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """确认后删除并读回验证。confirm=false 抛 ConfirmRequiredError。"""
        tool = "delete_from_plan"
        if not confirm:
            raise ConfirmRequiredError(tool, instance)

        plan = self._parse(source, instance)
        info = self._mgr.validate_instance(plan.instance)
        # 先确认还是同一个项目，再逐个确认构件还在
        self._mgr.check_project_identity([], plan.instance)
        self._check_targets_exist(plan)
        self._check_capability(plan)

        operation_id = self._logger.generate_id()
        timestamp = datetime.now().isoformat(timespec="seconds")

        # 删除偶发"返回成功但没删掉"，删后核对、没删掉重试，以最终读回为准
        rows, attempts, last = self._delete_until_gone(plan)
        verify = self._verify_from_rows(plan, rows)

        deleted = [
            {"guid": g, "gone": g.lower() in verify["gone_guids"]}
            for g in plan.guids
        ]
        failed = (
            [] if verify["status"] == "success"
            else [{"error": last.error, "attempts": attempts}]
        )

        self._record(operation_id, timestamp, info, tool,
                     len(plan.guids), deleted, failed, verify["status"])

        return {
            "operation_id": operation_id,
            "instance": info.instance_id,
            "project": info.project_name,
            "attempts": attempts,
            "verify": {k: v for k, v in verify.items() if k != "gone_guids"},
            "deleted": deleted,
            "failed": failed,
        }

    def _delete_until_gone(
        self, plan: DeletePlan
    ) -> tuple[dict[str, dict[str, Any]], int, Any]:
        """反复删除仍存在的构件，直到全消失或用完次数。

        返回（最终读回 rows，实际尝试次数，最后一次通道结果）。
        """
        last = None
        rows: dict[str, dict[str, Any]] = {}
        for attempt in range(1, MAX_DELETE_ATTEMPTS + 1):
            pending = (
                list(plan.guids) if attempt == 1
                else [g for g in plan.guids
                      if self._present(rows.get(g.lower()))]
            )
            last = self._channel.delete(pending, plan.instance)
            time.sleep(0.3 * attempt)
            rows = self._read_rows(plan.guids, plan.instance)
            if not any(self._present(rows.get(g.lower()))
                       for g in plan.guids):
                return rows, attempt, last
        return rows, MAX_DELETE_ATTEMPTS, last

    # --- 内部：计划与能力 -------------------------------------------------

    @staticmethod
    def _parse(
        source: dict[str, Any], instance: str | None
    ) -> DeletePlan:
        plan = DeletePlan.from_dict(source)
        if instance is not None:
            plan.instance = instance
        return plan

    def _check_capability(self, plan: DeletePlan) -> None:
        """版本闸门：DeleteElements 必须可用。"""
        if not self._channel.supports_delete(plan.instance):
            raise ChannelCapabilityError(
                self._channel.name, "DeleteElements",
                hint="当前 Tapir 版本不支持删除构件",
                instance=plan.instance,
            )

    def _check_targets_exist(self, plan: DeletePlan) -> None:
        """构件存在性预检：直接读 rows 判断。"""
        rows = self._read_rows(plan.guids, plan.instance)
        missing = [
            g for g in plan.guids
            if not self._present(rows.get(g.lower()))
        ]
        if missing:
            raise InvalidArgumentError(
                "guids", missing,
                "这些构件当前项目中不存在（可能已删除），无法删除",
            )

    # --- 内部：读回与验证 -------------------------------------------------

    @staticmethod
    def _present(row: Any) -> bool:
        """构件是否真实存在：删除后 Tapir 会返回 details 为空的占位项，
        必须看 details 是否非空，不能只看返回项。"""
        return bool(row) and bool(row.get("details"))

    def _read_rows(
        self, guids: list[str], instance: str | None
    ) -> dict[str, dict[str, Any]]:
        """批量读构件，按请求顺序对应 GUID，保留顶层 type/id/details。

        返回项的 id 是元素编号（如 SW-001）不是 GUID，不能拿它做键；
        Tapir 保证返回顺序与请求一致。
        """
        params = {
            "elements": [
                {"elementId": {"guid": str(g)}} for g in guids
            ],
            "fields": ["type", "id", "details"],
        }
        raw = _to_dict(_tapir.execute(
            "GetDetailsOfElements", params, instance
        ))
        out: dict[str, dict[str, Any]] = {}
        if not isinstance(raw, dict):
            return out
        for guid, item in zip(guids, raw.get("detailsOfElements", [])):
            if isinstance(item, dict):
                out[str(guid).lower()] = item
        return out

    def _verify_from_rows(
        self, plan: DeletePlan, rows: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        """按最终读回 rows 判断：GUID 的 details 读不到即已删除。"""
        gone = {
            g.lower() for g in plan.guids
            if not self._present(rows.get(g.lower()))
        }
        requested = len(plan.guids)
        verified = len(gone)
        status = ("success" if verified == requested
                  else "partial_success" if verified else "failed")
        return {"requested": requested, "verified": verified,
                "failed": requested - verified, "status": status,
                "gone_guids": gone}

    # --- 内部：日志 -------------------------------------------------------

    def _record(self, operation_id, timestamp, info, tool, total,
                deleted, failed, verify_status) -> None:
        self._logger.log(OperationLog(
            operation_id=operation_id, timestamp=timestamp,
            instance=info.instance_id, project=info.project_name, tool=tool,
            target_count=total,
            after={"deleted": deleted, "failed": failed},
            execute_status="success" if deleted else "failed",
            verify_status=verify_status,
        ))


# 模块级单例
service = DeleteService()
