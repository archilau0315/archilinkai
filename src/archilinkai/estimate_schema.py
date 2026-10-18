"""概算表 JSON Schema（V0.32）。

设计目标：定义概算表的数据结构，支持无单价框架（待定额接入后填价）。
概算表 vs 清单报表：清单只有工程量，概算表含单价、合价、人材机、取费。
"""

from __future__ import annotations

from typing import Any

# 概算表条目（一条清单项）
ESTIMATE_ITEM_SCHEMA = {
    "code": "str",           # 清单编码（如 010502001）
    "name": "str",           # 项目名称（如 现浇混凝土墙）
    "unit": "str",           # 计量单位（如 m³）
    "quantity": "float",     # 工程量
    "quota_code": "str|None",    # 定额编号（如 5-12，待匹配）
    "quota_name": "str|None",    # 定额名称（如 现浇混凝土柱 矩形柱 C40）
    "unit_price": "float|None",  # 定额单价（元/单位，待接入）
    "total_price": "float|None", # 合价（quantity × unit_price，待计算）
    "labor_price": "float|None", # 人工费（待接入）
    "material_price": "float|None",  # 材料费（待接入）
    "machine_price": "float|None",   # 机械费（待接入）
    "labor_qty": "float|None",       # 人工工日（待接入）
    "material_items": "list[dict]|None",  # 材料明细（待接入）
    "source": "str|None",    # 数据来源（如 "aggregate:concrete_volume"）
    "specs": "dict|None",    # 规格特征（如 {"强度": "C40", "截面": "矩形"}）
}

# 概算表汇总
ESTIMATE_SUMMARY_SCHEMA = {
    "direct_cost": "float",      # 直接费（分部分项合计）
    "measure_fee": "float",      # 措施项目费
    "management_fee": "float",   # 管理费
    "profit": "float",           # 利润
    "tax": "float",              # 税金
    "total": "float",            # 含税总价
}

# 概算表整体
ESTIMATE_TABLE_SCHEMA = {
    "project_name": "str",
    "project_code": "str|None",   # 项目编码
    "date": "str",
    "items": "list[ESTIMATE_ITEM]",
    "summary": "ESTIMATE_SUMMARY",
    "region": "str|None",         # 适用地区（如 辽宁）
    "quota_version": "str|None",  # 定额版本（如 2024）
    "notes": "list[str]|None",    # 备注
}


def create_estimate_item(
    code: str,
    name: str,
    unit: str,
    quantity: float,
    source: str | None = None,
    specs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """创建概算表条目（无价格，待定额接入后填价）。"""
    return {
        "code": code,
        "name": name,
        "unit": unit,
        "quantity": round(quantity, 4),
        "quota_code": None,
        "quota_name": None,
        "unit_price": None,
        "total_price": None,
        "labor_price": None,
        "material_price": None,
        "machine_price": None,
        "labor_qty": None,
        "material_items": None,
        "source": source,
        "specs": specs or {},
    }


def create_estimate_table(
    project_name: str,
    items: list[dict[str, Any]],
    region: str | None = None,
    quota_version: str | None = None,
) -> dict[str, Any]:
    """创建概算表（无价格框架）。"""
    import time
    return {
        "project_name": project_name,
        "project_code": None,
        "date": time.strftime("%Y-%m-%d"),
        "items": items,
        "summary": {
            "direct_cost": 0.0,
            "measure_fee": 0.0,
            "management_fee": 0.0,
            "profit": 0.0,
            "tax": 0.0,
            "total": 0.0,
        },
        "region": region,
        "quota_version": quota_version,
        "notes": [],
    }


def aggregate_rows_to_estimate_items(
    rows: list[dict[str, Any]],
    value_column: str | None = None,
    source_prefix: str = "aggregate",
) -> list[dict[str, Any]]:
    """把 aggregate 的 flat_rows 转成概算表条目列表。

    rows: flat_rows（aggregate 返回的 flat_rows 字段）
    value_column: 指定哪一列作为工程量值（缺省自动探测）
    source_prefix: 来源标记前缀
    """
    from archilinkai.report_service import _pick_value_column, _aggregate_by_code

    if not rows:
        return []
    value_col = _pick_value_column(rows[0], value_column)
    if not value_col:
        raise ValueError(f"rows 中未找到量值列（sum/sum_*/formula_result）")

    aggregated = _aggregate_by_code(rows, value_col)
    items = []
    for a in aggregated:
        item = create_estimate_item(
            code=a["code"],
            name=a["code_name"],
            unit=a["code_unit"],
            quantity=a["value"],
            source=f"{source_prefix}:{a.get('template', 'unknown')}",
        )
        items.append(item)
    return items
