"""建模计划预览模块（V1.2）。

只做一件事：把建模计划整理成人能看懂、能核对的预览信息，不写入模型。
预览是"先看后建"安全机制的一部分。
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

from model_plan import ModelPlan

# 构件中文名（名称，量词）
_TYPE_CN = {"Wall": ("墙", "面"), "Column": ("柱", "根"),
            "Beam": ("梁", "根"), "Slab": ("板", "块"),
            "Door": ("门", "扇"), "Window": ("窗", "扇"),
            "Stair": ("楼梯", "跑"), "Roof": ("屋顶", "个"),
            "Morph": ("变形体", "个"), "Object": ("对象", "个"),
            "Lamp": ("灯具", "盏"),
            "Mesh": ("网面", "块"), "Opening": ("洞口", "个"),
            "Zone": ("房间区域", "个"), "MEPRoute": ("机电管线", "条")}


def build_preview(
    plan: ModelPlan, channel_name: str | None = None,
    version: str | None = None,
) -> dict[str, Any]:
    """生成预览：一句话总结 + 分类统计 + 逐构件明细。"""
    counter: Counter[str] = Counter(e.type for e in plan.elements)
    wall_length = round(sum(_line_length(e.data)
                            for e in plan.elements if e.type == "Wall"), 3)
    elements = [_describe(e.type, e.data, e.index) for e in plan.elements]

    summary = _summary(counter, wall_length)
    out: dict[str, Any] = {
        "summary": summary,
        "total": len(plan.elements),
        "counts": dict(counter),
        "wall_total_length": wall_length,
        "elements": elements,
        "risk": (
            "创建可在 ArchiCAD 中用 Ctrl+Z 撤销；请核对位置和尺寸后再确认。"
            "注意：门、窗必须挂在直墙上（多边形墙不能挂）；"
            "若项目默认结构为复合结构，板厚以复合层定义为准，"
            "计划中的 thickness 会被覆盖。"
            "屋顶底标高 level 要填当前楼层标高（首层填 0）："
            "填到看不见的楼层会创建失败。屋顶不填坡度时按多平面屋顶创建，"
            "坡面由项目默认设置决定；多平面屋顶不支持开洞，"
            "需要开洞请用单坡屋顶（给 slope）。"
            "变形体支持方块和任意形状（body 顶点+面）；"
            "楼梯按项目默认楼梯规则生成，给出的字段覆盖默认。"
            "对象/灯具的 name 必须与项目已加载库里的部件名完全一致"
            "（中文库如 '沙发 01'），名字不对会报 Not found library part。"
            "网面用 3D 点做起伏地形，底标高 level 与点上的 z 高程别搞混；"
            "独立洞口只能挂墙、板、梁、网面，基点位置决定洞口落在哪。"
            "房间区域自动识别要求房间四周有闭合的墙，识别不出来就改用 polygon 手画。"
            "机电管线折点用 3D 坐标（z 是管底/管中心标高），"
            "风管和水管要选对 domain，截面形状圆形时 width 按直径理解。"
        ),
    }
    if channel_name:
        out["channel"] = f"{channel_name} {version}".strip()
    return out


def _summary(counter: Counter[str], wall_length: float) -> str:
    parts = [
        f"{_TYPE_CN.get(t, (t, '个'))[0]} {n} {_TYPE_CN.get(t, (t, '个'))[1]}"
        for t, n in counter.items()
    ]
    text = f"将创建 {sum(counter.values())} 个构件：" + "、".join(parts)
    if counter.get("Wall"):
        text += f"，墙总长 {wall_length:.2f}m"
    return text


def _describe(element_type: str, data: dict[str, Any], index: int) -> dict[str, Any]:
    if element_type == "Wall":
        length = _line_length(data)
        return {
            "index": index,
            "text": (
                f"墙：({_fmt(data['start'])})→({_fmt(data['end'])})，"
                f"长 {length:.2f}m，高 {data['height']:g}m，厚 {data['thickness']:g}m"
            ),
        }
    if element_type == "Column":
        return {
            "index": index,
            "text": f"柱：({_fmt(data)})，高 {data['height']:g}m",
        }
    if element_type == "Beam":
        length = _line_length(data)
        return {
            "index": index,
            "text": (
                f"梁：({_fmt(data['start'])})→({_fmt(data['end'])})，"
                f"长 {length:.2f}m，截面 {data['width']:g}×{data['height']:g}m，"
                f"顶标高 {data['z']:g}m"
            ),
        }
    if element_type in ("Door", "Window"):
        name = _TYPE_CN[element_type][0]
        wall_text = _host_ref_text(data["wall"], "墙")
        return {
            "index": index,
            "text": (
                f"{name}：挂在{wall_text}，距墙起点 {data['offset']:g}m，"
                f"洞口 {data['width']:g}×{data['height']:g}m，"
                f"{'窗台' if element_type == 'Window' else '门槛'}"
                f"高 {data['sill']:g}m"
            ),
        }
    if element_type == "Stair":
        path = data["path"]
        length = sum(
            _line_length({"start": path[i], "end": path[i + 1]})
            for i in range(len(path) - 1)
        )
        text = (
            f"楼梯：{_fmt(path[0])}→{_fmt(path[-1])}，"
            f"{len(path) - 1} 段基线长 {length:.2f}m，"
            f"梯宽 {data['flightWidth']:g}m，"
            f"总高 {data['totalHeight']:g}m，底标高 {data['z']:g}m"
        )
        if "steps" in data:
            text += f"，{data['steps']} 级"
        return {"index": index, "text": text}
    if element_type == "Morph":
        p = data["position"]
        base = f"变形体：基点 ({p['x']:g},{p['y']:g},{p['z']:g})，"
        if "size" in data:
            s = data["size"]
            text = base + (
                f"尺寸 {s['x']:g}×{s['y']:g}×{s['z']:g}m（方块）"
            )
        else:
            b = data["body"]
            kind = "实体" if b["solid"] else "曲面"
            text = base + (
                f"{kind}，{len(b['vertices'])} 个顶点、"
                f"{len(b['faces'])} 个面（任意形状）"
            )
        return {"index": index, "text": text}
    if element_type == "Roof":
        return {"index": index, "text": _roof_text(data)}
    if element_type in ("Object", "Lamp"):
        name = _TYPE_CN[element_type][0]
        return {
            "index": index,
            "text": (
                f"{name}：'{data['name']}'，"
                f"落点 ({data['x']:g},{data['y']:g},{data['z']:g})"
            ),
        }
    if element_type == "Mesh":
        return {"index": index, "text": _mesh_text(data)}
    if element_type == "Opening":
        return {
            "index": index,
            "text": (
                f"洞口：{_host_ref_text(data['host'])}，"
                f"基点 ({data['basePoint']['x']:g},"
                f"{data['basePoint']['y']:g},{data['basePoint']['z']:g})，"
                f"{data['width']:g}×{data['height']:g}m"
            ),
        }
    if element_type == "Zone":
        return {"index": index, "text": _zone_text(data)}
    if element_type == "MEPRoute":
        return {"index": index, "text": _mep_route_text(data)}
    # Slab：列出顶点数和包围盒范围
    xs = [p["x"] for p in data["polygon"]]
    ys = [p["y"] for p in data["polygon"]]
    text = (
        f"板：{len(data['polygon'])} 个顶点，"
        f"范围 ({min(xs):g},{min(ys):g})~({max(xs):g},{max(ys):g})，"
        f"顶标高 {data['level']:g}m，厚 {data['thickness']:g}m"
    )
    if "holes" in data:
        text += f"，开 {len(data['holes'])} 个洞"
    return {"index": index, "text": text}


def _roof_text(data: dict[str, Any]) -> str:
    """屋顶明细：多边形范围 + 标高厚度 + 坡度信息。"""
    xs = [p["x"] for p in data["polygon"]]
    ys = [p["y"] for p in data["polygon"]]
    text = (
        f"屋顶：{len(data['polygon'])} 个顶点，"
        f"范围 ({min(xs):g},{min(ys):g})~({max(xs):g},{max(ys):g})，"
        f"底标高 {data['level']:g}m，厚 {data['thickness']:g}m"
    )
    if "slope" in data:
        pivot = data.get("pivot")
        if pivot is None:
            axis = "转轴取第 1 条边"
        else:
            axis = f"转轴 ({_fmt(pivot['start'])})→({_fmt(pivot['end'])})"
        text += f"，单坡 {data['slope']:g}°，{axis}"
    else:
        text += "，多平面"
    if "holes" in data:
        text += f"，开 {len(data['holes'])} 个洞"
    return text


def _mep_route_text(data: dict[str, Any]) -> str:
    """机电管线明细：专业、折点数、长度、标高、截面。"""
    path = data["path"]
    length = 0.0
    for a, b in zip(path, path[1:]):
        length += ((b["x"] - a["x"]) ** 2 + (b["y"] - a["y"]) ** 2
                   + (b["z"] - a["z"]) ** 2) ** 0.5
    zs = [p["z"] for p in path]
    domain_cn = {"Ventilation": "风管", "Piping": "水管",
                 "CableCarrier": "桥架"}[data["domain"]]
    shape_cn = {"Rectangular": "矩形", "Circular": "圆形",
                "Oval": "椭圆形", "UShape": "U 形"}[data["shape"]]
    return (
        f"{domain_cn}：{len(path)} 个折点，总长 {length:g}m，"
        f"标高 {min(zs):g}~{max(zs):g}m，{shape_cn}截面 "
        f"{data['width']:g}×{data['height']:g}m"
    )


def _zone_text(data: dict[str, Any]) -> str:
    """房间区域明细：名称编号 + 几何方式与范围。"""
    if "polygon" in data:
        poly = data["polygon"]
        xs = [p["x"] for p in poly]
        ys = [p["y"] for p in poly]
        text = (
            f"房间区域：'{data['name']}'（编号 {data['number']}），"
            f"手动轮廓 {len(poly)} 点，"
            f"范围 ({min(xs):g},{min(ys):g})~({max(xs):g},{max(ys):g})"
        )
    else:
        p = data["referencePoint"]
        text = (
            f"房间区域：'{data['name']}'（编号 {data['number']}），"
            f"自动识别，参考点 ({p['x']:g},{p['y']:g})"
        )
    if "category" in data:
        text += "，已指定类别"
    return text


def _mesh_text(data: dict[str, Any]) -> str:
    """网面明细：顶点数、范围、标高，洞和等高线数量。"""
    poly = data["polygon"]
    xs = [p["x"] for p in poly]
    ys = [p["y"] for p in poly]
    zs = [p["z"] for p in poly]
    text = (
        f"网面：{len(poly)} 个顶点，"
        f"范围 ({min(xs):g},{min(ys):g})~({max(xs):g},{max(ys):g})，"
        f"高程 {min(zs):g}~{max(zs):g}m，底标高 {data['level']:g}m"
    )
    if "holes" in data:
        text += f"，开 {len(data['holes'])} 个洞"
    if "sublines" in data:
        text += f"，{len(data['sublines'])} 条等高线"
    return text


def _line_length(data: dict[str, Any]) -> float:
    dx = data["end"]["x"] - data["start"]["x"]
    dy = data["end"]["y"] - data["start"]["y"]
    return math.hypot(dx, dy)


def _fmt(point: dict[str, Any]) -> str:
    return f"{point['x']:g},{point['y']:g}"


def _host_ref_text(ref: int | str, kind: str = "构件") -> str:
    """宿主引用的通俗说法：计划序号或已有 GUID。kind 为构件种类。"""
    if isinstance(ref, int):
        return f"计划{kind}#{ref}"
    return f"已有{kind} {str(ref)[:8]}…"
