"""schemas.py 单元测试：数据结构 to_dict 与 success_result。"""

from archibridge.schemas import (
    ElementSummary,
    Filter,
    InstanceInfo,
    InstanceStatus,
    OperationLog,
    Operator,
    PageResult,
    PreviewResult,
    QueryRequest,
    ToolResult,
    VerifyResult,
    success_result,
)


def test_instance_info_to_dict_status_serialized():
    info = InstanceInfo(
        instance_id="ac29-1", port=19723, version=29, build=3000,
        language="CHS", project_name="Demo.pln",
        status=InstanceStatus.HEALTHY,
    )
    d = info.to_dict()
    assert d["instance_id"] == "ac29-1"
    assert d["port"] == 19723
    assert d["version"] == 29
    assert d["status"] == "healthy"  # 枚举序列化为 value


def test_instance_status_values():
    assert InstanceStatus.CONNECTED.value == "connected"
    assert InstanceStatus.DISCONNECTED.value == "disconnected"
    assert InstanceStatus.HEALTHY.value == "healthy"


def test_operator_count_and_values():
    assert len(Operator) == 9
    assert Operator.EQ.value == "="
    assert Operator.CONTAINS.value == "contains"
    assert Operator.STARTS_WITH.value == "starts_with"
    assert Operator.IN.value == "in"


def test_filter_to_dict():
    f = Filter(field="Fire Rating", operator=Operator.EQ, value="A")
    d = f.to_dict()
    assert d == {"field": "Fire Rating", "operator": "=", "value": "A"}


def test_query_request_to_dict_defaults():
    req = QueryRequest()
    d = req.to_dict()
    assert d["limit"] == 100
    assert d["cursor"] is None
    assert d["filters"] == []


def test_page_result_next_cursor():
    page = PageResult(items=[{"guid": "A"}], count=1, next_cursor="abc")
    assert page.to_dict()["next_cursor"] == "abc"
    page_end = PageResult(items=[], count=0)
    assert page_end.to_dict()["next_cursor"] is None


def test_element_summary_optional_fields():
    s = ElementSummary(guid="G1", element_type="Wall")
    d = s.to_dict()
    assert d["guid"] == "G1"
    assert d["name"] is None
    assert d["story_index"] is None


def test_preview_result_defaults():
    p = PreviewResult(
        target_count=3, target_guids=["A", "B", "C"],
        before_values=[{"guid": "A"}], target_value="600",
    )
    d = p.to_dict()
    assert d["target_count"] == 3
    assert d["unchangeable"] == []
    assert d["estimated_change"] == 0


def test_verify_result_to_dict():
    v = VerifyResult(requested=36, executed=36, verified=34, failed=2,
                     status="partial_success")
    d = v.to_dict()
    assert d["status"] == "partial_success"
    assert d["failed"] == 2


def test_operation_log_to_dict():
    log = OperationLog(
        operation_id="OP-20260923-00001", timestamp="2026-09-23T10:00:00",
        instance="ac29-1", project="Demo.pln", tool="set_element_properties",
        target_count=36, property="Fire Rating",
    )
    d = log.to_dict()
    assert d["operation_id"] == "OP-20260923-00001"
    assert d["execute_status"] == "pending"
    assert d["verify_status"] is None


def test_tool_result_minimal():
    r = ToolResult(status="success")
    assert r.to_dict() == {"status": "success"}


def test_success_result_helper():
    d = success_result(
        instance="ac29-1", project="Demo.pln", count=2,
        items=[{"guid": "A"}],
    )
    assert d["status"] == "success"
    assert d["instance"] == "ac29-1"
    assert d["project"] == "Demo.pln"
    assert d["count"] == 2
    assert d["items"] == [{"guid": "A"}]
