"""Preview / Confirm / Execute / Verify 四阶段操作服务（V0.3 8.5）。

所有可能修改模型的数据写入 Tool 统一采用四阶段机制：
    Preview → Confirm → Execute → Verify

- Preview：返回目标元素数、当前值、目标值、不可改元素、风险、预计修改数
- Confirm：写入默认 confirm=false，需明确 confirm=true 才执行
- Execute：调 Tapir 写入命令（Tapir 内部已包 ACAPI_CallUndoableCommand，可撤销）
- Verify：执行后重新读回，报告 requested/executed/verified/failed/status

不能仅根据 Tapir 调用未抛异常就认定模型已正确修改。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from archibridge import audit_log
from archibridge import instance_manager
from archibridge import property_service
from archibridge.errors import ClassificationNotFoundError, ConfirmRequiredError
from archibridge.schemas import OperationLog, PreviewResult, VerifyResult
from archibridge.tapir_adapter import adapter as _tapir


class OperationService:
    """写操作四阶段服务。"""

    def __init__(
        self,
        mgr: instance_manager.InstanceManager,
        logger: audit_log.OperationLogger,
    ) -> None:
        self._mgr = mgr
        self._logger = logger
        self._property = property_service.PropertyService(mgr)

    # --- Preview ----------------------------------------------------------

    def preview_property_change(
        self,
        element_guids: list[str],
        property_name: str,
        value: Any,
        instance: str | None = None,
    ) -> PreviewResult:
        """预览属性修改：取 before 值 + 校验目标值 + 风险提示。

        类型未知或不符时直接抛异常，不进入 Execute。
        """
        # 写操作前必须重新确认实例仍然有效（V0.3 8.3）
        info = self._mgr.validate_instance(instance)
        # 并核对项目身份（project_name 作为弱校验，project_identity 强校验待实测）
        return self._property.preview_change(
            element_guids, property_name, value, instance
        )

    # --- Execute + Verify -------------------------------------------------

    def execute_property_change(
        self,
        element_guids: list[str],
        property_name: str,
        value: Any,
        confirm: bool = False,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """执行属性修改并验证。

        confirm=false 时抛 ConfirmRequiredError，绝不执行。
        返回 {operation_id, verify, before, after}。
        """
        tool = "set_element_properties"
        if not confirm:
            raise ConfirmRequiredError(tool, instance)

        # 写操作前：实例有效 + 项目身份强校验（防写错项目）
        info = self._mgr.validate_instance(instance)
        self._mgr.check_project_identity(
            [str(g) for g in element_guids], instance
        )
        operation_id = self._logger.generate_id()
        timestamp = datetime.now().isoformat(timespec="seconds")

        # 取 before 值（来自 Preview 同源逻辑）
        preview = self._property.preview_change(
            element_guids, property_name, value, instance
        )
        before = {row["guid"]: row.get(property_name) for row in preview.before_values}

        # 构造写入参数 + 调用原生 API（绕开 Tapir 通道的格式不兼容问题）
        prop_id = self._property.get_property_id(property_name, instance)
        prop_type = self._property.get_property_type(property_name, instance)

        execute_status = "success"
        try:
            self._property.set_property_values(
                prop_type, preview.target_value,
                element_guids, prop_id, property_name, instance,
            )
        except Exception as exc:
            execute_status = "failed"
            self._record(
                operation_id, timestamp, info, tool,
                len(element_guids), property_name,
                before, {}, execute_status, None,
            )
            raise

        # Verify：重新读回，核对目标值
        verify = self._verify_property_change(
            element_guids, property_name, preview.target_value, instance
        )
        after = self._read_after_values(
            element_guids, property_name, instance
        )

        verify_status = verify.status
        self._record(
            operation_id, timestamp, info, tool,
            len(element_guids), property_name,
            before, after, execute_status, verify_status,
        )

        return {
            "operation_id": operation_id,
            "instance": info.instance_id,
            "project": info.project_name,
            "verify": verify.to_dict(),
            "before": before,
            "after": after,
        }

    # --- Verify 内部 -------------------------------------------------------

    def _verify_property_change(
        self,
        element_guids: list[str],
        property_name: str,
        expected_value: str,
        instance: str | None,
    ) -> VerifyResult:
        """重新读取受影响元素，报告 requested/executed/verified/failed/status。"""
        requested = len(element_guids)
        after_map = self._property.get_values(
            element_guids, [property_name], instance
        )
        verified = 0
        for guid in element_guids:
            actual = after_map.get(guid, {}).get(property_name)
            if _values_match(actual, expected_value):
                verified += 1
        failed = requested - verified
        status = _verify_status(requested, verified)
        return VerifyResult(
            requested=requested,
            executed=requested,
            verified=verified,
            failed=failed,
            status=status,
        )

    def _read_after_values(
        self, element_guids: list[str], property_name: str, instance: str | None
    ) -> dict[str, Any]:
        return self._property.get_values(
            element_guids, [property_name], instance
        )

    # --- 分类挂接（同样四阶段）---------------------------------------------

    def _find_classification_system(self, name: str | None, instance):
        """按名称找分类系统；name=None 时要求项目只有一个系统。"""
        conn = self._mgr.get_conn(instance)
        systems = conn.commands.GetAllClassificationSystems()
        if not systems:
            raise ClassificationNotFoundError(name or "(任何系统)", "系统")
        if name is None:
            if len(systems) > 1:
                names = [s.name for s in systems]
                raise ClassificationNotFoundError(
                    f"项目有多个分类系统 {names}，请指定 system_name", "系统"
                )
            return systems[0]
        for s in systems:
            if s.name == name:
                return s
        raise ClassificationNotFoundError(name, "系统")

    def _find_classification_item(self, system, item_name: str, instance):
        """在分类树中按名称精确匹配分类项（含子项）。"""
        conn = self._mgr.get_conn(instance)
        sid = conn.types.ClassificationSystemId(
            guid=system.classificationSystemId.guid
        )
        items = conn.commands.GetAllClassificationsInSystem(sid)

        def walk(arr, path):
            for it in arr:
                item = it.classificationItem
                p = f"{path} > {item.id}"
                if item.id == item_name:
                    return item, p
                found = walk(getattr(item, "children", None) or [], p)
                if found:
                    return found
            return None

        found = walk(items, "")
        if not found:
            raise ClassificationNotFoundError(item_name, "分类项")
        return found  # (item, full_path)

    def _read_classifications(self, guids, system_id_guid, instance):
        """读元素当前分类，返回 {guid_str: item_id_str | None}。"""
        conn = self._mgr.get_conn(instance)
        t = conn.types
        elements = [
            t.ElementIdArrayItem(t.ElementId(guid=g)) for g in guids
        ]
        res = conn.commands.GetClassificationsOfElements(
            elements,
            [t.ClassificationSystemIdArrayItem(
                t.ClassificationSystemId(guid=system_id_guid))],
        )
        out = {}
        for g, r in zip(guids, res):
            ids = getattr(r, "classificationIds", None)
            if not ids:
                out[g] = None
                continue
            item_id = ids[0].classificationId.classificationItemId
            out[g] = str(item_id.guid) if item_id else None
        return out

    def preview_classification_change(
        self,
        element_guids: list[str],
        item_name: str,
        system_name: str | None,
        instance,
    ) -> dict[str, Any]:
        """预览分类挂接：当前分类 + 目标分类 + 风险，不写入。"""
        info = self._mgr.validate_instance(instance)
        system = self._find_classification_system(system_name, instance)
        item, path = self._find_classification_item(system, item_name, instance)
        target_id = str(item.classificationItemId.guid)
        before = self._read_classifications(
            [str(g) for g in element_guids],
            str(system.classificationSystemId.guid), instance,
        )
        return {
            "instance": info.instance_id,
            "project": info.project_name,
            "system": system.name,
            "system_id": str(system.classificationSystemId.guid),
            "target_item": path,
            "target_item_id": target_id,
            "target_count": len(element_guids),
            "before": before,
            "risk": "分类挂接影响元素在明细表/交互计算中的归类，可撤销（Ctrl+Z）。",
        }

    def execute_classification_change(
        self,
        element_guids: list[str],
        item_name: str,
        system_name: str | None,
        confirm: bool = False,
        instance=None,
    ) -> dict[str, Any]:
        """执行分类挂接并验证。confirm=False 抛 ConfirmRequiredError。"""
        tool = "attach_classification"
        if not confirm:
            raise ConfirmRequiredError(tool, instance)

        info = self._mgr.validate_instance(instance)
        guids = [str(g) for g in element_guids]
        self._mgr.check_project_identity(guids, instance)
        operation_id = self._logger.generate_id()
        timestamp = datetime.now().isoformat(timespec="seconds")

        # 预览同源：系统/项/before 校验与取数一次完成
        preview = self.preview_classification_change(
            element_guids, item_name, system_name, instance
        )
        before = preview["before"]

        # 构造写入行
        conn = self._mgr.get_conn(instance)
        t = conn.types
        rows = [
            t.ElementClassification(
                elementId=t.ElementId(guid=g),
                classificationId=t.ClassificationId(
                    classificationSystemId=t.ClassificationSystemId(
                        guid=preview["system_id"]
                    ),
                    classificationItemId=t.ClassificationItemId(
                        guid=preview["target_item_id"]
                    ),
                ),
            )
            for g in guids
        ]

        execute_status = "success"
        try:
            conn.commands.SetClassificationsOfElements(rows)
        except Exception as exc:
            execute_status = "failed"
            self._record(
                operation_id, timestamp, info, tool,
                len(guids), item_name,
                before, {}, execute_status, None,
            )
            raise

        # Verify：重新读回核对
        after = self._read_classifications(
            guids, preview["system_id"], instance
        )
        verified = sum(1 for v in after.values() if v == preview["target_item_id"])
        verify = VerifyResult(
            requested=len(guids),
            executed=len(guids),
            verified=verified,
            failed=len(guids) - verified,
            status=_verify_status(len(guids), verified),
        )
        self._record(
            operation_id, timestamp, info, tool,
            len(guids), item_name,
            before, after, execute_status, verify.status,
        )

        return {
            "operation_id": operation_id,
            "instance": info.instance_id,
            "project": info.project_name,
            "system": preview["system"],
            "target_item": preview["target_item"],
            "verify": verify.to_dict(),
            "before": before,
            "after": after,
        }

    # --- 日志记录 ---------------------------------------------------------

    def _record(
        self,
        operation_id: str,
        timestamp: str,
        info,
        tool: str,
        target_count: int,
        prop_name: str,
        before: dict[str, Any],
        after: dict[str, Any],
        execute_status: str,
        verify_status: str | None,
    ) -> None:
        log = OperationLog(
            operation_id=operation_id,
            timestamp=timestamp,
            instance=info.instance_id,
            project=info.project_name,
            tool=tool,
            target_count=target_count,
            property=prop_name,
            before=before,
            after=after,
            execute_status=execute_status,
            verify_status=verify_status,
        )
        self._logger.log(log)


def _values_match(actual: Any, expected: str) -> bool:
    """宽松比对：数值/字符串归一化后相等即认为匹配。"""
    if actual is None:
        return False
    try:
        return str(actual).strip().lower() == str(expected).strip().lower()
    except Exception:
        return False


def _verify_status(requested: int, verified: int) -> str:
    # 请求数为 0（无操作）视为 success，避免与 verified==0 的 failed 分支冲突
    if requested == 0:
        return "success"
    if verified == 0:
        return "failed"
    if verified == requested:
        return "success"
    return "partial_success"


# 模块级单例
operations = OperationService(instance_manager.manager, audit_log.logger)
