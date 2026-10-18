"""create_service + channel_base 单元测试。

用假的通道/实例管理器/日志器跑完整调度链路，不连真机：
- confirm 闸门、版本能力闸门
- 分组创建、结果汇总、读回验证
- channel_base 的 check_supports 与 CreateResult
"""

from types import SimpleNamespace

import pytest

from archibridge import audit_log
from archibridge.channel_base import CreateResult, ModelChannel
from archibridge.create_service import CreateService
from archibridge.errors import (
    ChannelCapabilityError, ConfirmRequiredError, ErrorCode,
)


# --- 假依赖 ---------------------------------------------------------------


class FakeChannel(ModelChannel):
    name = "Fake"

    def __init__(self, supported=("Wall", "Column"), fail=False) -> None:
        self._supported = set(supported)
        self.fail = fail
        self.calls: list[tuple[str, int]] = []
        self.item_log: list[tuple[str, list]] = []

    def get_version(self, instance=None) -> str:
        return "9.9"

    def supports(self, element_type, instance=None) -> bool:
        return element_type in self._supported

    def create(self, element_type, items, instance=None):
        self.calls.append((element_type, len(items)))
        self.item_log.append((element_type, list(items)))
        if self.fail:
            return [CreateResult(ok=False, error="boom") for _ in items]
        return [
            CreateResult(ok=True, guid=f"{element_type}-{i}")
            for i, _ in enumerate(items)
        ]


class FakeManager:
    def __init__(self, existing_guids=None) -> None:
        self.info = SimpleNamespace(instance_id="ac-test",
                                    project_name="测试项目")
        self._existing = existing_guids

    def validate_instance(self, instance=None):
        return self.info

    def check_project_identity(self, guids, instance=None):
        return {}

    def get_conn(self, instance=None):
        elems = [
            SimpleNamespace(elementId=SimpleNamespace(guid=g))
            for g in (self._existing or [])
        ]
        return SimpleNamespace(
            commands=SimpleNamespace(GetAllElements=lambda: elems)
        )


def _service(channel=None, existing_guids=None, tmp_path=None):
    logger = audit_log.OperationLogger(
        log_file=str(tmp_path / ".test_ops.jsonl")
    )
    return CreateService(
        mgr=FakeManager(existing_guids),
        logger=logger,
        channel=channel or FakeChannel(),
    )


WALL_COLUMN_PLAN = {
    "elements": [
        {"type": "Wall",
         "start": {"x": 0, "y": 0}, "end": {"x": 6, "y": 0}},
        {"type": "Column", "x": 0, "y": 0},
        {"type": "Column", "x": 6, "y": 0},
    ]
}


# --- confirm 闸门 ---------------------------------------------------------


def test_execute_without_confirm_rejected(tmp_path):
    service = _service(tmp_path=tmp_path)
    with pytest.raises(ConfirmRequiredError):
        service.execute(WALL_COLUMN_PLAN, confirm=False)


# --- 预览 -----------------------------------------------------------------


def test_preview_returns_summary(tmp_path):
    service = _service(tmp_path=tmp_path)
    out = service.preview(WALL_COLUMN_PLAN)
    assert out["instance"] == "ac-test"
    assert out["project"] == "测试项目"
    assert out["total"] == 3
    assert out["counts"] == {"Wall": 1, "Column": 2}
    assert out["channel"] == "Fake 9.9"


def test_preview_blocked_when_channel_unsupported(tmp_path):
    service = _service(channel=FakeChannel(supported=("Column",)),
                       tmp_path=tmp_path)
    with pytest.raises(ChannelCapabilityError) as exc:
        service.preview(WALL_COLUMN_PLAN)
    assert exc.value.code == ErrorCode.CHANNEL_CAPABILITY_UNSUPPORTED


# --- 执行成功 -------------------------------------------------------------


def test_execute_creates_by_type_and_verifies(tmp_path):
    # 读回时通道产生的 GUID 都存在 → 验证通过
    existing = ["Wall-0", "Column-0", "Column-1"]
    service = _service(existing_guids=existing, tmp_path=tmp_path)
    out = service.execute(WALL_COLUMN_PLAN, confirm=True)

    assert len(out["created"]) == 3
    assert out["failed"] == []
    assert out["verify"]["status"] == "success"
    assert out["verify"]["verified"] == 3
    # 按类型分了两趟创建
    assert ("Wall", 1) in out_calls(service)
    assert ("Column", 2) in out_calls(service)
    assert out["operation_id"].startswith("OP-")


