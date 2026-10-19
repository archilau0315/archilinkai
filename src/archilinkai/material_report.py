"""材料统计模块

按构件类型汇总材料用量（混凝土/钢筋/模板/涂料/保温/砖砌体/防水等）。
"""
from __future__ import annotations

from typing import Any
from collections import defaultdict

from archilinkai import i18n
from archilinkai import property_service
from archilinkai import renovation_service
from archilinkai.cost_data import PRICE_BOOK
from archilinkai.query_engine import QueryRequest, engine

# 构件类型 → 材料因子 (kg/m³, kg/m², m²/m³ 等)
MATERIAL_FACTORS: dict[str, dict[str, float]] = {
    "Wall": {
        "砖砌体": 0.52,      # m³/m² (墙厚约 0.2m)
        "内墙涂料": 1.0,      # m²/m² (双面)
        "外墙涂料": 0.5,      # m²/m² (单面)
        "保温板": 1.0,        # m²/m²
        "防水涂料": 0.2,      # m²/m² (卫生间/厨房)
    },
    "Beam": {
        "混凝土": 1.0,        # m³/m³
        "钢筋": 120.0,        # kg/m³
        "模板": 9.6,          # m²/m³
    },
    "Column": {
        "混凝土": 1.0,
        "钢筋": 150.0,
        "模板": 7.2,
    },
    "Slab": {
        "混凝土": 1.0,
        "钢筋": 100.0,
        "模板": 3.0,
    },
    "Stair": {
        "混凝土": 1.0,
        "钢筋": 100.0,
    },
    "Roof": {
        "防水卷材": 1.1,      # m²/m² (含搭接)
        "保温板": 1.0,        # m²/m²
        "混凝土": 0.12,       # m³/m² (找坡层+保护层)
    },
}

# 属性名 → 构件类型对应值
ATTR_MAP: dict[str, dict[str, str]] = {
    "quantity": {
        "Wall": "General_NetVolume",
        "Beam": "General_Volume",
        "Column": "General_Volume",
        "Slab": "General_Volume",
        "Stair": "General_Volume",
        "Roof": "General_Area",
    },
}

# Wall 专用：墙厚属性（用于把体积换算成面积）
WALL_THICKNESS_ATTR = "General_Thickness"

# 材料类别 → 计量单位（避免不同单位混算，V0.62）
MATERIAL_UNITS: dict[str, str] = {
    "砖砌体": "m³", "混凝土": "m³", "钢筋": "kg", "模板": "m²",
    "内墙涂料": "m²", "外墙涂料": "m²", "保温板": "m²",
    "防水卷材": "m²", "防水涂料": "m²", "砌块": "m³",
}

# 材料类别 → (PRICE_BOOK 键, 换算系数)，用于材料费联动（V0.62）
# 系数把「元/PRICE_BOOK 单位」折算为「元/材料计量单位」。
MATERIAL_PRICE: dict[str, tuple[str, float]] = {
    "砖砌体": ("蒸压加气混凝土砌块", 1.0),
    "混凝土": ("C30 预拌混凝土", 1.0),
    "钢筋": ("HRB400 钢筋", 0.001),             # 元/t → 元/kg
    "模板": ("木模板", 1.0),
    "内墙涂料": ("内墙乳胶漆", 1.0),
    "外墙涂料": ("外墙乳胶漆", 1.0),
    "防水卷材": ("SBS 改性沥青防水卷材", 1.0),
    "保温板": ("挤塑聚苯板 XPS", 0.05),          # 元/m³ → 元/m²（按 50mm 厚折算）
}


def _material_unit_price(mat: str) -> float | None:
    """材料类别 → 参考单价（元/计量单位）；未覆盖或单价缺失返回 None。"""
    key_factor = MATERIAL_PRICE.get(mat)
    if not key_factor:
        return None
    key, factor = key_factor
    price = PRICE_BOOK.get(key)
    return price * factor if price is not None else None



def _fetch_elements(element_type: str, instance: str | None) -> list[dict[str, Any]]:
    page = engine.query(QueryRequest(element_type=element_type, limit=10000))
    return page.items


