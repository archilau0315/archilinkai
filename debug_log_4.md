# Debug Log 4

> 接续 debug_log_3.md（902 行已满）

---

## 2026-10-13 V0.32 P1 Tapir 命令批：碰撞/图层/收藏夹/IFC/区域边界/详情修改

### 变更
- tapir_adapter.py：新增 12 个便捷方法
  - get_collisions(g1, g2, volume_tolerance, perform_surface_check, surface_tolerance)
  - get_layers(attribute_ids, fields=None)
  - create_layers(layer_data_array, overwrite_existing=False)
  - delete_attributes(attributes_to_delete)
  - get_favorites_by_type(element_type)
  - apply_favorites_to_elements(favorites, apply_settings, apply_classifications, apply_categories, apply_properties)
  - get_ifc_ids_of_elements(guids)
  - get_elements_by_ifc_ids(ifc_ids)
  - get_ifc_properties_of_elements(guids)
  - set_details_of_elements(elements_with_details)
  - get_zone_boundaries(zone_guids)
  - update_zones(keep_stamp_position, undo_top_trim, undo_bottom_trim)
- read_tools.py：+6 只读工具（get_collisions / list_favorites / get_ifc_ids /
  get_elements_by_ifc_ids / get_ifc_properties / get_zone_boundaries）
- write_tools.py：+5 写入工具（create_layers / delete_attributes / apply_favorites /
  set_element_details / update_zones），全部 confirm=False 预览模式
- tests/unit/test_tapir_adapter.py：+13 用例（各命令 cmd/params/返回值透传）

### 真机验证（AC28 build 6003，办公楼改造项目）
- GetCollisions：Wall vs Column 各 10 个，检出 2 对碰撞（body=True）
- GetLayers：初版 attributeIds 裸字符串列表返回空；修正为 [{"attributeId":{"guid"}}] 后成功，返回 5 项（含 name/isHidden/isLocked/intersectionGroupNr）
- GetFavoritesByType("Wall")：17 项收藏夹（如"01 建筑 内墙_加气混凝土砌块_瓷砖(双侧)"）
- GetIFCIdsOfElements：3 面墙均返回 IFC ID
- GetElementsByIFCIds：用 IFC ID 反查成功，GUID 大小写不敏感
- GetIFCPropertiesOfElements：返回 Pset_BuildingElementProxyCommon 等 IFC 属性集
- GetZoneBoundaries：报错 -2130313110（Failed to execute zone boundary query），项目有 5 个 Zone 但查询失败，疑似 Zone 数据损坏或 Tapir 版本限制
- UpdateZones：报错 -2130312312（Failed to update zones），与 GetZoneBoundaries 同因

### 备注
- 单测 493 → 506 全过（+13）
- 工具数 37 → 48
- apply_favorites_to_elements 默认 True 的开关参数不传参（Tapir 默认 true），仅 False 时传参
- Zone 相关 2 个命令在当前项目报错，单测通过，参数格式正确，属项目数据或 Tapir 版本限制

---

## 2026-10-17 V0.33 P0 Tapir 命令批：连接关系/移动旋转/预览图/材料物理性能

### 变更
- tapir_adapter.py：+5 便捷方法
  - get_connected_elements(guids, connected_element_type)
  - move_elements(elements_with_move_vectors)
  - rotate_elements(elements_with_rotations)
  - get_element_preview_image(guid, image_type, image_format, width, height)
  - get_building_material_physical_properties(attribute_ids)
- read_tools.py：+3 只读工具
  - get_connected_elements（墙→窗、幕墙→框架、楼梯→踏踢板等）
  - get_element_preview_image（2D/Section/3D，png/jpg，返回 base64）
  - get_building_material_properties（建筑材料物理性能）
- write_tools.py：+2 写入工具（confirm 模式）
  - move_elements(guids, dx, dy, dz, copy, confirm)
  - rotate_elements(guids, origin, begin_point, end_point, copy, confirm)
- tests/unit/test_tapir_adapter.py：+5 用例

