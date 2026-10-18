"""tapir_channel 修改链路单元测试（V0.4）。

真机命令执行留给集成测试；这里只测：
- 业务 {guid, changes} → Tapir Modify 入参
- executionResults 行 → CreateResult
"""

from archibridge.channel_base import CreateResult
from archibridge.tapir_channel import TapirChannel
import pytest


@pytest.fixture
def ch():
    return TapirChannel()


def test_wall_full_modify_param(ch):
    p = ch._build_modify_param("Wall", {
        "guid": "g1",
        "changes": {
            "start": {"x": 1.0, "y": 2.0},
            "end": {"x": 3.0, "y": 2.0},
            "height": 4.0, "thickness": 0.3,
        },
    })
    assert p == {
        "elementId": {"guid": "g1"},
        "begCoordinate": {"x": 1.0, "y": 2.0},
        "endCoordinate": {"x": 3.0, "y": 2.0},
        "height": 4.0, "thickness": 0.3,
    }


def test_wall_partial_modify_param(ch):
    """只改高度时不带坐标字段。"""
    p = ch._build_modify_param(
        "Wall", {"guid": "g1", "changes": {"height": 4.0}}
    )
    assert p == {"elementId": {"guid": "g1"}, "height": 4.0}


def test_column_translate_param(ch):
    p = ch._build_modify_param("Column", {
        "guid": "c1",
        "changes": {"x": 1.0, "y": 2.0, "height": 3.5},
    })
    assert p == {
        "elementId": {"guid": "c1"},
        "origin": {"x": 1.0, "y": 2.0},
        "height": 3.5,
    }


def test_column_section_param(ch):
    p = ch._build_modify_param("Column", {
        "guid": "c1",
        "changes": {"width": 0.4, "depth": 0.5},
    })
    assert p == {
        "elementId": {"guid": "c1"},
        "width": 0.4, "depth": 0.5,
    }


def test_opening_modify_param(ch):
    p = ch._build_modify_param("Window", {
        "guid": "w1",
        "changes": {"width": 1.5, "height": 1.8, "sill": 1.0},
    })
    assert p == {
        "elementId": {"guid": "w1"},
        "width": 1.5, "height": 1.8, "sillHeight": 1.0,
    }


def test_parse_success_row(ch):
    result = ch._parse_modify_row({"success": True})
    assert isinstance(result, CreateResult)
    assert result.ok and result.error is None


def test_parse_failure_row(ch):
    result = ch._parse_modify_row({
        "success": False,
        "error": {"code": -1, "message": "No wall fields to modify."},
    })
    assert not result.ok
    assert result.error == "No wall fields to modify."


def test_parse_garbage_row(ch):
    result = ch._parse_modify_row("nope")
    assert not result.ok


# --- 梁 / 板 / 屋顶拼装 -----------------------------------------------------


def test_beam_modify_param(ch):
    p = ch._build_modify_param("Beam", {
        "guid": "b1",
        "changes": {
            "start": {"x": 0.0, "y": 1.0},
            "end": {"x": 5.0, "y": 1.0},
            "width": 0.2, "height": 0.4,
        },
    })
    assert p == {
        "elementId": {"guid": "b1"},
        "begCoordinate": {"x": 0.0, "y": 1.0},
        "endCoordinate": {"x": 5.0, "y": 1.0},
        "width": 0.2, "height": 0.4,
    }


def test_slab_modify_param(ch):
    p = ch._build_modify_param("Slab", {
        "guid": "s1",
        "changes": {"level": 3.0, "thickness": 0.25},
    })
    assert p == {
        "elementId": {"guid": "s1"},
        "zCoordinate": 3.0, "thickness": 0.25,
    }


def test_roof_modify_param(ch):
    p = ch._build_modify_param("Roof", {
        "guid": "r1",
        "changes": {"thickness": 0.3, "eavesOverhang": 0.6},
    })
    assert p == {
        "elementId": {"guid": "r1"},
        "thickness": 0.3, "eavesOverhang": 0.6,
    }
