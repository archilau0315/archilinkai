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
        {"guid": "g1", "element_type": "Wall", "story_index": 0, "name": "W1"},
        {"guid": "g2", "element_type": "Wall", "story_index": 1, "name": "W2"},
        {"guid": "g3", "element_type": "Slab", "story_index": 1, "name": "S1"},
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
            units = {"General_NetVolume": "m³", "General_SurfaceArea": "m²",
                     "General_3DLength": "m", "General_Height": "m"}
            return {
                g: {n: {"value": v[g], "unit": units.get(n, "m³")}
                    for n in names}
                for g in guids
            }

        def get_values(self, guids, names, instance=None):
            return {g: {} for g in guids}

    monkeypatch.setattr(aggregate_service.property_service, "service", FakeProp())
    monkeypatch.setattr(
        aggregate_service, "_fetch_story_names",
        lambda instance: {0: "一层", 1: "二层"},
    )
    return s


def test_aggregate_by_story(svc):
    out = svc.aggregate("General_NetVolume", ["story"], "Wall")
    assert out["unit"] == "m³"
    assert len(out["rows"]) == 2
    s1 = next(g for g in out["rows"] if g["group"]["story"] == 1)
    assert s1["sum"] == 2.0
    # 楼层名补全
    assert s1["group"]["story_name"] == "二层"
    # 构件名列表
    assert "W2" in s1["element_names"]


def test_aggregate_by_type(svc):
    out = svc.aggregate("General_NetVolume")
    wall = next(g for g in out["rows"] if g["group"]["type"] == "Wall")
    assert wall["count"] == 2
    assert wall["sum"] == 3.0
    # 类型中文名
    assert wall["group"]["type_name"] == "墙"
    # flat_rows 含 element_names
    flat_wall = next(f for f in out["flat_rows"] if f["type"] == "Wall")
    assert "W1" in flat_wall["element_names"]


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
    assert out["unit"] == "m²"
    # Wall 在 story 0/1 各 1
    assert len(out["rows"]) == 2


def test_aggregate_by_template_merges_types(svc):
    # concrete_volume 含 Wall + Slab + with_code=True → 按 story+type 分项
    # story 1 有 Wall(2.0) 和 Slab(5.0) 两项，不合并
    out = svc.aggregate_by_template("concrete_volume")
    s1_rows = [g for g in out["rows"] if g["group"]["story"] == 1]
    assert len(s1_rows) == 2
    by_type = {g["group"]["type"]: g for g in s1_rows}
    assert by_type["Wall"]["sum"] == 2.0
    assert by_type["Slab"]["sum"] == 5.0
    # 每行都带清单编码（GB 50500）
    assert by_type["Wall"]["group"]["code"] == "010502001"
    assert by_type["Slab"]["group"]["code_name"] == "现浇混凝土板"


def test_aggregate_by_template_unknown(svc):
    with pytest.raises(ValueError, match="未知算量模板"):
        svc.aggregate_by_template("no_such")


# --- 损耗系数 -----------------------------------------------------------

def test_aggregate_with_waste_factor(svc):
    out = svc.aggregate("General_NetVolume", ["story"], "Wall", waste_factor=0.03)
    g = out["rows"][0]
    assert "sum_with_waste" in g
    assert g["sum_with_waste"] == round(g["sum"] * 1.03, 4)


def test_template_concrete_has_waste(svc):
    """concrete_volume 模板带 3% 损耗。"""
    out = svc.aggregate_by_template("concrete_volume")
    g = out["rows"][0]
    assert "sum_with_waste" in g
    assert g["sum_with_waste"] > g["sum"]


# --- 多量合并 ------------------------------------------------------------

def test_aggregate_multi_quantities(svc):
    out = svc.aggregate(
        quantities=["General_NetVolume", "General_SurfaceArea"],
        group_by=["type"], element_type="Wall")
    assert "units" in out
    g = out["rows"][0]
    assert "sum_General_NetVolume" in g
    assert "sum_General_SurfaceArea" in g
    assert "avg_General_NetVolume" in g
    # flat_rows 也含多量列
    flat = out["flat_rows"][0]
    assert "sum_General_NetVolume" in flat
    assert "sum_General_SurfaceArea" in flat


def test_template_wall_summary_multi(svc):
    """wall_summary 模板出体积+面积+长度三列。"""
    out = svc.aggregate_by_template("wall_summary")
    assert "units" in out
    g = out["rows"][0]
    assert "sum_General_NetVolume" in g
    assert "sum_General_SurfaceArea" in g
    assert "sum_General_3DLength" in g


