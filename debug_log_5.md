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


---

## 2026-10-19 V0.62 材料统计增强（单位/翻新分组/材料费/导出）

### 变更
- material_report.py（325 行）：
  - A 新增 `MATERIAL_UNITS`（材料→计量单位），修正"不同单位混算"——汇总/按类型各行标注单位
  - B `generate_material_report(...)` 增 `split_by_renovation`：复用 renovation_service
    读取 `Category_RenovationStatus`，输出 `by_renovation: {状态: {材料: 用量}}`，
    明细行附 `renovation`
  - C `export_material_excel` 重写：多表（材料汇总 / 各构件类型 / 按翻新状态 / 明细），
    表头加粗+底色、边框、冻结首行、列宽自适应
  - D 新增 `MATERIAL_PRICE`（材料→PRICE_BOOK 键 + 换算系数）与 `_material_unit_price`：
    汇总页输出「参考单价 / 材料费」列及 `material_cost_total`；未覆盖单价的不计价（cost=None）
- material_report_tools.py（85 行）：两个工具增 `split_by_renovation` 参数；文件名自动补 .xlsx
- i18n.json：新增 material.h_unit / h_unit_price / h_cost / h_cost_total / h_renovation / sheet_renovation
- tests/unit/test_material.py（新建）：6 用例

### 材料费映射（复用 cost_data.PRICE_BOOK，单一价源）
- 混凝土→C30 预拌混凝土 380/m³；钢筋→HRB400 钢筋 4000/t×0.001=4/kg
- 砖砌体→蒸压加气混凝土砌块 350/m³；模板→木模板 45/m²
- 内墙/外墙涂料→内墙/外墙乳胶漆 18 / 25 元/m²；防水卷材→SBS 卷材 32/m²
- 保温板→挤塑聚苯板 XPS 380/m³×0.05=19 元/m²（按 50mm 厚折算，注释说明）
- 防水涂料：无参考价 → 不计价

### 验证
- 单测 649 → 655 全过（新增 6 用例覆盖单位/材料费/翻新分组/导出多表）
- 真机验证因无在线 ArchiCAD 实例跳过；由单测直接校验生成的 xlsx 结构

### 备注
- material_report.py 325 行 < 500，无需拆分
- `summary`/`by_type` 结构未变（向后兼容），仅新增 units/price/by_renovation 字段


---

## 2026-10-19 V0.63 规范审查新增 2 规则（墙高厚比 / 疏散门净宽）

### 变更
- code_review_common.py：`DEFAULT_LIMITS` 新增 `wall_slenderness_max: 30.0`
  （`door_exit_min_width: 0.9` / `door_frame_allowance: 0.10` 早已存在、原未被启用，本轮复用）
- code_review_rules_a.py：新增两条规则——
  - 规则 18 `check_wall_slenderness`：`Wall_MaximumHeight / General_Thickness > 30` 判违规；
    属性缺失或值≤0 跳过（不误报）
  - 规则 19 `check_evacuation_door_width`：`_EVAC_DOOR_KEYWORDS = ("疏散","安全出口","逃生","exit","evac")`
    名称过滤；`净宽 = General_Width - door_frame_allowance`，`< door_exit_min_width(0.9)` 判违规
- code_review_service.py：import 两条规则、`all_rules` 追加、分发循环追加两个 `elif`（规则数 17→19）
- i18n.json：新增 4 个 en 键（wall_slenderness.rule/msg、evacuation_door.rule/msg）
- code_review_tools.py：`run_code_review` docstring 补两条规则说明
- tests/unit/test_code_review_rules.py：新增 9 用例
  （墙高厚比 5 个：违规/达标/缺属性/零厚/无墙；疏散门 4 个：违规/达标/非疏散跳过/无门）

### 范围决策（证据驱动，避免死规则与误报）
- 原设想多数不可行：窗台高度/门洞净宽/净高已在 check_openings 实现；
  栏杆净距/走廊净宽/坡道坡度在 Tapir 无可用属性（不支持栏杆/坡道）
