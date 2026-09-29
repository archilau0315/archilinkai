"""工程量→定额匹配引擎（V0.32）。

功能：
1. 名称相似度匹配：工程量名称 ↔ 定额名称（如 "现浇混凝土柱" ↔ "现浇混凝土柱 矩形柱 C40"）
2. 规格提取：从名称/描述中提取强度等级、截面类型、材料等特征
3. 单位换算：m³ ↔ 10m³、m² ↔ 100m²、t ↔ kg 等

使用：
    matcher = QuotaMatcher()
    result = matcher.match("现浇混凝土柱 C40", unit="m³", quantity=137.15)
    # 返回匹配的定额条目 + 换算后数量
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

# 单位换算表：目标单位 → (源单位, 换算系数)
UNIT_CONVERT = {
    "10m³": ("m³", 0.1),
    "100m²": ("m²", 0.01),
    "10m": ("m", 0.1),
    "100m": ("m", 0.01),
    "t": ("kg", 0.001),
    "kg": ("t", 1000),
    "樘": ("m²", None),  # 樘→m² 需按门/窗洞口面积换算，无法固定系数
}

# 规格关键词提取规则
SPEC_PATTERNS = {
    "强度等级": r"([Cc]\d{2})",            # C25/C30/C35/C40
    "抗渗等级": r"([Pp]\d+)",              # P6/P8
    "截面类型": r"(矩形|圆形|异形|构造柱|圈梁|过梁|悬挑板|平板|女儿墙)",
    "材料": r"(混凝土|钢筋|砌体|砂浆|铝合金|钢|木质|塑料)",
    "施工工艺": r"(现浇|预制|泵送|非泵送|干挂|湿贴)",
    "厚度": r"δ?(\d+)mm",                 # δ50 / 50mm
}


def extract_specs(text: str) -> dict[str, str]:
    """从文本提取规格特征。"""
    specs = {}
    for key, pattern in SPEC_PATTERNS.items():
        m = re.search(pattern, text)
        if m:
            specs[key] = m.group(1)
    return specs


def similarity(a: str, b: str) -> float:
    """计算两个名称的相似度（0-1）。"""
    return SequenceMatcher(None, a, b).ratio()


def convert_unit(quantity: float, from_unit: str, to_unit: str) -> float:
    """单位换算。无法换算时返回原值。"""
    if from_unit == to_unit:
        return quantity
    # 查换算表
    if to_unit in UNIT_CONVERT:
        base_unit, factor = UNIT_CONVERT[to_unit]
        if from_unit == base_unit and factor is not None:
            return quantity * factor
    # 反向查
    if from_unit in UNIT_CONVERT:
        base_unit, factor = UNIT_CONVERT[from_unit]
        if to_unit == base_unit and factor is not None:
            return quantity / factor
    return quantity


class QuotaMatcher:
    """定额匹配器。给定工程量名称/单位/数量，匹配定额条目。"""

    def __init__(self, quota_db: list[dict[str, Any]] | None = None):
        """quota_db: 定额条目列表，每条含 code/name/unit/specs。"""
        self.quota_db = quota_db or []

    def add_quota(self, quota: dict[str, Any]) -> None:
        """添加定额条目。"""
        self.quota_db.append(quota)

    def match(
        self,
        name: str,
        unit: str,
        quantity: float,
        threshold: float = 0.6,
    ) -> list[dict[str, Any]]:
        """匹配定额条目，按相似度排序。

        返回：匹配的定额条目列表，每条含：
          - quota: 定额条目
          - similarity: 相似度（0-1）
          - converted_quantity: 换算后数量
          - matched_specs: 匹配到的规格特征
        """
        specs = extract_specs(name)
        results = []
        for quota in self.quota_db:
            sim = similarity(name, quota["name"])
            # 规格特征加分
            matched = {}
            for k, v in specs.items():
                qv = quota.get("specs", {}).get(k)
                if qv and v.lower() == qv.lower():
                    sim += 0.1
                    matched[k] = v
            if sim >= threshold:
                conv_qty = convert_unit(quantity, unit, quota["unit"])
                results.append({
                    "quota": quota,
                    "similarity": round(sim, 3),
                    "converted_quantity": round(conv_qty, 4),
                    "matched_specs": matched,
                })
        return sorted(results, key=lambda x: x["similarity"], reverse=True)

    def match_best(
        self,
        name: str,
        unit: str,
        quantity: float,
    ) -> dict[str, Any] | None:
        """返回最佳匹配（相似度最高）。"""
        results = self.match(name, unit, quantity, threshold=0.4)
        return results[0] if results else None


def match_aggregate_to_quota(
    rows: list[dict[str, Any]],
    quota_db: list[dict[str, Any]],
    value_column: str | None = None,
) -> list[dict[str, Any]]:
    """把 aggregate 的 flat_rows 匹配到定额条目。

    返回：概算表条目列表，含 quota_code/quota_name/unit_price 等。
    """
    from estimate_schema import create_estimate_item
    from report_service import _pick_value_column, _aggregate_by_code

    if not rows:
        return []
    value_col = _pick_value_column(rows[0], value_column)
    if not value_col:
        raise ValueError(f"rows 中未找到量值列")

    aggregated = _aggregate_by_code(rows, value_col)
    matcher = QuotaMatcher(quota_db)
    items = []
    for a in aggregated:
        name = a["code_name"]
        unit = a["code_unit"]
        qty = a["value"]
        match = matcher.match_best(name, unit, qty)
        item = create_estimate_item(
            code=a["code"],
            name=name,
            unit=unit,
            quantity=qty,
            source=f"aggregate:{a.get('template', 'unknown')}",
        )
        if match:
            item["quota_code"] = match["quota"]["code"]
            item["quota_name"] = match["quota"]["name"]
            item["unit_price"] = match["quota"].get("unit_price")
            if item["unit_price"]:
                item["total_price"] = round(
                    match["converted_quantity"] * item["unit_price"], 2)
            item["labor_price"] = match["quota"].get("labor_price")
            item["material_price"] = match["quota"].get("material_price")
            item["machine_price"] = match["quota"].get("machine_price")
            item["specs"] = match["matched_specs"]
        items.append(item)
    return items
