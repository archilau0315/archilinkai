# -*- coding: utf-8 -*-
"""tapir_channel 删除链路单元测试（V0.7）。"""

import pytest

from channel_base import CreateResult
from tapir_channel import TapirChannel


@pytest.fixture
def ch():
    return TapirChannel()


def test_delete_empty_returns_ok_without_call(ch, monkeypatch):
    called = []
    # _tapir 在 tapir_channel 模块内被导入
    import tapir_channel
    monkeypatch.setattr(
        tapir_channel, "_tapir",
        _FakeTapir(called, {"success": True})
    )
    r = ch.delete([], "ac29-1")
    assert r.ok is True
    assert called == []


def test_delete_success(ch, monkeypatch):
    called = []
    import tapir_channel
    monkeypatch.setattr(
        tapir_channel, "_tapir",
        _FakeTapir(called, {"success": True})
    )
    r = ch.delete(["G1", "G2"], "ac29-1")
    assert r.ok is True
    # 参数拼装
    assert called[0][0] == "DeleteElements"
    assert called[0][2] == "ac29-1"
    assert called[0][1] == {
        "elements": [
            {"elementId": {"guid": "G1"}},
            {"elementId": {"guid": "G2"}},
        ]
    }


def test_delete_failure(ch, monkeypatch):
    called = []
    import tapir_channel
    monkeypatch.setattr(
        tapir_channel, "_tapir",
        _FakeTapir(called, {
            "success": False,
            "error": {"code": -2130313115,
                      "message": "Failed to delete elements."},
        })
    )
    r = ch.delete(["G1"], "ac29-1")
    assert r.ok is False
    assert r.error == "Failed to delete elements."


def test_supports_delete(ch, monkeypatch):
    monkeypatch.setattr(
        ch, "_command_available",
        lambda name, key, inst=None: name == "DeleteElements"
    )
    assert ch.supports_delete("ac29-1") is True


class _FakeTapir:
    """记录调用并返回固定结果。"""

    def __init__(self, calls, result):
        self._calls = calls
        self._result = result

    def execute(self, command_name, params, instance):
        self._calls.append((command_name, params, instance))
        return self._result
