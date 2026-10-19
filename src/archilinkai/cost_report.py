"""成本估算报表层：概算表 xlsx 导出（V0.56 从 cost_estimator 拆出）。"""

from __future__ import annotations

from typing import Any

from archilinkai import i18n


# ---- 概算表 xlsx 导出（GB 50500 风格排版） ------------------------------

def _est_headers() -> list[str]:
    """概算表列头（随语言变化，故用函数而非模块常量）。"""
    return [
        i18n.t("estimate.h_seq", "序号"), i18n.t("estimate.h_code", "项目编码"),
        i18n.t("estimate.h_name", "项目名称"), i18n.t("estimate.h_unit", "计量单位"),
        i18n.t("estimate.h_qty", "工程量"),
        i18n.t("estimate.h_unit_price", "单价(元)"),
        i18n.t("estimate.h_total_price", "合价(元)"),
        i18n.t("estimate.h_labor", "人工费(元)"),
        i18n.t("estimate.h_material", "材料费(元)"),
        i18n.t("estimate.h_machine", "机械费(元)"),
    ]


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
        raise ValueError(i18n.t("estimate.err_empty", "概算表 items 为空，无法生成报表"))
    s = table.get("summary", {})
    headers = _est_headers()
    ncol = len(headers)

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
    ws.title = i18n.t("estimate.sheet", "成本概算表")

    def _put(row, col, val, font=None, align=center, border_=border):
        c = ws.cell(row, col, val)
        c.font = font or Font()
        c.alignment = align
        if border_:
            c.border = border_
        return c

    # 标题 + 项目信息
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    c = ws.cell(1, 1, i18n.t("estimate.title", "工程成本概算表"))
    c.font = title_font
    c.alignment = center
    ws.row_dimensions[1].height = 28
    _date = table.get('date', time.strftime('%Y-%m-%d'))
    _price = table.get('labor_price', '-')
    info = i18n.t(
        "estimate.info",
        f"工程名称：{table.get('project_name') or '未命名工程'}    "
        f"编制时间：{_date}    "
        f"工日单价：{_price} 元",
        name=table.get('project_name')
        or i18n.t("estimate.unnamed_project", "未命名工程"),
        date=_date, price=_price)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncol)
    c = ws.cell(2, 1, info)
    c.font = bold
    c.alignment = left
    ws.row_dimensions[2].height = 22

    # 表头
    for i, h in enumerate(headers, 1):
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
        _put(row_idx, 1, i18n.t("estimate.direct_cost", "直接费合计"), bold)
        _put(row_idx, 7, s.get("direct_cost", 0), bold, right)
        for j in (8, 9, 10):
            _put(row_idx, j, "", bold)
        ws.row_dimensions[row_idx].height = 20
        row_idx += 1

    # 取费块
    fee_rows = [
        (i18n.t("estimate.management_fee", "企业管理费"), s.get("management_fee", 0)),
        (i18n.t("estimate.profit", "利 润"), s.get("profit", 0)),
        (i18n.t("estimate.tax", "税 金"), s.get("tax", 0)),
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
    _put(row_idx, 1, i18n.t("estimate.total", "含税总价"), bold)
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
            pie.title = i18n.t("estimate.chart_lmr", "人材机占比")
            data = [labor, material, machine]
            pie.add_data(Reference(ws, min_col=1, min_row=row_idx, max_row=row_idx + 2, max_col=2), titles_from_data=True)
            pie.set_categories(Reference(ws, min_col=1, min_row=row_idx, max_row=row_idx + 2))
            # 写数据到隐藏区域
            ws.cell(row_idx, 1, i18n.t("estimate.labor", "人工费"))
            ws.cell(row_idx, 2, labor)
            ws.cell(row_idx + 1, 1, i18n.t("estimate.material", "材料费"))
            ws.cell(row_idx + 1, 2, material)
            ws.cell(row_idx + 2, 1, i18n.t("estimate.machine", "机械费"))
            ws.cell(row_idx + 2, 2, machine)
            ws.add_chart(pie, f"H{row_idx}")
            row_idx += 4

        # 取费构成柱状图
        mgmt = s.get("management_fee", 0)
        profit = s.get("profit", 0)
        tax = s.get("tax", 0)
        if mgmt + profit + tax > 0:
            bar = BarChart()
            bar.title = i18n.t("estimate.chart_fee", "取费构成")
            bar.y_axis.title = i18n.t("estimate.axis_amount", "金额(元)")
            bar.x_axis.title = i18n.t("estimate.axis_item", "费用项")
            data = [mgmt, profit, tax]
            bar.add_data(Reference(ws, min_col=1, min_row=row_idx, max_row=row_idx + 2, max_col=2), titles_from_data=True)
            bar.set_categories(Reference(ws, min_col=1, min_row=row_idx, max_row=row_idx + 2))
            ws.cell(row_idx, 1, i18n.t("estimate.management_fee", "企业管理费"))
            ws.cell(row_idx, 2, mgmt)
            ws.cell(row_idx + 1, 1, i18n.t("estimate.profit", "利润"))
            ws.cell(row_idx + 1, 2, profit)
            ws.cell(row_idx + 2, 1, i18n.t("estimate.tax", "税金"))
            ws.cell(row_idx + 2, 2, tax)
            ws.add_chart(bar, f"H{row_idx}")
            row_idx += 4

    # 覆盖率 + 备注
    cov = table.get("coverage", {})
    if cov:
        cov_text = i18n.t(
            "estimate.coverage",
            f"细算覆盖率：{cov.get('coverage_pct', '-')}%  "
            f"(精确 {cov.get('detailed', 0)} / 兜底 "
            f"{cov.get('fallback', 0)} / 未覆盖 {cov.get('skipped', 0)})",
            pct=cov.get('coverage_pct', '-'), detailed=cov.get('detailed', 0),
            fallback=cov.get('fallback', 0), skipped=cov.get('skipped', 0))
        ws.merge_cells(start_row=row_idx, start_column=1,
                       end_row=row_idx, end_column=ncol)
        c = ws.cell(row_idx, 1, cov_text)
        c.alignment = left
        row_idx += 1
    for note in table.get("notes") or []:
        ws.merge_cells(start_row=row_idx, start_column=1,
                       end_row=row_idx, end_column=ncol)
        c = ws.cell(row_idx, 1, i18n.t("estimate.note_prefix", f"备注：{note}", note=note))
        c.alignment = left
        row_idx += 1

    # 列宽
    widths = [6, 14, 24, 9, 12, 12, 14, 12, 14, 12]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    wb.save(path)
    return path
