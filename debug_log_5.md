# 变更记录 5

> 接续 debug_log_4.md（1080 行已超 800 上限）

---

## 2026-10-19 V0.60 工程量清单报表按翻新状态分表

### 变更
- report_service.py：抽出 `_fill_sheet(ws, rows, value_col, project_name, date_str, title_text)`
  （原 build_report 排版逻辑，返回按 code 聚合后的数据行）
  - 新增 `split_rows_by_renovation(rows)`：按 renovation 分组返回 [(状态值, 显示名, 行)]，
    按 新建→拆除→已建 排序；label 优先取 renovation_label，回退 renovation_service.label，
    再回退 i18n 的 report.unknown_state
  - `build_report(...)` 增 `group_by_renovation`：true 时同 workbook 多 sheet，
    sheet 名/标题 = `工程量清单 · {label}`
  - `_pick_value_column` 签名由 `(row, hint)` 改为 `(rows, hint)`，要求所选量值列
    **所有行都存在**，避免多模板混合时缺该列的行被静默按 0 计入
- read_tools_quantity.py：`export_table` 增 `group_by_renovation` 参数，
  report 分支透传并据此计算 `n_sheets`
- i18n.json：新增 report.unknown_state
- 同步 `_pick_value_column` 两处跨模块调用点（quota_matcher.py / estimate_schema.py）
- tests/unit/test_aggregate.py：新增 4 用例 + 6 处编码断言同步

### 真机验证（ac28-1）
- `build_report(group_by_renovation=True)` 输出 3 sheet：
  ['工程量清单 · 新建', '工程量清单 · 拆除', '工程量清单 · 已建']，各 6 数据行

### 验证
- 单测 644 → 648 全过

### 备注
- 修复真机暴露的「末行值为 0」：floor_finish_area/ceiling_area 无 sum_with_waste 列，
  旧逻辑只看 rows[0] 导致静默归零；改「所有行都有」策略后自动探测到正确的量值列
- 改动集中在报表层与导出参数，风险小


---

## 2026-10-19 V0.61 概算报表分状态美化

### 变更
- cost_report.py：
  - 新增 `_THEME_COLORS`（新建 C6EFCE 绿 / 拆除 FFC7CE 红 / 合计 D9E1F2 蓝灰）
  - `_est_headers(show_share=False)` 支持追加「占比」列头
  - `_fill_sheet(...)` 增 `theme`（表头着色）与 `show_share`（合计表占比列）参数
  - 数据行占比 = 该行合价 / 全部行合价之和，显示为百分比
  - 新增冻结表头（`freeze_panes="A4"`）与打印设置（横向、按页宽缩放）
  - `build_combined_estimate_report` 为三张表分别传入 theme/show_share
- i18n.json：新增 estimate.h_share（占比 / Share）
- tests/unit/test_estimate_renovation.py：新增 1 用例（着色、占比列、冻结）

### 验证
- 单测 648 → 649 全过
- 新增用例直接加载生成的 xlsx，断言：新建/拆除/合计表头底色分别为绿/红/蓝灰、
  新建表无「占比」列而合计表有且首行占比 = 新建总价 /（新建+拆除）总价、freeze_panes=A4
- 真机验证因当前无在线 ArchiCAD 实例（ac28-1/ac29-1 均不可用）跳过

### 备注
- 纯报表排版层改动，不触碰计算逻辑；`build_estimate_report`（单表）行为不变
- 合计表 item 行仍以「新建概算/拆除概算」两组小计展示，占比反映两者含税总价份额
