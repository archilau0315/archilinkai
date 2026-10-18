# -*- coding: utf-8 -*-
"""房间区域 Zone（V0.13）单元测试。"""

import pytest

from archilinkai.errors import InvalidArgumentError
from archilinkai.model_plan import ModelPlan
from archilinkai.plan_preview import build_preview
from archilinkai.tapir_channel import _COMMAND, TapirChannel


def _zone(element):
    return {"elements": [element]}


SQUARE = [
    {"x": 0, "y": 0}, {"x": 4, "y": 0},
    {"x": 4, "y": 3}, {"x": 0, "y": 3},
]


# --- 计划校验 ---------------------------------------------------------------


def test_zone_polygon():
    plan = ModelPlan.from_dict(_zone(
        {"type": "Zone", "name": "客厅", "polygon": SQUARE}))
    d = plan.elements[0].data
    assert d["name"] == "客厅"
    assert d["number"] == "1"  # 缺省编号=序号+1
    assert len(d["polygon"]) == 4


def test_zone_reference_point():
    plan = ModelPlan.from_dict(_zone(
        {"type": "Zone", "name": "卧室", "number": "R1",
         "referencePoint": {"x": 2, "y": 2}}))
    d = plan.elements[0].data
    assert d["number"] == "R1"
    assert d["referencePoint"] == {"x": 2.0, "y": 2.0}


def test_zone_category_stamp():
    plan = ModelPlan.from_dict(_zone(
        {"type": "Zone", "name": "厨房", "polygon": SQUARE,
         "category": "CAT-GUID-1",
         "stamp": {"x": 2, "y": 1.5}}))
    d = plan.elements[0].data
    assert d["category"] == "CAT-GUID-1"
    assert d["stamp"] == {"x": 2.0, "y": 1.5}


def test_zone_missing_name():
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict(_zone(
            {"type": "Zone", "polygon": SQUARE}))


def test_zone_both_geometries():
    """两种几何同时给：报错。"""
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict(_zone(
            {"type": "Zone", "name": "x",
             "polygon": SQUARE,
             "referencePoint": {"x": 1, "y": 1}}))


def test_zone_no_geometry():
    """两种几何都不给：报错。"""
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict(_zone(
            {"type": "Zone", "name": "x"}))


def test_zone_short_polygon():
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict(_zone(
            {"type": "Zone", "name": "x",
             "polygon": [{"x": 0, "y": 0}, {"x": 1, "y": 1}]}))


def test_zone_bad_category():
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict(_zone(
            {"type": "Zone", "name": "x", "polygon": SQUARE,
             "category": "  "}))


# --- 通道参数 ---------------------------------------------------------------


def test_command_mapping():
    assert _COMMAND["Zone"] == ("CreateZones", "zonesData")


def test_build_param_polygon():
    item = {"name": "客厅", "number": "1",
            "polygon": [{"x": 0, "y": 0}, {"x": 4, "y": 0},
                        {"x": 4, "y": 3}, {"x": 0, "y": 3}],
            "category": "C1", "stamp": {"x": 2, "y": 1.5}}
    p = TapirChannel()._build_zone_param(item)
    assert p["name"] == "客厅"
    assert p["numberStr"] == "1"
    assert p["geometry"]["polygonCoordinates"][1] == {"x": 4, "y": 0}
    assert p["categoryAttributeId"] == {"guid": "C1"}
    assert p["stampPosition"] == {"x": 2, "y": 1.5}


def test_build_param_reference():
    item = {"name": "卧室", "number": "2",
            "referencePoint": {"x": 2.5, "y": 1.5}}
    p = TapirChannel()._build_zone_param(item)
    assert p["geometry"] == {
        "referencePosition": {"x": 2.5, "y": 1.5}}
    assert "categoryAttributeId" not in p


# --- 预览 -------------------------------------------------------------------


def test_preview_polygon():
    plan = ModelPlan.from_dict(_zone(
        {"type": "Zone", "name": "客厅", "polygon": SQUARE}))
    prev = build_preview(plan, "Tapir", "1.5.9")
    assert prev["counts"] == {"Zone": 1}
    text = prev["elements"][0]["text"]
    assert "客厅" in text and "手动轮廓 4 点" in text
    assert "房间区域" in prev["risk"]


def test_preview_reference():
    plan = ModelPlan.from_dict(_zone(
        {"type": "Zone", "name": "卧室",
         "referencePoint": {"x": 2, "y": 2}}))
    text = build_preview(plan)["elements"][0]["text"]
    assert "自动识别" in text and "2,2" in text
