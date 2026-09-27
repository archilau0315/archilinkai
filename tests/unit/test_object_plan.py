# -*- coding: utf-8 -*-
"""对象/灯具（Object/Lamp，V0.11）单元测试：计划校验 + 通道参数 + 预览。"""

import pytest

from errors import InvalidArgumentError
from model_plan import ModelPlan
from plan_preview import build_preview
from tapir_channel import _COMMAND, TapirChannel


def _plan(element):
    return {"elements": [element]}


# --- 计划校验：合法 ---------------------------------------------------------


def test_object_defaults():
    """只给 name，坐标默认原点地面。"""
    plan = ModelPlan.from_dict(_plan({"type": "Object", "name": "沙发 01"}))
    data = plan.elements[0].data
    assert data["name"] == "沙发 01"
    assert (data["x"], data["y"], data["z"]) == (0.0, 0.0, 0.0)


def test_object_with_coords():
    plan = ModelPlan.from_dict(_plan(
        {"type": "Object", "name": "餐椅 01", "x": 2.5, "y": 3.0, "z": 0.0}))
    data = plan.elements[0].data
    assert (data["x"], data["y"], data["z"]) == (2.5, 3.0, 0.0)


def test_lamp_shares_builder():
    """Lamp 与 Object 共用同一校验，类型名保留。"""
    plan = ModelPlan.from_dict(_plan(
        {"type": "Lamp", "name": "吊灯 01", "z": 2.6}))
    e = plan.elements[0]
    assert e.type == "Lamp"
    assert e.data["name"] == "吊灯 01"
    assert e.data["z"] == 2.6


def test_name_stripped():
    plan = ModelPlan.from_dict(_plan({"type": "Object", "name": " 床 01 "}))
    assert plan.elements[0].data["name"] == "床 01"


# --- 计划校验：非法 ---------------------------------------------------------


def test_missing_name():
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict(_plan({"type": "Object", "x": 1, "y": 2}))


def test_blank_name():
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict(_plan({"type": "Object", "name": "   "}))


def test_non_string_name():
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict(_plan({"type": "Object", "name": 123}))


# --- 通道参数拼装 -----------------------------------------------------------


def test_command_mapping():
    assert _COMMAND["Object"] == ("CreateObjects", "objectsData")
    assert _COMMAND["Lamp"] == ("CreateLamps", "lampsData")


def test_build_param_object():
    item = {"name": "沙发 01", "x": 1.0, "y": 2.0, "z": 0.0}
    param = TapirChannel()._build_param("Object", item)
    assert param == {
        "libraryPartName": "沙发 01",
        "coordinates": {"x": 1.0, "y": 2.0, "z": 0.0},
    }


def test_build_param_lamp():
    item = {"name": "吊灯 01", "x": 1.0, "y": 2.0, "z": 2.6}
    param = TapirChannel()._build_param("Lamp", item)
    assert param == {
        "libraryPartName": "吊灯 01",
        "coordinates": {"x": 1.0, "y": 2.0, "z": 2.6},
    }


# --- 预览 -------------------------------------------------------------------


def test_preview_describe():
    plan = ModelPlan.from_dict(_plan(
        {"type": "Object", "name": "沙发 01", "x": 1.5, "y": 2.5}))
    preview = build_preview(plan, "Tapir", "1.5.9")
    assert preview["counts"] == {"Object": 1}
    assert "沙发 01" in preview["elements"][0]["text"]
    assert "1.5,2.5,0" in preview["elements"][0]["text"]
    assert "库里的部件名" in preview["risk"]
