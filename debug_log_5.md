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
