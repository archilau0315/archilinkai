"""特殊构件的校验：楼梯、屋顶、变形体、对象（家具）/灯具。"""

from __future__ import annotations

from typing import Any

from errors import InvalidArgumentError
import plan_values
from plan_values import (coord_number, hole_polygons3d, number,
                        point, point3d, point3z, positive)

#: 本族默认值
_DEFAULTS: dict[str, dict[str, float]] = {
    "Stair": {"z": 0.0, "totalHeight": 3.0, "flightWidth": 1.2},
    "Roof": {"level": 0.0, "thickness": 0.3},
    "Morph": {"x": 0.0, "y": 0.0, "z": 0.0,
              "sx": 1.0, "sy": 1.0, "sz": 1.0},
    "Object": {"x": 0.0, "y": 0.0, "z": 0.0},
    "Mesh": {"level": 0.0},
    "Opening": {"width": 1.0, "height": 2.0},
    "MEPRoute": {"shape": "Rectangular", "width": 0.3, "height": 0.2},
}

#: 机电专业域、截面形状（与 Tapir 枚举一致）
MEP_DOMAINS = frozenset({"Ventilation", "Piping", "CableCarrier"})
MEP_SHAPES = frozenset({"Rectangular", "Circular", "Oval", "UShape"})


def build_object(data: dict[str, Any], index: int) -> dict[str, Any]:
    """对象/灯具（V0.11）：库部件名 name + 落点 x/y/z（默认原点地面）。

    name 必须与项目已加载库里的部件名完全一致（中文库如 '沙发 01'），
    名字不对 Tapir 会报 Not found library part。
    """
    prefix = f"elements[{index}]"
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise InvalidArgumentError(
            f"{prefix}.name", name,
            "应为非空的库部件名（如 '沙发 01'，须与已加载库完全一致）",
        )
    d = _DEFAULTS["Object"]
    return {
        "name": name.strip(),
        "x": coord_number(data.get("x", d["x"]), f"{prefix}.x"),
        "y": coord_number(data.get("y", d["y"]), f"{prefix}.y"),
        "z": coord_number(data.get("z", d["z"]), f"{prefix}.z"),
    }


def build_mesh(data: dict[str, Any], index: int) -> dict[str, Any]:
    """网面（V0.12）：3D 多边形 polygon（≥3 点，点可带高程 z）+ 底标高 level。

    holes 给内部洞（3D 多边形）；sublines 给内部等高线
    （每条线是一串 3D 点），用来做起伏地形。
    """
    prefix = f"elements[{index}]"
    raw_poly = data.get("polygon")
    if not isinstance(raw_poly, list) or len(raw_poly) < 3:
        raise InvalidArgumentError(
            f"{prefix}.polygon", raw_poly, "网面至少需要 3 个顶点"
        )
    polygon = [point3z(p, f"{prefix}.polygon[{i}]")
               for i, p in enumerate(raw_poly)]
    d = _DEFAULTS["Mesh"]
    out: dict[str, Any] = {
        "polygon": polygon,
        "level": number(data.get("level", d["level"]), f"{prefix}.level"),
    }
    if "holes" in data:
        out["holes"] = hole_polygons3d(data["holes"], f"{prefix}.holes")
    if "sublines" in data:
        out["sublines"] = _mesh_sublines(data["sublines"], prefix)
    return out


def _mesh_sublines(raw: Any, prefix: str) -> list[list[dict[str, float]]]:
    """校验网面内部等高线：每条线 ≥1 个 3D 点。"""
    if not isinstance(raw, list) or not raw:
        raise InvalidArgumentError(
            f"{prefix}.sublines", raw, "应为非空的等高线列表"
        )
    out: list[list[dict[str, float]]] = []
    for i, line in enumerate(raw):
        if not isinstance(line, list) or not line:
            raise InvalidArgumentError(
                f"{prefix}.sublines[{i}]", line, "每条线至少 1 个点"
            )
        out.append([point3z(p, f"{prefix}.sublines[{i}][{j}]")
                    for j, p in enumerate(line)])
    return out


