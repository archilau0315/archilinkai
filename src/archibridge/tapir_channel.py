"""Tapir 建模通道（V0.2）：ModelChannel 的 Tapir 实现。

职责（只做这一件事）：把已校验的计划元素翻译成 Tapir 创建命令并解析结果。
能力与参数结构来自 Tapir 1.5.9 源码 + AC29 真机实测。

V0.3 支持：Wall、Column、Beam、Slab、Door、Window、Stair、Roof、Morph。
门、窗由 create_service 先把"墙引用"解析成真实 GUID，再交给本通道。
变形体 V0.3 只支持方块；屋顶支持多平面和单坡。
V0.11 新增：Object（家具）、Lamp（灯具），按库部件名放置。
"""

from __future__ import annotations

import math
from typing import Any

from archibridge import instance_manager
from archibridge.channel_base import CreateResult, ModelChannel
from archibridge.tapir_adapter import _to_dict, adapter as _tapir

# 业务元素类型 →（Tapir 创建命令名，请求数组字段名）
_COMMAND: dict[str, tuple[str, str]] = {
    "Wall": ("CreateWalls", "wallsData"),
    "Column": ("CreateColumns", "columnsData"),
    "Beam": ("CreateBeams", "beamsData"),
    "Slab": ("CreateSlabs", "slabsData"),
    "Door": ("CreateDoors", "doorsData"),
    "Window": ("CreateWindows", "windowsData"),
    "Stair": ("CreateStairs", "stairsData"),
    "Roof": ("CreateRoofs", "roofsData"),
    "Morph": ("CreateMorphs", "morphsData"),
    "Object": ("CreateObjects", "objectsData"),
    "Lamp": ("CreateLamps", "lampsData"),
    "Mesh": ("CreateMeshes", "meshesData"),
    "Opening": ("CreateOpenings", "openingsData"),
    "Zone": ("CreateZones", "zonesData"),
    "MEPRoute": ("CreateMEPRoutingElements", "routingElementsData"),
}

# 业务元素类型 →（Tapir 修改命令名，请求数组字段名），V0.4
_MODIFY_COMMAND: dict[str, tuple[str, str]] = {
    "Wall": ("ModifyWalls", "wallsWithDetails"),
    "Column": ("ModifyColumns", "columnsWithDetails"),
    "Beam": ("ModifyBeams", "beamsWithDetails"),
    "Slab": ("ModifySlabs", "slabsWithDetails"),
    "Roof": ("ModifyRoofs", "roofsWithDetails"),
    "Door": ("ModifyDoors", "doorsWithDetails"),
    "Window": ("ModifyWindows", "windowsWithDetails"),
}


