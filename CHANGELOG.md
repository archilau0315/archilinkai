# 更新日志（Changelog）

筑元智联 ArchiLinkAI 版本历史。当前包版本以 `src/archilinkai/__init__.py` 为单源（与 pyproject.toml 同步，CI 校验）。

> 早期版本号 V0.x 为研发迭代号；自 0.38.0 起进入包发布号（与 V0.38 对应）。

## [研发迭代 V0.60] - 2026-10-19

- V0.60 工程量清单报表按翻新状态分表：`report_service` 抽出 `_fill_sheet` 并新增 `split_rows_by_renovation`（按 新建→拆除→已建 排序，label 优先取 `renovation_label`）；`build_report` 增 `group_by_renovation`，同一 workbook 输出多 sheet（标题 = `工程量清单 · {label}`）；`export_table` 增 `group_by_renovation` 参数；**修复**多模板混排时量值列静默归零——原 `_pick_value_column(row, hint)` 只看首行，若该列在其他行缺失（如 floor_finish_area 无 `sum_with_waste`）则整体按 0 计入，改为「要求所有行都具备该列」的自适应探测

## [研发迭代 V0.52–V0.59] - 2026-10-19

- V0.59 新建+拆除双估算：新增模块 `cost_demolition_data`（拆除参考定额 `DEMOLITION_CONSUMPTION` 覆盖 38 个清单编码）；`CostEstimator`/`estimate_from_flat_rows` 支持 `consumption_table` 选表（建造/拆除）；新增纯函数 `split_rows_by_renovation` / `combine_estimate_tables`；`estimate_project` 增 `renovation_status` + `split_by_renovation`，一次输出「新建 / 拆除 / 合计」三组并按 3 sheet 导出 xlsx；**修复** `estimate_project` 历史遗留量值缺陷——原按行用清单编码去重，把同编码的多楼层行全部丢弃，导致概算严重少算（实测新建量仅剩 ~4%），改为模板级「编码整块认领」去重；**修正**清单编码错位——code_table 中墙/柱/梁编码与名称及定额条目互不对应（Wall 010502001 却名「墙」、同码定额为「矩形柱」），按 GB 50854 校正为 Wall→010504001 / Column→010502001 / Beam→010503002 / Slab→010505003，并补齐 010503002 消耗量
- V0.58 拆除/新建分别算量：基于 AC 翻新状态（内置属性 `Category_RenovationStatus`：Existing/ToBeDemolished/New）过滤与分组；`aggregate_quantities` / `aggregate_by_template` 新增 `renovation_status` + `split_by_renovation` 参数；新增工具 `list_renovation_summary`；新增模块 `renovation_service`；修复 `list_all_properties` 报错（`success_result(**data)` → `data=data`）；AC28「1.1办公楼改造」真机验证（拆除 231 / 新建 2583）
- V0.57 规范审查增强：梁跨高比按**水平投影跨度**计算（斜梁取 details 起止点，兜底 General_3DLength）；柱长细比按结构类型分型限值（混凝土 20 / 钢 43）
- V0.56 拆分 `cost_estimator.py`（848 行）为 `cost_data`（438）/`cost_engine`（154）/`cost_report`（204）+ 薄聚合器
- V0.55 钢结构适配：梁跨高比框架化（structure_type: concrete/steel/continuous/any）+ 新增柱长细比规则（17 条）；story<0 假柱过滤；AC28 雄安厂房真机 beam 误报 564→6
- V0.54 规范审查新增柱最小截面/梁高跨比 2 规则（14→16）
- V0.53 规范审查拆 4 子模块，新增楼板厚度/承重外墙厚度 2 规则（12→14）
- V0.52 多语言输出（zh/en，`ALAI_LANG` / `serve --lang`，英文目录外置 `data/i18n.json`）、只读工具拆 4 子模块、72 工具描述双语；新增 `get_locale` 诊断工具
- 工具 73 个，单测 644 全过

## [研发迭代 V0.39–V0.51] - 2026-09 ~ 2026-10

- 规范强条审查模块（12 条规则）、材料统计、属性别名解析、算量模板 40→44
- 产品化 S0–S3：PyPI 包化/CI、环境自检向导 `doctor`、桌面安装器（Inno Setup）、HTTP 网关（Bearer 鉴权/审计）
- 细节见 readme「版本里程碑」

## [0.38.0] - 2026-10-18

- 算量返回加 `warnings`（量值缺失告警：缺 N/M 个元素，占比%）
- 估价加 `calc_mode` 标记（精确/兜底/未覆盖）与 `coverage` 覆盖率统计
- 概算表 xlsx 导出（GB 50500 风格：人材机明细/直接费合计/管理费/利润/税金/含税总价/覆盖率/备注行）
- 新增 `estimate_project` 一键全链路（算量→细算→可选导出 xlsx），同编码跨模板自动去重防双算
- 工具 66 个，单测 537 全过

