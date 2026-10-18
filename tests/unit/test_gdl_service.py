"""gdl_service.py 单元测试：confirm 拦截 + 读写委托。"""

import pytest

from archilinkai.errors import ConfirmRequiredError
from archilinkai import gdl_service as mod
from archilinkai.gdl_service import GDLService


def _svc(monkeypatch):
    svc = GDLService.__new__(GDLService)  # 不依赖真实 manager
    return svc


def test_set_requires_confirm(monkeypatch):
    svc = GDLService.__new__(GDLService)
    with pytest.raises(ConfirmRequiredError):
        svc.set_parameters(["g1"], "ac_cavity", 0.2, confirm=False)


def test_set_calls_tapir_when_confirmed(monkeypatch):
    svc = GDLService.__new__(GDLService)

    class _Info:
        instance_id = "ac29-1"
        project_name = "P"

    svc._mgr = type("M", (), {
        "validate_instance": lambda self, inst: _Info()
    })()
    monkeypatch.setattr(mod.audit_log.logger, "generate_id", lambda: "OP-1")
    captured = {}

    def _fake_set(params, instance):
        captured["params"] = params

    monkeypatch.setattr(
        mod._tapir, "set_gdl_parameters_of_elements", _fake_set
    )
    r = svc.set_parameters(["g1"], "ac_cavity", 0.2, confirm=True)
    assert r["operation_id"] == "OP-1"
    assert r["verify"]["status"] == "success"
    assert captured["params"][0]["gdlParameters"][0]["name"] == "ac_cavity"


def test_get_parameters_delegates(monkeypatch):
    svc = GDLService.__new__(GDLService)

    def _fake_execute(cmd, params, instance):
        return {"cmd": cmd, "params": params}

    monkeypatch.setattr(mod._tapir, "execute", _fake_execute)
    monkeypatch.setattr(mod, "_to_dict", lambda v: v)
    r = svc.get_parameters(["g1", "g2"], "ac29-1")
    assert r["cmd"] == "GetGDLParametersOfElements"
    assert len(r["params"]["elementIds"]) == 2
