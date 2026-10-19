"""GB 50500 工程量清单报表排版（V0.26）。

输入 aggregate 算量结果的 flat_rows（含 code/code_name/code_unit + 量值列），
按清单编码聚合同项工程量，输出符合清单计价格式的 xlsx 文件。

报表结构（一张表）：
  行1  标题：工程量清单（合并居中）
  行2  项目信息：工程名称 + 编制时间（合并居中）
  行3  表头：序号 / 项目编码 / 项目名称 / 计量单位 / 工程量
  行4+ 数据行：按 code 升序，同 code 合并求和
  末行 合计：仅当所有数据行单位一致时显示数值合计
"""

from __future__ import annotations

import os
import time
from typing import Any

from archilinkai import i18n


def _pick_value_column(row: dict[str, Any], hint: str | None) -> str | None:
    """从 row 找量值列名。优先 hint，再按约定顺序探测。"""
    if hint and hint in row:
        return hint
    for k in row:
        if k == "sum" or k.startswith("sum_") or k == "formula_result":
            return k
    return None


def _aggregate_by_code(
    rows: list[dict[str, Any]], value_col: str,
) -> list[dict[str, Any]]:
    """同 code 合并求和。无 code 的行按 code_name 分组（兜底）。"""
    bucket: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for r in rows:
        code = r.get("code") or r.get("code_name") or i18n.t(
            "report.uncategorized", "未分类")
        if code not in bucket:
            bucket[code] = {
                "code": r.get("code", ""),
                "code_name": r.get("code_name", code),
                "code_unit": r.get("code_unit", ""),
                "value": 0.0,
                "count": 0,
            }
            order.append(code)
        v = r.get(value_col)
        if isinstance(v, (int, float)):
            bucket[code]["value"] += v
        bucket[code]["count"] += r.get("count", 1) or 1
    out = []
    for code in order:
        b = bucket[code]
        b["value"] = round(b["value"], 4)
        out.append(b)
    return out


def build_report(
    rows: list[dict[str, Any]],
    value_column: str | None = None,
    project_name: str | None = None,
    filename: str = "report",
    out_dir: str | None = None,
) -> str:
    """生成工程量清单 xlsx 报表，返回文件路径。

    rows: flat_rows（aggregate 返回的 flat_rows 字段）
    value_column: 指定哪一列作为工程量值（缺省自动探测 sum/sum_xxx/formula_result）
    project_name: 报表标题行附工程名（缺省取 "未命名工程"）
    filename: 文件名（不含扩展名）
    out_dir: 输出目录（缺省取本模块同级 output/）
    """
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, Side
    from openpyxl.utils import get_column_letter

    if not rows:
        raise ValueError(i18n.t("report.err_empty", "rows 为空，无法生成报表"))
    value_col = _pick_value_column(rows[0], value_column)
    if not value_col:
        raise ValueError(i18n.t(
            "report.err_no_value",
            "rows 中未找到量值列（sum/sum_*/formula_result），"
            "请显式传 value_column 参数"))

    if out_dir is None:
        out_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(out_dir, exist_ok=True)
    safe_name = "".join(c for c in filename if c.isalnum() or c in "-_") or "report"
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(out_dir, f"{safe_name}_{ts}.xlsx")

    aggregated = _aggregate_by_code(rows, value_col)
    # 按 code 排序（无 code 的"未分类"放最后）
    aggregated.sort(key=lambda x: (x["code"] == "", x["code"]))

    wb = Workbook()
    ws = wb.active
    ws.title = i18n.t("report.title", "工程量清单")
    headers = [
        i18n.t("report.h_seq", "序号"), i18n.t("report.h_code", "项目编码"),
        i18n.t("report.h_name", "项目名称"), i18n.t("report.h_unit", "计量单位"),
        i18n.t("report.h_qty", "工程量"),
    ]
    ncol = len(headers)

    # 样式
    bold = Font(bold=True, size=11)
    title_font = Font(bold=True, size=14)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left = Alignment(horizontal="left", vertical="center", wrap_text=True)
    thin = Side(border_style="thin", color="000000")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    # 行1：标题
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    c = ws.cell(1, 1, i18n.t("report.title", "工程量清单"))
    c.font = title_font
    c.alignment = center
    ws.row_dimensions[1].height = 28

    # 行2：项目信息
    date_str = time.strftime("%Y-%m-%d")
    info = i18n.t(
        "report.info",
        f"工程名称：{project_name or '未命名工程'}    编制时间：{date_str}",
        name=project_name or i18n.t("report.unnamed_project", "未命名工程"),
        date=date_str)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncol)
    c = ws.cell(2, 1, info)
    c.font = bold
    c.alignment = left
    ws.row_dimensions[2].height = 22

    # 行3：表头
    for i, h in enumerate(headers, 1):
        c = ws.cell(3, i, h)
        c.font = bold
        c.alignment = center
        c.border = border
    ws.row_dimensions[3].height = 22

    # 数据行
    row_idx = 4
    for i, item in enumerate(aggregated, 1):
        vals = [i, item["code"], item["code_name"],
                item["code_unit"], item["value"]]
        for j, v in enumerate(vals, 1):
            c = ws.cell(row_idx, j, v)
            c.alignment = center if j != 3 else left
            c.border = border
        ws.row_dimensions[row_idx].height = 20
        row_idx += 1

    # 合计行：仅当所有数据行单位一致时显示
    units = {it["code_unit"] for it in aggregated if it["code_unit"]}
    if len(units) == 1:
        total = round(sum(it["value"] for it in aggregated), 4)
        ws.merge_cells(start_row=row_idx, start_column=1,
                       end_row=row_idx, end_column=4)
        c = ws.cell(row_idx, 1, i18n.t("report.total", "合 计"))
        c.font = bold
        c.alignment = center
        c.border = border
        c = ws.cell(row_idx, 5, total)
        c.font = bold
        c.alignment = center
        c.border = border
        ws.row_dimensions[row_idx].height = 22
        row_idx += 1

    # 列宽
    widths = [6, 14, 32, 10, 14]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    wb.save(path)
    return path
