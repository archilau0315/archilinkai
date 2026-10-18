"""ArchiCAD 实例发现/连接/重连模块（V0.3 8.3）。

InstanceManager 维护 {instance_id: InstanceEntry} 注册表。
不得假定启动时扫描得到的 _REGISTRY 永久有效；所有写操作执行前
必须重新确认实例仍然有效（validate_instance + 核对项目身份）。

实例 ID 规则：ac + 主版本号 + 序号，如 ac29-1、ac29-2；
同版本多实例按扫描到的端口顺序编号，避免撞名。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import archicad

from archibridge.errors import (
    InstanceDisconnectedError,
    InstanceNotFoundError,
    MultipleInstancesError,
    NoInstanceAvailableError,
    ProjectIdentityChangedError,
)
from archibridge.schemas import InstanceInfo, InstanceStatus

# ArchiCAD 官方端口范围：19723–19743
_PORT_RANGE = range(19723, 19744)


@dataclass
class InstanceEntry:
    """注册表条目：连接对象 + 实例信息 + 项目身份基线。"""

    conn: archicad.ACConnection
    info: InstanceInfo
    project_identity: dict[str, Any] | None = None

    def to_public_dict(self) -> dict[str, Any]:
        """对外暴露 info（不暴露 conn 句柄）。"""
        return self.info.to_dict()


def read_project_identity(conn: archicad.ACConnection) -> dict[str, Any]:
    """经 Tapir GetProjectInfo 读取项目身份。

    实测字段（已保存项目）：projectPath/projectLocation（完整文件路径）、
    projectName、isUntitled、isTeamwork；未保存项目仅有后两个布尔字段。
    Tapir 未加载时返回空 dict（调用方按"无法确认"处理）。
    """
    try:
        command_id = conn.types.AddOnCommandId("TapirCommand", "GetProjectInfo")
        info = conn.commands.ExecuteAddOnCommand(command_id)
        return {
            "path": info.get("projectPath") or info.get("projectLocation"),
            "name": info.get("projectName"),
            "is_untitled": info.get("isUntitled"),
            "is_teamwork": info.get("isTeamwork"),
        }
    except Exception:
        return {}


def _tapir_get_project_name(conn: archicad.ACConnection) -> str:
    """取项目展示名（复用 read_project_identity，不再重复实现）。"""
    identity = read_project_identity(conn)
    if not identity:
        return "Tapir 未加载?"
    if identity.get("is_untitled"):
        return "未命名项目"
    return identity.get("name") or "已命名项目"


class InstanceManager:
    """实例生命周期管理器。

    生命周期：discover → register → validate → connected →
              healthy → disconnected → refresh/reconnect → connected
    """

    def __init__(self) -> None:
        self._registry: dict[str, InstanceEntry] = {}

    # --- 发现 -------------------------------------------------------------

    def discover_instances(self) -> dict[str, InstanceInfo]:
        """扫描端口，建立 {实例ID: InstanceInfo} 映射。

        多版本多实例并存时按 (version, port顺序) 编号。
        未发现任何实例时抛 NoInstanceAvailableError。
        """
        registry: dict[str, InstanceEntry] = {}
        version_counter: dict[int, int] = {}

        for port in _PORT_RANGE:
            conn = archicad.ACConnection.connect(port=port)
            if conn is None:
                continue
            entry = self._build_entry(conn, port, version_counter)
            if entry is not None:
                registry[entry.info.instance_id] = entry

        if not registry:
            # 不抛异常时也清空旧注册表，避免误用陈旧连接
            self._registry = {}
            raise NoInstanceAvailableError()

        self._registry = registry
        return {iid: e.info for iid, e in registry.items()}

    def _build_entry(
        self,
        conn: archicad.ACConnection,
        port: int,
        version_counter: dict[int, int],
    ) -> InstanceEntry | None:
        """构建单个实例条目。连接损坏时返回 None 跳过。"""
        try:
            # GetProductInfo 返回三元组：(版本号 int, 构建号 int, 语言代码 str)
            version, build, lang = conn.commands.GetProductInfo()
        except Exception:
            # 端口能连但命令不可用，视为坏连接，跳过
            return None

        version_counter[version] = version_counter.get(version, 0) + 1
        instance_id = f"ac{version}-{version_counter[version]}"
        identity = read_project_identity(conn)
        info = InstanceInfo(
            instance_id=instance_id,
            port=port,
            version=version,
            build=build,
            language=lang,
            project_name=identity.get("name") or "未命名项目",
            status=InstanceStatus.CONNECTED,
        )
        return InstanceEntry(conn=conn, info=info, project_identity=identity)

    # --- 查询 -------------------------------------------------------------

    def list_instances(self) -> list[InstanceInfo]:
        """列出所有已注册实例。"""
        return [e.info for e in self._registry.values()]

    def get_entry(self, instance: str | None = None) -> InstanceEntry:
        """获取实例条目。

        - instance 为 None 且仅一个实例时返回该实例；
        - instance 为 None 且多个实例时抛 MultipleInstancesError；
        - instance 指定但不存在时抛 InstanceNotFoundError。
        """
        if instance is None:
            if not self._registry:
                raise NoInstanceAvailableError()
            if len(self._registry) > 1:
                raise MultipleInstancesError(list(self._registry))
            return next(iter(self._registry.values()))
        if instance not in self._registry:
            raise InstanceNotFoundError(instance, list(self._registry))
        return self._registry[instance]

    def get_conn(
        self, instance: str | None = None
    ) -> archicad.ACConnection:
        """获取 archicad 连接对象（供其它服务调用）。"""
        return self.get_entry(instance).conn

    def get_info(self, instance: str | None = None) -> InstanceInfo:
        """获取实例信息。"""
        return self.get_entry(instance).info

    # --- 校验与生命周期 ---------------------------------------------------

    def validate_instance(self, instance: str | None = None) -> InstanceInfo:
        """验证实例仍有效（重新执行 GetProductInfo）。

        写操作前必须调用；连接已失效时抛 InstanceDisconnectedError。
        """
        entry = self.get_entry(instance)
        try:
            version, build, lang = entry.conn.commands.GetProductInfo()
        except Exception as exc:
            entry.info.status = InstanceStatus.DISCONNECTED
            raise InstanceDisconnectedError(entry.info.instance_id) from exc
        # 核对版本/构建号未变，避免项目被换
        if (version, build, lang) != (
            entry.info.version,
            entry.info.build,
            entry.info.language,
        ):
            entry.info.status = InstanceStatus.DISCONNECTED
            raise InstanceDisconnectedError(entry.info.instance_id)
        entry.info.status = InstanceStatus.HEALTHY
        return entry.info

    def check_project_identity(
        self,
        element_guids: list[str],
        instance: str | None = None,
    ) -> dict[str, Any]:
        """写入前核对项目身份（强校验）。

        1. 文件路径（已保存项目最强标识）与基线不一致 → 拦截
        2. 目标元素 GUID 当前全部存在（走 archicad 原生 API，不依赖 Tapir）
        不一致抛 ProjectIdentityChangedError；通过返回当前身份 dict。
        """
        entry = self.get_entry(instance)
        current = read_project_identity(entry.conn)
        baseline = entry.project_identity

        # 旧条目无基线：现场建立，避免历史数据阻塞
        if baseline is None:
            entry.project_identity = current
            baseline = current

        # 路径比对：基线有路径时强一致；基线无路径（未保存）时，
        # 当前突然出现路径或项目名变化，也算项目切换
        if baseline.get("path"):
            if current.get("path") != baseline["path"]:
                raise ProjectIdentityChangedError(
                    entry.info.instance_id, baseline, current
                )
        elif current.get("path") or (
            baseline.get("is_untitled") and not current.get("is_untitled")
        ):
            raise ProjectIdentityChangedError(
                entry.info.instance_id, baseline, current
            )

        # GUID 存在性：换项目后相同 GUID 不可能存在
        all_guids = {
            str(e.elementId.guid)
            for e in entry.conn.commands.GetAllElements()
        }
        missing = [g for g in element_guids if str(g) not in all_guids]
        if missing:
            raise ProjectIdentityChangedError(
                entry.info.instance_id,
                baseline,
                {"current": current, "missing_elements": missing},
            )
        return current

    def reconnect_instance(self, instance: str) -> InstanceInfo:
        """重连指定实例。"""
        if instance not in self._registry:
            raise InstanceNotFoundError(instance, list(self._registry))
        old = self._registry[instance]
        old.info.status = InstanceStatus.REFRESHING
        conn = archicad.ACConnection.connect(port=old.info.port)
        if conn is None:
            old.info.status = InstanceStatus.DISCONNECTED
            raise InstanceDisconnectedError(instance)
        old.conn = conn
        old.info.status = InstanceStatus.CONNECTED
        return old.info

    def remove_dead_instance(self, instance: str) -> None:
        """移除已失效实例。"""
        self._registry.pop(instance, None)

    def refresh_instances(self) -> dict[str, InstanceInfo]:
        """刷新所有实例：重新扫描端口，合并新旧连接。

        仍在运行的实例保留 ID；新实例按规则编号；失效实例标记断开。
        """
        # 先把所有实例标为 disconnected，扫描中重新激活
        for entry in self._registry.values():
            entry.info.status = InstanceStatus.DISCONNECTED

        version_counter: dict[int, int] = {}
        new_registry: dict[str, InstanceEntry] = {}

        for port in _PORT_RANGE:
            conn = archicad.ACConnection.connect(port=port)
            if conn is None:
                continue
            try:
                version, build, lang = conn.commands.GetProductInfo()
            except Exception:
                continue
            version_counter[version] = version_counter.get(version, 0) + 1
            instance_id = f"ac{version}-{version_counter[version]}"
            identity = read_project_identity(conn)
            info = InstanceInfo(
                instance_id=instance_id,
                port=port,
                version=version,
                build=build,
                language=lang,
                project_name=identity.get("name") or "未命名项目",
                status=InstanceStatus.CONNECTED,
            )
            new_registry[instance_id] = InstanceEntry(
                conn=conn, info=info, project_identity=identity
            )

        self._registry = new_registry
        if not self._registry:
            raise NoInstanceAvailableError()
        return {iid: e.info for iid, e in self._registry.items()}


# 模块级单例：server.py 启动时 discover，运行期共用
manager = InstanceManager()
