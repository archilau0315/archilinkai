"""model_plan.py 单元测试：解析、校验、默认值补全。

全部为纯逻辑，不连真机；通道能力闸门由 create_service 测试覆盖。
"""

import pytest

from archibridge.errors import ArchicadMCPError, ErrorCode
from archibridge.model_plan import MAX_ELEMENTS, ModelPlan


def _plan(elements, instance=None):
    source = {"elements": elements}
    if instance is not None:
        source["instance"] = instance
    return ModelPlan.from_dict(source)


# --- 正常解析与默认值 -----------------------------------------------------


def test_wall_uses_defaults():
    plan = _plan([{"type": "Wall",
                   "start": {"x": 0, "y": 0}, "end": {"x": 6, "y": 0}}])
    wall = plan.elements[0]
    assert wall.data["height"] == 3.0
    assert wall.data["thickness"] == 0.2


def test_column_uses_default_height():
    plan = _plan([{"type": "Column", "x": 1, "y": 2}])
    col = plan.elements[0]
    assert col.data["height"] == 3.0
    assert col.data["x"] == 1.0 and col.data["y"] == 2.0


def test_explicit_values_kept():
    plan = _plan([{"type": "Wall",
                   "start": {"x": 0, "y": 0}, "end": {"x": 4, "y": 0},
                   "height": 2.5, "thickness": 0.3}])
    wall = plan.elements[0]
    assert wall.data["height"] == 2.5
    assert wall.data["thickness"] == 0.3


def test_instance_passed_through():
    plan = _plan([{"type": "Column", "x": 0, "y": 0}], instance="ac29-1")
    assert plan.instance == "ac29-1"


def test_types_used_dedup_in_order():
    plan = _plan([
        {"type": "Wall", "start": {"x": 0, "y": 0}, "end": {"x": 1, "y": 0}},
        {"type": "Column", "x": 0, "y": 0},
        {"type": "Column", "x": 1, "y": 1},
    ])
    assert plan.types_used() == ["Wall", "Column"]


def test_to_dict_roundtrip():
    plan = _plan([{"type": "Column", "x": 1, "y": 2}], instance="ac29-1")
    out = plan.to_dict()
    assert out["instance"] == "ac29-1"
    assert out["elements"][0]["type"] == "Column"
    assert out["elements"][0]["index"] == 0


def test_int_coordinates_become_float():
    plan = _plan([{"type": "Column", "x": 3, "y": 4}])
    assert isinstance(plan.elements[0].data["x"], float)


# --- 校验失败 -------------------------------------------------------------


def _error_code(elements):
    with pytest.raises(ArchicadMCPError) as exc:
        _plan(elements)
    return exc.value.code


def test_empty_elements_rejected():
    assert _error_code([]) == ErrorCode.INVALID_ARGUMENT


def test_missing_elements_rejected():
    with pytest.raises(ArchicadMCPError):
        ModelPlan.from_dict({})


def test_unknown_type_rejected():
    assert _error_code([{"type": "Roof", "x": 0}]) == ErrorCode.INVALID_ARGUMENT


def test_zero_length_wall_rejected():
    assert _error_code([
        {"type": "Wall",
         "start": {"x": 1, "y": 1}, "end": {"x": 1, "y": 1}}
    ]) == ErrorCode.INVALID_ARGUMENT


def test_non_positive_height_rejected():
    assert _error_code([
        {"type": "Column", "x": 0, "y": 0, "height": 0}
    ]) == ErrorCode.INVALID_ARGUMENT


def test_non_numeric_coordinate_rejected():
    assert _error_code([{"type": "Column", "x": "a", "y": 0}]) \
        == ErrorCode.INVALID_ARGUMENT


def test_boolean_coordinate_rejected():
    """true/false 虽为布尔但不能当坐标。"""
    assert _error_code([{"type": "Column", "x": True, "y": 0}]) \
        == ErrorCode.INVALID_ARGUMENT


def test_coordinate_out_of_limit_rejected():
    assert _error_code([{"type": "Column", "x": 200000, "y": 0}]) \
        == ErrorCode.INVALID_ARGUMENT


