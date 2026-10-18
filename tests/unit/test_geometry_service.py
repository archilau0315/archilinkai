"""geometry_service.py 单元测试：纯函数，固定 dict 输入验证规整结果。"""

import pytest

from archilinkai.geometry_service import summarize, summarize_all


# 墙的最小完整样本
WALL = {
    "guid": "g-1",
    "type": "Wall",
    "floorIndex": 0,
    "id": "SW - 001",
    "details": {
        "geometryType": "Straight",
        "structureType": "Composite",
        "zCoordinate": 0,
        "begCoordinate": {"x": 0.0, "y": 0.0},
        "endCoordinate": {"x": 4.0, "y": 3.0},
        "height": 3,
        "begThickness": 0.3,
        "endThickness": 0.3,
    },
    "floorPlanPolygons": [
        {"coordinates": [
            {"x": 0.0, "y": 0.0}, {"x": 4.0, "y": 0.0},
            {"x": 4.0, "y": 3.0}, {"x": 0.0, "y": 3.0},
        ]}
    ],
}


def test_wall_length_is_hypotenuse():
    # 3-4-5 直角三角形 → length=5
    out = summarize(WALL)
    assert out["summary"]["length"] == 5.0


def test_wall_summary_fields():
    s = summarize(WALL)["summary"]
    assert s["height"] == 3
    assert s["thickness_begin"] == 0.3
    assert s["thickness_end"] == 0.3
    assert s["structure_type"] == "Composite"


def test_points_and_elevation():
    out = summarize(WALL)
    assert out["base_point"] == {"x": 0.0, "y": 0.0, "z": 0.0}
    assert out["end_point"]["x"] == 4.0
    assert out["elevation"] == {"bottom": 0.0, "top": 3.0}


def test_bounding_box_from_polygons():
    bbox = summarize(WALL)["bounding_box"]
    assert bbox["min"] == {"x": 0.0, "y": 0.0, "z": 0.0}
    assert bbox["max"] == {"x": 4.0, "y": 3.0, "z": 3.0}
    assert bbox["size"] == {"x": 4.0, "y": 3.0, "z": 3.0}
    assert summarize(WALL)["polygon_count"] == 1


def test_curved_wall_no_length_guess():
    """曲墙不能用弦长冒充长度，length 字段应缺席（不报错）。"""
    curved = dict(WALL)
    curved["details"] = dict(WALL["details"], geometryType="Curved")
    out = summarize(curved)
    assert "length" not in out["summary"]


def test_missing_details_no_crash():
    """details 为空（非墙类型/取数不全）时仍返回基本信息，不抛异常。"""
    minimal = {"type": "Object", "floorIndex": 2, "id": "X", "details": {}}
    out = summarize(minimal)
    assert out["type"] == "Object"
    assert out["floor_index"] == 2
    assert "summary" not in out
    assert "bounding_box" not in out


def test_non_wall_element_bbox_only():
    """板类元素无 begCoordinate：不出起止点，但有多边形就能出包围盒。"""
    slab = {
        "type": "Slab", "floorIndex": 0, "id": "S-1",
        "details": {"zCoordinate": 0, "height": 0.2},
        "floorPlanPolygons": [{"coordinates": [
            {"x": 1.0, "y": 1.0}, {"x": 2.0, "y": 1.0},
            {"x": 2.0, "y": 2.0},
        ]}],
    }
    out = summarize(slab)
    assert "base_point" not in out
    assert out["bounding_box"]["size"] == {"x": 1.0, "y": 1.0, "z": 0.2}


def test_summarize_all_batch():
    out = summarize_all([WALL, WALL])
    assert len(out) == 2