## [0.37.0] - 2026-10-18

- 成本估算细算引擎 `estimate_cost`：算量 flat_rows → 消耗量×市场价 → 人材机分解 → 管理 5%/利润 4.5%/税 9% → 含税总价
- 内置 15 个清单编码消耗量表 + 2026 市场参考价库；价格/费率/工日单价均可覆盖；未覆盖消耗量的条目不定价并提示

## [0.36.0] - 2026-10-17

- P2 只读命令批 9 工具：list_stories / get_gdl_parameters / list_mep_elements / get_mep_routing_elements / get_mep_ports / get_element_relations / list_all_properties / get_calculation_units / get_navigator_tree
- Tapir 盘点收官结论：官方 265 命令中剩余 213 个多为 UI/Teamwork/修订类，价值低

## [0.35.0] - 2026-10-16

- 算量模板 23→29：roof_waterproof_area / stair_concrete_volume / column_concrete_volume / beam_concrete_volume / ceiling_area / floor_finish_area，全部带 GB 50500 清单编码

## [0.34.0] - 2026-10-16

- 图层组合：get_layer_combination_details（读组合内每层显隐/锁定/线框/交叉组）、create_layer_combinations（创建/覆盖，confirm 模式）

## [0.33.0] - 2026-10-16

- P0 Tapir 命令批：get_connected_elements（墙→门窗/幕墙→框架）、get_element_preview_image（2D/Section/3D base64）、get_building_material_properties（材料物理性能）、move_elements、rotate_elements（confirm 模式）

## [0.32.0] - 2026-10-14

- P1 Tapir 命令批：碰撞检测 get_collisions、收藏夹 list_favorites/apply_favorites、IFC 三件套（get_ifc_ids/get_elements_by_ifc_ids/get_ifc_properties）、图层与属性管理（create_layers/delete_attributes）、set_element_details、get_zone_boundaries/update_zones
- 真机验证：碰撞 2 对、图层 5 项、收藏夹 17 项、IFC 读写正常

## [0.31.0] - 2026-10-13

- list_library_parts（库部件清单含 skippedCount 诊断）、get_subelements_of_hierarchical（幕墙/楼梯拆子构件）
- 真机：库部件 2894 项；幕墙 46→框架 39+面板 10；楼梯 19→踏板 22+踢板 22+结构 3

## [0.30.0] - 2026-10-13

- list_attributes 工具（12 类属性清单），修正命令名为 GetAttributesByType
- 真机：Layer 259 / Composite 300 / BuildingMaterial 379 项

## [0.21.0] – [0.29.0] 算量体系成型（2026-09-27 → 10-12）

- 算量模板+CSV/Excel 导出、楼层名/构件名补全、损耗系数+多量合并、自定义模板、公式计算（ast 安全求值器）、GB 50500 清单编码映射与标准清单报表、复合墙分层算量、幕墙/栏杆专属模板
- 幕墙/栏杆/壳体/天窗确认为只读可算量类型（Tapir 未实现创建）

## [0.10.0] – [0.20.0] 建模计划扩展与工程量基础（2026-09-25 → 09-27）

- 建模计划补齐家具/灯具/网面/独立洞口/房间区域/机电管线（MEPRoute）
- 工程量读取 get_element_quantities（14 项通用量）、汇总 aggregate_quantities（分组聚合）、分类过滤、属性缓存、相近名建议、回归脚本 regression.py
- 楼梯/屋顶/变形体创建、板/屋顶开洞、L 形楼梯、计划离线校验 lint_model_plan

## [0.4.0] – [0.9.0] 构件修改与删除（2026-09-23 → 09-25）

- 修改：墙/柱/门窗 → 梁/板/屋顶/变形体任意形状（modify_plan/modify_service）
- 删除：预检→删除→读回确认，最多重试 3 次（delete_plan/delete_service）
- 关键坑：构件删除后 Tapir 返回 details 为空的占位项，存在性判断看 details 非空

## [0.1.0] – [0.3.x] 架构奠基（2026-09-22 → 09-23）

- FastMCP 骨架、InstanceManager 多实例、Query Engine、四阶段写入（Preview→Confirm→Execute→Verify）、统一错误码、测试矩阵、Benchmark
- 建模计划第一版：墙/柱 → 梁/板 → 门/窗；通道抽象层 channel_base（可插拔）
- AC28+AC29 双版本真机验证通过
