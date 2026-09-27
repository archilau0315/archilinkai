"""aggregate_service 单元测试：分组纯函数 + 服务层（mock 查询和取量）。"""

import pytest

import aggregate_service
from aggregate_service import AggregateService, _group


class TestGroup:
    def test_sum_by_type(self):
        rows = [
            {"type": "Wall", "Q": 1.0}, {"type": "Wall", "Q": 2.0},
            {"type": "Slab", "Q": 5.0},
        ]
        out = _group(rows, ["type"], "Q")
        assert len(out) == 2
        wall = next(g for g in out if g["group"]["type"] == "Wall")
        assert wall["count"] == 2
        assert wall["sum"] == 3.0
        assert wall["avg"] == 1.5

    def test_none_counts_but_not_sums(self):
        rows = [{"type": "Wall", "Q": 1.0}, {"type": "Wall", "Q": None}]
        out = _group(rows, ["type"], "Q")
        g = out[0]
        assert g["count"] == 2
        assert g["sum"] == 1.0
        assert g["skipped_none"] == 1
        assert g["avg"] == 1.0

    def test_all_none_avg_is_none(self):
        rows = [{"type": "Wall", "Q": None}]
        out = _group(rows, ["type"], "Q")
        assert out[0]["avg"] is None
        assert out[0]["sum"] == 0.0

    def test_multi_dim(self):
        rows = [
            {"type": "Wall", "story": 0, "Q": 1.0},
            {"type": "Wall", "story": 1, "Q": 2.0},
            {"type": "Wall", "story": 0, "Q": 3.0},
        ]
        out = _group(rows, ["type", "story"], "Q")
        assert len(out) == 2
        s0 = next(g for g in out if g["group"]["story"] == 0)
        assert s0["sum"] == 4.0

    def test_empty(self):
        assert _group([], ["type"], "Q") == []


@pytest.fixture()
def svc(monkeypatch):
    s = AggregateService()
    monkeypatch.setattr(
        aggregate_service.instance_manager.manager, "get_info",
        lambda instance=None: None,
    )
    _BASE = [
        {"guid": "g1", "element_type": "Wall", "story_index": 0},
        {"guid": "g2", "element_type": "Wall", "story_index": 1},
        {"guid": "g3", "element_type": "Slab", "story_index": 1},
    ]
    monkeypatch.setattr(
        aggregate_service, "_fetch_all",
        lambda req, instance: [
            r for r in _BASE if not req.element_type or r["element_type"] == req.element_type
        ],
    )

    class FakeProp:
        def get_quantities(self, guids, names, instance=None):
            v = {"g1": 1.0, "g2": 2.0, "g3": 5.0}
            return {
                g: {names[0]: {"value": v[g], "unit": "m³"}} for g in guids
            }

        def get_values(self, guids, names, instance=None):
            return {g: {} for g in guids}

    monkeypatch.setattr(aggregate_service.property_service, "service", FakeProp())
    return s


def test_aggregate_by_story(svc):
    out = svc.aggregate("General_NetVolume", ["story"], "Wall")
    assert out["unit"] == "m³"
    assert len(out["rows"]) == 2
    s1 = next(g for g in out["rows"] if g["group"]["story"] == 1)
    assert s1["sum"] == 2.0


def test_aggregate_by_type(svc):
    out = svc.aggregate("General_NetVolume")
    wall = next(g for g in out["rows"] if g["group"]["type"] == "Wall")
    assert wall["count"] == 2
    assert wall["sum"] == 3.0
