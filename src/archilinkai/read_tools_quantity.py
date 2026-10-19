"""只读工具子模块：算量 / 汇总 / 概算 / 导出（V0.52 拆出）。

只做一件事：向 FastMCP 注册算量与导出类工具。
通过 register(mcp, safe) 调用，复用 server 的统一异常包装。
"""

from __future__ import annotations

from typing import Any

from archilinkai import aggregate_service
from archilinkai import errors
from archilinkai import i18n
from archilinkai import instance_manager
from archilinkai import property_service
from mcp.server.fastmcp import FastMCP
from archilinkai.schemas import success_result


def register(mcp: FastMCP, safe) -> None:
    """注册算量与导出类工具。safe 为 server._safe（统一异常包装）。"""

    #: 默认工程量清单（BuiltIn 属性名，AC29 真机验证可读）
    DEFAULT_QUANTITIES = [
        "General_3DLength", "General_Height", "General_Width",
        "General_Thickness", "General_GrossVolume", "General_NetVolume",
        "General_SurfaceArea", "General_Area",
        "General_GrossTopSurfaceArea", "General_NetTopSurfaceArea",
        "General_GrossEdgeSurfaceArea", "General_NetEdgeSurfaceArea",
        "General_GrossBottomSurfaceArea", "General_NetBottomSurfaceArea",
    ]

    @mcp.tool()
    def get_element_quantities(
        element_guids: list[str],
        quantities: list[str] | None = None,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """批量读取工程量（面积/体积/长度等），带单位标注。算量取数入口。

        quantities 缺省用默认 14 项通用量；也可传任意 BuiltIn 属性名，
        如 Wall_ReferenceLineLength、Slab_GrossTopSurfaceArea、
        Zone_CalculatedArea 等。元素不支持某项时该项 value 为 None。
        单位按项目默认公制：长度 m、面积 m²、体积 m³。

        English: Batch-read quantities (area/volume/length, etc.) with unit labels; the takeoff data entry point.
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            names = quantities or DEFAULT_QUANTITIES
            data = property_service.service.get_quantities(
                element_guids, names, instance
            )
            items = [
                {"guid": g, "quantities": data[g]} for g in element_guids
            ]
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(items), items=items,
            )
        return safe(instance, _run)

    @mcp.tool()
    def get_property_definition(
        property_name: str, instance: str | None = None
    ) -> dict[str, Any]:
        """查属性定义：类型/单位/分组/描述；枚举属性附带全部可选项。

        English: Look up a property definition: type/unit/group/description; enums list all options.
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            d = property_service.service.get_property_definition(
                property_name, instance)
            if d is None:
                raise errors.PropertyNotFoundError(
                    property_name, instance,
                    suggestions=property_service.service
                    .suggest_property_names(property_name, instance),
                )
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=1, data=d,
            )
        return safe(instance, _run)

    @mcp.tool()
    def aggregate_quantities(
        quantity: str | None = None,
        group_by: list[str] | None = None,
        element_type: str | None = None,
        stories: list[int] | None = None,
        filters: list[dict] | None = None,
        instance: str | None = None,
        classification: str | None = None,
        formula: str | None = None,
        formula_name: str | None = None,
    ) -> dict[str, Any]:
        """按维度分组汇总工程量（count/sum/avg）。算量出表入口。

        quantity 为 BuiltIn 量名（如 General_NetVolume）；或用 formula 自定义公式
        （如 "General_NetVolume * 1.03"），需配 formula_name（结果列名）。
        group_by 维度："type"（构件类型）、"story"（楼层）或属性名，可多选，
        缺省 ["type"]。例：按楼层汇总墙的净体积 →
        quantity="General_NetVolume", element_type="Wall", group_by=["story"]
        classification：只统计挂了该分类项的元素，如 "标准墙"。

        English: Group and aggregate quantities by dimension (count/sum/avg); the takeoff table entry point.
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            data = aggregate_service.service.aggregate(
                quantity, group_by, element_type, stories, filters, instance,
                classification, formula=formula, formula_name=formula_name,
            )
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(data["rows"]),
                data={"unit": data["unit"], "groups": data["rows"],
                      "flat": data["flat_rows"],
                      "warnings": data.get("warnings", [])},
            )
        return safe(instance, _run)

    @mcp.tool()
    def list_quantity_templates() -> dict[str, Any]:
        """列出所有预设算量规则模板名及说明，供 aggregate_by_template 调用。

        English: List all preset quantity template names and descriptions for aggregate_by_template.
        """
        def _run() -> dict[str, Any]:
            items = [
                {"name": k, "description": i18n.template_desc(k, v["description"])}
                for k, v in aggregate_service.QUANTITY_TEMPLATES.items()
            ]
            return success_result(count=len(items), items=items)
        return safe(None, _run)

    @mcp.tool()
    def aggregate_by_template(
        template_name: str, instance: str | None = None,
    ) -> dict[str, Any]:
        """按预设模板算量（如 concrete_volume 混凝土体积、wall_area 墙体面积）。
        用 list_quantity_templates 查看全部模板。

        English: Aggregate quantities by a preset template (e.g. concrete_volume, wall_area).
        """
        def _run() -> dict[str, Any]:
            info = instance_manager.manager.get_info(instance)
            data = aggregate_service.service.aggregate_by_template(
                template_name, instance)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(data["rows"]),
                data={"template": data["template"],
                      "description": data["description"],
                      "unit": data["unit"],
                      "groups": data["rows"],
                      "flat": data["flat_rows"],
                      "warnings": data.get("warnings", [])},
            )
        return safe(instance, _run)

    @mcp.tool()
    def aggregate_by_custom_template(
        template: dict[str, Any],
        instance: str | None = None,
    ) -> dict[str, Any]:
        """按自定义模板算量。

        template 须含（三选一）：
        - quantity（单量 str）或 quantities（多量 list）或 formula（规则公式 str）
        - group_by：分组维度（type/story/属性名）
        - element_types：构件类型列表（如 ["Wall","Column"]）
        可选：description / waste_factor（损耗系数）
              formula_name（公式结果列名）/ formula_unit（公式结果单位）

        示例1（普通量）：
        {"quantity":"General_NetVolume","group_by":["story"],
         "element_types":["Wall"],"waste_factor":0.05,
         "description":"墙体体积含5%损耗"}
        示例2（公式法）：
        {"formula":"General_NetVolume * 1.03","formula_name":"含损耗体积",
         "formula_unit":"m³","group_by":["story"],
         "element_types":["Wall","Column"],"description":"混凝土含3%损耗"}

        English: Aggregate quantities by a custom template.
        """
        def _run() -> dict[str, Any]:
            data = aggregate_service.service.aggregate_by_custom_template(
                template, instance)
            return success_result(
                instance=instance,
                count=len(data["rows"]),
                data={"rows": data["rows"],
                      "flat_rows": data["flat_rows"],
                      "unit" if "unit" in data else "units":
                          data.get("unit", data.get("units")),
                      "template": data["template"],
                      "description": data["description"],
                      "warnings": data.get("warnings", [])},
            )
        return safe(instance, _run)

    @mcp.tool()
    def estimate_cost(
        rows: list[dict[str, Any]],
        project_name: str,
        labor_price: float = 130.0,
        price_overrides: dict[str, float] | None = None,
        fee_overrides: dict[str, float] | None = None,
        region: str | None = None,
    ) -> dict[str, Any]:
        """成本估算细算：由算量 flat_rows 出人材机分解概算表。

        rows 传 aggregate_quantities / aggregate_by_template 的 flat 数组
        （须含 code/code_name/code_unit 列，即模板 with_code=true）。
        细算路径：消耗量 × 市场价 → 人工/材料/机械费 → 管理费/利润/税金 → 总价。
        labor_price 工日单价（默认 130 元）；price_overrides 覆盖材料市场价
        （如 {"C30 预拌混凝土": 400.0}）；fee_overrides 覆盖费率
        （如 {"management_fee": 0.06, "profit": 0.05, "tax": 0.09}）。
        未覆盖消耗量的条目不定价并在 notes 提示。

        English: Detailed cost estimate: build a labor/material/machine breakdown from takeoff flat_rows.
        """
        def _run() -> dict[str, Any]:
            from archilinkai.cost_estimator import estimate_from_flat_rows
            table = estimate_from_flat_rows(
                rows, project_name, labor_price, price_overrides,
                fee_overrides, region)
            s = table["summary"]
            return success_result(
                count=len(table["items"]),
                data={
                    "summary": s,
                    "coverage": table.get("coverage", {}),
                    "items": table["items"],
                    "notes": table["notes"],
                    "fee_rates": table["fee_rates"],
                    "labor_price": table["labor_price"],
                    "region": table["region"],
                    "date": table["date"],
                },
            )
        return safe(None, _run)

    @mcp.tool()
    def estimate_project(
        template_names: list[str],
        project_name: str,
        labor_price: float = 130.0,
        price_overrides: dict[str, float] | None = None,
        fee_overrides: dict[str, float] | None = None,
        region: str | None = None,
        export_xlsx: bool = False,
        filename: str = "estimate",
        custom_consumption: dict[str, dict[str, Any]] | None = None,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """一键全链路：模板算量 → 成本细算 →（可选）导出概算 xlsx。

        template_names 传模板名列表（用 list_quantity_templates 查询），
        模板须带清单编码（with_code 自动启用）。同编码跨模板自动去重
        （按传入顺序保留第一个），避免双算。labor_price 工日单价；
        price_overrides 覆盖材料市场价；fee_overrides 覆盖费率；
        custom_consumption 自定义定额（编码→{labor_qty, materials, machines}），
        与内置表合并且自定义优先；export_xlsx=true 导出 GB 50500 概算表。

        English: One-stop pipeline: template takeoff -> cost estimate -> (optional) export GB 50500 xlsx.
        """
        def _run() -> dict[str, Any]:
            from archilinkai.cost_estimator import (
                build_estimate_report,
                estimate_from_flat_rows,
            )
            info = instance_manager.manager.get_info(instance)
            all_rows: list[dict[str, Any]] = []
            seen_codes: set[str] = set()
            per_template: dict[str, Any] = {}
            dedup_notes: list[str] = []
            for tname in template_names:
                r = aggregate_service.service.aggregate_by_template(
                    tname, instance)
                kept = []
                for row in r.get("flat_rows", []):
                    code = str(row.get("code") or "")
                    if code and code in seen_codes:
                        dedup_notes.append(
                            f"编码 {code} 已由前序模板统计，跳过「{tname}」")
                        continue
                    seen_codes.add(code)
                    kept.append(row)
                per_template[tname] = {
                    "rows": len(r.get("rows", [])),
                    "kept": len(kept),
                }
                all_rows.extend(kept)
            table = estimate_from_flat_rows(
                all_rows, project_name, labor_price, price_overrides,
                fee_overrides, region, custom_consumption=custom_consumption)
            table["notes"] = dedup_notes + table.get("notes", [])
            result: dict[str, Any] = {
                "per_template": per_template,
                "summary": table["summary"],
                "coverage": table.get("coverage", {}),
                "items": table["items"],
                "notes": table["notes"],
                "fee_rates": table["fee_rates"],
                "labor_price": table["labor_price"],
                "date": table["date"],
            }
            if export_xlsx:
                result["xlsx_path"] = build_estimate_report(
                    table, filename or project_name)
            return success_result(
                instance=info.instance_id, project=info.project_name,
                count=len(table["items"]), data=result,
            )
        return safe(instance, _run)

    @mcp.tool()
    def import_custom_quota(
        custom: dict[str, dict[str, Any]],
        save: bool = False,
        clear: bool = False,
    ) -> dict[str, Any]:
        """校验并预览自定义定额，可选持久化（跨重启自动加载）。

        custom 格式：{编码: {"labor_qty": 工日,
                "materials": [[材料名, 消耗量, 单位], ...],
                "machines": [[机械名, 台班, 单位], ...]}}
        save=true 时把校验通过的条目写入用户目录，下次 CostEstimator 自动加载；
        clear=true 时删除已持久化的定额（与 save 互斥，优先 clear）。
        返回：accepted_count、invalid、overridden_builtin、merged_total、
        sample、saved_path（save=true 时）。

        English: Validate and preview custom quotas, optionally persist them (auto-loaded across restarts).
        """
        from archilinkai.cost_estimator import (
            CONSUMPTION,
            clear_persisted_consumption,
            merge_custom_consumption,
            save_persisted_consumption,
        )

        if clear:
            clear_persisted_consumption()
            return {"cleared": True, "note": "已删除持久化定额。"}

        accepted: dict[str, dict[str, Any]] = {}
        invalid: dict[str, str] = {}
        for code, cons in (custom or {}).items():
            if not isinstance(cons, dict):
                invalid[str(code)] = "条目不是对象"
                continue
            if "labor_qty" not in cons:
                invalid[str(code)] = "缺 labor_qty"
                continue
            try:
                lq = float(cons["labor_qty"])
            except (TypeError, ValueError):
                invalid[str(code)] = "labor_qty 不是数字"
                continue
            entry = {
                "labor_qty": lq,
                "materials": [
                    tuple(m) for m in cons.get("materials", [])
                    if isinstance(m, (list, tuple)) and len(m) >= 2
                ],
                "machines": [
                    tuple(m) for m in cons.get("machines", [])
                    if isinstance(m, (list, tuple)) and len(m) >= 2
                ],
            }
            accepted[str(code)] = entry

        merged = merge_custom_consumption(accepted)
        overridden = [c for c in accepted if c in CONSUMPTION]
        sample = dict(list(accepted.items())[:3])
        result = {
            "accepted_count": len(accepted),
            "invalid": invalid,
            "overridden_builtin": overridden,
            "merged_total": len(merged),
            "sample": sample,
        }
        if save and accepted:
            path = save_persisted_consumption(accepted)
            result["saved_path"] = path
            result["note"] = (
                f"已持久化 {len(accepted)} 条定额到 {path}，"
                "下次 estimate_project 自动加载。")
        else:
            result["note"] = (
                "预览模式：把 accepted 传给 estimate_project 的 "
                "custom_consumption 即时生效，或加 save=true 持久化。")
        return result

    @mcp.tool()
    def export_table(
        rows: list[dict[str, Any]] | None = None,
        sheets: list[dict[str, Any]] | None = None,
        filename: str = "export",
        fmt: str = "csv",
        value_column: str | None = None,
        project_name: str | None = None,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """把算量结果导出为文件，返回路径。

        单表：传 rows（flat 数组），fmt 选 csv / xlsx / report，默认 csv。
        多表：传 sheets=[{"name":"表名","rows":[...]}, ...]，自动用 xlsx，
          一次写多张表到同一 Excel 文件。
        report：fmt=report 时按 GB 50500 工程量清单格式排版（标题/项目信息
          /表头/数据行/合计），rows 须含 code/code_name/code_unit 列
          （由模板 with_code=true 触发 aggregate 自动附加）；
          value_column 指定量值列名（缺省自动探测 sum/sum_xxx/formula_result）；
          project_name 写到报表项目信息行。
        filename 不含扩展名，存到项目同级 output 目录。

        English: Export takeoff results to a file and return its path.
        """
        import os
        import time

        def _write_sheet(ws, sheet_rows: list[dict[str, Any]]) -> list[str]:
            """写一张表：表头+数据+加粗+列宽。返回列名列表。"""
            if not sheet_rows:
                return []
            fieldnames = list(sheet_rows[0].keys())
            ws.append(fieldnames)
            for row in sheet_rows:
                ws.append([row.get(k) for k in fieldnames])
            from openpyxl.styles import Font
            for cell in ws[1]:
                cell.font = Font(bold=True)
            for i, col in enumerate(ws.columns, 1):
                mx = max(len(str(c.value or "")) for c in col)
                ws.column_dimensions[ws.cell(1, i).column_letter].width = min(mx + 4, 40)
            return fieldnames

        def _run() -> dict[str, Any]:
            nonlocal fmt
            if sheets and fmt != "xlsx":
                fmt = "xlsx"  # 多表自动 xlsx
            if not rows and not sheets:
                raise errors.InvalidArgumentError(
                    "rows", "rows 和 sheets 均为空，无可导出数据")
            out_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "output")
            os.makedirs(out_dir, exist_ok=True)
            safe_name = "".join(
                c for c in filename if c.isalnum() or c in "-_") or "export"
            ts = time.strftime("%Y%m%d_%H%M%S")
            total_rows = 0
            columns: list[str] = []
            if fmt == "report":
                # GB 50500 工程量清单报表
                from archilinkai import report_service
                source_rows = rows or (sheets[0].get("rows", []) if sheets else [])
                path = report_service.build_report(
                    source_rows, value_column=value_column,
                    project_name=project_name, filename=safe_name,
                    out_dir=out_dir)
                total_rows = len(source_rows)
                columns = ["序号", "项目编码", "项目名称", "计量单位", "工程量"]
                return success_result(
                    instance=instance,
                    count=total_rows,
                    data={"file_path": path, "rows": total_rows,
                          "format": "report", "columns": columns,
                          "sheets": 1},
                )
            if fmt == "xlsx":
                from openpyxl import Workbook
                path = os.path.join(out_dir, f"{safe_name}_{ts}.xlsx")
                wb = Workbook()
                if sheets:
                    for i, sheet in enumerate(sheets):
                        ws = wb.active if i == 0 else wb.create_sheet()
                        ws.title = (sheet.get("name") or f"Sheet{i+1}")[:31]
                        sr = sheet.get("rows", [])
                        total_rows += len(sr)
                        if i == 0:
                            columns = _write_sheet(ws, sr)
                        else:
                            _write_sheet(ws, sr)
                else:
                    ws = wb.active
                    ws.title = safe_name[:31]
                    columns = _write_sheet(ws, rows)
                    total_rows = len(rows)
                wb.save(path)
            else:
                import csv
                path = os.path.join(out_dir, f"{safe_name}_{ts}.csv")
                columns = list(rows[0].keys())
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.DictWriter(f, fieldnames=columns)
                    w.writeheader()
                    w.writerows(rows)
                total_rows = len(rows)
            return success_result(
                instance=instance,
                count=total_rows,
                data={"file_path": path, "rows": total_rows,
                      "format": fmt, "columns": columns,
                      "sheets": len(sheets) if sheets else 1},
            )
        return safe(instance, _run)
