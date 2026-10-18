"""建模创建服务（V0.0）：计划 → 通道 → 模型。

只做调度，不直接拼命令：
- 计划解析/校验：model_plan
- 能不能建（版本闸门）：ModelChannel.supports
- 真正创建：ModelChannel.create
- 人看的预览：plan_preview

写入安全沿用 V0.3：confirm=false 不创建；创建前校验实例与项目身份；
创建后读回验证；全程记录 operation 日志。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from archibridge import audit_log
from archibridge import instance_manager
from archibridge import plan_preview
from archibridge.errors import ConfirmRequiredError
from archibridge.model_plan import HOST_BASED, ModelPlan, WALL_BASED
from archibridge.schemas import OperationLog
from archibridge.tapir_channel import channel as _default_channel


class CreateService:
    """按建模计划创建构件的调度服务。"""

    def __init__(self, mgr=None, logger=None, channel=None) -> None:
        self._mgr = mgr or instance_manager.manager
        self._logger = logger or audit_log.logger
        self._channel = channel or _default_channel

    # --- 解析与预览 -------------------------------------------------------

    def preview(
        self, source: dict[str, Any], instance: str | None = None
    ) -> dict[str, Any]:
        """解析计划 + 连接校验 + 版本闸门，返回预览。不写入。"""
        plan = self._parse(source, instance)
        info = self._mgr.validate_instance(plan.instance)
        self._check_capabilities(plan)
        version = self._channel.get_version(plan.instance)
        preview = plan_preview.build_preview(
            plan, self._channel.name, version
        )
        return {
            "instance": info.instance_id, "project": info.project_name,
            **preview,
        }

    # --- 执行 -------------------------------------------------------------

    def execute(
        self,
        source: dict[str, Any],
        confirm: bool = False,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """确认后创建并验证。confirm=false 抛 ConfirmRequiredError。"""
        tool = "create_from_plan"
        if not confirm:
            raise ConfirmRequiredError(tool, instance)

        plan = self._parse(source, instance)
        info = self._mgr.validate_instance(plan.instance)
        # 引用"已有宿主"的构件，先确认这些宿主当前项目里确实存在：
        # 门窗引用已有墙；独立洞口引用已有墙/板/梁/网面
        external_hosts = [
            e.data["wall"] for e in plan.elements
            if e.type in WALL_BASED and isinstance(e.data["wall"], str)
        ]
        external_hosts += [
            e.data["host"] for e in plan.elements
            if e.type == "Opening" and isinstance(e.data["host"], str)
        ]
        self._mgr.check_project_identity(external_hosts, plan.instance)
        self._check_capabilities(plan)

        operation_id = self._logger.generate_id()
        timestamp = datetime.now().isoformat(timespec="seconds")
        results = self._create_all(plan)

        created = [r for r in results if r["guid"]]
        failed = [r for r in results if not r["guid"]]
        verify = self._verify(created, plan)

        self._record(operation_id, timestamp, info, tool,
                     len(plan.elements), created, failed, verify["status"])

        return {
            "operation_id": operation_id,
            "instance": info.instance_id,
            "project": info.project_name,
            "verify": verify,
            "created": created,
            "failed": failed,
        }

    # --- 内部 -------------------------------------------------------------

    def _parse(
        self, source: dict[str, Any], instance: str | None
    ) -> ModelPlan:
        plan = ModelPlan.from_dict(source)
        # 工具参数 instance 优先于计划内字段
        if instance is not None:
            plan.instance = instance
        return plan

    def _check_capabilities(self, plan: ModelPlan) -> None:
        """版本闸门：计划用到的每类构件，通道必须支持，否则直接拦截。"""
        for element_type in plan.types_used():
            self._channel.check_supports(element_type, plan.instance)

    def _create_all(self, plan: ModelPlan) -> list[dict[str, Any]]:
        """两轮创建，再按计划序号汇总：

        1) 独立构件（墙/柱/梁/板/网面等）先建
        2) 门/窗/独立洞口后建，此时所引用的宿主已有真实 GUID
        """
        results: dict[int, dict[str, Any]] = {}

        # 第一轮：独立构件
        for element_type in plan.types_used():
            if element_type in HOST_BASED:
                continue
            group = [e for e in plan.elements if e.type == element_type]
            self._run_group(element_type, group,
                            [e.data for e in group], results, plan.instance)

        # 第二轮：门窗（墙引用→真实 GUID）
        for element_type in ("Door", "Window"):
            group = [e for e in plan.elements if e.type == element_type]
            if not group:
                continue
            items, blocked = self._build_opening_items(group, results)
            rows = self._channel.create(element_type, items, plan.instance)
            self._collect_rows(element_type, group, rows, results)
            # 因墙没建成而被跳过的门窗
            for element, error in blocked:
                results[element.index] = {
                    "index": element.index, "type": element_type,
                    "guid": None, "error": error,
                }

        # 第二轮补：独立洞口（宿主引用→真实 GUID）
        group = [e for e in plan.elements if e.type == "Opening"]
        if group:
            items, blocked = self._build_hosted_items(group, results)
            rows = self._channel.create("Opening", items, plan.instance)
            self._collect_rows("Opening", group, rows, results)
            for element, error in blocked:
                results[element.index] = {
                    "index": element.index, "type": "Opening",
                    "guid": None, "error": error,
                }

        return [results[i] for i in sorted(results)]

    def _build_opening_items(self, group, results):
        """构造传给通道的门窗参数；墙引用无效的门窗挑出来标记失败。"""
        items: list[dict[str, Any]] = []
        usable: list = []
        blocked: list[tuple] = []
        for element in group:
            wall_guid = self._resolve_wall(element.data["wall"], results)
            if wall_guid is None:
                blocked.append((element, "所引用的墙未创建成功，门窗无法挂接"))
                continue
            d = element.data
            items.append({
                "ownerWallGuid": wall_guid,
                "offset": d["offset"], "width": d["width"],
                "height": d["height"], "sill": d["sill"],
            })
            usable.append(element)
        # 用 usable 替换 group 的语义：rows 与 usable 等长
        group[:] = usable
        return items, blocked

    def _build_hosted_items(self, group, results):
        """构造独立洞口参数；宿主无效/未建成的洞口挑出来标记失败。"""
        items: list[dict[str, Any]] = []
        usable: list = []
        blocked: list[tuple] = []
        for element in group:
            host_guid = self._resolve_wall(element.data["host"], results)
            if host_guid is None:
                blocked.append((element, "所引用的宿主未创建成功，洞口无法开洞"))
                continue
            d = element.data
            items.append({
                "ownerGuid": host_guid,
                "basePoint": dict(d["basePoint"]),
                "width": d["width"], "height": d["height"],
            })
            usable.append(element)
        group[:] = usable  # rows 与 usable 等长
        return items, blocked

    @staticmethod
    def _resolve_wall(wall_ref, results) -> str | None:
        """序号引用→新墙 GUID（墙失败则 None）；GUID 引用→原样返回。"""
        if isinstance(wall_ref, str):
            return wall_ref
        row = results.get(wall_ref)
        return row["guid"] if row and row["guid"] else None

    def _run_group(self, element_type, group, items, results, instance):
        """通用：调通道创建一类构件并收集结果。"""
        rows = self._channel.create(element_type, items, instance)
        self._collect_rows(element_type, group, rows, results)

    @staticmethod
    def _collect_rows(element_type, group, rows, results):
        for element, row in zip(group, rows):
            results[element.index] = {
                "index": element.index, "type": element_type,
                "guid": row.guid, "error": row.error,
            }

    def _verify(self, created: list[dict[str, Any]], plan: ModelPlan) -> dict[str, Any]:
        """读回核对：新建构件当前都存在即通过。

        GUID 统一转小写比对：Tapir 返回大写，Python UUID 字符串为小写。
        MEP 路由在 GetAllElements 中不出现，走通道的 exists 专用查询。
        """
        if not created:
            return {"requested": 0, "verified": 0, "failed": 0,
                    "status": "failed"}

        existing = {
            str(e.elementId.guid).lower()
            for e in self._mgr.get_conn(plan.instance).commands.GetAllElements()
        }
        verified = 0
        for r in created:
            if r["type"] == "MEPRoute":
                ok = self._channel.exists("MEPRoute", r["guid"], plan.instance)
            else:
                ok = str(r["guid"]).lower() in existing
            verified += int(ok)

        requested = len(created)
        status = ("success" if verified == requested
                  else "partial_success" if verified else "failed")
        return {"requested": requested, "verified": verified,
                "failed": requested - verified, "status": status}

    def _record(self, operation_id, timestamp, info, tool, total,
                created, failed, verify_status) -> None:
        self._logger.log(OperationLog(
            operation_id=operation_id, timestamp=timestamp,
            instance=info.instance_id, project=info.project_name, tool=tool,
            target_count=total,
            after={"created": created, "failed": failed},
            execute_status="success" if created else "failed",
            verify_status=verify_status,
        ))


# 模块级单例
service = CreateService()
