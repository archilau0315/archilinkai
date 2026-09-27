"""板/屋顶开洞（holes）单元测试。

覆盖：plan_values.hole_polygons、plan_framing.build_slab、
plan_special.build_roof、modify_plan Slab holes、
tapir_channel 创建/修改参数拼装、modify_service 洞比对。
"""

import pytest

from errors import ArchicadMCPError, ErrorCode, InvalidArgumentError
from model_plan import ModelPlan
from modify_plan import ModifyPlan
from tapir_channel import TapirChannel
import modify_service


# --- plan_values.hole_polygons ----------------------------------------------


def test_hole_polygons_ok():
    from plan_values import hole_polygons
    raw = [[{"x": 0, "y": 0}, {"x": 1, "y": 0}, {"x": 1, "y": 1}]]
    out = hole_polygons(raw, "f")
    assert out == [[{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0},
                    {"x": 1.0, "y": 1.0}]]


def test_hole_polygons_empty_rejected():
    from plan_values import hole_polygons
    with pytest.raises(InvalidArgumentError):
        hole_polygons([], "f")


def test_hole_polygons_too_few_points():
    from plan_values import hole_polygons
    with pytest.raises(InvalidArgumentError):
        hole_polygons([[{"x": 0, "y": 0}, {"x": 1, "y": 0}]], "f")


def test_hole_polygons_bad_point():
    from plan_values import hole_polygons
    with pytest.raises(InvalidArgumentError):
        hole_polygons([[{"x": 0, "y": 0}, {"x": 1, "y": 0}, {"x": "a"}]], "f")


# --- build_slab（创建）------------------------------------------------------


def test_slab_holes_ok():
    plan = ModelPlan.from_dict({"elements": [{
        "type": "Slab",
        "polygon": [{"x": 0, "y": 0}, {"x": 4, "y": 0}, {"x": 4, "y": 4}],
        "holes": [[{"x": 1, "y": 1}, {"x": 2, "y": 1}, {"x": 2, "y": 2}]],
    }]})
    d = plan.elements[0].data
    assert "holes" in d
    assert len(d["holes"]) == 1
    assert d["holes"][0][0] == {"x": 1.0, "y": 1.0}


def test_slab_holes_optional():
    plan = ModelPlan.from_dict({"elements": [{
        "type": "Slab",
        "polygon": [{"x": 0, "y": 0}, {"x": 4, "y": 0}, {"x": 4, "y": 4}],
    }]})
    assert "holes" not in plan.elements[0].data


def test_slab_holes_bad_rejected():
    with pytest.raises(ArchicadMCPError) as exc:
        ModelPlan.from_dict({"elements": [{
            "type": "Slab",
            "polygon": [{"x": 0, "y": 0}, {"x": 4, "y": 0}, {"x": 4, "y": 4}],
            "holes": [[{"x": 1, "y": 1}, {"x": 2, "y": 1}]],
        }]})
    assert exc.value.code == ErrorCode.INVALID_ARGUMENT


# --- build_roof（创建）------------------------------------------------------


_ROOF_POLY = [{"x": 0, "y": 0}, {"x": 6, "y": 0},
              {"x": 6, "y": 4}, {"x": 0, "y": 4}]
_HOLE = [[{"x": 1, "y": 1}, {"x": 2, "y": 1}, {"x": 2, "y": 2}]]


def test_roof_holes_slope_ok():
    plan = ModelPlan.from_dict({"elements": [{
        "type": "Roof", "polygon": _ROOF_POLY, "slope": 30, "holes": _HOLE,
    }]})
    d = plan.elements[0].data
    assert d["slope"] == 30.0
    assert "holes" in d


def test_roof_holes_multiplane_rejected():
    with pytest.raises(ArchicadMCPError) as exc:
        ModelPlan.from_dict({"elements": [{
            "type": "Roof", "polygon": _ROOF_POLY, "holes": _HOLE,
        }]})
    assert exc.value.code == ErrorCode.INVALID_ARGUMENT


# --- modify_plan（修改）------------------------------------------------------


def test_modify_slab_holes_ok():
    plan = ModifyPlan.from_dict({"items": [{
        "type": "Slab", "guid": "s1", "holes": _HOLE,
    }]})
    assert plan.items[0].changes["holes"] == _HOLE


def test_modify_slab_holes_empty_rejected():
    with pytest.raises(InvalidArgumentError):
        ModifyPlan.from_dict({"items": [{
            "type": "Slab", "guid": "s1", "holes": [],
        }]})


def test_modify_slab_holes_bad_rejected():
    with pytest.raises(InvalidArgumentError):
        ModifyPlan.from_dict({"items": [{
            "type": "Slab", "guid": "s1",
            "holes": [[{"x": 1, "y": 1}, {"x": 2, "y": 1}]],
        }]})


