# 更新日志（Changelog）

筑联 ArchiBridge 版本历史。当前包版本以 `src/archibridge/__init__.py` 为单源（与 pyproject.toml 同步，CI 校验）。

> 早期版本号 V0.x 为研发迭代号；自 0.38.0 起进入包发布号（与 V0.38 对应）。

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
