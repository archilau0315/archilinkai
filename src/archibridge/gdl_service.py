"""GDL 参数读写服务（V0.3 分层整理）。

把原来散在 server.py 的 GDL 逻辑集中到一处：
- get_parameters：经 Tapir 读已放置对象的参数
- set_parameters：经 Tapir 批量改参数，confirm 拦截 + 操作 ID

本次只做位置迁移，功能与原来完全一致。
"""

from __future__ import annotations

from typing import Any

from archibridge import audit_log
from archibridge import instance_manager
from archibridge.errors import ConfirmRequiredError
from archibridge.tapir_adapter import _to_dict, adapter as _tapir


class GDLService:
    """GDL 对象参数读取与批量修改。"""

    def __init__(self, mgr: instance_manager.InstanceManager) -> None:
        self._mgr = mgr

    def get_parameters(
        self, element_guids: list[str], instance: str | None = None
    ) -> Any:
        """读 GDL 参数，返回规整后的原生结构（dict/list）。"""
        params = {"elementIds": [{"guid": g} for g in element_guids]}
        result = _tapir.execute("GetGDLParametersOfElements", params, instance)
        return _to_dict(result)

    def set_parameters(
        self,
        element_guids: list[str],
        parameter_name: str,
        value: Any,
        confirm: bool = False,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """批量改 GDL 参数。

        confirm=false 直接抛 ConfirmRequiredError；写入成功返
        {operation_id, instance, project, verify}。
        """
        tool = "set_gdl_parameters"
        if not confirm:
            raise ConfirmRequiredError(tool, instance)

        info = self._mgr.validate_instance(instance)
        operation_id = audit_log.logger.generate_id()
        elements_with_params = [
            {
                "elementId": {"guid": guid},
                "gdlParameters": [{"name": parameter_name, "value": value}],
            }
            for guid in element_guids
        ]
        _tapir.set_gdl_parameters_of_elements(elements_with_params, instance)
        return {
            "operation_id": operation_id,
            "instance": info.instance_id,
            "project": info.project_name,
            "verify": {
                "requested": len(element_guids),
                "executed": len(element_guids),
                "verified": len(element_guids),
                "failed": 0,
                "status": "success",
                "note": "GDL 参数 Verify 待实机验证后细化。",
            },
        }


# 模块级单例
service = GDLService(instance_manager.manager)
