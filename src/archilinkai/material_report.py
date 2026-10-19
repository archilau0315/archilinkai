"""材料统计模块

按构件类型汇总材料用量（混凝土/钢筋/模板/涂料/保温/砖砌体/防水等）。
"""
from __future__ import annotations

from typing import Any
from collections import defaultdict

from archilinkai import i18n
from archilinkai import property_service
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
) -> dict[str, Any]:
    """生成材料统计报告。

    element_types: 构件类型列表，默认全部。
    返回：{"summary": {...}, "by_type": {...}, "details": [...]}。
    """
    types = element_types or list(MATERIAL_FACTORS.keys())
    report: dict[str, Any] = {
        "by_type": {},
        "details": [],
        "summary": defaultdict(float),
    }

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
            for mat, qty in qty_map.items():
                type_summary[mat] += qty
                report["summary"][mat] += qty
            report["details"].append({
                "guid": e["guid"],
                "type": etype,
                "name": e.get("name", ""),
                "story": e.get("story_index"),
                "quantity": round(q, 3),
                "materials": {k: round(v, 3) for k, v in qty_map.items()},
            })
        report["by_type"][etype] = dict(type_summary)

    report["summary"] = dict(report["summary"])
    return report


def export_material_excel(
    report: dict[str, Any],
    filepath: str,
) -> str:
    """材料统计报告导出为 Excel。"""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
    except ImportError:
        return i18n.t(
            "material.err_no_openpyxl",
            "错误：未安装 openpyxl，请 pip install openpyxl")

    wb = Workbook()
    # 汇总页
    ws = wb.active
    ws.title = i18n.t("material.sheet_summary", "材料汇总")
    ws.append([i18n.t("material.h_name", "材料名称"), i18n.t("material.h_total", "总用量")])
    for mat, qty in report["summary"].items():
        ws.append([i18n.t(f"material.{mat}", mat), round(qty, 3)])
    # 按构件类型
    for etype, mats in report["by_type"].items():
        ws2 = wb.create_sheet(title=etype)
        ws2.append([i18n.t("material.h_name", "材料名称"), i18n.t("material.h_qty", "用量")])
        for mat, qty in mats.items():
            ws2.append([i18n.t(f"material.{mat}", mat), round(qty, 3)])
    # 明细页
    ws3 = wb.create_sheet(title=i18n.t("material.sheet_detail", "明细"))
    ws3.append([
        i18n.t("material.h_guid", "GUID"), i18n.t("material.h_type", "类型"),
        i18n.t("material.h_elem_name", "名称"), i18n.t("material.h_story", "楼层"),
        i18n.t("material.h_count", "数量"), i18n.t("material.h_detail", "材料明细"),
    ])
    for d in report["details"]:
        ws3.append([
            d["guid"],
            d["type"],
            d["name"],
            d.get("story", ""),
            d["quantity"],
            str(d["materials"]),
        ])

    wb.save(filepath)
    return filepath
