"""成本估算细算引擎（V0.37）。

设计目标：材料市场价 + 人工/机械消耗量分解的细算方式，
避免直接套用单方指标导致高估。

细算路径：
    flat_rows（aggregate 算量结果）
    → aggregate_rows_to_estimate_items（清单条目，V0.32 已有）
    → CostEstimator.estimate_table（本模块：消耗量 × 市场价 → 人材机 → 取费 → 总价）

价格与消耗量为 2026 年市场/施工通用参考值，均可用参数覆盖。
"""

from __future__ import annotations

from typing import Any

# ---- 材料市场价库（元/单位，2026 参考价，可覆盖） -----------------------

PRICE_BOOK: dict[str, float] = {
    # 预拌混凝土（元/m³）
    "C15 预拌混凝土": 320.0,
    "C20 预拌混凝土": 335.0,
    "C25 预拌混凝土": 350.0,
    "C30 预拌混凝土": 380.0,
    "C35 预拌混凝土": 410.0,
    "C40 预拌混凝土": 440.0,
    # 砂浆（元/m³）
    "M5 混合砂浆": 280.0,
    "M7.5 混合砂浆": 300.0,
    "M10 混合砂浆": 320.0,
    "M5 水泥砂浆": 300.0,
    "M10 水泥砂浆": 330.0,
    # 钢筋（元/t）
    "HPB300 钢筋": 3900.0,
    "HRB400 钢筋": 4000.0,
    # 砌块砖材
    "标准砖": 0.55,          # 元/块
    "蒸压加气混凝土砌块": 350.0,  # 元/m³
    # 防水保温
    "SBS 改性沥青防水卷材": 32.0,  # 元/m²
    "基层处理剂": 8.0,        # 元/kg
    # 装饰
    "不锈钢扶手": 85.0,       # 元/m
    "不锈钢栏杆立柱": 12.0,    # 元/kg
    "塑料薄膜": 0.8,          # 元/m²（混凝土养护）
    "安全网": 3.5,            # 元/m²
}

# 人工与机械单价（元）
DEFAULT_LABOR_PRICE = 130.0       # 综合工日（元/工日）
MACHINE_BOOK: dict[str, float] = {
    "混凝土振捣器": 15.0,      # 元/台班
    "砂浆搅拌机": 45.0,
    "钢筋切断机": 60.0,
    "钢筋弯曲机": 55.0,
    "对焊机": 90.0,
    "卷扬机": 80.0,
    "塔式起重机": 550.0,
}

# ---- 消耗量：清单编码 → 每 1 清单单位的工料消耗 ------------------------
# labor_qty: 工日/单位；materials: (材料名, 数量/单位, 计量单位)
# machines: (机械名, 台班/单位)；未列出的编码走 KEYWORD_FALLBACK

