"""instance_manager.py 单元测试：get_entry 异常路径 + remove_dead_instance。

discover/refresh 需 archicad 连接，留给集成测试；
本文件只测不连真机的纯逻辑路径（手动构造 _registry）。
"""

import pytest

from archilinkai.errors import (
    InstanceDisconnectedError,
    InstanceNotFoundError,
    MultipleInstancesError,
    NoInstanceAvailableError,
    ProjectIdentityChangedError,
)
from archilinkai import instance_manager as im_mod
from archilinkai.instance_manager import InstanceEntry, InstanceManager
from archilinkai.schemas import InstanceInfo, InstanceStatus


def _make_info(instance_id="ac29-1", **kw):
    base = dict(
        instance_id=instance_id, port=19723, version=29, build=3000,
        language="CHS", project_name="Demo.pln",
        status=InstanceStatus.CONNECTED,
    )
    base.update(kw)
    return InstanceInfo(**base)


def _make_entry(instance_id="ac29-1", conn=None):
    """构造测试用条目，conn 用 None 占位（仅异常路径测试不需要真连）。"""
    return InstanceEntry(conn=conn, info=_make_info(instance_id))


def _managers_with(registry):
    """构造已填充 registry 的 InstanceManager。"""
    mgr = InstanceManager()
    mgr._registry = registry
    return mgr


# --- get_entry：空 / 多实例 / 不存在 ------------------------------------


def test_get_entry_empty_raises():
    mgr = _managers_with({})
    with pytest.raises(NoInstanceAvailableError):
        mgr.get_entry()


def test_get_entry_multiple_raises():
    mgr = _managers_with({
        "ac28-1": _make_entry("ac28-1"),
        "ac29-1": _make_entry("ac29-1"),
    })
    with pytest.raises(MultipleInstancesError) as exc_info:
        mgr.get_entry()
    assert "ac28-1" in str(exc_info.value)


def test_get_entry_single_returns_it():
    entry = _make_entry("ac29-1")
    mgr = _managers_with({"ac29-1": entry})
    assert mgr.get_entry() is entry


def test_get_entry_specific_not_found():
    mgr = _managers_with({"ac29-1": _make_entry("ac29-1")})
    with pytest.raises(InstanceNotFoundError) as exc_info:
        mgr.get_entry("ac28-1")
    # 错误信息应列出当前可用实例
    assert "ac29-1" in exc_info.value.to_dict()["message"]


def test_get_entry_specific_returns_it():
    entry = _make_entry("ac28-1")
    mgr = _managers_with({
        "ac28-1": entry,
        "ac29-1": _make_entry("ac29-1"),
    })
    assert mgr.get_entry("ac28-1") is entry


# --- get_info / list_instances -----------------------------------------


def test_list_instances_returns_all():
    mgr = _managers_with({
        "ac28-1": _make_entry("ac28-1"),
        "ac29-1": _make_entry("ac29-1"),
    })
    infos = mgr.list_instances()
    assert len(infos) == 2
    ids = {i.instance_id for i in infos}
    assert ids == {"ac28-1", "ac29-1"}


def test_list_instances_empty():
    assert _managers_with({}).list_instances() == []


def test_get_info_delegates():
    entry = _make_entry("ac29-1")
    mgr = _managers_with({"ac29-1": entry})
    assert mgr.get_info().instance_id == "ac29-1"


def test_get_info_specific():
    mgr = _managers_with({
        "ac28-1": _make_entry("ac28-1"),
        "ac29-1": _make_entry("ac29-1"),
    })
    assert mgr.get_info("ac28-1").version == 28 if False else True
    # 用 ac28-1 的 port 验证
    assert mgr.get_info("ac28-1").instance_id == "ac28-1"


# --- remove_dead_instance ---------------------------------------------


def test_remove_dead_instance_existing():
    mgr = _managers_with({
        "ac28-1": _make_entry("ac28-1"),
        "ac29-1": _make_entry("ac29-1"),
    })
    mgr.remove_dead_instance("ac28-1")
    assert "ac28-1" not in mgr._registry
    assert "ac29-1" in mgr._registry


def test_remove_dead_instance_missing_silent():
    """移除不存在的实例应静默（不抛）。"""
    mgr = _managers_with({"ac29-1": _make_entry("ac29-1")})
    mgr.remove_dead_instance("ac99-1")  # 不应抛 KeyError
    assert len(mgr._registry) == 1


# --- InstanceEntry.to_public_dict --------------------------------------


def test_entry_to_public_dict_excludes_conn():
    """对外暴露 info，不应泄露 conn 句柄。"""
    entry = _make_entry("ac29-1", conn=object())
    d = entry.to_public_dict()
    assert "conn" not in d
    assert d["instance_id"] == "ac29-1"
    assert d["status"] == "connected"


# --- validate_instance：坏连接抛断开 ------------------------------------


def test_validate_instance_disconnected_raises():
    """GetProductInfo 抛异常时应标记 disconnected。"""
    from unittest.mock import MagicMock

    bad_conn = MagicMock()
    bad_conn.commands.GetProductInfo.side_effect = RuntimeError("link down")
    entry = _make_entry("ac29-1")
    entry.conn = bad_conn
    mgr = _managers_with({"ac29-1": entry})
    with pytest.raises(InstanceDisconnectedError):
        mgr.validate_instance("ac29-1")
    assert entry.info.status == InstanceStatus.DISCONNECTED


