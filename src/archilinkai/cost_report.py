"""成本估算报表层：概算表 xlsx 导出（V0.56 从 cost_estimator 拆出）。

V0.59 新增 build_combined_estimate_report：新建/拆除/合计三张表写同一 workbook。
"""

from __future__ import annotations

from typing import Any

from archilinkai import i18n


# ---- 概算表 xlsx 导出（GB 50500 风格排版） ------------------------------

# 分状态主题色（表头底色，V0.61）
_THEME_COLORS = {
    "new": "C6EFCE",        # 新建：绿
    "demolition": "FFC7CE",  # 拆除：红
    "total": "D9E1F2",       # 合计：蓝灰
}


def _est_headers(show_share: bool = False) -> list[str]:
    """概算表列头（随语言变化，故用函数而非模块常量）。"""
    headers = [
        i18n.t("estimate.h_seq", "序号"), i18n.t("estimate.h_code", "项目编码"),
        i18n.t("estimate.h_name", "项目名称"), i18n.t("estimate.h_unit", "计量单位"),
        i18n.t("estimate.h_qty", "工程量"),
        i18n.t("estimate.h_unit_price", "单价(元)"),
        i18n.t("estimate.h_total_price", "合价(元)"),
        i18n.t("estimate.h_labor", "人工费(元)"),
        i18n.t("estimate.h_material", "材料费(元)"),
        i18n.t("estimate.h_machine", "机械费(元)"),
    ]
    if show_share:
        headers.append(i18n.t("estimate.h_share", "占比"))
    return headers


def _fill_sheet(ws, table: dict[str, Any], with_chart: bool,
                allow_empty: bool = False, theme: str | None = None,
                show_share: bool = False) -> None:
    """把概算表写进 worksheet（标题/项目信息/明细/取费/图表/备注）。

    allow_empty=False 时 items 为空抛错；True 时容忍空表（只写表头与取费块）。
    theme: "new"/"demolition"/"total" 给表头着色（区分分状态表）；
    show_share: true 时追加「占比」列（用于合计表展示新建/拆除占比）。
    """
    import time

    from openpyxl.chart import PieChart, BarChart, Reference
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    items = table.get("items") or []
    if not items and not allow_empty:
        raise ValueError(i18n.t("estimate.err_empty", "概算表 items 为空，无法生成报表"))
    s = table.get("summary", {})
    headers = _est_headers(show_share)
    ncol = len(headers)

    bold = Font(bold=True, size=11)
    title_font = Font(bold=True, size=14)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left = Alignment(horizontal="left", vertical="center", wrap_text=True)
    right = Alignment(horizontal="right", vertical="center")
    thin = Side(border_style="thin", color="000000")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    header_fill = (PatternFill("solid", fgColor=_THEME_COLORS[theme])
                   if theme in _THEME_COLORS else None)

    def _put(row, col, val, font=None, align=center, border_=border, fill=None):
        c = ws.cell(row, col, val)
        c.font = font or Font()
        c.alignment = align
        if border_:
            c.border = border_
        if fill is not None:
            c.fill = fill
        return c

    # 标题 + 项目信息
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    c = ws.cell(1, 1, i18n.t("estimate.title", "工程成本概算表"))
    c.font = title_font
    c.alignment = center
    if header_fill is not None:
        c.fill = header_fill
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
        _put(3, i, h, bold, fill=header_fill)
    ws.row_dimensions[3].height = 22

    # 数据行
    denom = sum(it.get("total_price") or 0 for it in items) if show_share else 0
    row_idx = 4
    for idx, it in enumerate(items, 1):
        vals = [idx, it.get("code", ""), it.get("name", ""),
                it.get("unit", ""), it.get("quantity", ""),
                it.get("unit_price") if it.get("unit_price") is not None else "—",
                it.get("total_price") if it.get("total_price") is not None else "—",
                it.get("labor_price") if it.get("labor_price") is not None else "—",
                it.get("material_price") if it.get("material_price") is not None else "—",
                it.get("machine_price") if it.get("machine_price") is not None else "—"]
        if show_share:
            pct = round((it.get("total_price") or 0) / denom * 100, 1) if denom else 0.0
            vals.append(f"{pct}%")
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

    # 冻结表头（滚动时标题与表头常驻）+ 打印设置（横向、按页宽缩放）
    ws.freeze_panes = "A4"
    ws.page_setup.orientation = "landscape"
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0

    # 列宽
    widths = [6, 14, 24, 9, 12, 12, 14, 12, 14, 12]
    if show_share:
        widths.append(9)
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _out_path(filename: str | None, out_dir: str | None) -> str:
    """统一生成输出路径（output 目录 + 时间戳 .xlsx）。"""
    import os
    import time

    if out_dir is None:
        out_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(out_dir, exist_ok=True)
    safe_name = "".join(c for c in (filename or "estimate")
                        if c.isalnum() or c in "-_") or "estimate"
    return os.path.join(
        out_dir, f"{safe_name}_{time.strftime('%Y%m%d_%H%M%S')}.xlsx")


def build_estimate_report(
    table: dict[str, Any],
    filename: str = "estimate",
    out_dir: str | None = None,
    with_chart: bool = True,
) -> str:
    """概算表 → xlsx（标题/项目信息/人材机明细/合计/取费/图表/备注），返回路径。"""
    from openpyxl import Workbook

    path = _out_path(filename, out_dir)
    wb = Workbook()
    ws = wb.active
    ws.title = i18n.t("estimate.sheet", "成本概算表")
    _fill_sheet(ws, table, with_chart)
    wb.save(path)
    return path


def build_combined_estimate_report(
    new_table: dict[str, Any],
    demo_table: dict[str, Any],
    total_table: dict[str, Any],
    project_name: str | None = None,
    filename: str = "estimate",
    out_dir: str | None = None,
    with_chart: bool = True,
) -> str:
    """新建/拆除/合计三张表 → 同一 workbook 的 3 个 sheet，返回路径。

    sheet 名：新建概算 / 拆除概算 / 合计（随 i18n 语言变化）。
    各表按状态着色（新建绿 / 拆除红 / 合计蓝灰），合计表追加「占比」列。
    单组为空时该 sheet 仍生成（只写表头与合计块），不中断导出。
    """
    from openpyxl import Workbook

    path = _out_path(filename, out_dir)
    wb = Workbook()
    sheets = [
        (i18n.t("estimate.sheet_new", "新建概算"), new_table, "new", False),
        (i18n.t("estimate.sheet_demolition", "拆除概算"), demo_table,
         "demolition", False),
        (i18n.t("estimate.sheet_total", "合计"), total_table, "total", True),
    ]
    for i, (title, table, theme, show_share) in enumerate(sheets):
        ws = wb.active if i == 0 else wb.create_sheet()
        ws.title = str(title)[:31]
        if project_name and not table.get("project_name"):
            table["project_name"] = project_name
        _fill_sheet(ws, table, with_chart, allow_empty=True,
                    theme=theme, show_share=show_share)
    wb.save(path)
    return path