def _num(v: Any) -> float:
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def generate_material_report(
    element_types: list[str] | None = None,
    instance: str | None = None,
    split_by_renovation: bool = False,
) -> dict[str, Any]:
    """生成材料统计报告。

    element_types: 构件类型列表，默认全部。
    split_by_renovation: true 时额外按翻新状态（新建/拆除/已建）分组统计。
    返回：{"summary", "by_type", "details", "units", "price",
           "material_cost_total"}（分状态时另含 "by_renovation"）。
    - summary/by_type: {材料: 用量}（各自单位见 units）
    - units: {材料: 计量单位}
    - price: {材料: {"unit_price", "cost"}}；未覆盖单价的材料 cost 为 None
    """
    types = element_types or list(MATERIAL_FACTORS.keys())
    report: dict[str, Any] = {
        "by_type": {},
        "details": [],
        "summary": defaultdict(float),
    }
    by_renovation: dict[str, dict[str, float]] = {}

    for etype in types:
        factors = MATERIAL_FACTORS.get(etype, {})
        if not factors:
            continue
        elems = _fetch_elements(etype, instance)
        if not elems:
            continue
        guids = [e["guid"] for e in elems]
        # 获取数量属性
        attr_name = ATTR_MAP["quantity"].get(etype, "General_Volume")
        props = property_service.service.get_values(guids, [attr_name], instance)
        # Wall 需要墙厚来换算面积
        if etype == "Wall":
            thick_props = property_service.service.get_values(
                guids, [WALL_THICKNESS_ATTR], instance)
        else:
            thick_props = {}
        # 翻新状态（按需读取）
        status_map = (renovation_service.get_status_map(guids, instance)
                      if split_by_renovation else {})

        type_summary: dict[str, float] = defaultdict(float)
        for e in elems:
            q = _num(props.get(e["guid"], {}).get(attr_name))
            if q <= 0:
                continue
            # Wall：体积 → 面积换算
            if etype == "Wall":
                t = _num(thick_props.get(e["guid"], {}).get(
                    WALL_THICKNESS_ATTR)) or 0.2
                area = q / t if t > 0 else 0
                qty_map = {
                    "砖砌体": q,               # m³
                    "内墙涂料": area * 2,       # 双面
                    "外墙涂料": area,           # 单面
                    "保温板": area,
                    "防水涂料": area * 0.2,     # 卫生间/厨房比例
                }
            else:
                qty_map = {
                    mat: q * factor
                    for mat, factor in factors.items()
                }
            st = status_map.get(e["guid"], "Undefined") if split_by_renovation else None
            for mat, qty in qty_map.items():
                type_summary[mat] += qty
                report["summary"][mat] += qty
                if st is not None:
                    by_renovation.setdefault(st, defaultdict(float))
                    by_renovation[st][mat] += qty
            detail = {
                "guid": e["guid"],
                "type": etype,
                "name": e.get("name", ""),
                "story": e.get("story_index"),
                "quantity": round(q, 3),
                "materials": {k: round(v, 3) for k, v in qty_map.items()},
            }
            if st is not None:
                detail["renovation"] = st
            report["details"].append(detail)
        report["by_type"][etype] = dict(type_summary)

    report["summary"] = dict(report["summary"])
    report["units"] = {m: MATERIAL_UNITS.get(m, "") for m in report["summary"]}
    # 材料费联动：量 × 参考单价（未覆盖单价的不计价）
    price: dict[str, dict[str, Any]] = {}
    total_cost = 0.0
    for mat, qty in report["summary"].items():
        up = _material_unit_price(mat)
        if up is None:
            price[mat] = {"unit_price": None, "cost": None}
            continue
        cost = round(qty * up, 2)
        price[mat] = {"unit_price": round(up, 2), "cost": cost}
        total_cost += cost
    report["price"] = price
    report["material_cost_total"] = round(total_cost, 2)
    if split_by_renovation:
        report["by_renovation"] = {
            k: dict(v) for k, v in by_renovation.items()}
    return report