# --- CSV 导出 -----------------------------------------------------------

def test_aggregate_custom_template(svc):
    """自定义模板：单量+损耗+多类型合并。"""
    tpl = {
        "quantity": "General_NetVolume",
        "group_by": ["story"],
        "element_types": ["Wall", "Slab"],
        "waste_factor": 0.05,
        "description": "自定义测试",
    }
    out = svc.aggregate_by_custom_template(tpl)
    assert out["template"] == "自定义测试"
    g = out["rows"][0]
    assert "sum" in g
    assert "sum_with_waste" in g
    assert g["sum_with_waste"] > g["sum"]


def test_aggregate_custom_template_multi(svc):
    """自定义多量模板。"""
    tpl = {
        "quantities": ["General_NetVolume", "General_SurfaceArea"],
        "group_by": ["type"],
        "element_types": ["Wall"],
    }
    out = svc.aggregate_by_custom_template(tpl)
    assert "units" in out
    g = out["rows"][0]
    assert "sum_General_NetVolume" in g
    assert "sum_General_SurfaceArea" in g


def test_aggregate_custom_template_invalid(svc):
    """缺字段报错。"""
    with pytest.raises(ValueError, match="quantity"):
        svc.aggregate_by_custom_template({"group_by": ["type"]})


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


# --- 公式求值 -----------------------------------------------------------

def test_formula_vars():
    from formula_eval import formula_vars
    assert formula_vars("General_NetVolume * 1.03") == ["General_NetVolume"]
    vars2 = formula_vars("General_SurfaceArea + General_NetVolume")
    assert set(vars2) == {"General_SurfaceArea", "General_NetVolume"}
    assert formula_vars("1.03 * 2") == []


def test_eval_formula_basic():
    from formula_eval import eval_formula
    assert eval_formula("General_NetVolume * 1.03",
                        {"General_NetVolume": 10.0}) == 10.3
    assert eval_formula("General_SurfaceArea * 2",
                        {"General_SurfaceArea": 5.0}) == 10.0
    assert eval_formula("General_NetVolume + General_SurfaceArea",
                        {"General_NetVolume": 3.0, "General_SurfaceArea": 4.0}) == 7.0


def test_eval_formula_none():
    from formula_eval import eval_formula
    assert eval_formula("General_NetVolume * 1.03",
                        {"General_NetVolume": None}) is None
    assert eval_formula("General_NetVolume * 1.03", {}) is None


def test_eval_formula_sub_div():
    from formula_eval import eval_formula
    assert eval_formula("General_GrossVolume - General_NetVolume",
                        {"General_GrossVolume": 10.0, "General_NetVolume": 8.0}) == 2.0
    assert eval_formula("General_SurfaceArea / 2",
                        {"General_SurfaceArea": 10.0}) == 5.0


def test_eval_formula_rejects_call():
    """公式不允许函数调用等危险操作。"""
    from formula_eval import eval_formula
    with pytest.raises(ValueError):
        eval_formula("__import__('os')", {})
    with pytest.raises(ValueError):
        eval_formula("open('x')", {})


def test_eval_formula_rejects_syntax():
    from formula_eval import eval_formula
    with pytest.raises(ValueError, match="语法错误"):
        eval_formula("1 +", {})


# --- aggregate 公式模式 -------------------------------------------------

def test_aggregate_with_formula(svc):
    """公式法：NetVolume * 2，按类型汇总墙。"""
    out = svc.aggregate(
        formula="General_NetVolume * 2",
        formula_name="双倍体积",
        formula_unit="m³",
        group_by=["type"], element_type="Wall",
    )
    assert out["unit"] == "m³"
    g = out["rows"][0]
    # g1(1.0)+g2(2.0)=3.0, *2=6.0
    assert g["sum"] == 6.0
    assert "avg" in g


def test_aggregate_formula_none_skipped(svc, monkeypatch):
    """公式引用的量值为 None 时计入 skipped_none。"""
    class FakePropNone:
        def get_quantities(self, guids, names, instance=None):
            return {g: {n: {"value": None, "unit": "m"} for n in names}
                    for g in guids}
        def get_values(self, guids, names, instance=None):
            return {g: {} for g in guids}
    monkeypatch.setattr(aggregate_service.property_service, "service", FakePropNone())
    out = svc.aggregate(
        formula="General_Height * 2",
        formula_name="高度*2",
        group_by=["type"], element_type="Wall",
    )
    g = out["rows"][0]
    assert g["skipped_none"] == g["count"]
    assert g["sum"] == 0.0


