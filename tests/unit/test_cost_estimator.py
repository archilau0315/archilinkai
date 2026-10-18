"""cost_estimator 细算引擎单测（V0.37）。"""

from __future__ import annotations

import pytest

from archibridge.cost_estimator import (
    CONSUMPTION,
    CostEstimator,
    estimate_from_flat_rows,
)


def _item(code="010502001", name="现浇混凝土矩形柱", unit="m³", qty=100.0):
    return {
        "code": code, "name": name, "unit": unit, "quantity": qty,
        "quota_code": None, "quota_name": None, "unit_price": None,
        "total_price": None, "labor_price": None, "material_price": None,
        "machine_price": None, "labor_qty": None, "material_items": None,
        "source": "test", "specs": {},
    }


def test_price_book_and_consumption_nonempty():
    assert len(CONSUMPTION) >= 15
    assert CONSUMPTION["010502001"]["labor_qty"] == 0.23


def test_estimate_item_concrete_column():
    est = CostEstimator()
    item = est.estimate_item(_item())
    # 人工：0.23 工日/m³ × 100 m³ × 130 元
    assert item["labor_qty"] == 23.0
    assert item["labor_price"] == pytest.approx(2990.0)
    # 材料：C30 1.015×100×380 = 38570；薄膜 0.5×100×0.8 = 40
    assert item["material_price"] == pytest.approx(38610.0)
    # 机械：振捣器 0.06×100×15 = 90
    assert item["machine_price"] == pytest.approx(90.0)
    assert item["total_price"] == pytest.approx(2990.0 + 38610.0 + 90.0)
    assert item["unit_price"] == pytest.approx(item["total_price"] / 100)
    # 材料明细展开
    names = [m["name"] for m in item["material_items"]]
    assert "C30 预拌混凝土" in names and "塑料薄膜" in names


def test_estimate_item_price_override():
    est = CostEstimator(price_overrides={"C30 预拌混凝土": 400.0})
    item = est.estimate_item(_item())
    assert item["material_price"] == pytest.approx(1.015 * 100 * 400.0 + 40.0)


def test_estimate_item_fallback_by_keyword():
    # 编码不在 CONSUMPTION，名称带"混凝土"走关键词兜底
    item = _item(code="999999999", name="异形混凝土构件")
    est = CostEstimator()
    out = est.estimate_item(item)
    assert out["total_price"] is not None
    assert out["total_price"] > 0


def test_estimate_item_uncovered_adds_note():
    item = _item(code="999999999", name="神秘工艺构件")
    est = CostEstimator()
    out = est.estimate_item(item)
    assert out["total_price"] is None
    assert any("无消耗量参考" in n for n in est.notes)


def test_labor_price_override():
    est = CostEstimator(labor_price=150.0)
    item = est.estimate_item(_item())
    assert item["labor_price"] == pytest.approx(0.23 * 100 * 150.0)


def test_estimate_table_summary_and_fees():
    est = CostEstimator()
    items = [_item(qty=100.0), _item(code="010505003", name="现浇混凝土板",
                                     qty=50.0)]
    table = est.estimate_table(items, "测试项目")
    s = table["summary"]
    direct = sum(i["total_price"] for i in table["items"])
    assert s["direct_cost"] == pytest.approx(round(direct, 2))
    assert s["management_fee"] == pytest.approx(
        round(direct * 0.05, 2))
    assert s["profit"] == pytest.approx(round(direct * 0.045, 2))
    expected_tax = round(
        (s["direct_cost"] + s["management_fee"] + s["profit"]) * 0.09, 2)
    assert s["tax"] == pytest.approx(expected_tax)
    assert s["total"] == pytest.approx(
        s["direct_cost"] + s["management_fee"] + s["profit"] + s["tax"])
    assert table["fee_rates"]["tax"] == 0.09
    assert table["labor_price"] == 130.0


def test_fee_overrides():
    est = CostEstimator(fee_overrides={"management_fee": 0.06})
    table = est.estimate_table([_item()], "测试")
    assert table["fee_rates"]["management_fee"] == 0.06


def test_estimate_from_flat_rows_pipeline(monkeypatch):
    # mock 清单聚合链（避免依赖 report_service 的真实数据）
    from archibridge.estimate_schema import aggregate_rows_to_estimate_items

    rows = [{
        "type_name": "柱", "story_name": "首层",
        "code": "010502001", "code_name": "现浇混凝土矩形柱",
        "code_unit": "m³", "sum": 100.0, "template": "column_concrete_volume",
    }]
    items = aggregate_rows_to_estimate_items(rows)
    assert items[0]["code"] == "010502001"
    assert items[0]["quantity"] == pytest.approx(100.0)

    table = estimate_from_flat_rows(rows, "办公楼改造")
    assert table["summary"]["direct_cost"] > 0
    assert table["project_name"] == "办公楼改造"
    assert len(table["items"]) == 1


def test_calc_mode_and_coverage():
    est = CostEstimator()
    items = [
        _item(),                                            # detailed
        _item(code="999999999", name="异形混凝土构件"),        # fallback
        _item(code="999999999", name="神秘工艺构件"),          # skipped
    ]
    table = est.estimate_table(items, "测试")
    modes = [i.get("calc_mode") for i in table["items"]]
    assert modes == ["detailed", "fallback", "skipped"]
    cov = table["coverage"]
    assert cov["detailed"] == 1
    assert cov["fallback"] == 1
    assert cov["skipped"] == 1
    assert cov["total"] == 3
    assert cov["coverage_pct"] == pytest.approx(66.7)
    # notes 含未覆盖提示
    assert any("无消耗量参考" in n for n in table["notes"])


def test_build_estimate_report(tmp_path):
    est = CostEstimator()
    table = est.estimate_table(
        [_item(qty=100.0),
         _item(code="010505003", name="现浇混凝土板", qty=50.0)], "办公楼改造")
    from archibridge.cost_estimator import build_estimate_report
    path = build_estimate_report(table, "v38_test", str(tmp_path))
    assert path.endswith(".xlsx")
    assert "v38_test_" in path

    from openpyxl import load_workbook
    wb = load_workbook(path)
    ws = wb.active
    assert ws.title == "成本概算表"
    assert ws.cell(1, 1).value == "工程成本概算表"
    assert "办公楼改造" in ws.cell(2, 1).value
    # 表头第 3 行
    assert ws.cell(3, 2).value == "项目编码"
    # 数据行第 4 行：柱
    assert ws.cell(4, 2).value == "010502001"
    # 直接费合计在数据行之后
    texts = [ws.cell(r, 1).value for r in range(4, 20)]
    assert "直接费合计" in texts
    assert "含税总价" in texts
    # 取费值与 summary 一致
    total_row = next(r for r in range(4, 20) if ws.cell(r, 1).value == "含税总价")
    assert ws.cell(total_row, 7).value == pytest.approx(
        table["summary"]["total"])


def test_build_estimate_report_empty_raises():
    from archibridge.cost_estimator import build_estimate_report
    with pytest.raises(ValueError):
        build_estimate_report({"items": [], "summary": {}}, "x", ".")