def test_missing_wall_start_rejected():
    assert _error_code([
        {"type": "Wall", "end": {"x": 1, "y": 0}}
    ]) == ErrorCode.INVALID_ARGUMENT


def test_missing_column_y_rejected():
    assert _error_code([{"type": "Column", "x": 0}]) \
        == ErrorCode.INVALID_ARGUMENT


def test_too_many_elements_rejected():
    items = [{"type": "Column", "x": i, "y": 0}
             for i in range(MAX_ELEMENTS + 1)]
    assert _error_code(items) == ErrorCode.INVALID_ARGUMENT


def test_non_object_element_rejected():
    assert _error_code(["not-an-object"]) == ErrorCode.INVALID_ARGUMENT


# --- 梁（V0.1 新增）------------------------------------------------------


def test_beam_defaults():
    plan = _plan([{"type": "Beam",
                   "start": {"x": 0, "y": 0}, "end": {"x": 6, "y": 0}}])
    beam = plan.elements[0]
    assert beam.data["height"] == 0.3
    assert beam.data["width"] == 0.2
    assert beam.data["z"] == 0.0


def test_beam_explicit_values_kept():
    plan = _plan([{"type": "Beam",
                   "start": {"x": 0, "y": 0}, "end": {"x": 6, "y": 0},
                   "z": 3.2, "height": 0.4, "width": 0.25}])
    beam = plan.elements[0]
    assert beam.data["z"] == 3.2
    assert beam.data["height"] == 0.4
    assert beam.data["width"] == 0.25


def test_beam_zero_length_rejected():
    assert _error_code([
        {"type": "Beam",
         "start": {"x": 1, "y": 1}, "end": {"x": 1, "y": 1}}
    ]) == ErrorCode.INVALID_ARGUMENT


def test_beam_negative_z_allowed():
    """地下梁顶标高可为负。"""
    plan = _plan([{"type": "Beam",
                   "start": {"x": 0, "y": 0}, "end": {"x": 6, "y": 0},
                   "z": -1.5}])
    assert plan.elements[0].data["z"] == -1.5


def test_beam_bad_height_rejected():
    assert _error_code([
        {"type": "Beam",
         "start": {"x": 0, "y": 0}, "end": {"x": 6, "y": 0}, "height": 0}
    ]) == ErrorCode.INVALID_ARGUMENT


# --- 板（V0.1 新增）------------------------------------------------------


def test_slab_defaults():
    plan = _plan([{"type": "Slab", "polygon": [
        {"x": 0, "y": 0}, {"x": 6, "y": 0}, {"x": 6, "y": 4}]}])
    slab = plan.elements[0]
    assert slab.data["level"] == 0.0
    assert slab.data["thickness"] == 0.2
    assert len(slab.data["polygon"]) == 3


def test_slab_explicit_values_kept():
    plan = _plan([{"type": "Slab", "level": 3.0, "thickness": 0.25,
                   "polygon": [
                       {"x": 0, "y": 0}, {"x": 6, "y": 0},
                       {"x": 6, "y": 4}, {"x": 0, "y": 4}]}])
    slab = plan.elements[0]
    assert slab.data["level"] == 3.0
    assert slab.data["thickness"] == 0.25


def test_slab_too_few_points_rejected():
    assert _error_code([
        {"type": "Slab", "polygon": [{"x": 0, "y": 0}, {"x": 1, "y": 0}]}
    ]) == ErrorCode.INVALID_ARGUMENT


def test_slab_missing_polygon_rejected():
    assert _error_code([{"type": "Slab"}]) == ErrorCode.INVALID_ARGUMENT


def test_slab_bad_point_rejected():
    assert _error_code([
        {"type": "Slab", "polygon": [
            {"x": 0, "y": 0}, {"x": 1, "y": 0}, {"x": 1}]}
    ]) == ErrorCode.INVALID_ARGUMENT


# --- 门 / 窗（V0.2 新增）-------------------------------------------------


