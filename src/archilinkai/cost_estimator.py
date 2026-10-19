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
    # 涂料装饰
    "外墙乳胶漆": 25.0,       # 元/m²
    "内墙乳胶漆": 18.0,       # 元/m²
    "腻子粉": 3.0,            # 元/kg
    "真石漆": 45.0,           # 元/m²
    # 门窗幕墙
    "铝合金型材": 22.0,       # 元/kg
    "中空玻璃": 120.0,        # 元/m²
    "密封胶": 15.0,           # 元/支
    "木材": 1800.0,           # 元/m³
    "门五金": 80.0,           # 元/套
    "窗五金": 60.0,           # 元/套
    # 保温
    "挤塑聚苯板 XPS": 380.0,  # 元/m³
    "岩棉板": 320.0,          # 元/m³
    "粘结砂浆": 900.0,        # 元/t
    "抹面砂浆": 950.0,        # 元/t
    # 模板
    "木模板": 45.0,           # 元/m²
    "钢模板": 55.0,           # 元/m²
    "模板支撑": 8.0,          # 元/m²
    # 楼地面
    "水泥砂浆": 330.0,        # 元/m³（复用 M10 水泥砂浆语义）
    # ---- V0.41 补充：块料/壁纸 ----
    "地砖 600x600": 60.0,     # 元/m²
    "墙砖 300x600": 55.0,     # 元/m²
    "瓷砖粘结剂": 1.2,        # 元/kg
    "填缝剂": 2.0,            # 元/kg
    "瓷砖踢脚线": 12.0,       # 元/m
    "壁纸": 35.0,             # 元/m²
    "壁纸胶": 5.0,            # 元/kg
    # ---- V0.41 补充：给排水 ----
    "镀锌钢管 DN25": 35.0,    # 元/m
    "PPR给水管 DN25": 12.0,   # 元/m
    "PVC排水管 DN110": 45.0,  # 元/m
    "阀门": 65.0,             # 元/个
    "水龙头": 35.0,           # 元/个
    "坐便器": 800.0,          # 元/套
    "洗脸盆": 350.0,          # 元/套
    "淋浴器": 250.0,          # 元/套
    # ---- V0.41 补充：暖通 ----
    "镀锌钢板 δ=0.75": 45.0,  # 元/m²（风管主材）
    "风管保温棉": 22.0,       # 元/m²
    "百叶风口": 80.0,         # 元/个
    "消声器": 200.0,          # 元/个
    "风机盘管": 1500.0,       # 元/台
    # ---- V0.41 补充：电气 ----
    "桥架 200x100": 45.0,     # 元/m
    "电力电缆 YJV-3x16": 85.0,  # 元/m
    "PVC线管 DN20": 6.0,      # 元/m
    "BV电线 2.5mm²": 3.2,     # 元/m
    "BV电线 4mm²": 5.5,       # 元/m
    "开关插座": 18.0,         # 元/套
    "吸顶灯": 80.0,           # 元/套
    "LED灯带": 12.0,          # 元/m
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
    # ---- V0.39 扩充：涂料/门窗幕墙/保温/模板/找平 ----
    "011406001": {  # 墙面喷刷涂料
        "labor_qty": 0.12,
        "materials": [("外墙乳胶漆", 1.05, "m²"),
                      ("腻子粉", 0.6, "kg")],
        "machines": [],
    },
    "010801001": {  # 木质门
        "labor_qty": 0.8,
        "materials": [("木材", 0.05, "m³"),
                      ("门五金", 1.0, "套")],
        "machines": [],
    },
    "010807001": {  # 金属窗
        "labor_qty": 0.6,
        "materials": [("铝合金型材", 8.0, "kg"),
                      ("中空玻璃", 1.1, "m²"),
                      ("密封胶", 0.5, "支"),
                      ("窗五金", 1.0, "套")],
        "machines": [],
    },
    "010805001": {  # 幕墙
        "labor_qty": 1.2,
        "materials": [("铝合金型材", 12.0, "kg"),
                      ("中空玻璃", 1.05, "m²"),
                      ("密封胶", 0.8, "支")],
        "machines": [],
    },
    "011001001": {  # 保温隔热墙面（外墙外保温）
        "labor_qty": 0.18,
        "materials": [("挤塑聚苯板 XPS", 0.05, "m³"),
                      ("粘结砂浆", 0.006, "t"),
                      ("抹面砂浆", 0.006, "t")],
        "machines": [],
    },
    "010803001": {  # 保温隔热屋面
        "labor_qty": 0.06,
        "materials": [("挤塑聚苯板 XPS", 0.08, "m³")],
        "machines": [],
    },
    "011702001": {  # 现浇混凝土模板（综合）
        "labor_qty": 0.35,
        "materials": [("木模板", 0.4, "m²"),
                      ("钢模板", 0.3, "m²"),
                      ("模板支撑", 1.0, "m²")],
        "machines": [],
    },
    "011102001": {  # 地面找平层
        "labor_qty": 0.10,
        "materials": [("M10 水泥砂浆", 0.02, "m³")],
        "machines": [("砂浆搅拌机", 0.004, "台班")],
    },
    "011302001": {  # 天棚喷刷涂料
        "labor_qty": 0.10,
        "materials": [("内墙乳胶漆", 1.05, "m²"),
                      ("腻子粉", 0.5, "kg")],
        "machines": [],
    },
    # ---- V0.41 补充：装修块料/壁纸 ----
    "011105002": {  # 块料楼地面（地砖）
        "labor_qty": 0.25,
        "materials": [("地砖 600x600", 1.02, "m²"),
                      ("瓷砖粘结剂", 4.0, "kg"),
                      ("填缝剂", 0.3, "kg")],
        "machines": [("砂浆搅拌机", 0.02, "台班")],
    },
    "011204001": {  # 墙面块料面层（墙砖）
        "labor_qty": 0.35,
        "materials": [("墙砖 300x600", 1.03, "m²"),
                      ("瓷砖粘结剂", 5.0, "kg"),
                      ("填缝剂", 0.4, "kg")],
        "machines": [],
    },
    "011105003": {  # 踢脚线（瓷砖）
        "labor_qty": 0.05,
        "materials": [("瓷砖踢脚线", 1.05, "m"),
                      ("瓷砖粘结剂", 0.5, "kg")],
        "machines": [],
    },
    "011407001": {  # 墙面壁纸
        "labor_qty": 0.12,
        "materials": [("壁纸", 1.10, "m²"),
                      ("壁纸胶", 0.3, "kg")],
        "machines": [],
    },
    # ---- V0.41 补充：给排水 ----
    "031001001": {  # 镀锌钢管（给水，综合 DN25）
        "labor_qty": 0.18,
        "materials": [("镀锌钢管 DN25", 1.02, "m"),
                      ("阀门", 0.02, "个")],
        "machines": [],
    },
    "031004001": {  # 卫生器具（坐便器+洗脸盆+淋浴器综合）
        "labor_qty": 1.5,
        "materials": [("坐便器", 0.35, "套"),
                      ("洗脸盆", 0.35, "套"),
                      ("淋浴器", 0.30, "套"),
                      ("水龙头", 1.0, "个")],
        "machines": [],
    },
    # ---- V0.41 补充：暖通 ----
    "030702001": {  # 通风管道（镀锌钢板风管）
        "labor_qty": 0.30,
        "materials": [("镀锌钢板 δ=0.75", 1.15, "m²"),
                      ("风管保温棉", 1.0, "m²")],
        "machines": [],
    },
    "030701001": {  # 通风空调设备（风机盘管）
        "labor_qty": 1.0,
        "materials": [("风机盘管", 1.0, "台"),
                      ("百叶风口", 2.0, "个"),
                      ("消声器", 0.5, "个")],
        "machines": [],
    },
    # ---- V0.41 补充：电气 ----
    "030404031": {  # 桥架
        "labor_qty": 0.15,
        "materials": [("桥架 200x100", 1.02, "m")],
        "machines": [],
    },
    "030408001": {  # 电力电缆
        "labor_qty": 0.30,
        "materials": [("电力电缆 YJV-3x16", 1.02, "m")],
        "machines": [],
    },
    "030411001": {  # 配管（PVC线管）
        "labor_qty": 0.12,
        "materials": [("PVC线管 DN20", 1.03, "m")],
        "machines": [],
    },
    "030412001": {  # 配线（BV电线）
        "labor_qty": 0.05,
        "materials": [("BV电线 2.5mm²", 1.10, "m")],
        "machines": [],
    },
    "030404035": {  # 开关插座
        "labor_qty": 0.10,
        "materials": [("开关插座", 1.0, "套")],
        "machines": [],
    },
    "030412004": {  # 照明灯具（吸顶灯）
        "labor_qty": 0.20,
        "materials": [("吸顶灯", 1.0, "套"),
                      ("LED灯带", 0.5, "m")],
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


def merge_custom_consumption(
    custom: dict[str, dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    """合并内置消耗量表与用户自定义定额（自定义优先，覆盖同编码内置项）。

    自定义条目格式：
        {"编码": {"labor_qty": float,
                  "materials": [[名称, 消耗量, 单位], ...],
                  "machines": [[名称, 台班, 单位], ...]}}
    materials/machines 用 list 形式（JSON 无 tuple），合并时转 tuple。
    """
    merged = {k: dict(v) for k, v in CONSUMPTION.items()}
    if not custom:
        return merged
    for code, cons in custom.items():
        if not isinstance(cons, dict) or "labor_qty" not in cons:
            continue
        entry = {
            "labor_qty": float(cons["labor_qty"]),
            "materials": [tuple(m) for m in cons.get("materials", [])],
            "machines": [tuple(m) for m in cons.get("machines", [])],
        }
        merged[str(code)] = entry
    return merged


# ---- 自定义定额持久化（用户目录，跨重启自动加载） ---------------------

def _persisted_quota_path() -> str:
    import os
    return os.path.join(
        os.path.expanduser("~"), ".archilinkai", "custom_quota.json")


def load_persisted_consumption() -> dict[str, dict[str, Any]]:
    """读取已持久化的自定义定额，无文件或损坏返回 {}。"""
    import json
    import os
    path = _persisted_quota_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_persisted_consumption(
    custom: dict[str, dict[str, Any]],
) -> str:
    """把自定义定额写入用户目录，下次 CostEstimator 自动加载。返回路径。"""
    import json
    import os
    path = _persisted_quota_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # materials/machines 转 list 以便 JSON 序列化
    serializable = {}
    for code, cons in (custom or {}).items():
        if not isinstance(cons, dict) or "labor_qty" not in cons:
            continue
        serializable[str(code)] = {
            "labor_qty": float(cons["labor_qty"]),
            "materials": [list(m) for m in cons.get("materials", [])],
            "machines": [list(m) for m in cons.get("machines", [])],
        }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)
    return path


def clear_persisted_consumption() -> None:
    """删除已持久化的自定义定额。"""
    import os
    path = _persisted_quota_path()
    if os.path.exists(path):
        os.remove(path)


class CostEstimator:
    """细算估算器：消耗量 × 市场价 → 人材机 → 取费 → 总价。"""

    def __init__(
        self,
        labor_price: float = DEFAULT_LABOR_PRICE,
        price_overrides: dict[str, float] | None = None,
        fee_overrides: dict[str, float] | None = None,
        region: str | None = None,
        custom_consumption: dict[str, dict[str, Any]] | None = None,
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
        # 消耗量表：内置 + 持久化定额 + 本次传入自定义（优先级递增）
        persisted = load_persisted_consumption()
        merged = {**persisted, **(custom_consumption or {})}
        self.consumption = merge_custom_consumption(merged)
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
            self.notes.append(f"{code} {name}：无消耗量参考，未定价")
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
) -> dict[str, Any]:
    """flat_rows → 概算表全流程：转换 → 细算 → 汇总。"""
    from archilinkai.estimate_schema import aggregate_rows_to_estimate_items

    items = aggregate_rows_to_estimate_items(flat_rows)
    est = CostEstimator(
        labor_price, price_overrides, fee_overrides, region,
        custom_consumption=custom_consumption,
    )
    return est.estimate_table(items, project_name)


# ---- 概算表 xlsx 导出（GB 50500 风格排版） ------------------------------

_EST_HEADERS = ["序号", "项目编码", "项目名称", "计量单位", "工程量",
                "单价(元)", "合价(元)", "人工费(元)", "材料费(元)", "机械费(元)"]


def build_estimate_report(
    table: dict[str, Any],
    filename: str = "estimate",
    out_dir: str | None = None,
    with_chart: bool = True,
) -> str:
    """概算表 → xlsx（标题/项目信息/人材机明细/合计/取费/图表/备注），返回路径。"""
    import os
    import time

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.chart import PieChart, BarChart, Reference

    items = table.get("items") or []
    if not items:
        raise ValueError("概算表 items 为空，无法生成报表")
    s = table.get("summary", {})
    ncol = len(_EST_HEADERS)

    if out_dir is None:
        out_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(out_dir, exist_ok=True)
    safe_name = "".join(c for c in filename if c.isalnum() or c in "-_") \
        or "estimate"
    path = os.path.join(
        out_dir, f"{safe_name}_{time.strftime('%Y%m%d_%H%M%S')}.xlsx")

    bold = Font(bold=True, size=11)
    title_font = Font(bold=True, size=14)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left = Alignment(horizontal="left", vertical="center", wrap_text=True)
    right = Alignment(horizontal="right", vertical="center")
    thin = Side(border_style="thin", color="000000")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    wb = Workbook()
    ws = wb.active
    ws.title = "成本概算表"

    def _put(row, col, val, font=None, align=center, border_=border):
        c = ws.cell(row, col, val)
        c.font = font or Font()
        c.alignment = align
        if border_:
            c.border = border_
        return c

    # 标题 + 项目信息
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    c = ws.cell(1, 1, "工程成本概算表")
    c.font = title_font
    c.alignment = center
    ws.row_dimensions[1].height = 28
    info = (f"工程名称：{table.get('project_name') or '未命名工程'}    "
            f"编制时间：{table.get('date', time.strftime('%Y-%m-%d'))}    "
            f"工日单价：{table.get('labor_price', '-')} 元")
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncol)
    c = ws.cell(2, 1, info)
    c.font = bold
    c.alignment = left
    ws.row_dimensions[2].height = 22

    # 表头
    for i, h in enumerate(_EST_HEADERS, 1):
        _put(3, i, h, bold)
    ws.row_dimensions[3].height = 22

    # 数据行
    row_idx = 4
    for idx, it in enumerate(items, 1):
        vals = [idx, it.get("code", ""), it.get("name", ""),
                it.get("unit", ""), it.get("quantity", ""),
                it.get("unit_price") if it.get("unit_price") is not None else "—",
                it.get("total_price") if it.get("total_price") is not None else "—",
                it.get("labor_price") if it.get("labor_price") is not None else "—",
                it.get("material_price") if it.get("material_price") is not None else "—",
                it.get("machine_price") if it.get("machine_price") is not None else "—"]
        for j, v in enumerate(vals, 1):
            align = left if j == 3 else (
                right if j >= 6 and isinstance(v, (int, float)) else center)
            _put(row_idx, j, v, align=align)
        ws.row_dimensions[row_idx].height = 20
        row_idx += 1

    # 直接费合计
    units = {it.get("unit") for it in items if it.get("unit")}
    if len(units) == 1:
        ws.merge_cells(start_row=row_idx, start_column=1,
                       end_row=row_idx, end_column=6)
        _put(row_idx, 1, "直接费合计", bold)
        _put(row_idx, 7, s.get("direct_cost", 0), bold, right)
        for j in (8, 9, 10):
            _put(row_idx, j, "", bold)
        ws.row_dimensions[row_idx].height = 20
        row_idx += 1

    # 取费块
    fee_rows = [
        ("企业管理费", s.get("management_fee", 0)),
        ("利 润", s.get("profit", 0)),
        ("税 金", s.get("tax", 0)),
    ]
    for label, val in fee_rows:
        ws.merge_cells(start_row=row_idx, start_column=1,
                       end_row=row_idx, end_column=6)
        _put(row_idx, 1, label, bold)
        _put(row_idx, 7, val, bold, right)
        for j in (8, 9, 10):
            _put(row_idx, j, "", bold)
        ws.row_dimensions[row_idx].height = 20
        row_idx += 1
    ws.merge_cells(start_row=row_idx, start_column=1,
                   end_row=row_idx, end_column=6)
    _put(row_idx, 1, "含税总价", bold)
    _put(row_idx, 7, s.get("total", 0), bold, right)
    for j in (8, 9, 10):
        _put(row_idx, j, "", bold)
    ws.row_dimensions[row_idx].height = 22
    row_idx += 2

    # 图表
    if with_chart:
        # 人材机占比饼图
        labor = s.get("labor_cost", 0)
        material = s.get("material_cost", 0)
        machine = s.get("machine_cost", 0)
        if labor + material + machine > 0:
            pie = PieChart()
            pie.title = "人材机占比"
            labels = ["人工费", "材料费", "机械费"]
            data = [labor, material, machine]
            pie.add_data(Reference(ws, min_col=1, min_row=row_idx, max_row=row_idx + 2, max_col=2), titles_from_data=True)
            pie.set_categories(Reference(ws, min_col=1, min_row=row_idx, max_row=row_idx + 2))
            # 写数据到隐藏区域
            ws.cell(row_idx, 1, "人工费")
            ws.cell(row_idx, 2, labor)
            ws.cell(row_idx + 1, 1, "材料费")
            ws.cell(row_idx + 1, 2, material)
            ws.cell(row_idx + 2, 1, "机械费")
            ws.cell(row_idx + 2, 2, machine)
            ws.add_chart(pie, f"H{row_idx}")
            row_idx += 4

        # 取费构成柱状图
        mgmt = s.get("management_fee", 0)
        profit = s.get("profit", 0)
        tax = s.get("tax", 0)
        if mgmt + profit + tax > 0:
            bar = BarChart()
            bar.title = "取费构成"
            bar.y_axis.title = "金额(元)"
            bar.x_axis.title = "费用项"
            data = [mgmt, profit, tax]
            bar.add_data(Reference(ws, min_col=1, min_row=row_idx, max_row=row_idx + 2, max_col=2), titles_from_data=True)
            bar.set_categories(Reference(ws, min_col=1, min_row=row_idx, max_row=row_idx + 2))
            ws.cell(row_idx, 1, "企业管理费")
            ws.cell(row_idx, 2, mgmt)
            ws.cell(row_idx + 1, 1, "利润")
            ws.cell(row_idx + 1, 2, profit)
            ws.cell(row_idx + 2, 1, "税金")
            ws.cell(row_idx + 2, 2, tax)
            ws.add_chart(bar, f"H{row_idx}")
            row_idx += 4

    # 覆盖率 + 备注
    cov = table.get("coverage", {})
    if cov:
        cov_text = (f"细算覆盖率：{cov.get('coverage_pct', '-')}%  "
                    f"(精确 {cov.get('detailed', 0)} / 兜底 "
                    f"{cov.get('fallback', 0)} / 未覆盖 {cov.get('skipped', 0)})")
        ws.merge_cells(start_row=row_idx, start_column=1,
                       end_row=row_idx, end_column=ncol)
        c = ws.cell(row_idx, 1, cov_text)
        c.alignment = left
        row_idx += 1
    for note in table.get("notes") or []:
        ws.merge_cells(start_row=row_idx, start_column=1,
                       end_row=row_idx, end_column=ncol)
        c = ws.cell(row_idx, 1, f"备注：{note}")
        c.alignment = left
        row_idx += 1

    # 列宽
    widths = [6, 14, 24, 9, 12, 12, 14, 12, 14, 12]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    wb.save(path)
    return path