### 备注
- 单测 506 → 511 全过
- 工具数 48 → 53
- 真机验证：AC28 未启动，跳过；单测已覆盖参数格式
- MoveElements/RotateElements 输出为 ExecutionResults（批量执行结果）
- GetBuildingMaterialPhysicalProperties 的 attributeIds 用 [{attributeId:{guid}}] 包装（与 GetLayers 一致）

---

## 2026-10-18 V0.34 P1 收尾：图层组合

### 变更
- tapir_adapter.py：+2 便捷方法
  - get_layer_combinations(attribute_ids)（注意入参 key 是 attributes 非 attributeIds）
  - create_layer_combinations(layer_combination_data_array, overwrite_existing=False)
- read_tools.py：+1 只读工具 get_layer_combination_details
- write_tools.py：+1 写入工具 create_layer_combinations（confirm 模式）
- tests/unit/test_tapir_adapter.py：+2 用例

### 备注
- 单测 511 → 513 全过
- 工具数 53 → 55
- 图层组合每层字段全必填：attributeId/isHidden/isLocked/isWireframe/intersectionGroupNr
- 真机验证跳过（AC 未启动）

---

## 2026-10-18 V0.35 算量模板扩充（23→29）

### 变更
- aggregate_service.py：QUANTITY_TEMPLATES +6 模板
  - roof_waterproof_area（屋面防水，Roof 表面积，010902001）
  - stair_concrete_volume（楼梯混凝土，Stair 净体积，010506001）
  - column_concrete_volume（柱混凝土，含 3% 损耗，010502001）
  - beam_concrete_volume（梁混凝土，含 3% 损耗，010505001）
  - ceiling_area（天棚抹灰，板净底面，011301001）
  - floor_finish_area（楼地面面层，板净顶面，011101001）
- tests/unit/test_aggregate.py：模板计数断言 23→29

### 备注
- 单测 513 全过
- 全部带 code_override（GB 50500 清单编码）

---

## 2026-10-18 V0.36 P2 只读命令批：楼层/MEP/关系/属性/单位/导航树

### 变更
- tapir_adapter.py：+9 便捷方法
  - get_stories / get_gdl_parameters_of_elements / get_mep_elements /
    get_mep_routing_elements / get_mep_ports / get_relations_of_elements /
    get_all_properties / get_calculation_units / get_navigator_item_tree
- read_tools.py：+9 只读工具
  - list_stories / get_gdl_parameters / list_mep_elements /
    get_mep_routing_elements / get_mep_ports / get_element_relations /
    list_all_properties / get_calculation_units / get_navigator_tree
- tests/unit/test_tapir_adapter.py：+9 用例

### 盘点结论
- 官方 265 命令，接入后未覆盖 213 个；大部分为 UI 交互/项目开关/Teamwork/修订管理，对 LLM 工作流价值低
- 本批挑选对建模/算量/审图最有用的 9 个只读命令
- GetMEPRoutingElements 解决"机电构件普通接口无法查看"痛点
- 写入类 P2（标注/BCF/Teamwork/Modify 系列/设计选项/修订）暂缓

### 备注
- 单测 513 → 522 全过
- 工具数 55 → 64
- 真机验证跳过（AC 未启动）

---

## 2026-10-18 V0.37 成本估算细算引擎

### 变更
- cost_estimator.py（新增 250 行）：
  - PRICE_BOOK 材料市场价（混凝土 5 强度/砂浆/钢筋/砌块/防水/装饰，2026 参考价）
  - MACHINE_BOOK 机械台班价 7 项；DEFAULT_LABOR_PRICE 130 元/工日
  - CONSUMPTION 消耗量表：15 个清单编码 → 每单位人工工日/材料明细/机械台班
  - KEYWORD_FALLBACK 关键词兜底 7 类
  - CostEstimator.estimate_item：单条目细算（人材机分解+材料明细展开）
  - CostEstimator.estimate_table：全表取费（管理 5%/利润 4.5%/税 9%，可覆盖）
  - estimate_from_flat_rows：flat_rows → 概算表全流程