def _wall_and_window():
    return [
        {"type": "Wall",
         "start": {"x": 0, "y": 0}, "end": {"x": 6, "y": 0}},
        {"type": "Window", "wall": 0, "offset": 3.0},
    ]


def test_window_defaults():
    plan = _plan(_wall_and_window())
    win = plan.elements[1]
    assert win.data["width"] == 1.2
    assert win.data["height"] == 1.5
    assert win.data["sill"] == 0.9
    assert win.data["offset"] == 3.0
    assert win.data["wall"] == 0


def test_door_defaults():
    plan = _plan([
        {"type": "Wall",
         "start": {"x": 0, "y": 0}, "end": {"x": 6, "y": 0}},
        {"type": "Door", "wall": 0},
    ])
    door = plan.elements[1]
    assert door.data["width"] == 1.0
    assert door.data["height"] == 2.1
    assert door.data["sill"] == 0.0
    assert door.data["offset"] == 1.0


def test_opening_wall_guid_string_allowed():
    plan = _plan([
        {"type": "Window",
         "wall": "ABCDEF12-3456-7890-ABCD-EF1234567890", "offset": 2.0},
    ])
    assert plan.elements[0].data["wall"].startswith("ABCDEF12")


def test_opening_explicit_values_kept():
    plan = _plan([
        {"type": "Wall",
         "start": {"x": 0, "y": 0}, "end": {"x": 6, "y": 0}},
        {"type": "Window", "wall": 0, "offset": 1.5,
         "width": 2.0, "height": 1.8, "sill": 1.0},
    ])
    win = plan.elements[1]
    assert (win.data["offset"], win.data["width"],
            win.data["height"], win.data["sill"]) == (1.5, 2.0, 1.8, 1.0)


def test_opening_wall_reference_must_point_to_wall():
    # 序号 0 是柱，不是墙 → 交叉校验失败
    bad = [
        {"type": "Column", "x": 0, "y": 0},
        {"type": "Window", "wall": 0},
    ]
    assert _error_code(bad) == ErrorCode.INVALID_ARGUMENT


def test_opening_wall_index_out_of_range():
    assert _error_code([
        {"type": "Window", "wall": 5}
    ]) == ErrorCode.INVALID_ARGUMENT


def test_opening_missing_wall_rejected():
    assert _error_code([{"type": "Window"}]) == ErrorCode.INVALID_ARGUMENT


def test_opening_wall_wrong_type_rejected():
    # wall 既不是数字也不是字符串（如 list / bool）
    for bad_wall in [[0], True, None]:
        assert _error_code([{"type": "Door", "wall": bad_wall}]) \
            == ErrorCode.INVALID_ARGUMENT


def test_opening_empty_guid_rejected():
    assert _error_code([{"type": "Door", "wall": "   "}]) \
        == ErrorCode.INVALID_ARGUMENT


def test_opening_negative_offset_rejected():
    assert _error_code([
        {"type": "Window", "wall": "GUID-X", "offset": -0.1}
    ]) == ErrorCode.INVALID_ARGUMENT


def test_opening_zero_offset_allowed():
    """门窗正好在墙起点，offset 0 合法。"""
    plan = _plan([
        {"type": "Window", "wall": "GUID-X", "offset": 0}
    ])
    assert plan.elements[0].data["offset"] == 0


def test_opening_bad_width_or_sill_rejected():
    assert _error_code([
        {"type": "Window", "wall": "GUID-X", "width": 0}
    ]) == ErrorCode.INVALID_ARGUMENT
    assert _error_code([
        {"type": "Door", "wall": "GUID-X", "sill": -0.2}
    ]) == ErrorCode.INVALID_ARGUMENT


# --- 楼梯 / 屋顶 / 变形体（V0.3 新增）------------------------------------


def test_stair_defaults():
    plan = _plan([{"type": "Stair",
                   "start": {"x": 0, "y": 0}, "end": {"x": 4, "y": 0}}])
    d = plan.elements[0].data
    assert d["z"] == 0.0
    assert d["totalHeight"] == 3.0
    assert d["flightWidth"] == 1.2
    assert "steps" not in d


