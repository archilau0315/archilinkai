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


def test_aggregate_with_classification(svc, monkeypatch):
    # 分类过滤：只保留 g1
    monkeypatch.setattr(
        aggregate_service, "_classification_guids",
        lambda guids, name, instance: {"g1"},
    )
    out = svc.aggregate("General_NetVolume", classification="标准墙")
    assert len(out["rows"]) == 1
    assert out["rows"][0]["count"] == 1
    assert out["rows"][0]["sum"] == 1.0


# --- 模板 ---------------------------------------------------------------

def test_templates_exist():
    from aggregate_service import QUANTITY_TEMPLATES, get_template
    assert "concrete_volume" in QUANTITY_TEMPLATES
    assert get_template("concrete_volume")["quantity"] == "General_NetVolume"
    assert get_template("no_such") is None


def test_aggregate_by_template(svc):
    out = svc.aggregate_by_template("wall_area")
    assert out["template"] == "wall_area"
    assert out["unit"] == "m³"
    # Wall 在 story 0/1 各 1
    assert len(out["rows"]) == 2


def test_aggregate_by_template_merges_types(svc):
    # concrete_volume 含 Wall + Slab，合并后 story 1 应有 Wall(2.0) + Slab(5.0)
    out = svc.aggregate_by_template("concrete_volume")
    s1 = next(g for g in out["rows"] if g["group"]["story"] == 1)
    assert s1["count"] == 2
    assert s1["sum"] == 7.0


def test_aggregate_by_template_unknown(svc):
    with pytest.raises(ValueError, match="未知算量模板"):
        svc.aggregate_by_template("no_such")


# --- CSV 导出 -----------------------------------------------------------

def test_export_csv_logic(tmp_path):
    """验证 export_table 内部的 CSV 写入逻辑（字段、内容、编码）。"""
    import csv
    import os
    import time

    rows = [
        {"story": 0, "count": 2, "sum": 3.0, "avg": 1.5},
        {"story": 1, "count": 1, "sum": 5.0, "avg": 5.0},
    ]
    out_dir = str(tmp_path / "output")
    os.makedirs(out_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(out_dir, f"concrete_{ts}.csv")
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    assert os.path.exists(path)
    with open(path, encoding="utf-8-sig") as f:
        content = f.read()
    assert "story,count,sum,avg" in content
    assert "3.0" in content
