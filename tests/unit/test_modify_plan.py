"""modify_plan.py 单元测试：修改计划解析与校验。"""

import pytest

from archilinkai.errors import InvalidArgumentError
from archilinkai.modify_plan import ModifyPlan, MAX_ITEMS


def _wall(guid="G-1", **changes):
    return {"type": "Wall", "guid": guid, **changes}


# --- 合法计划 ---------------------------------------------------------------


def test_minimal_plan_ok():
    plan = ModifyPlan.from_dict({"items": [_wall(height=4.0)]})
    assert len(plan.items) == 1
    assert plan.items[0].changes == {"height": 4.0}
    assert plan.instance is None


def test_instance_passed_through():
    plan = ModifyPlan.from_dict({
        "instance": "ac29-1",
        "items": [{"type": "Window", "guid": "w1", "width": 1.5}],
    })
    assert plan.instance == "ac29-1"


def test_blank_guid_trimmed():
    plan = ModifyPlan.from_dict({"items": [_wall(guid="  g1  ", height=3.5)]})
    assert plan.items[0].guid == "g1"


def test_types_used_dedup_and_order():
    plan = ModifyPlan.from_dict({"items": [
        _wall(guid="a", height=3.0),
        {"type": "Column", "guid": "b", "x": 1.0, "y": 2.0},
        _wall(guid="c", thickness=0.3),
    ]})
    assert plan.types_used() == ["Wall", "Column"]


# --- 结构错误 ---------------------------------------------------------------


def test_items_must_be_nonempty_list():
    with pytest.raises(InvalidArgumentError):
        ModifyPlan.from_dict({"items": []})
    with pytest.raises(InvalidArgumentError):
        ModifyPlan.from_dict({})


def test_too_many_items():
    items = [_wall(guid=f"g{i}", height=3.0) for i in range(MAX_ITEMS + 1)]
    with pytest.raises(InvalidArgumentError):
        ModifyPlan.from_dict({"items": items})


def test_unknown_type_rejected():
    with pytest.raises(InvalidArgumentError):
        ModifyPlan.from_dict({"items": [{"type": "Slab", "guid": "g"}]})


def test_bad_guid_rejected():
    with pytest.raises(InvalidArgumentError):
        ModifyPlan.from_dict({"items": [_wall(guid="", height=3.0)]})
    with pytest.raises(InvalidArgumentError):
        ModifyPlan.from_dict({"items": [_wall(guid=123, height=3.0)]})


def test_no_changes_rejected():
    with pytest.raises(InvalidArgumentError):
        ModifyPlan.from_dict({"items": [_wall()]})


def test_unknown_field_rejected():
    with pytest.raises(InvalidArgumentError):
        ModifyPlan.from_dict({"items": [_wall(height=3.0, color="red")]})


# --- 数值规则 ---------------------------------------------------------------


def test_non_positive_rejected():
    with pytest.raises(InvalidArgumentError):
        ModifyPlan.from_dict({"items": [_wall(height=0)]})
    with pytest.raises(InvalidArgumentError):
        ModifyPlan.from_dict({"items": [_wall(thickness=-0.2)]})


def test_negative_sill_rejected():
    with pytest.raises(InvalidArgumentError):
        ModifyPlan.from_dict({
            "items": [{"type": "Door", "guid": "d", "sill": -0.01}]
        })


def test_bool_not_a_number():
    with pytest.raises(InvalidArgumentError):
        ModifyPlan.from_dict({"items": [_wall(height=True)]})


# --- 点与配对规则 -----------------------------------------------------------


def test_wall_point_must_have_xy():
    with pytest.raises(InvalidArgumentError):
        ModifyPlan.from_dict({"items": [_wall(start={"x": 1.0})]})


def test_wall_single_endpoint_allowed():
    """只挪一个端点是正常操作，点给全即可。"""
    plan = ModifyPlan.from_dict({
        "items": [_wall(end={"x": 5.0, "y": 0.0})]
    })
    assert plan.items[0].changes["end"] == {"x": 5.0, "y": 0.0}


def test_wall_start_equals_end_rejected():
    with pytest.raises(InvalidArgumentError):
        ModifyPlan.from_dict({"items": [
            _wall(start={"x": 1.0, "y": 2.0},
                  end={"x": 1.0, "y": 2.0})
        ]})


def test_column_xy_must_come_together():
    with pytest.raises(InvalidArgumentError):
        ModifyPlan.from_dict({"items": [
            {"type": "Column", "guid": "c", "x": 1.0}
        ]})
    with pytest.raises(InvalidArgumentError):
        ModifyPlan.from_dict({"items": [
            {"type": "Column", "guid": "c", "y": 1.0}
        ]})


def test_column_translate_ok():
    plan = ModifyPlan.from_dict({"items": [
        {"type": "Column", "guid": "c", "x": 1.0, "y": 2.0}
    ]})
    assert plan.items[0].changes == {"x": 1.0, "y": 2.0}


def test_column_section_fields_ok():
    plan = ModifyPlan.from_dict({"items": [
        {"type": "Column", "guid": "c", "width": 0.4, "depth": 0.5}
    ]})
    assert plan.items[0].changes == {"width": 0.4, "depth": 0.5}


# --- 梁 / 板 / 屋顶 ---------------------------------------------------------


def test_beam_endpoint_modify():
    plan = ModifyPlan.from_dict({"items": [
        {"type": "Beam", "guid": "b",
         "start": {"x": 0.0, "y": 0.0},
         "end": {"x": 5.0, "y": 0.0}, "height": 0.4}
    ]})
    assert plan.items[0].changes == {
        "start": {"x": 0.0, "y": 0.0},
        "end": {"x": 5.0, "y": 0.0}, "height": 0.4,
    }


def test_beam_point_needs_xy():
    with pytest.raises(InvalidArgumentError):
        ModifyPlan.from_dict({"items": [
            {"type": "Beam", "guid": "b", "start": {"x": 1.0}}
        ]})


def test_beam_start_equals_end_rejected():
    with pytest.raises(InvalidArgumentError):
        ModifyPlan.from_dict({"items": [
            {"type": "Beam", "guid": "b",
             "start": {"x": 1.0, "y": 1.0},
             "end": {"x": 1.0, "y": 1.0}}
        ]})


def test_slab_level_and_thickness():
    plan = ModifyPlan.from_dict({"items": [
        {"type": "Slab", "guid": "s", "level": -0.1, "thickness": 0.25}
    ]})
    # 标高允许负数（下沉板）
    assert plan.items[0].changes == {"level": -0.1, "thickness": 0.25}


def test_roof_thickness_and_eaves():
    plan = ModifyPlan.from_dict({"items": [
        {"type": "Roof", "guid": "r",
         "thickness": 0.3, "eavesOverhang": 0.6}
    ]})
    assert plan.items[0].changes == {"thickness": 0.3, "eavesOverhang": 0.6}


def test_beam_relative_level_field_rejected():
    """梁不开放相对楼层位移 level。"""
    with pytest.raises(InvalidArgumentError):
        ModifyPlan.from_dict({"items": [
            {"type": "Beam", "guid": "b", "level": 1.0}
        ]})