- read_tools.py：+1 工具 estimate_cost（rows+项目名 → 概算表）
- tests/unit/test_cost_estimator.py（新增，9 用例）

### 设计要点
- 细算路径：消耗量 × 市场价 → 人材机 → 直接费 → 管理费/利润/税金 → 总价
- 混凝土类消耗系数 1.015（含 1.5% 损耗）
- 未命中消耗量的条目不定价，写 notes 提示，避免瞎编
- 价格/消耗量/费率全部可参数覆盖

### 备注
- 单测 522 → 531 全过
- 工具数 64 → 65

---

## 2026-10-18 V0.38 算量估价链路补强（P0 批）

### 变更
- aggregate_service.py：
  - aggregate() 返回加 warnings（量值缺失元素数+占比提示，求和按 0 时告警）
  - aggregate_by_template / aggregate_by_custom_template 收集并透传 warnings
- cost_estimator.py：
  - estimate_item 加 calc_mode 标记（detailed/fallback/skipped）
  - estimate_table 加 coverage 覆盖率统计（含 coverage_pct）
  - 新增 build_estimate_report()：概算表 xlsx（标题/项目信息/人材机明细/
    直接费合计/管理费/利润/税金/含税总价/覆盖率/备注，GB 50500 风格排版）
- read_tools.py：
  - aggregate_quantities / aggregate_by_template / aggregate_by_custom_template
    透传 warnings
  - estimate_cost 返回加 coverage
  - 新增 estimate_project 一键全链路工具：模板算量→细算→可选导出 xlsx；
    同编码跨模板自动去重（按传入顺序保留第一个），防止双算
- tests：test_cost_estimator +3 用例（覆盖率/报表/空表报错），
  test_aggregate +3 用例（warnings 告警/齐全为空/模板透传）

### 设计要点
- estimate_project 解决 LLM 三步链路断点，一次调用完成算量+估价+导出
- 去重防双算：concrete_volume 与 column_concrete_volume 同传时后者被跳过
- 未定价条目在 xlsx 中显示"—"，覆盖率行写入表尾

### 备注
- 单测 531 → 537 全过
- 工具数 65 → 66

---

---

## 2026-10-18 V0.39（S0）包产品化：archicad-mcp → 筑元智联 ArchiLinkAI

### 变更
- 目录重组：37 个模块 git mv 到 src/archilinkai/（保留 git 历史）；
  regression.py / benchmark.py 留在根目录作开发脚本
- 新增 src/archilinkai/__init__.py（__version__='0.38.0' 版本单源）+ __main__.py
- 全部 .py + tests import 改写：import X → from archilinkai import X（68 文件 281 行，脚本批量）
- 新增 pyproject.toml：包名 archilinkai，console_scripts 入口 archilinkai=archilinkai.server:main，
  依赖 mcp/archicad/openpyxl，pip install -e . 可编辑安装验证通过
- server.py（包内）：mcp 名改 archilinkai；模块级 discover_instances 移入 main()
  （单测提速 49s→6.5s）；启动横幅带版本号
- 新增根目录兼容薄壳 server.py：sys.path 注入 src 后调 archilinkai.server.main，
  旧版 MCP 配置 python server.py 不失效
- 新增 CHANGELOG.md：readme 版本历史迁移至此（Keep a Changelog 风格分区）
- 新增 .github/workflows/ci.yml：win/mac × py3.10/3.12 矩阵 + 版本一致性校验 + tag 触发 PyPI 发布
- readme：标题品牌化（筑元智联 ArchiLinkAI）、客户端矩阵表述、安装段改 pip/三入口
- benchmark.py：源码态 sys.path 注入

### 顺手修复
- read_tools.py 中 get_gdl_parameters 重复定义两处（V0.33 与早期批次），
  删旧版保留 V0.33 版（FastMCP 启动警告消除）

### 验证
- 三入口全通：archilinkai / python -m archilinkai / python server.py
- 537 单测全过；pip install -e . 正常

### 备注
- S0 验收清单剩余：干净虚拟机 uvx 验证、PyPI 发布（待 tag 推送后走 CI）