- 无在线 ArchiCAD 实例无法真机验证属性可用性 → 经 Grep 仓库实证确证
  `Wall_MaximumHeight`（Wall 只读 length）/`WindowDoor_FireRating`（Door/Window string）
  为真实属性，最终只落地两条低误报规则

### 验证
- 单测 655 → 664 全过（新增 9 用例）
- 真机验证因无在线 ArchiCAD 实例跳过

### 备注
- 墙高厚比取宽松限值 30 以降低误报（未细分承重/砂浆）；疏散门按名称过滤，零误报
- code_review_rules_a.py 仍 < 500 行，无需拆分


---

## 2026-10-19 V0.64 规范审查新增 3 规则（梁截面宽度/高宽比/防火门等级）

### 真机属性侦察（AC28「1.1办公楼改造」）
- Beam 的 `General_Width` ✅ = 截面宽（0.25/0.3/0.13 真实值）；假梁模式确认（0.13×0.06、L=0.17m 装饰段）
- Door 的 `WindowDoor_FireRating` ✅ 存在，非防火门返回 "" 或 null
- `General_CrossSectionWidth/Height` 不存在（静默跳过，不可用）
- 墙肢长度规则放弃：改造项目砖墙/门窗垛多，"墙长<8×墙厚"会大量误报

### 变更
- code_review_common.py：`DEFAULT_LIMITS` 新增 4 键
  - `beam_section_min_width: 0.20`（GB 50010 6.3.1 框架梁截面宽度不宜小于 200mm）
  - `beam_aspect_ratio_max: 4.0`（同条，截面高宽比不宜大于 4）
  - `fake_beam_max_length: 0.5` / `fake_beam_min_height: 0.15`（假梁过滤阈值）
- code_review_rules_a.py：新增 3 条规则（19→22）
  - 规则 20 `check_beam_section_width`：梁宽 < 0.20 判违规；**仅 concrete 生效**
    （steel/continuous/any 返回空——钢结构窄翼缘 H 梁属正常，防误报）
  - 规则 21 `check_beam_aspect_ratio`：h/b > 4 判违规；**仅 concrete 生效**
  - 规则 22 `check_fire_door_rating`：名称含 防火/fire 的门 FireRating 为空判违规
    （数据完整性检查，普通门不参与，零误报）
  - 新增公共 helper `_is_fake_beam`（长度<0.5 或 高度<0.15 → 装饰段跳过）
- code_review_service.py：import 3 规则、all_rules 追加、elif 分发
  （两条梁规则传 structure_type）
- i18n.json：新增 6 个 en 键（beam_section_width/beam_aspect_ratio/fire_door_rating 各 rule+msg）
- code_review_tools.py：docstring 同步（规则 19→22，structure_type 说明补充）
- tests/unit/test_code_review_rules.py：新增 17 用例
  （梁宽 7 个：违规/达标/钢结构跳过/假梁×2/缺属性/无梁；
    高宽比 5 个：违规/达标/钢结构跳过/假梁/缺属性；
    防火门 5 个：null 违规/空串违规/已标达标/普通门跳过/无门）

### 验证
- 单测 664 → 681 全过（新增 17 用例）
- AC28「1.1办公楼改造」真机验证：
  - beam_section_width：67 条（KL 梁宽 0.08~0.14m，真实检出）
  - beam_aspect_ratio：40 条（h=1.4~1.67m 薄梁，高宽比 14~17.5，真实检出）
  - fire_door_rating：0 条（项目无防火门名称标记，零误报符合预期）
  - 假梁过滤生效（0.13×0.06 装饰段未出现在违规列表）

### 备注
- 两条梁规则与既有 check_beam_span_ratio 共用 structure_type 框架，行为一致
- 防火门规则属"数据完整性"类提示，value 为空串、limit 为"甲/乙/丙级"说明
- code_review_rules_a.py 现 768 行，逼近 800 行拆分线；下次再新增规则前应先拆出 rules_c 子模块


