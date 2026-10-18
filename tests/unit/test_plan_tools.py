"""lint_model_plan 单元测试。"""

from archibridge import server


class _MCP:
    """最小 FastMCP 替身：收集注册的工具。"""

    def __init__(self):
        self.tools = {}

    def tool(self):
        def deco(fn):
            self.tools[fn.__name__] = fn
            return fn
        return deco


def _get_lint():
    m = _MCP()
    server.plan_tools.register(m, server._safe)
    return m.tools["lint_model_plan"]


def test_lint_ok():
    r = _get_lint()({"elements": [
        {"type": "Wall", "start": {"x": 0, "y": 0}, "end": {"x": 6, "y": 0}},
        {"type": "Wall", "start": {"x": 6, "y": 0}, "end": {"x": 6, "y": 4}},
        {"type": "Window", "wall": 0, "offset": 3.0},
    ]})
    assert r["status"] == "success"
    assert r["data"]["ok"] is True
    assert r["count"] == 3
    assert r["data"]["types"] == {"Wall": 2, "Window": 1}


def test_lint_bad_plan():
    r = _get_lint()({"elements": [{"type": "Wall"}]})
    assert r["status"] == "error"
    assert r["error_code"] == "INVALID_ARGUMENT"
    assert "start" in r["message"] or "end" in r["message"]


def test_lint_empty_plan():
    r = _get_lint()({"elements": []})
    assert r["status"] == "error"
    assert r["error_code"] == "INVALID_ARGUMENT"


def test_lint_window_bad_wall_ref():
    r = _get_lint()({"elements": [
        {"type": "Window", "wall": 5, "offset": 1.0},
    ]})
    assert r["status"] == "error"
    assert r["error_code"] == "INVALID_ARGUMENT"


def test_lint_multi_plane_roof_holes():
    r = _get_lint()({"elements": [{
        "type": "Roof",
        "polygon": [{"x": 0, "y": 0}, {"x": 6, "y": 0}, {"x": 6, "y": 4}],
        "holes": [[{"x": 1, "y": 1}, {"x": 2, "y": 1}, {"x": 2, "y": 2}]],
    }]})
    assert r["status"] == "error"
    assert "多平面" in r["message"]


def test_lint_l_stair_ok():
    r = _get_lint()({"elements": [{
        "type": "Stair",
        "path": [{"x": 0, "y": 0}, {"x": 4, "y": 0}, {"x": 4, "y": 3}],
    }]})
    assert r["status"] == "success"
    assert r["data"]["types"] == {"Stair": 1}