CONSUMPTION: dict[str, dict[str, Any]] = {
    # 混凝土类（均含 1.5% 损耗 → 消耗系数 1.015）
    "010402001": {  # 砖砌体
        "labor_qty": 1.3,
        "materials": [("M5 混合砂浆", 0.22, "m³"), ("标准砖", 520.0, "块")],
        "machines": [("砂浆搅拌机", 0.04, "台班")],
    },
    "010501001": {  # 垫层
        "labor_qty": 0.10,
        "materials": [("C15 预拌混凝土", 1.01, "m³")],
        "machines": [("混凝土振捣器", 0.03, "台班")],
    },
    "010502001": {  # 现浇混凝土矩形柱
        "labor_qty": 0.23,
        "materials": [("C30 预拌混凝土", 1.015, "m³"),
                      ("塑料薄膜", 0.5, "m²")],
        "machines": [("混凝土振捣器", 0.06, "台班")],
    },
    "010502002": {  # 现浇混凝土构造柱（同柱）
        "labor_qty": 0.26,
        "materials": [("C25 预拌混凝土", 1.015, "m³")],
        "machines": [("混凝土振捣器", 0.06, "台班")],
    },
    "010503001": {  # 现浇混凝土基础梁
        "labor_qty": 0.24,
        "materials": [("C30 预拌混凝土", 1.015, "m³")],
        "machines": [("混凝土振捣器", 0.06, "台班")],
    },
    "010504001": {  # 现浇混凝土直形墙
        "labor_qty": 0.19,
        "materials": [("C30 预拌混凝土", 1.015, "m³"),
                      ("塑料薄膜", 0.8, "m²")],
        "machines": [("混凝土振捣器", 0.05, "台班")],
    },
    "010505001": {  # 现浇混凝土梁
        "labor_qty": 0.24,
        "materials": [("C30 预拌混凝土", 1.015, "m³")],
        "machines": [("混凝土振捣器", 0.06, "台班")],
    },
    "010505003": {  # 现浇混凝土板
        "labor_qty": 0.13,
        "materials": [("C30 预拌混凝土", 1.015, "m³"),
                      ("塑料薄膜", 1.0, "m²")],
        "machines": [("混凝土振捣器", 0.04, "台班")],
    },
    "010506001": {  # 现浇混凝土楼梯（量按体积）
        "labor_qty": 0.29,
        "materials": [("C30 预拌混凝土", 1.015, "m³")],
        "machines": [("混凝土振捣器", 0.06, "台班")],
    },
    "010515001": {  # 现浇构件钢筋
        "labor_qty": 5.5,
        "materials": [("HRB400 钢筋", 1.045, "t")],
        "machines": [("钢筋切断机", 0.25, "台班"),
                     ("钢筋弯曲机", 0.25, "台班"),
                     ("对焊机", 0.10, "台班")],
    },
    "010902001": {  # 屋面卷材防水
        "labor_qty": 0.07,
        "materials": [("SBS 改性沥青防水卷材", 1.15, "m²"),
                      ("基层处理剂", 0.3, "kg")],
        "machines": [],
    },
    "011101001": {  # 水泥砂浆楼地面
        "labor_qty": 0.13,
        "materials": [("M10 水泥砂浆", 0.025, "m³")],
        "machines": [("砂浆搅拌机", 0.005, "台班")],
    },
    "011201001": {  # 墙面一般抹灰
        "labor_qty": 0.16,
        "materials": [("M5 混合砂浆", 0.023, "m³")],
        "machines": [("砂浆搅拌机", 0.005, "台班")],
    },
    "011301001": {  # 天棚抹灰
        "labor_qty": 0.14,
        "materials": [("M5 混合砂浆", 0.021, "m³")],
        "machines": [("砂浆搅拌机", 0.005, "台班")],
    },
    "011503001": {  # 金属扶手栏杆
        "labor_qty": 0.35,
        "materials": [("不锈钢扶手", 1.06, "m"),
                      ("不锈钢栏杆立柱", 3.2, "kg")],
        "machines": [],
    },
}

# 未命中编码时按名称关键词兜底（材料分解粒度粗，作参考值）
KEYWORD_FALLBACK: list[tuple[str, dict[str, Any]]] = [
    ("混凝土", {"labor_qty": 0.20, "materials": [("C30 预拌混凝土", 1.015, "m³")],
               "machines": [("混凝土振捣器", 0.05, "台班")]}),
    ("砌体", {"labor_qty": 1.3, "materials": [("M5 混合砂浆", 0.22, "m³"),
                                             ("蒸压加气混凝土砌块", 0.95, "m³")],
             "machines": [("砂浆搅拌机", 0.04, "台班")]}),
    ("钢筋", {"labor_qty": 5.5, "materials": [("HRB400 钢筋", 1.045, "t")],
             "machines": [("钢筋切断机", 0.25, "台班")]}),
    ("防水", {"labor_qty": 0.07, "materials": [("SBS 改性沥青防水卷材", 1.15, "m²")],
             "machines": []}),
    ("抹灰", {"labor_qty": 0.15, "materials": [("M5 混合砂浆", 0.022, "m³")],
             "machines": [("砂浆搅拌机", 0.005, "台班")]}),
    ("楼地面", {"labor_qty": 0.13, "materials": [("M10 水泥砂浆", 0.025, "m³")],
               "machines": [("砂浆搅拌机", 0.005, "台班")]}),
    ("栏杆", {"labor_qty": 0.35, "materials": [("不锈钢扶手", 1.06, "m")],
             "machines": []}),
]

# 默认取费费率（按直接费计）
DEFAULT_FEE_RATES = {
    "management_fee": 0.05,   # 企业管理费
    "profit": 0.045,          # 利润
    "tax": 0.09,              # 增值税（一般计税）
}