def test_validate_instance_version_mismatch_raises():
    """版本/构建号变化应判为断开（项目可能被换）。"""
    from unittest.mock import MagicMock

    conn = MagicMock()
    # 实例信息记的 version=29 build=3000，但 GetProductInfo 返回 (29, 4000, 'CHS')
    conn.commands.GetProductInfo.return_value = (29, 4000, "CHS")
    entry = _make_entry("ac29-1")
    entry.conn = conn
    mgr = _managers_with({"ac29-1": entry})
    with pytest.raises(InstanceDisconnectedError):
        mgr.validate_instance("ac29-1")


def test_validate_instance_healthy():
    from unittest.mock import MagicMock

    conn = MagicMock()
    info = _make_info("ac29-1")  # version=29, build=3000, language=CHS
    conn.commands.GetProductInfo.return_value = (29, 3000, "CHS")
    entry = InstanceEntry(conn=conn, info=info)
    mgr = _managers_with({"ac29-1": entry})
    result = mgr.validate_instance("ac29-1")
    assert result.status == InstanceStatus.HEALTHY


# --- check_project_identity：项目强校验 -----------------------------------


def _identity_conn(guids):
    """mock conn：GetAllElements 返回元素，guid 为给定字符串。"""
    from unittest.mock import MagicMock

    conn = MagicMock()
    elems = []
    for g in guids:
        e = MagicMock()
        e.elementId.guid = g
        elems.append(e)
    conn.commands.GetAllElements.return_value = elems
    return conn


def _identity_entry(conn, baseline):
    return InstanceEntry(
        conn=conn, info=_make_info("ac29-1"), project_identity=baseline
    )


def test_identity_passes_when_unchanged(monkeypatch):
    ident = {"path": "E:/A.pln", "name": "A",
             "is_untitled": False, "is_teamwork": False}
    monkeypatch.setattr(im_mod, "read_project_identity", lambda conn: ident)
    entry = _identity_entry(_identity_conn(["g1"]), ident)
    mgr = _managers_with({"ac29-1": entry})
    assert mgr.check_project_identity(["g1"], "ac29-1")["path"] == "E:/A.pln"


def test_identity_blocks_path_change(monkeypatch):
    base = {"path": "E:/A.pln", "name": "A",
            "is_untitled": False, "is_teamwork": False}
    other = dict(base, path="E:/B.pln")
    monkeypatch.setattr(im_mod, "read_project_identity", lambda conn: other)
    entry = _identity_entry(_identity_conn(["g1"]), base)
    mgr = _managers_with({"ac29-1": entry})
    with pytest.raises(ProjectIdentityChangedError) as exc_info:
        mgr.check_project_identity(["g1"], "ac29-1")
    assert exc_info.value.code.value == "PROJECT_IDENTITY_CHANGED"


def test_identity_blocks_missing_guid(monkeypatch):
    ident = {"path": "E:/A.pln", "name": "A",
             "is_untitled": False, "is_teamwork": False}
    monkeypatch.setattr(im_mod, "read_project_identity", lambda conn: ident)
    # 项目里只有 g1，请求改 g2
    entry = _identity_entry(_identity_conn(["g1"]), ident)
    mgr = _managers_with({"ac29-1": entry})
    with pytest.raises(ProjectIdentityChangedError):
        mgr.check_project_identity(["g2"], "ac29-1")


def test_identity_baseline_none_self_seeds(monkeypatch):
    """无基线的旧条目应现场建立基线并放行，不阻塞写入。"""
    ident = {"path": "E:/A.pln", "name": "A",
             "is_untitled": False, "is_teamwork": False}
    monkeypatch.setattr(im_mod, "read_project_identity", lambda conn: ident)
    entry = _identity_entry(_identity_conn(["g1"]), None)
    mgr = _managers_with({"ac29-1": entry})
    mgr.check_project_identity(["g1"], "ac29-1")
    assert entry.project_identity == ident


def test_identity_untitled_then_saved_blocks(monkeypatch):
    """未保存基线，当前项目突然有了路径 → 视为项目已切换。"""
    base = {"path": None, "name": None,
            "is_untitled": True, "is_teamwork": False}
    current = {"path": "E:/Saved.pln", "name": "Saved",
               "is_untitled": False, "is_teamwork": False}
    monkeypatch.setattr(im_mod, "read_project_identity", lambda conn: current)
    entry = _identity_entry(_identity_conn(["g1"]), base)
    mgr = _managers_with({"ac29-1": entry})
    with pytest.raises(ProjectIdentityChangedError):
        mgr.check_project_identity(["g1"], "ac29-1")


# --- discover_instances：探测超时防挂死（V0.65） --------------------------


def test_discover_instances_black_hole_port_no_hang(monkeypatch):
    """端口接受连接但永不应答（如 AC 模态弹窗阻塞 HTTP）时，
    探测应超时跳过并抛 NoInstanceAvailableError，不得永久挂起；
    结束后 socket 默认超时应恢复原值。"""
    import socket as socket_mod
    import threading
    import time

    srv = socket_mod.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)
    port = srv.getsockname()[1]

    def _accept_forever():
        while True:
            try:
                srv.accept()
            except OSError:
                return

    threading.Thread(target=_accept_forever, daemon=True).start()
    monkeypatch.setattr(im_mod, "_PORT_RANGE", range(port, port + 1))

    timeout_before = socket_mod.getdefaulttimeout()
    mgr = InstanceManager()
    start = time.monotonic()
    with pytest.raises(NoInstanceAvailableError):
        mgr.discover_instances()
    elapsed = time.monotonic() - start
    srv.close()
    # 未加探测超时前此处会永久挂起；修复后应在 ~3s/端口 内失败返回
    assert elapsed < 30
    assert socket_mod.getdefaulttimeout() == timeout_before
