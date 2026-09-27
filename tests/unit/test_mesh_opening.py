# -*- coding: utf-8 -*-
"""网面 Mesh / 独立洞口 Opening（V1.12）单元测试。"""

import pytest

from errors import InvalidArgumentError
from model_plan import ModelPlan
from plan_preview import build_preview
from tapir_channel import _COMMAND, TapirChannel


def _plan(element):
    return {"elements": [element]}


SQUARE = [
    {"x": 0, "y": 0}, {"x": 5, "y": 0},
    {"x": 5, "y": 5}, {"x": 0, "y": 5},
]


# --- Mesh 计划校验 ----------------------------------------------------------


def test_mesh_flat():
    """2D 点建平面网面，z 全 0。"""
    plan = ModelPlan.from_dict(_plan({"type": "Mesh", "polygon": SQUARE}))
    d = plan.elements[0].data
    assert d["level"] == 0.0
    assert [p["z"] for p in d["polygon"]] == [0.0] * 4


def test_mesh_with_height():
    """边界点带 z：起伏网面。"""
    poly = [
        {"x": 0, "y": 0, "z": 0}, {"x": 5, "y": 0, "z": 0},
        {"x": 5, "y": 5, "z": 2}, {"x": 0, "y": 5, "z": 2},
    ]
    plan = ModelPlan.from_dict(
        _plan({"type": "Mesh", "polygon": poly, "level": 1.0}))
    d = plan.elements[0].data
    assert d["level"] == 1.0
    assert [p["z"] for p in d["polygon"]] == [0.0, 0.0, 2.0, 2.0]


def test_mesh_holes_sublines():
    plan = ModelPlan.from_dict(_plan({
        "type": "Mesh", "polygon": SQUARE,
        "holes": [[{"x": 2, "y": 2, "z": 0.5},
                  {"x": 3, "y": 2}, {"x": 3, "y": 3}]],
        "sublines": [[{"x": 1, "y": 1, "z": 0.3},
                     {"x": 4, "y": 1, "z": 0.3}]],
    }))
    d = plan.elements[0].data
    assert d["holes"][0][0]["z"] == 0.5
    assert len(d["sublines"][0]) == 2


def test_mesh_missing_polygon():
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict(_plan({"type": "Mesh", "level": 0}))


def test_mesh_too_few_points():
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict(
            _plan({"type": "Mesh",
                   "polygon": [{"x": 0, "y": 0}, {"x": 1, "y": 1}]}))


def test_mesh_bad_subline():
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict(_plan(
            {"type": "Mesh", "polygon": SQUARE, "sublines": [[]]}))


# --- Opening 计划校验 -------------------------------------------------------


def test_opening_int_host():
    plan = ModelPlan.from_dict({"elements": [
        {"type": "Slab", "polygon": SQUARE, "level": 0},
        {"type": "Opening", "host": 0,
         "basePoint": {"x": 1, "y": 0, "z": 0}},
    ]})
    d = plan.elements[1].data
    assert d["host"] == 0
    assert d["width"] == 1.0 and d["height"] == 2.0


def test_opening_str_host():
    plan = ModelPlan.from_dict(_plan(
        {"type": "Opening", "host": "ABCD-1234",
         "basePoint": {"x": 1, "y": 1, "z": 0},
         "width": 0.9, "height": 2.1}))
    d = plan.elements[0].data
    assert d["host"] == "ABCD-1234"
    assert (d["width"], d["height"]) == (0.9, 2.1)


def test_opening_bad_host():
    for bad in (None, True, 1.5, "", "   "):
        with pytest.raises(InvalidArgumentError):
            ModelPlan.from_dict(_plan(
                {"type": "Opening", "host": bad,
                 "basePoint": {"x": 0, "y": 0, "z": 0}}))


def test_opening_negative_index():
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict(_plan(
            {"type": "Opening", "host": -1,
             "basePoint": {"x": 0, "y": 0, "z": 0}}))


def test_opening_missing_basepoint():
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict(_plan({"type": "Opening", "host": 0}))


def test_opening_host_type_rule():
    """序号引用：Slab 可以；Door 不允许。"""
    plan_ok = {"elements": [
        {"type": "Slab", "polygon": SQUARE, "level": 0},
        {"type": "Opening", "host": 0,
         "basePoint": {"x": 1, "y": 1, "z": 0}},
    ]}
    ModelPlan.from_dict(plan_ok)
    plan_bad = {"elements": [
        {"type": "Door", "wall": 1, "offset": 0.5},
        {"type": "Wall", "start": {"x": 0, "y": 0}, "end": {"x": 3, "y": 0}},
        {"type": "Opening", "host": 0,
         "basePoint": {"x": 1, "y": 1, "z": 0}},
    ]}
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict(plan_bad)


def test_opening_host_out_of_range():
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict(_plan(
            {"type": "Opening", "host": 9,
             "basePoint": {"x": 0, "y": 0, "z": 0}}))


# --- 通道参数拼装 -----------------------------------------------------------


def test_command_mapping():
    assert _COMMAND["Mesh"] == ("CreateMeshes", "meshesData")
    assert _COMMAND["Opening"] == ("CreateOpenings", "openingsData")


def test_build_param_mesh():
    item = {"polygon": [{"x": 0, "y": 0, "z": 0},
                        {"x": 5, "y": 0, "z": 0},
                        {"x": 5, "y": 5, "z": 1}],
            "level": 0.0,
            "holes": [[{"x": 2, "y": 2, "z": 0},
                      {"x": 3, "y": 2, "z": 0}, {"x": 3, "y": 3, "z": 0}]],
            "sublines": [[{"x": 1, "y": 1, "z": 0.5}]]}
    p = TapirChannel()._build_param("Mesh", item)
    assert p["polygonCoordinates"][2] == {"x": 5, "y": 5, "z": 1}
    assert p["holes"][0]["polygonCoordinates"][0]["z"] == 0
    assert p["sublines"][0]["coordinates"][0]["z"] == 0.5
    assert p["level"] == 0.0


def test_build_param_opening():
    item = {"ownerGuid": "G-1",
            "basePoint": {"x": 1, "y": 2, "z": 0},
            "width": 0.9, "height": 2.1}
    p = TapirChannel()._build_param("Opening", item)
    assert p == {
        "ownerElementId": {"guid": "G-1"},
        "basePoint": {"x": 1, "y": 2, "z": 0},
        "width": 0.9, "height": 2.1,
    }


# --- 预览 -------------------------------------------------------------------


def test_preview():
    plan = ModelPlan.from_dict(_plan({
        "type": "Mesh", "polygon": SQUARE,
        "sublines": [[{"x": 1, "y": 1, "z": 0.2}]]}))
    prev = build_preview(plan, "Tapir", "1.5.9")
    assert prev["counts"] == {"Mesh": 1}
    text = prev["elements"][0]["text"]
    assert "4 个顶点" in text and "1 条等高线" in text
    assert "网面" in prev["risk"]


def test_preview_opening():
    plan = ModelPlan.from_dict({"elements": [
        {"type": "Slab", "polygon": SQUARE, "level": 0},
        {"type": "Opening", "host": 0,
         "basePoint": {"x": 1, "y": 0, "z": 0.5}},
    ]})
    prev = build_preview(plan)
    text = prev["elements"][1]["text"]
    assert "计划构件#0" in text and "1×2m" in text