class TapirChannel(ModelChannel):
    """通过 Tapir Add-On 创建构件。"""

    name = "Tapir"

    def __init__(self, mgr: instance_manager.InstanceManager | None = None) -> None:
        self._mgr = mgr or instance_manager.manager
        # 可用性缓存：{instance: {element_type: bool}}，单次计划内避免重复查询
        self._avail_cache: dict[str, dict[str, bool]] = {}

    # --- 版本与能力（只读）------------------------------------------------

    def get_version(self, instance: str | None = None) -> str:
        try:
            result = _to_dict(_tapir.execute("GetAddOnVersion", None, instance))
            return str(result.get("version", "unknown"))
        except Exception:
            return "unknown"

    def supports(self, element_type: str, instance: str | None = None) -> bool:
        mapping = _COMMAND.get(element_type)
        if mapping is None:
            return False
        return self._command_available(mapping[0], element_type, instance)

    def supports_modify(
        self, element_type: str, instance: str | None = None
    ) -> bool:
        mapping = _MODIFY_COMMAND.get(element_type)
        if mapping is None:
            return False
        return self._command_available(
            mapping[0], f"modify:{element_type}", instance
        )

    def supports_delete(self, instance: str | None = None) -> bool:
        return self._command_available(
            "DeleteElements", "delete", instance
        )

    def _command_available(
        self, command_name: str, cache_key: str,
        instance: str | None = None,
    ) -> bool:
        """查某 Tapir 命令在实例上是否可用，按实例缓存。"""
        iid = self._mgr.get_info(instance).instance_id
        cached = self._avail_cache.setdefault(iid, {})
        if cache_key in cached:
            return cached[cache_key]
        try:
            conn = self._mgr.get_conn(instance)
            cid = conn.types.AddOnCommandId("TapirCommand", command_name)
            ok = bool(conn.commands.IsAddOnCommandAvailable(cid))
        except Exception:
            ok = False
        cached[cache_key] = ok
        return ok

    # --- 创建 -------------------------------------------------------------

    def create(
        self,
        element_type: str,
        items: list[dict[str, Any]],
        instance: str | None = None,
    ) -> list[CreateResult]:
        if not items:
            return []
        command_name, field_name = _COMMAND[element_type]
        params = {field_name: [self._build_param(element_type, it) for it in items]}
        raw = _to_dict(_tapir.execute(command_name, params, instance))
        rows = raw.get("elements", []) if isinstance(raw, dict) else []
        return [self._parse_row(row) for row in rows]

    def exists(
        self,
        element_type: str,
        guid: str,
        instance: str | None = None,
    ) -> bool:
        """MEP 路由专用：GetMEPRoutingElements 无 error 行即存在。

        路由在 GetAllElements 中不出现，只能用 MEP 专用查询确认。
        """
        if element_type != "MEPRoute":
            raise NotImplementedError(f"exists 暂仅支持 MEPRoute")
        raw = _to_dict(_tapir.execute(
            "GetMEPRoutingElements",
            {"elements": [{"elementId": {"guid": guid}}]}, instance))
        rows = raw.get("routingElements", []) if isinstance(raw, dict) else []
        return bool(rows) and "error" not in rows[0]

    # --- 修改（V0.4）------------------------------------------------------

    def modify(
        self,
        element_type: str,
        items: list[dict[str, Any]],
        instance: str | None = None,
    ) -> list[CreateResult]:
        if not items:
            return []
        command_name, field_name = _MODIFY_COMMAND[element_type]
        params = {
            field_name: [
                self._build_modify_param(element_type, it) for it in items
            ]
        }
        raw = _to_dict(_tapir.execute(command_name, params, instance))
        rows = raw.get("executionResults", []) if isinstance(raw, dict) else []
        return [self._parse_modify_row(row) for row in rows]

    def delete(
        self,
        guids: list[str],
        instance: str | None = None,
    ) -> CreateResult:
        """整批删除，返回一个结果。空列表按成功处理。"""
        if not guids:
            return CreateResult(ok=True)
        params = {
            "elements": [
                {"elementId": {"guid": str(g)}} for g in guids
            ]
        }
        raw = _to_dict(_tapir.execute("DeleteElements", params, instance))
        if isinstance(raw, dict) and raw.get("success") is True:
            return CreateResult(ok=True)
        err = raw.get("error") if isinstance(raw, dict) else None
        msg = err.get("message", str(err)) if isinstance(err, dict) else \
            f"无法解析的返回：{raw}"
        return CreateResult(ok=False, error=msg)

    def _build_modify_param(
        self, element_type: str, item: dict[str, Any]
    ) -> dict[str, Any]:
        """把 {guid, changes} 翻译成 Tapir Modify 入参。"""
        param: dict[str, Any] = {"elementId": {"guid": item["guid"]}}
        changes = item["changes"]
        if element_type == "Wall":
            if "start" in changes:
                param["begCoordinate"] = dict(changes["start"])
            if "end" in changes:
                param["endCoordinate"] = dict(changes["end"])
            for name in ("height", "thickness"):
                if name in changes:
                    param[name] = changes[name]
        elif element_type == "Column":
            if "x" in changes:  # x/y 已由计划保证成对
                param["origin"] = {"x": changes["x"], "y": changes["y"]}
            for name in ("height", "width", "depth"):
                if name in changes:
                    param[name] = changes[name]
        elif element_type == "Beam":
            if "start" in changes:
                param["begCoordinate"] = dict(changes["start"])
            if "end" in changes:
                param["endCoordinate"] = dict(changes["end"])
            for name in ("width", "height"):
                if name in changes:
                    param[name] = changes[name]
        elif element_type == "Slab":
            if "level" in changes:
                param["zCoordinate"] = changes["level"]
            if "thickness" in changes:
                param["thickness"] = changes["thickness"]
            if "holes" in changes:
                param["holes"] = [
                    {"polygonCoordinates": [{"x": p["x"], "y": p["y"]} for p in hole]}
                    for hole in changes["holes"]
                ]
        elif element_type == "Roof":
            for name in ("thickness", "eavesOverhang"):
                if name in changes:
                    param[name] = changes[name]
        else:  # Door / Window
            for name in ("width", "height"):
                if name in changes:
                    param[name] = changes[name]
            if "sill" in changes:
                param["sillHeight"] = changes["sill"]
        return param

    @staticmethod
    def _parse_modify_row(row: Any) -> CreateResult:
        if not isinstance(row, dict):
            return CreateResult(ok=False, error=f"无法解析的返回：{row}")
        if row.get("success") is True:
            return CreateResult(ok=True)
        err = row.get("error")
        msg = err.get("message", str(err)) if isinstance(err, dict) else str(row)
        return CreateResult(ok=False, error=msg)

    # --- 参数拼装与结果解析（内部）----------------------------------------

    def _build_param(
        self, element_type: str, item: dict[str, Any]
    ) -> dict[str, Any]:
        if element_type == "Wall":
            return {
                "begCoordinate": {"x": item["start"]["x"], "y": item["start"]["y"]},
                "endCoordinate": {"x": item["end"]["x"], "y": item["end"]["y"]},
                "height": item["height"],
                "thickness": item["thickness"],
            }
        if element_type == "Column":
            # z 默认 0（落在首层地面）
            return {
                "coordinates": {"x": item["x"], "y": item["y"], "z": 0.0},
                "height": item["height"],
            }
        if element_type == "Beam":
            # Tapir 必填：begCoordinate / endCoordinate / zCoordinate（顶标高）
            # 截面宽高独立必须关闭联动
            return {
                "begCoordinate": {"x": item["start"]["x"], "y": item["start"]["y"]},
                "endCoordinate": {"x": item["end"]["x"], "y": item["end"]["y"]},
                "zCoordinate": item["z"],
                "width": item["width"],
                "height": item["height"],
                "isWidthAndHeightLinked": False,
            }
        if element_type in ("Door", "Window"):
            # item 已由 create_service 解析：ownerWallGuid 是真实墙 GUID
            return {
                "ownerWallId": {"guid": item["ownerWallGuid"]},
                "centerOffset": item["offset"],
                "sillHeight": item["sill"],
                "width": item["width"],
                "height": item["height"],
            }
        if element_type == "Stair":
            # 必填 baseLinePoints（≥2 点）+ zCoordinate；多段 path 支持 L 形
            param = {
                "baseLinePoints": [
                    {"x": p["x"], "y": p["y"]} for p in item["path"]
                ],
                "zCoordinate": item["z"],
                "totalHeight": item["totalHeight"],
                "flightWidth": item["flightWidth"],
            }
            if "steps" in item:
                param["stepNum"] = item["steps"]
            return param
        if element_type == "Morph":
            return self._build_morph_param(item)
        if element_type == "Roof":
            return self._build_roof_param(item)
        if element_type in ("Object", "Lamp"):
            # 对象/灯具：库部件名 + 落点坐标（V0.11）
            return {
                "libraryPartName": item["name"],
                "coordinates": {"x": item["x"], "y": item["y"], "z": item["z"]},
            }
        if element_type == "Mesh":
            return self._build_mesh_param(item)
        if element_type == "Opening":
            # item 已由 create_service 解析：ownerGuid 是真实宿主 GUID
            return {
                "ownerElementId": {"guid": item["ownerGuid"]},
                "basePoint": {"x": item["basePoint"]["x"],
                              "y": item["basePoint"]["y"],
                              "z": item["basePoint"]["z"]},
                "width": item["width"], "height": item["height"],
            }
        if element_type == "Zone":
            return self._build_zone_param(item)
        if element_type == "MEPRoute":
            return self._build_mep_route_param(item)
        # Slab：必填 level + polygonCoordinates（≥3 点）；可选 holes
        param = {
            "level": item["level"],
            "thickness": item["thickness"],
            "referencePlaneLocation": "Top",
            "polygonCoordinates": [
                {"x": p["x"], "y": p["y"]} for p in item["polygon"]
            ],
        }
        if "holes" in item:
            param["holes"] = [
                {"polygonCoordinates": [{"x": p["x"], "y": p["y"]} for p in hole]}
                for hole in item["holes"]
            ]
        return param

    @staticmethod
    def _build_mesh_param(item: dict[str, Any]) -> dict[str, Any]:
        """网面参数：3D 多边形 + 底标高，可带 3D 洞和内部等高线。"""
        param: dict[str, Any] = {
            "level": item["level"],
            "polygonCoordinates": [
                {"x": p["x"], "y": p["y"], "z": p["z"]}
                for p in item["polygon"]
            ],
        }
        if "holes" in item:
            param["holes"] = [
                {"polygonCoordinates": [
                    {"x": p["x"], "y": p["y"], "z": p["z"]} for p in hole]}
                for hole in item["holes"]
            ]
        if "sublines" in item:
            param["sublines"] = [
                {"coordinates": [
                    {"x": p["x"], "y": p["y"], "z": p["z"]} for p in line]}
                for line in item["sublines"]
            ]
        return param

    @staticmethod
    def _build_zone_param(item: dict[str, Any]) -> dict[str, Any]:
        """房间区域参数：名称/编号 + 几何（手动多边形或自动识别点）。"""
        param: dict[str, Any] = {
            "name": item["name"], "numberStr": item["number"],
        }
        if "polygon" in item:
            param["geometry"] = {
                "polygonCoordinates": [
                    {"x": p["x"], "y": p["y"]} for p in item["polygon"]]
            }
        else:
            p = item["referencePoint"]
            param["geometry"] = {
                "referencePosition": {"x": p["x"], "y": p["y"]}}
        if "category" in item:
            param["categoryAttributeId"] = {"guid": item["category"]}
        if "stamp" in item:
            param["stampPosition"] = {"x": item["stamp"]["x"],
                                      "y": item["stamp"]["y"]}
        return param

    @staticmethod
    def _build_mep_route_param(item: dict[str, Any]) -> dict[str, Any]:
        """机电管线参数：专业 + 3D 折点 + 截面形状与尺寸。"""
        return {
            "domain": item["domain"],
            "nodeCoordinates": [
                {"x": p["x"], "y": p["y"], "z": p["z"]}
                for p in item["path"]],
            "crossSectionShape": item["shape"],
            "crossSectionWidth": item["width"],
            "crossSectionHeight": item["height"],
        }

    @staticmethod
    def _build_morph_param(item: dict[str, Any]) -> dict[str, Any]:
        """变形体：basePoint +（方块 size 或任意形状 body）。"""
        p = item["position"]
        param: dict[str, Any] = {
            "basePoint": {"x": p["x"], "y": p["y"], "z": p["z"]}
        }
        if "size" in item:
            s = item["size"]
            param["size"] = {"x": s["x"], "y": s["y"], "z": s["z"]}
            return param
        b = item["body"]
        param["body"] = {
            "bodyType": "Solid" if b["solid"] else "Surface",
            "vertices": [
                {"x": v["x"], "y": v["y"], "z": v["z"]}
                for v in b["vertices"]
            ],
            "polygons": [
                {"vertexIds": list(f)} for f in b["faces"]
            ],
        }
        return param

    @staticmethod
    def _build_roof_param(item: dict[str, Any]) -> dict[str, Any]:
        """屋顶参数：给 slope=单坡（角度换算成弧度），否则多平面。"""
        param = {
            "level": item["level"],
            "thickness": item["thickness"],
            "polygonCoordinates": [
                {"x": p["x"], "y": p["y"]} for p in item["polygon"]
            ],
        }
        if "holes" in item:
            param["holes"] = [
                {"polygonCoordinates": [{"x": p["x"], "y": p["y"]} for p in hole]}
                for hole in item["holes"]
            ]
        if "slope" not in item:
            return param
        # 单坡转轴：显式 pivot 优先，否则取多边形第 1 条边
        pivot = item.get("pivot")
        if pivot is None:
            beg, end = item["polygon"][0], item["polygon"][1]
        else:
            beg, end = pivot["start"], pivot["end"]
        param["pivotLine"] = {
            "begCoordinate": {"x": beg["x"], "y": beg["y"]},
            "endCoordinate": {"x": end["x"], "y": end["y"]},
        }
        param["angle"] = math.radians(item["slope"])
        return param

    @staticmethod
    def _parse_row(row: Any) -> CreateResult:
        if not isinstance(row, dict):
            return CreateResult(ok=False, error=f"无法解析的返回：{row}")
        element_id = row.get("elementId")
        if isinstance(element_id, dict) and element_id.get("guid"):
            return CreateResult(ok=True, guid=str(element_id["guid"]))
        err = row.get("error")
        msg = err.get("message", str(err)) if isinstance(err, dict) else str(row)
        return CreateResult(ok=False, error=msg)


# 模块级单例
channel = TapirChannel()
