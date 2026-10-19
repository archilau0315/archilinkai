"""算量模板与构件类型映射（V0.51 从 aggregate_service 拆出）。

仅存数据与模板校验，不做查询/汇总，单一职责。
"""
from __future__ import annotations

from typing import Any

# 构件类型英→中映射
_TYPE_CN: dict[str, str] = {
    "Wall": "墙", "Column": "柱", "Beam": "梁", "Slab": "板",
    "Door": "门", "Window": "窗", "Stair": "楼梯", "Roof": "屋顶",
    "Morph": "变形体", "Mesh": "网面", "Opening": "洞口",
    "Zone": "房间区域", "Object": "对象", "Lamp": "灯具",
    "CurtainWall": "幕墙", "Railing": "栏杆", "Shell": "壳体",
    "Skylight": "天窗", "MEPRoutingElement": "机电管线",
}


# 字段与 aggregate() 参数一一对应；description 供人/模型理解用途
QUANTITY_TEMPLATES: dict[str, dict[str, Any]] = {
    "concrete_volume": {
        "description": "混凝土体积：按楼层汇总墙/柱/梁/板的净体积（含 3% 损耗）",
        "quantity": "General_NetVolume",
        "group_by": ["story"],
        "element_types": ["Wall", "Column", "Beam", "Slab"],
        "waste_factor": 0.03,
        "with_code": True,
    },
    "wall_area": {
        "description": "墙体面积：按楼层汇总所有墙的表面积",
        "quantity": "General_SurfaceArea",
        "group_by": ["story"],
        "element_types": ["Wall"],
        "with_code": True,
    },
    "wall_length": {
        "description": "墙体长度：按楼层汇总所有墙的 3D 长度",
        "quantity": "General_3DLength",
        "group_by": ["story"],
        "element_types": ["Wall"],
        "with_code": True,
    },
    "slab_area": {
        "description": "楼板面积：按楼层汇总板的净顶面积",
        "quantity": "General_NetTopSurfaceArea",
        "group_by": ["story"],
        "element_types": ["Slab"],
        "with_code": True,
    },
    "door_window_area": {
        "description": "门窗洞口面积：按类型统计门和窗的洞口面积（宽×高，GB 50500 规则）",
        "formula": "General_Width * General_Height",
        "formula_name": "洞口面积",
        "formula_unit": "m²",
        "group_by": ["type"],
        "element_types": ["Door", "Window"],
        "with_code": True,
    },
    "door_area": {
        "description": "门洞口面积：按楼层汇总门的洞口面积（宽×高）",
        "formula": "General_Width * General_Height",
        "formula_name": "洞口面积",
        "formula_unit": "m²",
        "group_by": ["story"],
        "element_types": ["Door"],
        "with_code": True,
    },
    "window_area": {
        "description": "窗洞口面积：按楼层汇总窗的洞口面积（宽×高）",
        "formula": "General_Width * General_Height",
        "formula_name": "洞口面积",
        "formula_unit": "m²",
        "group_by": ["story"],
        "element_types": ["Window"],
        "with_code": True,
    },
    "zone_area": {
        "description": "房间面积：按楼层汇总房间区域的计算面积",
        "quantity": "Zone_CalculatedArea",
        "group_by": ["story"],
        "element_types": ["Zone"],
        "with_code": True,
    },
    "column_count": {
        "description": "柱计数：按楼层统计柱的数量",
        "quantity": "General_Height",
        "group_by": ["story"],
        "element_types": ["Column"],
        "with_code": True,
    },
    "mep_length": {
        "description": "机电管线长度：按专业汇总风管/水管/桥架的长度",
        "quantity": "General_3DLength",
        "group_by": ["type"],
        "element_types": ["MEPRoutingElement"],
        "with_code": True,
    },
    "wall_summary": {
        "description": "墙体综合：体积+面积+长度按楼层同时出表",
        "quantities": ["General_NetVolume", "General_SurfaceArea", "General_3DLength"],
        "group_by": ["story"],
        "element_types": ["Wall"],
    },
    "wall_paint_area": {
        "description": "墙面涂刷面积：表面积*2（双面），公式法演示",
        "formula": "General_SurfaceArea * 2",
        "formula_name": "涂刷面积",
        "formula_unit": "m²",
        "group_by": ["story"],
        "element_types": ["Wall"],
        "with_code": True,
        "code_override": {"code": "011406001", "name": "墙面喷刷涂料", "unit": "m²"},
    },
    "wall_composite_layers": {
        "description": "复合墙分层算量：内饰面面积/外饰面面积/核心层体积（V0.27 修正）",
        "quantities": ["Wall_NetInsideSurfaceArea", "Wall_NetOutsideSurfaceArea", "General_NetVolume"],
        "group_by": ["story"],
        "element_types": ["Wall"],
        "with_code": True,
    },
    "wall_insulation_area": {
        "description": "墙保温层面积：贴外墙外侧，按外饰面面积算（V0.27 修正）",
        "quantity": "Wall_NetOutsideSurfaceArea",
        "group_by": ["story"],
        "element_types": ["Wall"],
        "with_code": True,
        "code_override": {"code": "011001001", "name": "保温隔热墙面", "unit": "m²"},
    },
    "wall_core_volume": {
        "description": "墙核心层体积：净体积-内层-外层，结构层体积（V0.27 公式法）",
        "formula": "General_NetVolume - Wall_InsideSkinVolume - Wall_OutsideSkinVolume",
        "formula_name": "核心层体积",
        "formula_unit": "m³",
        "group_by": ["story"],
        "element_types": ["Wall"],
        "with_code": True,
    },
    "curtain_wall_area": {
        "description": "幕墙面积：按楼层汇总幕墙表面积（V0.28，幕墙无体积属性）",
        "quantity": "General_SurfaceArea",
        "group_by": ["story"],
        "element_types": ["CurtainWall"],
        "with_code": True,
    },
    "railing_length": {
        "description": "栏杆长度：按楼层汇总栏杆 3D 长度（V0.29，GB 50500 栏杆按 m 计）",
        "quantity": "General_3DLength",
        "group_by": ["story"],
        "element_types": ["Railing"],
        "with_code": True,
    },
    "concrete_volume_by_grade": {
        "description": "混凝土体积分强度：按楼层+类型+强度等级汇总（V0.30，概算分 C25/C30/C35/C40）",
        "quantity": "General_NetVolume",
        "group_by": ["story", "type", "General_ConcreteGrade"],
        "element_types": ["Wall", "Column", "Beam", "Slab"],
        "waste_factor": 0.03,
        "with_code": True,
    },
    "roller_shutter_area": {
        "description": "卷帘门面积：按楼层汇总防火卷帘门洞口面积（V0.30，GB 50500 规则）",
        "formula": "General_Width * General_Height",
        "formula_name": "洞口面积",
        "formula_unit": "m²",
        "group_by": ["story"],
        "element_types": ["Door"],
        "with_code": True,
    },
    "rebar_estimate": {
        "description": "钢筋估算：按混凝土体积×含钢率估算（V0.30，框架结构 0.12-0.18t/m³，默认 0.15）",
        "formula": "General_NetVolume * 0.15",
        "formula_name": "钢筋估算",
        "formula_unit": "t",
        "group_by": ["story", "type"],
        "element_types": ["Wall", "Column", "Beam", "Slab"],
        "with_code": True,
    },
    "formwork_area": {
        "description": "模板面积：按混凝土表面积×0.8 估算（V0.30，扣除底面/顶面不支模部分）",
        "formula": "General_SurfaceArea * 0.8",
        "formula_name": "模板面积",
        "formula_unit": "m²",
        "group_by": ["story", "type"],
        "element_types": ["Wall", "Column", "Beam", "Slab"],
        "with_code": True,
        "code_override": {"code": "011702001", "name": "现浇混凝土模板", "unit": "m²"},
    },
    "facade_paint_area": {
        "description": "外墙真石漆面积：按外饰面面积算（V0.31，概算外檐工程）",
        "quantity": "Wall_NetOutsideSurfaceArea",
        "group_by": ["story"],
        "element_types": ["Wall"],
        "with_code": True,
        "code_override": {"code": "011406001", "name": "墙面喷刷涂料", "unit": "m²"},
    },
    "masonry_volume": {
        "description": "砌体体积：按楼层汇总砌体墙净体积（V0.31，需配合 filters 筛选砌体墙）",
        "quantity": "General_NetVolume",
        "group_by": ["story"],
        "element_types": ["Wall"],
        "with_code": True,
        "code_override": {"code": "010402001", "name": "砖砌体", "unit": "m³"},
    },
    "roof_waterproof_area": {
        "description": "屋面防水面积：按楼层汇总屋顶表面积（V0.35，GB 50500 屋面卷材防水）",
        "quantity": "General_SurfaceArea",
        "group_by": ["story"],
        "element_types": ["Roof"],
        "with_code": True,
        "code_override": {"code": "010902001", "name": "屋面卷材防水", "unit": "m²"},
    },
    "stair_concrete_volume": {
        "description": "楼梯混凝土体积：按楼层汇总楼梯净体积（V0.35）",
        "quantity": "General_NetVolume",
        "group_by": ["story"],
        "element_types": ["Stair"],
        "with_code": True,
        "code_override": {"code": "010506001", "name": "现浇混凝土楼梯", "unit": "m³"},
    },
    "column_concrete_volume": {
        "description": "柱混凝土体积：按楼层汇总柱净体积（V0.35，含 3% 损耗）",
        "quantity": "General_NetVolume",
        "group_by": ["story"],
        "element_types": ["Column"],
        "waste_factor": 0.03,
        "with_code": True,
        "code_override": {"code": "010502001", "name": "现浇混凝土矩形柱", "unit": "m³"},
    },
    "beam_concrete_volume": {
        "description": "梁混凝土体积：按楼层汇总梁净体积（V0.35，含 3% 损耗）",
        "quantity": "General_NetVolume",
        "group_by": ["story"],
        "element_types": ["Beam"],
        "waste_factor": 0.03,
        "with_code": True,
        "code_override": {"code": "010503002", "name": "现浇混凝土矩形梁", "unit": "m³"},
    },
    "ceiling_area": {
        "description": "天棚抹灰面积：按楼层汇总板净底面面积（V0.35）",
        "quantity": "General_NetBottomSurfaceArea",
        "group_by": ["story"],
        "element_types": ["Slab"],
        "with_code": True,
        "code_override": {"code": "011301001", "name": "天棚抹灰", "unit": "m²"},
    },
    "floor_finish_area": {
        "description": "楼地面面层面积：按楼层汇总板净顶面面积（V0.35）",
        "quantity": "General_NetTopSurfaceArea",
        "group_by": ["story"],
        "element_types": ["Slab"],
        "with_code": True,
        "code_override": {"code": "011101001", "name": "水泥砂浆楼地面", "unit": "m²"},
    },
    # ---- V0.39 扩充：装修/屋面/机电 ----
    "wall_plaster_area": {
        "description": "墙面抹灰面积：按楼层汇总墙净内+外饰面面积（GB 50500 墙面抹灰）",
        "quantities": ["Wall_NetInsideSurfaceArea", "Wall_NetOutsideSurfaceArea"],
        "group_by": ["story"],
        "element_types": ["Wall"],
        "with_code": True,
        "code_override": {"code": "011201001", "name": "墙面一般抹灰", "unit": "m²"},
    },
    "wall_inside_paint_area": {
        "description": "内墙涂料面积：按楼层汇总墙净内饰面面积（V0.39）",
        "quantity": "Wall_NetInsideSurfaceArea",
        "group_by": ["story"],
        "element_types": ["Wall"],
        "with_code": True,
        "code_override": {"code": "011406001", "name": "墙面喷刷涂料", "unit": "m²"},
    },
    "roof_insulation_area": {
        "description": "屋面保温层面积：按楼层汇总屋顶表面积（V0.39，保温隔热屋面）",
        "quantity": "General_SurfaceArea",
        "group_by": ["story"],
        "element_types": ["Roof"],
        "with_code": True,
        "code_override": {"code": "010803001", "name": "保温隔热屋面", "unit": "m²"},
    },
    "roof_screed_area": {
        "description": "屋面找平层面积：按楼层汇总屋顶净顶面面积（V0.39）",
        "quantity": "General_NetTopSurfaceArea",
        "group_by": ["story"],
        "element_types": ["Roof"],
        "with_code": True,
    },
    "floor_screed_area": {
        "description": "地面找平层面积：按楼层汇总板净顶面面积（V0.39）",
        "quantity": "General_NetTopSurfaceArea",
        "group_by": ["story"],
        "element_types": ["Slab"],
        "with_code": True,
        "code_override": {"code": "011102001", "name": "地面找平层", "unit": "m²"},
    },
    "floor_tile_area": {
        "description": "地砖面积：按楼层汇总板净顶面面积（V0.39，块料楼地面）",
        "quantity": "General_NetTopSurfaceArea",
        "group_by": ["story"],
        "element_types": ["Slab"],
        "with_code": True,
        "code_override": {"code": "011105002", "name": "块料楼地面", "unit": "m²"},
    },
    "ceiling_paint_area": {
        "description": "天棚涂料面积：按楼层汇总板净底面面积（V0.39）",
        "quantity": "General_NetBottomSurfaceArea",
        "group_by": ["story"],
        "element_types": ["Slab"],
        "with_code": True,
        "code_override": {"code": "011302001", "name": "天棚喷刷涂料", "unit": "m²"},
    },
    "skirting_length": {
        "description": "踢脚线长度：按楼层汇总墙 3D 长度（V0.39，附墙踢脚线）",
        "quantity": "General_3DLength",
        "group_by": ["story"],
        "element_types": ["Wall"],
        "with_code": True,
        "code_override": {"code": "011105003", "name": "踢脚线", "unit": "m"},
    },
    "duct_area": {
        "description": "风管表面积：按楼层汇总机电管线表面积（V0.39，风管按 m²）",
        "quantity": "General_SurfaceArea",
        "group_by": ["story"],
        "element_types": ["MEPRoutingElement"],
        "with_code": True,
        "code_override": {"code": "030702001", "name": "通风管道", "unit": "m²"},
    },
    "pipe_length": {
        "description": "管道长度：按楼层汇总水管长度（V0.39，给排水管道按 m）",
        "quantity": "General_3DLength",
        "group_by": ["story"],
        "element_types": ["MEPRoutingElement"],
        "with_code": True,
        "code_override": {"code": "031001001", "name": "镀锌钢管", "unit": "m"},
    },
    "cable_tray_length": {
        "description": "桥架长度：按楼层汇总桥架长度（V0.39，电气桥架按 m）",
        "quantity": "General_3DLength",
        "group_by": ["story"],
        "element_types": ["MEPRoutingElement"],
        "with_code": True,
        "code_override": {"code": "030404031", "name": "桥架", "unit": "m"},
    },
    # ---- V0.51 扩充：机电保温/配管/电缆 ----
    "pipe_insulation_area": {
        "description": "管道保温面积：按楼层汇总管道外表面积（V0.51，绝热层）",
        "quantity": "General_SurfaceArea",
        "group_by": ["story"],
        "element_types": ["MEPRoutingElement"],
        "with_code": True,
        "code_override": {"code": "031208001", "name": "管道保温", "unit": "m²"},
    },
    "duct_insulation_area": {
        "description": "风管保温面积：按楼层汇总风管外表面积（V0.51，保温隔热）",
        "quantity": "General_SurfaceArea",
        "group_by": ["story"],
        "element_types": ["MEPRoutingElement"],
        "with_code": True,
        "code_override": {"code": "030703001", "name": "通风管道保温", "unit": "m²"},
    },
    "conduit_length": {
        "description": "电气配管长度：按楼层汇总配管 3D 长度（V0.51，GB 50500 配管）",
        "quantity": "General_3DLength",
        "group_by": ["story"],
        "element_types": ["MEPRoutingElement"],
        "with_code": True,
        "code_override": {"code": "030411001", "name": "配管", "unit": "m"},
    },
    "cable_length": {
        "description": "电缆敷设长度：按楼层汇总电缆 3D 长度（V0.51，GB 50500 电缆敷设）",
        "quantity": "General_3DLength",
        "group_by": ["story"],
        "element_types": ["MEPRoutingElement"],
        "with_code": True,
        "code_override": {"code": "030408001", "name": "电缆敷设", "unit": "m"},
    },
}


def get_template(name: str) -> dict[str, Any] | None:
    """按名取预设模板，找不到返回 None。"""
    return QUANTITY_TEMPLATES.get(name)


def validate_template(tpl: dict[str, Any]) -> None:
    """校验自定义模板字段，不合法抛 ValueError。

    必须含 quantity/quantities 或 formula 三者之一。
    可选 with_code（True 时按 GB 50500 清单编码附加 code 列）。
    """
    has_qty = "quantity" in tpl or "quantities" in tpl
    if not has_qty and "formula" not in tpl:
        raise ValueError("模板缺少 quantity/quantities 或 formula 字段")
    if "group_by" not in tpl:
        raise ValueError("模板缺少 group_by 字段")
    if "element_types" not in tpl:
        raise ValueError("模板缺少 element_types 字段")
    qty = tpl.get("quantities", tpl.get("quantity"))
    if isinstance(qty, str):
        tpl.setdefault("quantity", qty)
    elif isinstance(qty, list):
        tpl["quantities"] = qty
