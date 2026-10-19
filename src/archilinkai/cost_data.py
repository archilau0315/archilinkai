"""成本估算细算引擎（V0.37）。

设计目标：材料市场价 + 人工/机械消耗量分解的细算方式，
避免直接套用单方指标导致高估。

细算路径：
    flat_rows（aggregate 算量结果）
    → aggregate_rows_to_estimate_items（清单条目，V0.32 已有）
    → CostEstimator.estimate_table（消耗量 × 市场价 → 人材机 → 取费 → 总价）

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