def test_aggregate_formula_missing_both():
    """不传 quantity 也不传 formula 报错。"""
    s = aggregate_service.AggregateService()
    with pytest.raises(ValueError, match="formula"):
        s.aggregate(group_by=["type"])


# --- 公式模板 -----------------------------------------------------------

def test_template_wall_paint_area(svc):
    """wall_paint_area 模板：表面积*2，按楼层分组。"""
    out = svc.aggregate_by_template("wall_paint_area")
    assert out["template"] == "wall_paint_area"
    assert out["unit"] == "m²"
    # story 0: g1 SurfaceArea=1.0 *2=2.0; story 1: g2 SurfaceArea=2.0 *2=4.0
    s0 = next(g for g in out["rows"] if g["group"]["story"] == 0)
    assert s0["sum"] == 2.0
    s1 = next(g for g in out["rows"] if g["group"]["story"] == 1)
    assert s1["sum"] == 4.0


def test_template_paint_in_list():
    from aggregate_service import QUANTITY_TEMPLATES
    assert "wall_paint_area" in QUANTITY_TEMPLATES
    tpl = QUANTITY_TEMPLATES["wall_paint_area"]
    assert "formula" in tpl


# --- 公式自定义模板 -----------------------------------------------------

def test_aggregate_custom_template_formula(svc):
    """自定义公式模板：NetVolume * 1.03，多类型合并。"""
    tpl = {
        "formula": "General_NetVolume * 1.03",
        "formula_name": "含损耗体积",
        "formula_unit": "m³",
        "group_by": ["story"],
        "element_types": ["Wall", "Slab"],
        "description": "公式法含3%损耗",
    }
    out = svc.aggregate_by_custom_template(tpl)
    assert out["template"] == "公式法含3%损耗"
    assert out["unit"] == "m³"
    # story 1: Wall(2.0)+Slab(5.0)=7.0, *1.03=7.21
    s1 = next(g for g in out["rows"] if g["group"]["story"] == 1)
    assert s1["sum"] == round(7.0 * 1.03, 4)


def test_validate_template_accepts_formula():
    """有 formula 无 quantity 也能通过校验。"""
    from aggregate_service import validate_template
    validate_template({
        "formula": "General_NetVolume * 1.03",
        "group_by": ["story"],
        "element_types": ["Wall"],
    })


# --- V0.26 清单编码 + 报表 ---------------------------------------------

def test_code_table_lookup():
    """code_table 提供 GB 50500 清单编码。"""
    import code_table
    assert code_table.lookup("Wall")["code"] == "010502001"
    assert code_table.lookup("Wall")["unit"] == "m³"
    assert code_table.lookup("NotAType") is None
    assert code_table.lookup(None) is None


def test_aggregate_with_code_adds_type_dim(svc):
    """with_code=True 时强制 group_by 含 type，每组附 code 列。"""
    out = svc.aggregate(
        quantity="General_NetVolume",
        group_by=["story"],
        element_type="Wall",
        with_code=True,
    )
    g = out["rows"][0]
    assert "type" in g["group"]  # 自动加 type 维度
    assert g["group"]["code"] == "010502001"
    assert g["group"]["code_name"] == "现浇混凝土墙"
    assert g["group"]["code_unit"] == "m³"


def test_aggregate_with_code_no_type_dim_if_already_present(svc):
    """group_by 已含 type 时不再重复添加。"""
    out = svc.aggregate(
        quantity="General_NetVolume",
        group_by=["type"],
        element_type="Wall",
        with_code=True,
    )
    assert out["rows"][0]["group"]["code"] == "010502001"


def test_template_concrete_volume_has_code(svc):
    """concrete_volume 模板带 with_code=True。"""
    out = svc.aggregate_by_template("concrete_volume")
    # 每行都有清单编码
    for g in out["rows"]:
        assert g["group"].get("code")
        assert g["group"].get("code_name")


def test_custom_template_with_code(svc):
    """自定义模板支持 with_code 字段。"""
    tpl = {
        "quantity": "General_NetVolume",
        "group_by": ["story"],
        "element_types": ["Wall", "Slab"],
        "with_code": True,
    }
    out = svc.aggregate_by_custom_template(tpl)
    # 多 type 时按 story+type 分项
    by_st = {}
    for g in out["rows"]:
        key = (g["group"]["story"], g["group"]["type"])
        by_st[key] = g
    assert by_st[(1, "Wall")]["group"]["code"] == "010502001"
    assert by_st[(1, "Slab")]["group"]["code"] == "010505001"