def build_opening(data: dict[str, Any], index: int) -> dict[str, Any]:
    """独立洞口（V0.12）：宿主 host + 基点 basePoint + 洞口宽高。

    host 为本计划构件序号（整数）或项目中已有构件 GUID（字符串），
    宿主只能是墙、板、梁、网面。basePoint 是 3D 点（洞口定位点）。
    """
    prefix = f"elements[{index}]"
    host = data.get("host")
    if isinstance(host, bool) or not isinstance(host, (int, str)) \
            or (isinstance(host, str) and not host.strip()):
        raise InvalidArgumentError(
            f"{prefix}.host", host,
            "应为计划构件序号（整数）或已有构件 GUID（字符串）",
        )
    if isinstance(host, int) and host < 0:
        raise InvalidArgumentError(
            f"{prefix}.host", host, "序号不能为负"
        )
    base = point3z(data.get("basePoint"), f"{prefix}.basePoint")
    d = _DEFAULTS["Opening"]
    return {
        "host": host.strip() if isinstance(host, str) else host,
        "basePoint": base,
        "width": positive(data.get("width", d["width"]), f"{prefix}.width"),
        "height": positive(data.get("height", d["height"]), f"{prefix}.height"),
    }


def build_zone(data: dict[str, Any], index: int) -> dict[str, Any]:
    """房间区域（V0.13）：name 房间名 + number 编号，几何二选一。

    - polygon：手动给房间轮廓（≥3 个 2D 点）
    - referencePoint：给房间内一个点，ArchiCAD 自动按周围墙识别房间边界
    category 可选（区域类别属性 GUID），stamp 可选（区域标签落点）。
    """
    prefix = f"elements[{index}]"
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise InvalidArgumentError(
            f"{prefix}.name", name, "应为非空房间名（如 '客厅'）"
        )
    number = data.get("number", str(index + 1))
    if not isinstance(number, str) or not number.strip():
        raise InvalidArgumentError(
            f"{prefix}.number", number, "房间编号应为非空字符串"
        )
    has_poly = "polygon" in data
    has_ref = "referencePoint" in data
    if has_poly == has_ref:
        raise InvalidArgumentError(
            f"{prefix}.polygon", None,
            "polygon（手动轮廓）和 referencePoint（自动识别）必须给且只给一个",
        )

    out: dict[str, Any] = {
        "name": name.strip(),
        "number": number.strip(),
    }
    if has_poly:
        raw_poly = data["polygon"]
        if not isinstance(raw_poly, list) or len(raw_poly) < 3:
            raise InvalidArgumentError(
                f"{prefix}.polygon", raw_poly, "房间轮廓至少需要 3 个顶点"
            )
        out["polygon"] = [point(p, f"{prefix}.polygon[{i}]")
                          for i, p in enumerate(raw_poly)]
    else:
        out["referencePoint"] = point(
            data["referencePoint"], f"{prefix}.referencePoint")

    category = data.get("category")
    if category is not None:
        if not isinstance(category, str) or not category.strip():
            raise InvalidArgumentError(
                f"{prefix}.category", category, "应为非空类别属性 GUID"
            )
        out["category"] = category.strip()
    if "stamp" in data:
        out["stamp"] = point(data["stamp"], f"{prefix}.stamp")
    return out


def build_mep_route(data: dict[str, Any], index: int) -> dict[str, Any]:
    """机电管线路由（V0.14）：domain 专业 + path 3D 折线（≥2 点）。

    domain：Ventilation 风管 / Piping 水管 / CableCarrier 桥架。
    shape 截面形状（默认矩形），width/height 截面尺寸；
    圆形截面时 width 作直径。path 可带高低差（点 z 不同）。
    """
    prefix = f"elements[{index}]"
    domain = data.get("domain")
    if domain not in MEP_DOMAINS:
        raise InvalidArgumentError(
            f"{prefix}.domain", domain,
            "应为 Ventilation（风管）/ Piping（水管）/ CableCarrier（桥架）之一",
        )
    raw_path = data.get("path")
    if not isinstance(raw_path, list) or len(raw_path) < 2:
        raise InvalidArgumentError(
            f"{prefix}.path", raw_path, "管线至少需要 2 个 3D 折点"
        )
    path = [point3z(p, f"{prefix}.path[{i}]")
            for i, p in enumerate(raw_path)]
    shape = data.get("shape", _DEFAULTS["MEPRoute"]["shape"])
    if shape not in MEP_SHAPES:
        raise InvalidArgumentError(
            f"{prefix}.shape", shape,
            "应为 Rectangular/Circular/Oval/UShape 之一",
        )
    d = _DEFAULTS["MEPRoute"]
    return {
        "domain": domain,
        "path": path,
        "shape": shape,
        "width": positive(data.get("width", d["width"]), f"{prefix}.width"),
        "height": positive(data.get("height", d["height"]), f"{prefix}.height"),
    }


