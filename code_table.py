"""GB 50500 工程量清单编码映射（V0.26）。

按构件类型给出常用清单编码（参考《建设工程工程量清单计价规范》GB 50500-2008）。
模板/算量结果可用 with_code 启用：每个分组行追加 code/code_name/code_unit 列。

约定：
- code     清单编码（9 位数字串，如 "010502001"）
- code_name 清单项名称（如 "现浇混凝土墙"）
- code_unit 清单计量单位（如 "m³"），与算量单位保持一致便于直接出表
"""

from __future__ import annotations

#: 构件类型 → 清单项（编码/名称/单位）
CODE_TABLE: dict[str, dict[str, str]] = {
    "Wall":             {"code": "010502001", "name": "现浇混凝土墙",   "unit": "m³"},
    "Column":           {"code": "010503001", "name": "现浇混凝土柱",   "unit": "m³"},
    "Beam":             {"code": "010504001", "name": "现浇混凝土梁",   "unit": "m³"},
    "Slab":             {"code": "010505001", "name": "现浇混凝土板",   "unit": "m³"},
    "Stair":            {"code": "010506001", "name": "现浇混凝土楼梯", "unit": "m²"},
    "Roof":             {"code": "010901001", "name": "瓦屋面",         "unit": "m²"},
    "Door":             {"code": "010801001", "name": "木质门",         "unit": "樘"},
    "Window":           {"code": "010807001", "name": "金属窗",         "unit": "樘"},
    "CurtainWall":      {"code": "010805001", "name": "幕墙",           "unit": "m²"},
    "Zone":             {"code": "011001001", "name": "房间面积",       "unit": "m²"},
    "MEPRoutingElement":{"code": "030801001", "name": "机电管线",       "unit": "m"},
    "Morph":            {"code": "010507001", "name": "现浇混凝土其他构件", "unit": "m³"},
    "Opening":          {"code": "010808001", "name": "门窗洞口",       "unit": "m²"},
    "Railing":          {"code": "010606001", "name": "金属栏杆",       "unit": "m"},
    "Shell":            {"code": "010507002", "name": "壳体",           "unit": "m³"},
    "Skylight":         {"code": "010807002", "name": "采光天窗",       "unit": "樘"},
}


def lookup(element_type: str | None) -> dict[str, str] | None:
    """按构件类型查清单编码。无映射返回 None。"""
    if not element_type:
        return None
    return CODE_TABLE.get(element_type)