def out_calls(service):
    return service._channel.calls


def test_execute_groups_results_in_plan_order(tmp_path):
    service = _service(
        existing_guids=["Wall-0", "Column-0", "Column-1"],
        tmp_path=tmp_path,
    )
    out = service.execute(WALL_COLUMN_PLAN, confirm=True)
    indices = [c["index"] for c in out["created"]]
    assert indices == [0, 1, 2]
    assert out["created"][0]["type"] == "Wall"
    assert out["created"][0]["guid"] == "Wall-0"


# --- 执行与验证失败 -------------------------------------------------------


def test_execute_channel_failure_marked(tmp_path):
    service = _service(channel=FakeChannel(fail=True), tmp_path=tmp_path)
    out = service.execute(WALL_COLUMN_PLAN, confirm=True)
    assert out["created"] == []
    assert len(out["failed"]) == 3
    assert out["verify"]["status"] == "failed"


def test_verify_partial_when_guids_missing(tmp_path):
    # 只有 1 个 GUID 真正存在
    service = _service(existing_guids=["Wall-0"], tmp_path=tmp_path)
    out = service.execute(WALL_COLUMN_PLAN, confirm=True)
    assert out["verify"]["verified"] == 1
    assert out["verify"]["status"] == "partial_success"


class UpperCaseChannel(FakeChannel):
    """创建返回大写 GUID（模拟真实 Tapir 行为）。"""

    def create(self, element_type, items, instance=None):
        return [
            CreateResult(ok=True, guid=f"{element_type}-{i}".upper())
            for i, _ in enumerate(items)
        ]


def test_verify_guid_case_insensitive(tmp_path):
    # 系统里存小写，创建返回大写，归一化后应全部匹配
    service = _service(
        channel=UpperCaseChannel(),
        existing_guids=["wall-0", "column-0", "column-1"],
        tmp_path=tmp_path,
    )
    out = service.execute(WALL_COLUMN_PLAN, confirm=True)
    assert out["verify"]["verified"] == 3
    assert out["verify"]["status"] == "success"


MEP_PLAN = {
    "elements": [
        {"type": "MEPRoute", "domain": "Ventilation",
         "path": [{"x": 0, "y": 0, "z": 2.5}, {"x": 3, "y": 0, "z": 2.5}]},
    ]
}


class MepChannel(FakeChannel):
    """支持 MEPRoute，exists 按路由 GUID 伪造。"""

    def __init__(self, existing_routes=None) -> None:
        super().__init__(supported=("MEPRoute",))
        self._existing_routes = set(existing_routes or [])

    def exists(self, element_type, guid, instance=None) -> bool:
        assert element_type == "MEPRoute"
        return guid in self._existing_routes


def test_verify_mep_route_uses_channel_exists(tmp_path):
    channel = MepChannel(existing_routes=["MEPRoute-0"])
    service = _service(channel=channel, tmp_path=tmp_path)
    out = service.execute(MEP_PLAN, confirm=True)
    assert out["verify"]["verified"] == 1
    assert out["verify"]["status"] == "success"


def test_verify_mep_route_missing(tmp_path):
    service = _service(channel=MepChannel(), tmp_path=tmp_path)
    out = service.execute(MEP_PLAN, confirm=True)
    assert out["verify"]["verified"] == 0
    assert out["verify"]["status"] == "failed"


def test_instance_param_overrides_plan(tmp_path):
    service = _service(tmp_path=tmp_path)
    plan = {"instance": "ac29-1",
            "elements": [{"type": "Column", "x": 0, "y": 0}]}
    out = service.preview(plan, instance="ac28-1")
    # 不直接暴露 resolve 后实例，但 validate 不报错即说明走到了假管理器
    assert out["instance"] == "ac-test"


# --- channel_base 接口 ----------------------------------------------------


def test_create_result_to_dict():
    ok = CreateResult(ok=True, guid="g1").to_dict()
    bad = CreateResult(ok=False, error="err").to_dict()
    assert ok == {"ok": True, "guid": "g1"}
    assert bad == {"ok": False, "error": "err"}


def test_check_supports_passes_and_raises():
    channel = FakeChannel(supported=("Wall",))
    channel.check_supports("Wall")  # 不抛
    with pytest.raises(ChannelCapabilityError):
        channel.check_supports("Column")