def build_stair(data: dict[str, Any], index: int) -> dict[str, Any]:
    """直楼梯/L 形楼梯：基线起止点（或 path 多段折线）+ 底标高 + 总高 + 梯宽；可给踏步数。

    简单直梯：给 start + end（向后兼容）。
    L 形/多段：给 path（≥2 个点的列表），忽略 start/end。
    """
    prefix = f"elements[{index}]"
    if "path" in data:
        raw_path = data["path"]
        if not isinstance(raw_path, list) or len(raw_path) < 2:
            raise InvalidArgumentError(
                f"{prefix}.path", raw_path, "path 至少 2 个点"
            )
        path = [point(p, f"{prefix}.path[{i}]")
                for i, p in enumerate(raw_path)]
        # 检查连续重复点
        for i in range(1, len(path)):
            if path[i] == path[i - 1]:
                raise InvalidArgumentError(
                    f"{prefix}.path[{i-1}]~path[{i}]",
                    path[i], "连续点不能相同"
                )
    else:
        start = point(data.get("start"), f"{prefix}.start")
        end = point(data.get("end"), f"{prefix}.end")
        if start == end:
            raise InvalidArgumentError(
                f"{prefix}.start/end", start, "楼梯起止点不能相同（梯长为 0）"
            )
        path = [start, end]
    d = _DEFAULTS["Stair"]
    z = number(data.get("z", d["z"]), f"{prefix}.z")
    total_height = positive(data.get("totalHeight", d["totalHeight"]),
                            f"{prefix}.totalHeight")
    flight_width = positive(data.get("flightWidth", d["flightWidth"]),
                            f"{prefix}.flightWidth")
    out = {"path": path, "z": z,
           "totalHeight": total_height, "flightWidth": flight_width}
    if "steps" in data:
        steps = data["steps"]
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
            raise InvalidArgumentError(
                f"{prefix}.steps", steps, "应为不小于 1 的整数"
            )
        out["steps"] = steps
    return out


def build_roof(data: dict[str, Any], index: int) -> dict[str, Any]:
    """屋顶：多边形 + 底标高 + 厚度。

    给坡度 slope（度，0~90 不含）= 单坡屋顶，否则多平面。
    单坡转轴默认多边形第 1 条边，也可用 pivot 显式给起止点。
    holes 开洞列表仅在单坡时支持；多平面给了直接报错。
    """
    prefix = f"elements[{index}]"
    raw_poly = data.get("polygon")
    if not isinstance(raw_poly, list) or len(raw_poly) < 3:
        raise InvalidArgumentError(
            f"{prefix}.polygon", raw_poly, "屋顶至少需要 3 个顶点"
        )
    polygon = [point(p, f"{prefix}.polygon[{i}]")
               for i, p in enumerate(raw_poly)]
    d = _DEFAULTS["Roof"]
    level = number(data.get("level", d["level"]), f"{prefix}.level")
    thickness = positive(data.get("thickness", d["thickness"]),
                         f"{prefix}.thickness")
    out = {"polygon": polygon, "level": level, "thickness": thickness}
    if "slope" in data:
        out.update(_roof_slope(data, prefix))
        if "holes" in data:
            out["holes"] = plan_values.hole_polygons(
                data["holes"], f"{prefix}.holes"
            )
    else:
        if "holes" in data:
            raise InvalidArgumentError(
                f"{prefix}.holes", data["holes"],
                "多平面屋顶 Tapir 会静默忽略 holes，"
                "请改用单坡屋顶或先建多平面再手动开洞",
            )
        if "pivot" in data:
            raise InvalidArgumentError(
                f"{prefix}.pivot", data["pivot"],
                "给转轴 pivot 必须同时给坡度 slope",
            )
    return out


def _roof_slope(data: dict[str, Any], prefix: str) -> dict[str, Any]:
    """校验单坡屋顶的坡度与转轴。"""
    slope = data["slope"]
    if (isinstance(slope, bool) or not isinstance(slope, (int, float))
            or not 0 < float(slope) < 90):
        raise InvalidArgumentError(
            f"{prefix}.slope", slope,
            "应为 0~90 度之间的数字（不含 0、90）",
        )
    out: dict[str, Any] = {"slope": float(slope)}
    pivot = data.get("pivot")
    if pivot is not None:
        pivot = {
            "start": point(pivot.get("start"), f"{prefix}.pivot.start"),
            "end": point(pivot.get("end"), f"{prefix}.pivot.end"),
        }
        if pivot["start"] == pivot["end"]:
            raise InvalidArgumentError(
                f"{prefix}.pivot", pivot, "转轴起止点不能相同"
            )
        out["pivot"] = pivot
    return out


