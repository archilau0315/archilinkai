"""L 形/多段楼梯单元测试。

覆盖：plan_special.build_stair path 字段、tapir_channel 参数拼装、
plan_preview 多段描述。
"""

import pytest

from archibridge.errors import InvalidArgumentError
from archibridge.model_plan import ModelPlan
from archibridge.plan_preview import _describe
from archibridge.tapir_channel import TapirChannel


def test_stair_path_ok():
    plan = ModelPlan.from_dict({"elements": [{
        "type": "Stair",
        "path": [{"x": 0, "y": 0}, {"x": 4, "y": 0}, {"x": 4, "y": 3}],
    }]})
    d = plan.elements[0].data
    assert d["path"] == [
        {"x": 0.0, "y": 0.0}, {"x": 4.0, "y": 0.0}, {"x": 4.0, "y": 3.0},
    ]


def test_stair_path_two_points_ok():
    plan = ModelPlan.from_dict({"elements": [{
        "type": "Stair",
        "path": [{"x": 0, "y": 0}, {"x": 4, "y": 0}],
    }]})
    assert len(plan.elements[0].data["path"]) == 2


def test_stair_path_one_point_rejected():
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict({"elements": [{
            "type": "Stair", "path": [{"x": 0, "y": 0}],
        }]})


def test_stair_path_duplicate_point_rejected():
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict({"elements": [{
            "type": "Stair",
            "path": [{"x": 0, "y": 0}, {"x": 0, "y": 0}],
        }]})


def test_stair_path_and_start_end_ignored():
    """给 path 时 start/end 被忽略。"""
    plan = ModelPlan.from_dict({"elements": [{
        "type": "Stair",
        "path": [{"x": 0, "y": 0}, {"x": 4, "y": 0}],
        "start": {"x": 99, "y": 99}, "end": {"x": 100, "y": 100},
    }]})
    assert plan.elements[0].data["path"] == [
        {"x": 0.0, "y": 0.0}, {"x": 4.0, "y": 0.0},
    ]
    assert "start" not in plan.elements[0].data


def test_stair_backward_compat_start_end():
    """不传 path 时沿用 start/end（向后兼容）。"""
    plan = ModelPlan.from_dict({"elements": [{
        "type": "Stair",
        "start": {"x": 0, "y": 0}, "end": {"x": 4, "y": 0},
    }]})
    d = plan.elements[0].data
    assert d["path"] == [{"x": 0.0, "y": 0.0}, {"x": 4.0, "y": 0.0}]


def test_tapir_stair_multi_segment_param():
    ch = TapirChannel()
    p = ch._build_param("Stair", {
        "path": [{"x": 0.0, "y": 0.0}, {"x": 4.0, "y": 0.0},
                 {"x": 4.0, "y": 3.0}],
        "z": 0.0, "totalHeight": 3.0, "flightWidth": 1.2,
    })
    assert p["baseLinePoints"] == [
        {"x": 0.0, "y": 0.0}, {"x": 4.0, "y": 0.0}, {"x": 4.0, "y": 3.0},
    ]


def test_preview_stair_multi_segment():
    plan = ModelPlan.from_dict({"elements": [{
        "type": "Stair",
        "path": [{"x": 0, "y": 0}, {"x": 4, "y": 0}, {"x": 4, "y": 3}],
    }]})
    el = plan.elements[0]
    text = _describe(el.type, el.data, 0)["text"]
    assert "2 段基线长 7.00m" in text