def test_modify_roof_holes_rejected():
    with pytest.raises(InvalidArgumentError):
        ModifyPlan.from_dict({"items": [{
            "type": "Roof", "guid": "r1", "holes": _HOLE,
        }]})


# --- tapir_channel 参数拼装 ---------------------------------------------------


def test_create_slab_with_holes():
    ch = TapirChannel()
    p = ch._build_param("Slab", {
        "level": 0.0, "thickness": 0.2,
        "polygon": [{"x": 0, "y": 0}, {"x": 4, "y": 0}, {"x": 4, "y": 4}],
        "holes": [[{"x": 1.0, "y": 1.0}, {"x": 2.0, "y": 1.0},
                   {"x": 2.0, "y": 2.0}]],
    })
    assert p["holes"] == [{
        "polygonCoordinates": [
            {"x": 1.0, "y": 1.0}, {"x": 2.0, "y": 1.0}, {"x": 2.0, "y": 2.0},
        ],
    }]


def test_create_slab_without_holes():
    ch = TapirChannel()
    p = ch._build_param("Slab", {
        "level": 0.0, "thickness": 0.2,
        "polygon": [{"x": 0, "y": 0}, {"x": 4, "y": 0}, {"x": 4, "y": 4}],
    })
    assert "holes" not in p


def test_create_roof_slope_with_holes():
    ch = TapirChannel()
    p = ch._build_param("Roof", {
        "level": 0.0, "thickness": 0.3, "slope": 30,
        "polygon": [{"x": 0, "y": 0}, {"x": 6, "y": 0}, {"x": 6, "y": 4}],
        "holes": [[{"x": 1.0, "y": 1.0}, {"x": 2.0, "y": 1.0},
                   {"x": 2.0, "y": 2.0}]],
    })
    assert "holes" in p
    assert p["angle"] == pytest.approx(0.5236, abs=1e-3)


def test_create_roof_multiplane_no_holes_in_param():
    ch = TapirChannel()
    p = ch._build_param("Roof", {
        "level": 0.0, "thickness": 0.3,
        "polygon": [{"x": 0, "y": 0}, {"x": 6, "y": 0}, {"x": 6, "y": 4}],
    })
    assert "holes" not in p


def test_modify_slab_holes_param():
    ch = TapirChannel()
    p = ch._build_modify_param("Slab", {
        "guid": "s1", "changes": {"holes": _HOLE},
    })
    assert p == {
        "elementId": {"guid": "s1"},
        "holes": [{"polygonCoordinates": [
            {"x": 1.0, "y": 1.0}, {"x": 2.0, "y": 1.0}, {"x": 2.0, "y": 2.0},
        ]}],
    }


def test_modify_slab_holes_and_level():
    ch = TapirChannel()
    p = ch._build_modify_param("Slab", {
        "guid": "s1", "changes": {"level": 1.0, "holes": _HOLE},
    })
    assert p["zCoordinate"] == 1.0
    assert "holes" in p


# --- modify_service 洞比对 ----------------------------------------------------


def test_match_holes_same():
    target = [[{"x": 1.0, "y": 1.0}, {"x": 2.0, "y": 1.0},
               {"x": 2.0, "y": 2.0}]]
    actual = [[{"x": 1.0, "y": 1.0}, {"x": 2.0, "y": 1.0},
               {"x": 2.0, "y": 2.0}]]
    assert modify_service._match_holes(target, actual)


def test_match_holes_rotated_start():
    """Tapir 读回洞多边形起点可能轮换，按集合匹配。"""
    target = [[{"x": 1.0, "y": 1.0}, {"x": 2.0, "y": 1.0},
               {"x": 2.0, "y": 2.0}]]
    actual = [[{"x": 2.0, "y": 1.0}, {"x": 2.0, "y": 2.0},
               {"x": 1.0, "y": 1.0}]]
    assert modify_service._match_holes(target, actual)


def test_match_holes_count_mismatch():
    target = [[{"x": 1.0, "y": 1.0}, {"x": 2.0, "y": 1.0},
               {"x": 2.0, "y": 2.0}]]
    actual = []
    assert not modify_service._match_holes(target, actual)


def test_match_holes_vertex_mismatch():
    target = [[{"x": 1.0, "y": 1.0}, {"x": 2.0, "y": 1.0},
               {"x": 2.0, "y": 2.0}]]
    actual = [[{"x": 1.0, "y": 1.0}, {"x": 2.0, "y": 1.0},
               {"x": 3.0, "y": 3.0}]]
    assert not modify_service._match_holes(target, actual)


def test_read_holes_strip_closing_point():
    raw = [{"polygonOutline": [
        {"x": 0, "y": 0}, {"x": 1, "y": 0}, {"x": 1, "y": 1},
        {"x": 0, "y": 0},
    ]}]
    out = modify_service._read_holes(raw)
    assert out == [[{"x": 0, "y": 0}, {"x": 1, "y": 0}, {"x": 1, "y": 1}]]