def build_morph(data: dict[str, Any], index: int) -> dict[str, Any]:
    """变形体：基点 position + 形状（方块 size / 任意形状 body 二选一）。"""
    prefix = f"elements[{index}]"
    d = _DEFAULTS["Morph"]
    position = point3d(data.get("position"), f"{prefix}.position", d)
    if "size" in data and "body" in data:
        raise InvalidArgumentError(
            prefix, None, "size（方块）和 body（任意形状）只能给一个"
        )
    if "body" in data:
        return {"position": position, "body": build_morph_body(data["body"], prefix)}
    return {"position": position, "size": _morph_size(data.get("size"), d, prefix)}


def _morph_size(raw_size: Any, defaults: dict[str, float],
                prefix: str) -> dict[str, float]:
    if raw_size is None:
        return {"x": defaults["sx"], "y": defaults["sy"], "z": defaults["sz"]}
    if not isinstance(raw_size, dict):
        raise InvalidArgumentError(
            f"{prefix}.size", raw_size, "应为带 x、y、z 的对象"
        )
    return {
        "x": positive(raw_size.get("x"), f"{prefix}.size.x"),
        "y": positive(raw_size.get("y"), f"{prefix}.size.y"),
        "z": positive(raw_size.get("z"), f"{prefix}.size.z"),
    }


def build_morph_body(raw: Any, prefix: str) -> dict[str, Any]:
    """校验任意形状：vertices 顶点 + faces 面（顶点索引）。

    vertices 坐标相对基点；faces 每面 ≥3 个索引、从体外面看逆时针。
    solid=true 需 ≥4 顶点 ≥4 面（闭合实体最低要求）；
    solid=false 是开放曲面，≥2 顶点 ≥1 面。
    """
    if not isinstance(raw, dict):
        raise InvalidArgumentError(f"{prefix}.body", raw, "应为对象")
    raw_verts = raw.get("vertices")
    if not isinstance(raw_verts, list):
        raise InvalidArgumentError(
            f"{prefix}.body.vertices", raw_verts, "应为顶点列表"
        )
    vertices = [
        morph_vertex(v, f"{prefix}.body.vertices[{i}]")
        for i, v in enumerate(raw_verts)
    ]
    raw_faces = raw.get("faces")
    if not isinstance(raw_faces, list) or not raw_faces:
        raise InvalidArgumentError(
            f"{prefix}.body.faces", raw_faces, "应为非空的面列表"
        )
    n = len(vertices)
    faces = [
        morph_face(f, n, f"{prefix}.body.faces[{i}]")
        for i, f in enumerate(raw_faces)
    ]
    solid = raw.get("solid", False)
    if not isinstance(solid, bool):
        raise InvalidArgumentError(
            f"{prefix}.body.solid", solid, "应为 true/false"
        )
    if solid and (n < 4 or len(faces) < 4):
        raise InvalidArgumentError(
            f"{prefix}.body", None,
            "实体至少 4 个顶点、4 个面（四面体起步）",
        )
    if not solid and n < 2:
        raise InvalidArgumentError(
            f"{prefix}.body.vertices", None, "开放曲面至少 2 个顶点"
        )
    return {"vertices": vertices, "faces": faces, "solid": solid}


def morph_vertex(raw: Any, field_name: str) -> dict[str, float]:
    """body 顶点：3D，坐标有界。"""
    if not isinstance(raw, dict):
        raise InvalidArgumentError(field_name, raw, "应为带 x、y、z 的点")
    return {
        "x": coord_number(raw.get("x"), f"{field_name}.x"),
        "y": coord_number(raw.get("y"), f"{field_name}.y"),
        "z": coord_number(raw.get("z"), f"{field_name}.z"),
    }


def morph_face(raw: Any, n_vertices: int, field_name: str) -> list[int]:
    """一个面：≥3 个不超范围的顶点索引。"""
    if (not isinstance(raw, list) or len(raw) < 3
            or any(isinstance(i, bool) or not isinstance(i, int)
                   for i in raw)):
        raise InvalidArgumentError(
            field_name, raw, "应为至少 3 个顶点索引（整数）"
        )
    if any(i < 0 or i >= n_vertices for i in raw):
        raise InvalidArgumentError(
            field_name, raw, f"索引超出顶点范围（共 {n_vertices} 个）"
        )
    return list(raw)