def test_stair_explicit_values_and_steps():
    plan = _plan([{"type": "Stair",
                   "start": {"x": 1, "y": 1}, "end": {"x": 5, "y": 1},
                   "z": 0.5, "totalHeight": 2.8, "flightWidth": 1.0,
                   "steps": 14}])
    d = plan.elements[0].data
    assert d["z"] == 0.5 and d["totalHeight"] == 2.8
    assert d["flightWidth"] == 1.0 and d["steps"] == 14


def test_stair_zero_length_rejected():
    assert _error_code([
        {"type": "Stair", "start": {"x": 0, "y": 0}, "end": {"x": 0, "y": 0}}
    ]) == ErrorCode.INVALID_ARGUMENT


def test_stair_bad_steps_rejected():
    for bad in (0, -1, True, 1.5):
        assert _error_code([
            {"type": "Stair",
             "start": {"x": 0, "y": 0}, "end": {"x": 4, "y": 0},
             "steps": bad}
        ]) == ErrorCode.INVALID_ARGUMENT


_ROOF_POLY = [{"x": 0, "y": 0}, {"x": 6, "y": 0},
              {"x": 6, "y": 4}, {"x": 0, "y": 4}]


def test_roof_defaults_multiplane():
    plan = _plan([{"type": "Roof", "polygon": _ROOF_POLY}])
    d = plan.elements[0].data
    assert d["level"] == 0.0 and d["thickness"] == 0.3
    assert "slope" not in d


def test_roof_slope_uses_default_pivot_edge():
    plan = _plan([{"type": "Roof", "polygon": _ROOF_POLY, "slope": 30}])
    d = plan.elements[0].data
    assert d["slope"] == 30.0
    assert "pivot" not in d  # 通道拼装时默认取多边形第 1 条边


def test_roof_slope_with_explicit_pivot():
    pivot = {"start": {"x": 0, "y": 2}, "end": {"x": 6, "y": 2}}
    plan = _plan([{"type": "Roof", "polygon": _ROOF_POLY,
                   "slope": 15, "pivot": pivot}])
    assert plan.elements[0].data["pivot"] == pivot


def test_roof_bad_slope_rejected():
    for bad in (0, 90, -5, 91, True):
        assert _error_code([
            {"type": "Roof", "polygon": _ROOF_POLY, "slope": bad}
        ]) == ErrorCode.INVALID_ARGUMENT


def test_roof_too_few_points_rejected():
    assert _error_code([
        {"type": "Roof",
         "polygon": [{"x": 0, "y": 0}, {"x": 1, "y": 0}]}
    ]) == ErrorCode.INVALID_ARGUMENT


def test_roof_pivot_without_slope_rejected():
    assert _error_code([
        {"type": "Roof", "polygon": _ROOF_POLY,
         "pivot": {"start": {"x": 0, "y": 2}, "end": {"x": 6, "y": 2}}}
    ]) == ErrorCode.INVALID_ARGUMENT


def test_morph_defaults_unit_box():
    plan = _plan([{"type": "Morph"}])
    d = plan.elements[0].data
    assert d["position"] == {"x": 0.0, "y": 0.0, "z": 0.0}
    assert d["size"] == {"x": 1.0, "y": 1.0, "z": 1.0}


def test_morph_explicit_values():
    plan = _plan([{"type": "Morph",
                   "position": {"x": 2, "y": 3, "z": 1},
                   "size": {"x": 2, "y": 1.5, "z": 0.5}}])
    d = plan.elements[0].data
    assert d["position"] == {"x": 2.0, "y": 3.0, "z": 1.0}
    assert d["size"] == {"x": 2.0, "y": 1.5, "z": 0.5}


def test_morph_bad_size_rejected():
    assert _error_code([
        {"type": "Morph", "size": {"x": 0, "y": 1, "z": 1}}
    ]) == ErrorCode.INVALID_ARGUMENT
    assert _error_code([
        {"type": "Morph", "size": "big"}
    ]) == ErrorCode.INVALID_ARGUMENT