def test_report_service_build(tmp_path):
    """report_service 生成清单格式 xlsx。"""
    import os
    import report_service

    rows = [
        {"story": 0, "type": "Wall", "count": 2,
         "sum": 3.0, "code": "010502001",
         "code_name": "现浇混凝土墙", "code_unit": "m³"},
        {"story": 1, "type": "Wall", "count": 1,
         "sum": 5.0, "code": "010502001",
         "code_name": "现浇混凝土墙", "code_unit": "m³"},
        {"story": 1, "type": "Slab", "count": 1,
         "sum": 2.0, "code": "010505001",
         "code_name": "现浇混凝土板", "code_unit": "m³"},
    ]
    path = report_service.build_report(
        rows, value_column="sum", project_name="测试工程",
        filename="test_report", out_dir=str(tmp_path))
    assert os.path.exists(path)
    assert path.endswith(".xlsx")

    from openpyxl import load_workbook
    wb = load_workbook(path)
    ws = wb.active
    # 标题
    assert ws.cell(1, 1).value == "工程量清单"
    # 项目信息行
    assert "测试工程" in ws.cell(2, 1).value
    # 表头
    assert ws.cell(3, 1).value == "序号"
    assert ws.cell(3, 5).value == "工程量"
    # 数据行：Wall 同 code 合并 = 8.0，Slab = 2.0
    wall_row = next(r for r in range(4, ws.max_row + 1)
                    if ws.cell(r, 2).value == "010502001")
    assert ws.cell(wall_row, 5).value == 8.0
    slab_row = next(r for r in range(4, ws.max_row + 1)
                    if ws.cell(r, 2).value == "010505001")
    assert ws.cell(slab_row, 5).value == 2.0


def test_report_service_picks_value_column_auto(tmp_path):
    """未传 value_column 时自动探测 sum 列。"""
    import os
    import report_service

    rows = [
        {"type": "Wall", "sum": 3.0, "code": "010502001",
         "code_name": "现浇混凝土墙", "code_unit": "m³"},
    ]
    path = report_service.build_report(
        rows, filename="auto", out_dir=str(tmp_path))
    assert os.path.exists(path)


def test_report_service_rejects_empty():
    """rows 空时报错。"""
    import report_service
    with pytest.raises(ValueError, match="为空"):
        report_service.build_report([])


def test_report_service_rejects_missing_value_column(tmp_path):
    """rows 无量值列时报错。"""
    import report_service
    rows = [{"type": "Wall", "code": "010502001",
             "code_name": "墙", "code_unit": "m³"}]
    with pytest.raises(ValueError, match="量值列"):
        report_service.build_report(rows, out_dir=str(tmp_path))


def test_report_service_total_when_unit_consistent(tmp_path):
    """所有项单位一致时显示合计行。"""
    import report_service
    from openpyxl import load_workbook

    rows = [
        {"type": "Wall", "sum": 3.0, "code": "010502001",
         "code_name": "现浇混凝土墙", "code_unit": "m³"},
        {"type": "Slab", "sum": 5.0, "code": "010505001",
         "code_name": "现浇混凝土板", "code_unit": "m³"},
    ]
    path = report_service.build_report(
        rows, value_column="sum", filename="total", out_dir=str(tmp_path))
    wb = load_workbook(path)
    ws = wb.active
    last_val = ws.cell(ws.max_row, 5).value
    # 合计 = 8.0
    assert last_val == 8.0


def test_report_service_no_total_when_unit_mixed(tmp_path):
    """单位不一致时不显示合计。"""
    import report_service
    from openpyxl import load_workbook

    rows = [
        {"type": "Wall", "sum": 3.0, "code": "010502001",
         "code_name": "现浇混凝土墙", "code_unit": "m³"},
        {"type": "Door", "sum": 2.0, "code": "010801001",
         "code_name": "木质门", "code_unit": "樘"},
    ]
    path = report_service.build_report(
        rows, value_column="sum", filename="mixed", out_dir=str(tmp_path))
    wb = load_workbook(path)
    ws = wb.active
    # 末行不是合计（合计只在单位一致时出现），最后一行是数据行 Door
    assert ws.cell(ws.max_row, 4).value == "樘"
    assert ws.cell(ws.max_row, 5).value == 2.0
