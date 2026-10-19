"""成本估算计算层：CostEstimator + estimate_from_flat_rows（V0.56 从 cost_estimator 拆出）。"""

from __future__ import annotations

from typing import Any

from archilinkai import i18n
from archilinkai.cost_data import (
    DEFAULT_LABOR_PRICE, PRICE_BOOK, MACHINE_BOOK, DEFAULT_FEE_RATES,
    CONSUMPTION, merge_custom_consumption, load_persisted_consumption,
    _fallback_consumption,
)


class CostEstimator:
    """细算估算器：消耗量 × 市场价 → 人材机 → 取费 → 总价。"""

    def __init__(
        self,
        labor_price: float = DEFAULT_LABOR_PRICE,
        price_overrides: dict[str, float] | None = None,
        fee_overrides: dict[str, float] | None = None,
        region: str | None = None,
        custom_consumption: dict[str, dict[str, Any]] | None = None,
        consumption_table: dict[str, dict[str, Any]] | None = None,
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
        # 消耗量表：基表（默认建造 CONSUMPTION，可传拆除表）
        # + 持久化定额 + 本次传入自定义（优先级递增）
        persisted = load_persisted_consumption()
        merged = {**persisted, **(custom_consumption or {})}
        self.consumption = merge_custom_consumption(
            merged, consumption_table or CONSUMPTION)
        self.persisted_count = len(persisted)

    def estimate_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """细算单条目，就地填人材机字段并标记 calc_mode。

        calc_mode: detailed（编码精确命中）/ fallback（关键词兜底）/
        skipped（无参考，未定价）。
        """
        code = item.get("code") or ""
        name = item.get("name") or ""
        qty = item.get("quantity") or 0.0
        if code in self.consumption:
            cons, mode = self.consumption[code], "detailed"
        else:
            cons = _fallback_consumption(name)
            mode = "fallback" if cons else "skipped"
        if cons is None:
            self.notes.append(i18n.t(
                "estimate.note_no_consumption",
                f"{code} {name}：无消耗量参考，未定价", code=code, name=name))
            item["calc_mode"] = "skipped"
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
                self.notes.append(i18n.t(
                    "estimate.note_missing_price",
                    f"{code} {name}：缺市场价「{mname}」",
                    code=code, name=name, mname=mname))
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
            "calc_mode": mode,
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
        from archilinkai.estimate_schema import create_estimate_table

        priced = [self.estimate_item(i) for i in items]
        direct_cost = round(sum(i["total_price"] or 0 for i in priced), 2)
        labor_cost = round(sum(i.get("labor_price") or 0 for i in priced), 2)
        material_cost = round(sum(i.get("material_price") or 0 for i in priced), 2)
        machine_cost = round(sum(i.get("machine_price") or 0 for i in priced), 2)
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
            "labor_cost": labor_cost,
            "material_cost": material_cost,
            "machine_cost": machine_cost,
        }
        table["notes"] = list(self.notes)
        table["fee_rates"] = dict(self.fees)
        table["labor_price"] = self.labor_price
        table["coverage"] = self._coverage(priced)
        return table

    @staticmethod
    def _coverage(items: list[dict[str, Any]]) -> dict[str, Any]:
        """细算覆盖率统计。"""
        n = len(items)
        modes = {"detailed": 0, "fallback": 0, "skipped": 0}
        for i in items:
            m = i.get("calc_mode") or "skipped"
            modes[m] = modes.get(m, 0) + 1
        covered = modes["detailed"] + modes["fallback"]
        return {
            **modes,
            "total": n,
            "coverage_pct": round(covered / n * 100, 1) if n else 100.0,
        }


def estimate_from_flat_rows(
    flat_rows: list[dict[str, Any]],
    project_name: str,
    labor_price: float = DEFAULT_LABOR_PRICE,
    price_overrides: dict[str, float] | None = None,
    fee_overrides: dict[str, float] | None = None,
    region: str | None = None,
    custom_consumption: dict[str, dict[str, Any]] | None = None,
    consumption_table: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """flat_rows → 概算表全流程：转换 → 细算 → 汇总。

    consumption_table 缺省 CONSUMPTION（建造）；传 DEMOLITION_CONSUMPTION
    则按拆除定额细算。
    """
    from archilinkai.estimate_schema import aggregate_rows_to_estimate_items

    items = aggregate_rows_to_estimate_items(flat_rows)
    est = CostEstimator(
        labor_price, price_overrides, fee_overrides, region,
        custom_consumption=custom_consumption,
        consumption_table=consumption_table,
    )
    return est.estimate_table(items, project_name)


def split_rows_by_renovation(
    flat_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """按 "renovation" 键拆分 flat_rows。

    返回 (新建行, 拆除行, 已建条数)；Existing 行不计价，仅计数。
    """
    new_rows: list[dict[str, Any]] = []
    demo_rows: list[dict[str, Any]] = []
    existing = 0
    for r in flat_rows:
        st = r.get("renovation")
        if st == "New":
            new_rows.append(r)
        elif st == "ToBeDemolished":
            demo_rows.append(r)
        elif st == "Existing":
            existing += 1
    return new_rows, demo_rows, existing


# summary 中需逐项相加的金额字段
_SUMMARY_SUM_KEYS = (
    "direct_cost", "measure_fee", "management_fee", "profit", "tax",
    "total", "labor_cost", "material_cost", "machine_cost",
)


def combine_estimate_tables(
    new_table: dict[str, Any],
    demo_table: dict[str, Any],
    project_name: str,
) -> dict[str, Any]:
    """新建/拆除两表 → 合计表：summary 逐项相加，items 为两行分组小计。

    含税总价 total = 新建含税总价 + 拆除含税总价。
    """
    from archilinkai.estimate_schema import create_estimate_table

    ns = new_table.get("summary", {}) or {}
    ds = demo_table.get("summary", {}) or {}
    total_summary = {
        k: round((ns.get(k) or 0) + (ds.get(k) or 0), 2)
        for k in _SUMMARY_SUM_KEYS
    }
    rows = [
        (i18n.t("estimate.group_new", "新建概算"), ns),
        (i18n.t("estimate.group_demolition", "拆除概算"), ds),
    ]
    items = [{
        "code": "", "name": label, "unit": "项", "quantity": 1,
        "unit_price": s.get("total", 0.0), "total_price": s.get("total", 0.0),
        "labor_price": s.get("labor_cost", 0.0),
        "material_price": s.get("material_cost", 0.0),
        "machine_price": s.get("machine_cost", 0.0),
    } for label, s in rows]
    table = create_estimate_table(project_name, items, new_table.get("region"))
    table["summary"] = total_summary
    table["notes"] = (list(new_table.get("notes") or [])
                      + list(demo_table.get("notes") or []))
    table["fee_rates"] = dict(new_table.get("fee_rates") or {})
    table["labor_price"] = new_table.get("labor_price")
    return table
