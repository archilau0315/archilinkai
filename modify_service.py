"""构件修改服务（V0.4）：修改计划 → 读当前值 → 通道修改 → 读回验证。

只做调度，不直接拼命令：
- 计划解析/校验：modify_plan
- 能不能改（版本闸门）：ModelChannel.supports_modify
- 真正修改：ModelChannel.modify
- 当前值与改后验证：GetDetailsOfElements

写入安全沿用创建链路：confirm=false 不改；改前核对项目身份；
改后读回逐字段比对；全程记 operation 日志。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import audit_log
import instance_manager
from errors import ConfirmRequiredError
from modify_plan import ModifyPlan
from schemas import OperationLog
from tapir_adapter import _to_dict, adapter as _tapir
from tapir_channel import channel as _default_channel

#: 数值比对容差（米），ArchiCAD 内部按毫米存，0.01 足够
TOL = 0.01


def _read_holes(raw_holes: Any) -> list[list[dict[str, float]]]:
    """把 Tapir details 里的 holes 转成业务格式 [[{x,y}...], ...]。

    Tapir 返回的洞多边形会自动闭合（末点=首点），且起点可能轮换；
    比对前去掉闭合重复点。
    """
    out: list[list[dict[str, float]]] = []
    if not isinstance(raw_holes, list):
        return out
    for hole in raw_holes:
        outline = hole.get("polygonOutline") if isinstance(hole, dict) else None
        if not isinstance(outline, list):
            continue
        pts = [{"x": p.get("x"), "y": p.get("y")}
               for p in outline if isinstance(p, dict)]
        # 去闭合点
        if len(pts) > 1 and pts[0] == pts[-1]:
            pts = pts[:-1]
        out.append(pts)
    return out


def _match_holes(target: list, actual: list) -> bool:
    """洞比对：数量一致 + 每个目标洞在 actual 里找到顶点集合匹配的洞。

    顶点顺序可能轮换（Tapir 规范化），按"集合+容差"匹配。
    """
    if not isinstance(target, list) or not isinstance(actual, list):
        return False
    if len(target) != len(actual):
        return False
    unmatched = list(actual)
    for t_hole in target:
        found = None
        for a_hole in unmatched:
            if _same_polygon(t_hole, a_hole):
                found = a_hole
                break
        if found is None:
            return False
        unmatched.remove(found)
    return True


def _same_polygon(poly1: list, poly2: list) -> bool:
    """两个多边形顶点集合是否一致（容差 TOL，顺序无关）。"""
    if len(poly1) != len(poly2):
        return False
    used = [False] * len(poly2)
    for p1 in poly1:
        ok = False
        for j, p2 in enumerate(poly2):
            if used[j]:
                continue
            if (abs(float(p1["x"]) - float(p2["x"])) <= TOL
                    and abs(float(p1["y"]) - float(p2["y"])) <= TOL):
                used[j] = True
                ok = True
                break
        if not ok:
            return False
    return True


class ModifyService:
    """按修改计划调整已有构件的调度服务。"""

    def __init__(self, mgr=None, logger=None, channel=None) -> None:
        self._mgr = mgr or instance_manager.manager
        self._logger = logger or audit_log.logger
        self._channel = channel or _default_channel

    # --- 预览 -------------------------------------------------------------

    def preview(
        self, source: dict[str, Any], instance: str | None = None
    ) -> dict[str, Any]:
        """读回当前值，列出每项 旧值→新值。不写入。"""
        plan = self._parse(source, instance)
        info = self._mgr.validate_instance(plan.instance)
        self._check_capabilities(plan)

        current = self._read_details(
            [it.guid for it in plan.items], plan.instance
        )
        items: list[dict[str, Any]] = []
        missing: list[str] = []
        for it in plan.items:
            details = current.get(it.guid.lower())
            if details is None:
                missing.append(it.guid)
                continue
            values = self._current_values(it.type, details)
            items.append({
                "index": it.index, "type": it.type, "guid": it.guid,
                "changes": [
                    {"field": name, "from": values.get(name), "to": new}
                    for name, new in it.changes.items()
                ],
            })
        result = {
            "instance": info.instance_id, "project": info.project_name,
            "item_count": len(items), "items": items,
        }
        if missing:
            result["warnings"] = [
                f"构件当前项目中读不到（可能已删除）：{g}" for g in missing
            ]
        return result

    # --- 执行 -------------------------------------------------------------

    def execute(
        self,
        source: dict[str, Any],
        confirm: bool = False,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """确认后修改并读回验证。confirm=false 抛 ConfirmRequiredError。"""
        tool = "modify_from_plan"
        if not confirm:
            raise ConfirmRequiredError(tool, instance)

        plan = self._parse(source, instance)
        info = self._mgr.validate_instance(plan.instance)
        # 先确认还是同一个项目，再逐个确认构件还在（两者报错不同）
        self._mgr.check_project_identity([], plan.instance)
        self._check_targets_exist(plan)
        self._check_capabilities(plan)

        operation_id = self._logger.generate_id()
        timestamp = datetime.now().isoformat(timespec="seconds")

        rows = self._modify_all(plan)
        modified = [r for r in rows if r["ok"]]
        failed = [r for r in rows if not r["ok"]]
        verify = self._verify(plan, rows)

        self._record(operation_id, timestamp, info, tool,
                     len(plan.items), modified, failed, verify["status"])

        return {
            "operation_id": operation_id,
            "instance": info.instance_id,
            "project": info.project_name,
            "verify": verify,
            "modified": modified,
            "failed": failed,
        }

    # --- 内部：计划与能力 -------------------------------------------------

    @staticmethod
    def _parse(
        source: dict[str, Any], instance: str | None
    ) -> ModifyPlan:
        plan = ModifyPlan.from_dict(source)
        # 工具参数 instance 优先于计划内字段
        if instance is not None:
            plan.instance = instance
        return plan

    def _check_capabilities(self, plan: ModifyPlan) -> None:
        """版本闸门：每类构件的 Modify 命令必须可用。"""
        from errors import ChannelCapabilityError

        for element_type in plan.types_used():
            if not self._channel.supports_modify(element_type, plan.instance):
                raise ChannelCapabilityError(
                    self._channel.name, f"Modify {element_type}",
                    hint="当前 Tapir 版本不支持修改此类构件",
                    instance=plan.instance,
                )

    def _check_targets_exist(self, plan: ModifyPlan) -> None:
        """构件存在性预检：直接读 details 判断。

        不用 GetAllElements：真机实测它会漏掉个别构件（原因不明，
        该梁按类型能查到、全量列表里却没有）。
        """
        guids = [it.guid for it in plan.items]
        details = self._read_details(guids, plan.instance)
        missing = [
            g for g in guids if not details.get(g.lower())
        ]
        if missing:
            from errors import InvalidArgumentError

            raise InvalidArgumentError(
                "items.guid", missing,
                "这些构件当前项目中不存在（可能已删除），无法修改",
            )

    # --- 内部：执行 -------------------------------------------------------

    def _modify_all(self, plan: ModifyPlan) -> list[dict[str, Any]]:
        """按类型分组调通道，按计划序号汇总。"""
        results: dict[int, dict[str, Any]] = {}
        for element_type in plan.types_used():
            group = [it for it in plan.items if it.type == element_type]
            payload = [
                {"guid": it.guid, "changes": it.changes} for it in group
            ]
            rows = self._channel.modify(element_type, payload, plan.instance)
            for it, row in zip(group, rows):
                results[it.index] = {
                    "index": it.index, "type": element_type,
                    "guid": it.guid, "ok": row.ok, "error": row.error,
                }
        return [results[i] for i in sorted(results)]

    # --- 内部：读回与验证 -------------------------------------------------

    def _read_details(
        self, guids: list[str], instance: str | None
    ) -> dict[str, dict[str, Any]]:
        """批量读构件细节，按请求顺序对应 GUID 建表。

        注意返回项里的 id 是元素编号（如 SW-001），不是 GUID，
        不能拿它做键；Tapir 保证返回顺序与请求一致。
        """
        params = {
            "elements": [
                {"elementId": {"guid": str(g)}} for g in guids
            ],
            "fields": ["type", "id", "details"],
        }
        raw = _to_dict(_tapir.execute(
            "GetDetailsOfElements", params, instance
        ))
        out: dict[str, dict[str, Any]] = {}
        if not isinstance(raw, dict):
            return out
        items = raw.get("detailsOfElements", [])
        for guid, item in zip(guids, items):
            out[str(guid).lower()] = item.get("details", {})
        return out

    def _current_values(
        self, element_type: str, details: dict[str, Any]
    ) -> dict[str, Any]:
        """从 Tapir details 提取业务字段当前值（字段不存在则不放）。"""
        if element_type == "Wall":
            out: dict[str, Any] = {}
            beg = details.get("begCoordinate")
            if isinstance(beg, dict):
                out["start"] = {"x": beg.get("x"), "y": beg.get("y")}
            end = details.get("endCoordinate")
            if isinstance(end, dict):
                out["end"] = {"x": end.get("x"), "y": end.get("y")}
            if "height" in details:
                out["height"] = details["height"]
            if "begThickness" in details:
                out["thickness"] = details["begThickness"]
            return out
        if element_type == "Column":
            out = {}
            origin = details.get("origin")
            if isinstance(origin, dict):
                out["x"] = origin.get("x")
                out["y"] = origin.get("y")
            for name in ("height", "width", "depth"):
                if name in details:
                    out[name] = details[name]
            return out
        if element_type == "Beam":
            out = {}
            beg = details.get("begCoordinate")
            if isinstance(beg, dict):
                out["start"] = {"x": beg.get("x"), "y": beg.get("y")}
            end = details.get("endCoordinate")
            if isinstance(end, dict):
                out["end"] = {"x": end.get("x"), "y": end.get("y")}
            for name in ("width", "height"):
                if name in details:
                    out[name] = details[name]
            return out
        if element_type == "Slab":
            out = {}
            if "zCoordinate" in details:
                out["level"] = details["zCoordinate"]
            if "thickness" in details:
                out["thickness"] = details["thickness"]
            if "holes" in details:
                out["holes"] = _read_holes(details["holes"])
            return out
        if element_type == "Roof":
            out = {}
            for name in ("thickness", "eavesOverhang"):
                if name in details:
                    out[name] = details[name]
            return out
        # Door / Window
        out = {}
        for name in ("width", "height"):
            if name in details:
                out[name] = details[name]
        if "sillHeight" in details:
            out["sill"] = details["sillHeight"]
        return out

    def _verify(
        self, plan: ModifyPlan, rows: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """读回新值，对修改成功的项逐字段比对。"""
        ok_rows = [r for r in rows if r["ok"]]
        if not ok_rows:
            return {"requested": 0, "verified": 0, "failed": 0,
                    "status": "failed"}
        current = self._read_details(
            [r["guid"] for r in ok_rows], plan.instance
        )
        want = {it.guid.lower(): it for it in plan.items}
        verified = 0
        for r in ok_rows:
            item = want[r["guid"].lower()]
            details = current.get(r["guid"].lower(), {})
            values = self._current_values(item.type, details)
            if all(self._match(name, new, values.get(name))
                   for name, new in item.changes.items()):
                r["matched"] = True
                verified += 1
            else:
                r["matched"] = False
        requested = len(ok_rows)
        status = ("success" if verified == requested
                  else "partial_success" if verified else "failed")
        return {"requested": requested, "verified": verified,
                "failed": requested - verified, "status": status}

    @staticmethod
    def _match(field: str, target: Any, actual: Any) -> bool:
        """目标值与读回值比对；actual 为 None（字段没读到）直接失败。"""
        if actual is None:
            return False
        if field == "holes":
            return _match_holes(target, actual)
        if isinstance(target, dict):
            return all(
                abs(float(actual[k]) - float(target[k])) <= TOL
                for k in ("x", "y")
            )
        return abs(float(actual) - float(target)) <= TOL

    # --- 内部：日志 -------------------------------------------------------

    def _record(self, operation_id, timestamp, info, tool, total,
                modified, failed, verify_status) -> None:
        self._logger.log(OperationLog(
            operation_id=operation_id, timestamp=timestamp,
            instance=info.instance_id, project=info.project_name, tool=tool,
            target_count=total,
            after={"modified": modified, "failed": failed},
            execute_status="success" if modified else "failed",
            verify_status=verify_status,
        ))


# 模块级单例
service = ModifyService()
