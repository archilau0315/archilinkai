# -*- coding: utf-8 -*-
"""变形体任意形状（MorphBody）单元测试：计划校验 + 通道参数。"""

import pytest

from errors import InvalidArgumentError
from model_plan import ModelPlan
from tapir_channel import TapirChannel


# 一个四面体：底面三角 + 顶点，4 顶点 4 面
TETRA = {
    "solid": True,
    "vertices": [
        {"x": 0, "y": 0, "z": 0},
        {"x": 1, "y": 0, "z": 0},
        {"x": 0, "y": 1, "z": 0},
        {"x": 0, "y": 0, "z": 1},
    ],
    "faces": [[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]],
}


def _body_plan(body, position=None):
    el = {"type": "Morph", "body": body}
    if position:
        el["position"] = position
    return {"elements": [el]}


# --- 计划校验：合法 ---------------------------------------------------------


def test_tetra_body_ok():
    plan = ModelPlan.from_dict(_body_plan(TETRA))
    data = plan.elements[0].data
    assert "body" in data and "size" not in data
    assert len(data["body"]["vertices"]) == 4
    assert len(data["body"]["faces"]) == 4
    assert data["body"]["solid"] is True


def test_open_surface_minimum():
    """开放曲面：2+ 顶点 1 面即可。"""
    body = {
        "vertices": [
            {"x": 0, "y": 0, "z": 0},
            {"x": 1, "y": 0, "z": 0},
            {"x": 0, "y": 1, "z": 0},
        ],
        "faces": [[0, 1, 2]],
    }
    plan = ModelPlan.from_dict(_body_plan(body))
    assert plan.elements[0].data["body"]["solid"] is False


def test_body_with_position():
    plan = ModelPlan.from_dict(
        _body_plan(TETRA, position={"x": 10, "y": 10, "z": 0})
    )
    p = plan.elements[0].data["position"]
    assert p["x"] == 10 and p["y"] == 10


# --- 计划校验：错误 ---------------------------------------------------------


def test_size_and_body_mutex():
    el = {"type": "Morph", "size": {"x": 1, "y": 1, "z": 1},
          "body": TETRA}
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict({"elements": [el]})


def test_body_vertices_required():
    bad = {"faces": [[0, 1, 2]]}
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict(_body_plan(bad))


def test_body_faces_nonempty():
    bad = {"vertices": TETRA["vertices"], "faces": []}
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict(_body_plan(bad))


def test_solid_needs_four_vertices_and_faces():
    # 顶点够 4 个但面只有 1 个
    bad = {"solid": True, "vertices": TETRA["vertices"],
           "faces": [[0, 1, 2]]}
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict(_body_plan(bad))


def test_open_surface_needs_two_vertices():
    bad = {"vertices": [{"x": 0, "y": 0, "z": 0}],
           "faces": []}
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict(_body_plan(bad))


def test_face_index_out_of_range():
    bad = {
        "vertices": TETRA["vertices"],
        "faces": [[0, 1, 9]],
    }
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict(_body_plan(bad))


def test_face_needs_three_indices():
    bad = {"vertices": TETRA["vertices"], "faces": [[0, 1]]}
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict(_body_plan(bad))


def test_face_bool_index_rejected():
    body = {
        "vertices": TETRA["vertices"],
        "faces": [[0, 1, True]],
    }
    with pytest.raises(InvalidArgumentError):
        ModelPlan.from_dict(_body_plan(body))


# --- 通道参数 ---------------------------------------------------------------


def test_channel_body_param():
    ch = TapirChannel()
    item = {"position": {"x": 5, "y": 6, "z": 0}, "body": {
        "solid": True,
        "vertices": TETRA["vertices"],
        "faces": TETRA["faces"],
    }}
    p = ch._build_param("Morph", item)
    assert p["basePoint"] == {"x": 5, "y": 6, "z": 0}
    body = p["body"]
    assert body["bodyType"] == "Solid"
    assert len(body["vertices"]) == 4
    assert body["polygons"][0] == {"vertexIds": [0, 2, 1]}
    assert "size" not in p


def test_channel_box_still_works():
    ch = TapirChannel()
    item = {"position": {"x": 0, "y": 0, "z": 0},
            "size": {"x": 1, "y": 1, "z": 1}}
    p = ch._build_param("Morph", item)
    assert p["size"] == {"x": 1, "y": 1, "z": 1}
    assert "body" not in p
