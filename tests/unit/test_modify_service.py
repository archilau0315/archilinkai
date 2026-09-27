"""modify_service.py 单元测试（V0.4）。

真机依赖全部 mock：
- instance_manager：validate_instance / check_project_identity
- channel：supports_modify / modify
- GetDetailsOfElements：打桩 _read_details
"""

from unittest.mock import MagicMock

import pytest

from channel_base import CreateResult
from errors import ConfirmRequiredError
from modify_service import ModifyService
from schemas import InstanceInfo, InstanceStatus


INFO = InstanceInfo(
    instance_id="ac29-1", port=19723, version=29, build=5003,
    language="zh", project_name="测试项目",
    status=InstanceStatus.CONNECTED,
)


def _elements(*guids):
    """造官方包风格元素列表：e.elementId.guid 为给定字符串。"""
    out = []
    for g in guids:
        e = MagicMock()
        e.elementId.guid = g
        out.append(e)
    return out


@pytest.fixture
def svc():
    mgr = MagicMock()
    mgr.validate_instance.return_value = INFO
    # 存在性预检默认：默认墙 GUID 在项目里；特殊用例自行覆盖
    conn = MagicMock()
    conn.commands.GetAllElements.return_value = _elements("WALL-GUID")
    mgr.get_conn.return_value = conn
    channel = MagicMock()
    channel.name = "Tapir"
    channel.supports_modify.return_value = True
    service = ModifyService(mgr=mgr, logger=MagicMock(), channel=channel)
    return service


def _wall_plan(guid="WALL-GUID", **changes):
    return {"items": [{"type": "Wall", "guid": guid, **changes}]}


# --- 预览 -------------------------------------------------------------------


def test_preview_lists_from_to(svc):
    svc._read_details = MagicMock(return_value={
        "wall-guid": {
            "begCoordinate": {"x": 0.0, "y": 0.0},
            "endCoordinate": {"x": 6.0, "y": 0.0},
            "height": 3.0, "begThickness": 0.2,
        }
    })
    out = svc.preview(_wall_plan(height=4.0))
    assert out["instance"] == "ac29-1"
    assert out["item_count"] == 1
    change = out["items"][0]["changes"][0]
    assert change == {"field": "height", "from": 3.0, "to": 4.0}


def test_preview_missing_element_warning(svc):
    svc._read_details = MagicMock(return_value={})
    out = svc.preview(_wall_plan(height=4.0))
    assert out["items"] == []
    assert "读不到" in out["warnings"][0]


# --- 执行：confirm ----------------------------------------------------------


def test_execute_requires_confirm(svc):
    with pytest.raises(ConfirmRequiredError):
        svc.execute(_wall_plan(height=4.0), confirm=False)


def test_execute_checks_project_identity(svc):
    svc._read_details = MagicMock(return_value={
        "wall-guid": {"height": 4.0}
    })
    svc._channel.modify.return_value = [CreateResult(ok=True)]
    svc.execute(_wall_plan(height=4.0), confirm=True)
    svc._mgr.check_project_identity.assert_called_once()


# --- 执行：结果与验证 -------------------------------------------------------


def test_execute_success(svc):
    # 改前改后两次读 details：预览不用，这里 execute 只读一次（验证时）
    svc._read_details = MagicMock(return_value={
        "wall-guid": {"height": 4.0}
    })
    svc._channel.modify.return_value = [CreateResult(ok=True)]

    out = svc.execute(_wall_plan(height=4.0), confirm=True)
    assert out["verify"]["status"] == "success"
    assert out["verify"]["verified"] == 1
    assert len(out["modified"]) == 1
    assert out["failed"] == []


def test_execute_partial_failure(svc):
    """通道返回一成一败时，只验证成功的，失败项带 error。"""
    plan = {"items": [
        {"type": "Wall", "guid": "G1", "height": 4.0},
        {"type": "Wall", "guid": "G2", "height": 5.0},
    ]}
    svc._read_details = MagicMock(return_value={
        "g1": {"height": 4.0},
        "g2": {"height": 5.0},
    })
    svc._channel.modify.return_value = [
        CreateResult(ok=True),
        CreateResult(ok=False, error="Failed to load wall."),
    ]
    out = svc.execute(plan, confirm=True)
    assert out["verify"]["status"] == "success"
    assert out["verify"]["requested"] == 1
    assert len(out["failed"]) == 1
    assert out["failed"][0]["error"] == "Failed to load wall."


def test_execute_verify_failed_when_value_unchanged(svc):
    svc._read_details = MagicMock(return_value={
        "wall-guid": {"height": 3.0}  # 仍旧值
    })
    svc._channel.modify.return_value = [CreateResult(ok=True)]
    out = svc.execute(_wall_plan(height=4.0), confirm=True)
    assert out["verify"]["status"] == "failed"
    assert out["modified"][0]["matched"] is False


def test_execute_point_change_verified(svc):
    svc._read_details = MagicMock(return_value={
        "wall-guid": {
            "begCoordinate": {"x": 1.0, "y": 2.0},
        }
    })
    svc._channel.modify.return_value = [CreateResult(ok=True)]
    out = svc.execute(
        _wall_plan(start={"x": 1.0, "y": 2.0}), confirm=True
    )
    assert out["verify"]["status"] == "success"


def test_capability_gate_blocks(svc):
    from errors import ChannelCapabilityError

    svc._channel.supports_modify.return_value = False
    with pytest.raises(ChannelCapabilityError):
        svc.preview(_wall_plan(height=4.0))


def test_missing_target_reported_plainly(svc):
    """构件不在项目里：报"不存在"，不报"项目变化"。"""
    from errors import InvalidArgumentError

    # 默认 details 只有 WALL-GUID；查另一个 GUID
    svc._read_details = MagicMock(return_value={})
    with pytest.raises(InvalidArgumentError) as ei:
        svc.execute(_wall_plan(guid="GONE", height=4.0), confirm=True)
    assert "不存在" in str(ei.value)
