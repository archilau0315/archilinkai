# -*- coding: utf-8 -*-
"""delete_service.py 单元测试（V0.7）。"""

from unittest.mock import MagicMock

import pytest

from archilinkai.channel_base import CreateResult
from archilinkai.delete_service import DeleteService
from archilinkai.errors import (ChannelCapabilityError, ConfirmRequiredError,
                    InvalidArgumentError)
from archilinkai.schemas import InstanceInfo, InstanceStatus


INFO = InstanceInfo(
    instance_id="ac29-1", port=19723, version=29, build=5003,
    language="zh", project_name="测试项目",
    status=InstanceStatus.CONNECTED,
)


@pytest.fixture
def svc():
    mgr = MagicMock()
    mgr.validate_instance.return_value = INFO
    channel = MagicMock()
    channel.name = "Tapir"
    channel.supports_delete.return_value = True
    channel.delete.return_value = CreateResult(ok=True)
    service = DeleteService(mgr=mgr, logger=MagicMock(), channel=channel)
    return service


def _plan(*guids):
    return {"guids": list(guids)}


def _row(t, i, present=True):
    """存在：details 非空；删除占位：details 为空。"""
    return {"type": t, "id": i,
            "details": {"height": 2.0} if present else {}}


# --- 预览 -------------------------------------------------------------------


def test_preview_lists_targets(svc):
    svc._read_rows = MagicMock(return_value={
        "g1": _row("Wall", "SW-001"),
        "g2": _row("Column", "C-002"),
    })
    out = svc.preview(_plan("G1", "G2"))
    assert out["item_count"] == 2
    assert out["items"][0] == {
        "index": 0, "guid": "G1", "type": "Wall", "id": "SW-001"
    }
    assert "Ctrl+Z" in out["risk"]


def test_preview_warns_missing(svc):
    svc._read_rows = MagicMock(return_value={})
    out = svc.preview(_plan("G1"))
    assert out["item_count"] == 0
    assert out["warnings"]


# --- 执行 -------------------------------------------------------------------


def test_execute_needs_confirm(svc):
    with pytest.raises(ConfirmRequiredError):
        svc.execute(_plan("G1"), confirm=False)


def test_execute_all_deleted(svc):
    # 存在性预检读到构件；删后读回为空
    svc._read_rows = MagicMock(
        side_effect=[
            {"g1": _row("Wall", "SW-001")},
            {},
        ]
    )
    out = svc.execute(_plan("G1"), confirm=True)
    assert out["verify"]["status"] == "success"
    assert out["verify"]["verified"] == 1
    assert out["deleted"][0] == {"guid": "G1", "gone": True}
    assert out["failed"] == []


def test_execute_partial_delete(svc):
    svc._read_rows = MagicMock(
        side_effect=[
            {"g1": _row("Wall", "SW-001"),
             "g2": _row("Column", "C-002")},
            {"g2": _row("Column", "C-002")},  # G1 删了，G2 还在
            {"g2": _row("Column", "C-002")},  # attempt2 G2 仍在
            {"g2": _row("Column", "C-002")},  # attempt3 G2 仍在
        ]
    )
    out = svc.execute(_plan("G1", "G2"), confirm=True)
    assert out["verify"]["status"] == "partial_success"
    assert out["verify"]["verified"] == 1


def test_execute_missing_target_rejected(svc):
    svc._read_rows = MagicMock(return_value={})
    with pytest.raises(InvalidArgumentError):
        svc.execute(_plan("GONE"), confirm=True)


def test_execute_capability_gate(svc):
    svc._read_rows = MagicMock(return_value={
        "g1": _row("Wall", "SW-001")
    })
    svc._channel.supports_delete.return_value = False
    with pytest.raises(ChannelCapabilityError):
        svc.execute(_plan("G1"), confirm=True)


def test_execute_channel_failure_reported(svc):
    svc._channel.delete.return_value = CreateResult(
        ok=False, error="Failed to delete elements."
    )
    svc._read_rows = MagicMock(
        side_effect=[
            {"g1": _row("Wall", "SW-001")},
            {"g1": _row("Wall", "SW-001")},  # attempt1 没删掉
            {"g1": _row("Wall", "SW-001")},  # attempt2 仍在
            {"g1": _row("Wall", "SW-001")},  # attempt3 仍在
        ]
    )
    out = svc.execute(_plan("G1"), confirm=True)
    assert out["verify"]["status"] == "failed"
    assert out["attempts"] == 3
    assert out["failed"][0]["error"] == "Failed to delete elements."


def test_execute_succeeds_after_retry(svc):
    # 预检在；attempt1 没删掉；attempt2 删掉
    svc._read_rows = MagicMock(
        side_effect=[
            {"g1": _row("Wall", "SW-001")},
            {"g1": _row("Wall", "SW-001")},
            {},
        ]
    )
    out = svc.execute(_plan("G1"), confirm=True)
    assert out["verify"]["status"] == "success"
    assert out["attempts"] == 2
    assert out["failed"] == []