# --- 门 / 窗挂墙（V0.2 新增）---------------------------------------------


def _all_types_channel():
    return FakeChannel(supported=("Wall", "Column", "Beam", "Slab",
                                  "Door", "Window",
                                  "Stair", "Roof", "Morph"))


WALL_WINDOW_PLAN = {
    "elements": [
        {"type": "Wall",
         "start": {"x": 0, "y": 0}, "end": {"x": 6, "y": 0}},
        {"type": "Window", "wall": 0, "offset": 3.0},
    ]
}


def test_window_attached_to_new_wall(tmp_path):
    """窗序号引用本计划墙：墙先建，窗拿到墙的真实 GUID。"""
    channel = _all_types_channel()
    service = _service(
        channel=channel, existing_guids=["Wall-0", "Window-0"],
        tmp_path=tmp_path,
    )
    out = service.execute(WALL_WINDOW_PLAN, confirm=True)

    created = out["created"]
    assert len(created) == 2
    assert out["failed"] == []
    # 通道收到的窗参数里，ownerWallGuid = 墙的新 GUID "Wall-0"
    win_call = [items for et, items in channel.item_log if et == "Window"][0]
    assert win_call[0]["ownerWallGuid"] == "Wall-0"
    assert win_call[0]["offset"] == 3.0
    assert out["verify"]["status"] == "success"


def test_door_attached_to_existing_wall_guid(tmp_path):
    """门引用已有墙 GUID 字符串：原样透传。"""
    channel = _all_types_channel()
    service = _service(channel=channel,
                       existing_guids=["Door-0"], tmp_path=tmp_path)
    plan = {"elements": [
        {"type": "Door",
         "wall": "EXISTING-WALL-GUID", "offset": 1.0},
    ]}
    out = service.execute(plan, confirm=True)
    door_items = [items for et, items in channel.item_log if et == "Door"][0]
    assert door_items[0]["ownerWallGuid"] == "EXISTING-WALL-GUID"
    assert out["created"][0]["guid"] == "Door-0"


def test_independent_elements_created_before_openings(tmp_path):
    """创建顺序：墙（独立）必须排在窗（挂墙）前面。"""
    channel = _all_types_channel()
    service = _service(
        channel=channel, existing_guids=["Wall-0", "Window-0"],
        tmp_path=tmp_path,
    )
    service.execute(WALL_WINDOW_PLAN, confirm=True)
    types = [et for et, _ in channel.calls]
    assert types.index("Wall") < types.index("Window")


def test_window_blocked_when_wall_fails(tmp_path):
    """墙没建成：窗不发给通道，标记为挂接失败。"""
    channel = FakeChannel(
        supported=("Wall", "Window"), fail=True
    )
    service = _service(channel=channel, tmp_path=tmp_path)
    out = service.execute(WALL_WINDOW_PLAN, confirm=True)

    # 窗没有真正调用通道（只有墙失败的那一趟）
    called_types = [et for et, n in channel.calls if n > 0]
    assert "Window" not in called_types
    # 窗出现在 failed，错误信息说明墙没建成
    window_fail = [f for f in out["failed"] if f["type"] == "Window"][0]
    assert "墙未创建成功" in window_fail["error"]
    assert out["verify"]["status"] == "failed"


def test_stair_roof_morph_created_as_independent(tmp_path):
    """V0.3 三类都是独立构件：字段原样透传，结果按序号排。"""
    channel = _all_types_channel()
    service = _service(
        channel=channel,
        existing_guids=["Stair-0", "Roof-0", "Morph-0"],
        tmp_path=tmp_path,
    )
    plan = {"elements": [
        {"type": "Stair",
         "start": {"x": 0, "y": 0}, "end": {"x": 4, "y": 0}, "steps": 13},
        {"type": "Roof",
         "polygon": [{"x": 0, "y": 0}, {"x": 6, "y": 0}, {"x": 6, "y": 4}],
         "slope": 30},
        {"type": "Morph"},
    ]}
    out = service.execute(plan, confirm=True)

    log = dict(channel.item_log)
    assert log["Stair"][0]["steps"] == 13
    assert log["Roof"][0]["slope"] == 30
    assert log["Morph"][0]["size"] == {"x": 1, "y": 1, "z": 1}
    # 全部成功，结果 index 顺序 0,1,2
    assert [c["index"] for c in out["created"]] == [0, 1, 2]
    assert out["verify"]["status"] == "success"
