# -*- coding: utf-8 -*-
"""机电管线 MEPRoute（V0.14）单元测试。"""

import pytest

from errors import InvalidArgumentError
from model_plan import ModelPlan
from plan_preview import build_preview
from tapir_channel import _COMMAND, TapirChannel


def _route(element):
    return {"elements": [element]}


PATH = [
    {"x": 0, "y": 0, "z": 2.5},
    {"x": 5, "y": 0, "z": 2.5},
    {"x": 5, "y": 3, "z": 2.5},
]


# --- 计划校验 ---------------------------------------------------------------


def test_route_defaults():
    plan = ModelPlan.from_dict(_route(
        {"type": "MEPRoute", "domain": "Ventilation", "path": PATH}))
    d = plan.elements[0].data
    assert d["shape"] == "Rectangular"
    assert d["width"] == 0.3 and d["height"] == 0.2
    assert len(d["path"]) == 3


def test_route_piping_circular():
    plan = ModelPlan.from_dict(_route(
        {"type": "MEPRoute", "domain": "Piping",
         "path": [{"x": 0, "y": 0, "z": 1.0}, {"x": 4, "y": 0, "z": 1.0}],
         "shape": "Circular", "width": 0.1}))
    d = plan.elements[0].data
    assert d["shape"] == "Circular" and d["width"] == 0.1
    assert d["height"] == 0.2  # 缺省保留


def test_route_cable_carrier():
    plan = ModelPlan.from_dict(_route(
        {"type": "MEPRoute", "domain": "CableCarrier", "path": PATH,
         "width": 0.2, "height": 0.1}))
    assert plan.elements[0].data["domain"] == "CableCarrier"


def test_bad_domain():
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict(_route(
            {"type": "MEPRoute", "domain": "HVAC", "path": PATH}))


def test_missing_domain():
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict(_route({"type": "MEPRoute", "path": PATH}))


def test_too_few_nodes():
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict(_route(
            {"type": "MEPRoute", "domain": "Piping",
             "path": [{"x": 0, "y": 0, "z": 1}]}))


def test_bad_shape():
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict(_route(
            {"type": "MEPRoute", "domain": "Ventilation",
             "path": PATH, "shape": "Triangle"}))


def test_bad_width():
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict(_route(
            {"type": "MEPRoute", "domain": "Ventilation",
             "path": PATH, "width": 0}))


# --- 通道参数 ---------------------------------------------------------------


def test_command_mapping():
    assert _COMMAND["MEPRoute"] == (
        "CreateMEPRoutingElements", "routingElementsData")


def test_build_param():
    item = {"domain": "Ventilation", "shape": "Rectangular",
            "width": 0.4, "height": 0.25, "path": PATH}
    p = TapirChannel()._build_mep_route_param(item)
    assert p["domain"] == "Ventilation"
    assert p["nodeCoordinates"][1] == {"x": 5, "y": 0, "z": 2.5}
    assert p["crossSectionShape"] == "Rectangular"
    assert p["crossSectionWidth"] == 0.4
    assert p["crossSectionHeight"] == 0.25


# --- 预览 -------------------------------------------------------------------


def test_preview():
    plan = ModelPlan.from_dict(_route(
        {"type": "MEPRoute", "domain": "Ventilation", "path": PATH}))
    prev = build_preview(plan, "Tapir", "1.5.9")
    assert prev["counts"] == {"MEPRoute": 1}
    text = prev["elements"][0]["text"]
    assert "风管" in text and "3 个折点" in text
    assert "总长 8m" in text  # 5 + 3
    assert "标高 2.5~2.5m" in text
    assert "机电管线" in prev["risk"]


def test_preview_piping():
    plan = ModelPlan.from_dict(_route(
        {"type": "MEPRoute", "domain": "Piping",
         "path": [{"x": 0, "y": 0, "z": 1}, {"x": 4, "y": 0, "z": 1}],
         "shape": "Circular", "width": 0.1}))
    text = build_preview(plan)["elements"][0]["text"]
    assert "水管" in text and "圆形截面" in text