def _fallback_consumption(name: str) -> dict[str, Any] | None:
    for kw, cons in KEYWORD_FALLBACK:
        if kw in name:
            return cons
    return None


class CostEstimator:
    """细算估算器：消耗量 × 市场价 → 人材机 → 取费 → 总价。"""

    def __init__(
        self,
        labor_price: float = DEFAULT_LABOR_PRICE,
        price_overrides: dict[str, float] | None = None,
        fee_overrides: dict[str, float] | None = None,
        region: str | None = None,
    ):
        self.labor_price = labor_price
        self.prices = dict(PRICE_BOOK)
        if price_overrides:
            self.prices.update(price_overrides)
        self.machines = dict(MACHINE_BOOK)
        self.fees = dict(DEFAULT_FEE_RATES)
        if fee_overrides:
            self.fees.update(fee_overrides)
        self.region = region
        self.notes: list[str] = []

    def estimate_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """细算单条目，就地填 unit_price/labor_price/material_price/
        machine_price/labor_qty/material_items/total_price。"""
        code = item.get("code") or ""
        name = item.get("name") or ""
        qty = item.get("quantity") or 0.0
        cons = CONSUMPTION.get(code) or _fallback_consumption(name)
        if cons is None:
            self.notes.append(f"{code} {name}：无消耗量参考，未定价")
            return item

        # 人工费
        labor_qty_total = cons["labor_qty"] * qty
        labor_cost = labor_qty_total * self.labor_price

        # 材料费（逐项展开）
        material_items = []
        material_cost = 0.0
        for mname, per_unit, munit in cons["materials"]:
            price = self.prices.get(mname)
            if price is None:
                self.notes.append(f"{code} {name}：缺市场价「{mname}」")
                continue
            mq = per_unit * qty
            mc = round(mq * price, 2)
            material_cost += mc
            material_items.append({
                "name": mname, "unit": munit,
                "qty_per_unit": per_unit, "qty_total": round(mq, 4),
                "price": price, "cost": mc,
            })

        # 机械费
        machine_cost = 0.0
        for mname, per_unit, _ in cons.get("machines", []):
            price = self.machines.get(mname)
            if price is None:
                continue
            machine_cost += per_unit * qty * price

        total = round(labor_cost + material_cost + machine_cost, 2)
        unit_price = round(total / qty, 2) if qty else None
        item.update({
            "labor_qty": round(labor_qty_total, 3),
            "labor_price": round(labor_cost, 2),
            "material_price": round(material_cost, 2),
            "machine_price": round(machine_cost, 2),
            "material_items": material_items,
            "unit_price": unit_price,
            "total_price": total,
            "quota_code": item.get("quota_code") or f"细算:{code}",
        })
        return item

    def estimate_table(
        self,
        items: list[dict[str, Any]],
        project_name: str,
    ) -> dict[str, Any]:
        """细算全部条目并汇总取费，返回完整概算表。"""
        from estimate_schema import create_estimate_table

        priced = [self.estimate_item(i) for i in items]
        direct_cost = round(sum(i["total_price"] or 0 for i in priced), 2)
        management = round(direct_cost * self.fees["management_fee"], 2)
        profit = round(direct_cost * self.fees["profit"], 2)
        tax = round((direct_cost + management + profit) * self.fees["tax"], 2)
        total = round(direct_cost + management + profit + tax, 2)

        table = create_estimate_table(project_name, priced, self.region)
        table["summary"] = {
            "direct_cost": direct_cost,
            "measure_fee": 0.0,
            "management_fee": management,
            "profit": profit,
            "tax": tax,
            "total": total,
        }
        table["notes"] = list(self.notes)
        table["fee_rates"] = dict(self.fees)
        table["labor_price"] = self.labor_price
        return table


def estimate_from_flat_rows(
    flat_rows: list[dict[str, Any]],
    project_name: str,
    labor_price: float = DEFAULT_LABOR_PRICE,
    price_overrides: dict[str, float] | None = None,
    fee_overrides: dict[str, float] | None = None,
    region: str | None = None,
) -> dict[str, Any]:
    """flat_rows → 概算表全流程：转换 → 细算 → 汇总。"""
    from estimate_schema import aggregate_rows_to_estimate_items

    items = aggregate_rows_to_estimate_items(flat_rows)
    est = CostEstimator(labor_price, price_overrides, fee_overrides, region)
    return est.estimate_table(items, project_name)