def export_material_excel(
    report: dict[str, Any],
    filepath: str,
) -> str:
    """材料统计报告导出为 Excel（汇总/按类型/按翻新/明细 多表 + 样式）。"""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        return i18n.t(
            "material.err_no_openpyxl",
            "错误：未安装 openpyxl，请 pip install openpyxl")

    bold = Font(bold=True, size=11)
    center = Alignment(horizontal="center", vertical="center")
    left = Alignment(horizontal="left", vertical="center")
    thin = Side(border_style="thin", color="000000")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    head_fill = PatternFill("solid", fgColor="D9E1F2")

    def _write(ws, headers: list, rows: list, widths: list) -> None:
        for i, h in enumerate(headers, 1):
            c = ws.cell(1, i, h)
            c.font, c.alignment, c.border, c.fill = bold, center, border, head_fill
        for r, row in enumerate(rows, 2):
            for i, v in enumerate(row, 1):
                c = ws.cell(r, i, v)
                c.alignment = left if i <= 1 else center
                c.border = border
        ws.freeze_panes = "A2"
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w

    def _label(mat: str) -> str:
        return i18n.t(f"material.{mat}", mat)

    units = report.get("units", {})
    price = report.get("price", {})

    wb = Workbook()
    # 汇总页（材料 / 单位 / 总用量 / 参考单价 / 材料费）
    ws = wb.active
    ws.title = i18n.t("material.sheet_summary", "材料汇总")
    rows = []
    for mat, qty in report.get("summary", {}).items():
        p = price.get(mat, {})
        rows.append([
            _label(mat), units.get(mat, ""), round(qty, 3),
            p.get("unit_price") if p.get("unit_price") is not None else "—",
            p.get("cost") if p.get("cost") is not None else "—",
        ])
    _write(ws, [
        i18n.t("material.h_name", "材料名称"), i18n.t("material.h_unit", "单位"),
        i18n.t("material.h_total", "总用量"),
        i18n.t("material.h_unit_price", "参考单价(元)"),
        i18n.t("material.h_cost", "材料费(元)")],
        rows, [18, 8, 12, 14, 14])
    tr = len(rows) + 2
    c = ws.cell(tr, 1, i18n.t("material.h_cost_total", "材料费合计"))
    c.font = bold
    c = ws.cell(tr, 5, report.get("material_cost_total", 0))
    c.font, c.alignment = bold, center

    # 按构件类型
    for etype, mats in report.get("by_type", {}).items():
        ws2 = wb.create_sheet(title=str(etype)[:31])
        rows2 = [[_label(m), units.get(m, ""), round(q, 3)]
                 for m, q in mats.items()]
        _write(ws2, [
            i18n.t("material.h_name", "材料名称"), i18n.t("material.h_unit", "单位"),
            i18n.t("material.h_qty", "用量")],
            rows2, [18, 8, 12])

    # 按翻新状态（仅当报告含该分组）
    for st, mats in report.get("by_renovation", {}).items():
        base = i18n.t("material.sheet_renovation", "按翻新状态")
        ws3 = wb.create_sheet(title=f"{base}·{renovation_service.label(st)}"[:31])
        rows3 = [[_label(m), units.get(m, ""), round(q, 3)]
                 for m, q in mats.items()]
        _write(ws3, [
            i18n.t("material.h_name", "材料名称"), i18n.t("material.h_unit", "单位"),
            i18n.t("material.h_qty", "用量")],
            rows3, [18, 8, 12])

    # 明细页
    ws4 = wb.create_sheet(title=i18n.t("material.sheet_detail", "明细"))
    has_rev = any("renovation" in d for d in report.get("details", []))
    head = [
        i18n.t("material.h_guid", "GUID"), i18n.t("material.h_type", "类型"),
        i18n.t("material.h_elem_name", "名称"), i18n.t("material.h_story", "楼层")]
    if has_rev:
        head.append(i18n.t("material.h_renovation", "翻新状态"))
    head += [i18n.t("material.h_count", "数量"),
             i18n.t("material.h_detail", "材料明细")]
    rows4 = []
    for d in report.get("details", []):
        row = [d["guid"], d["type"], d["name"], d.get("story", "")]
        if has_rev:
            st = d.get("renovation") or "Undefined"
            row.append(renovation_service.label(st))
        row += [d["quantity"], str(d["materials"])]
        rows4.append(row)
    widths4 = [34, 10, 16, 8] + ([10] if has_rev else []) + [14, 40]
    _write(ws4, head, rows4, widths4)

    wb.save(filepath)
    return filepath

