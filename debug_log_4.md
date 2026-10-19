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

---

## 2026-10-18 品牌更名：ArchiBridge → ArchiLinkAI（ALAI），筑联 → 筑元智联

### 变更
- 包目录 src/archibridge → src/archilinkai；项目根目录 archicad-mcp → archilinkai
- 文档改名：archilinkai_research.md / archilinkai_plan.md / archilinkai_tech_spec.md
- 全文替换：archibridge→archilinkai（包名/导入/console 命令/横幅）、
  ArchiBridge→ArchiLinkAI、筑联→筑元智联；readme 配置示例路径同步
- 提交 31e130a

### 验证
- pip install -e . 重装；python -m archilinkai 启动横幅正常；537 单测全过

### 备注
- debug_log_1/2/3 历史记录保留旧路径，不回改
- 用户本机既有 MCP 客户端配置若指向旧绝对路径需手动更新为 archilinkai/server.py

---

## 2026-10-18 V0.40（S1）自检向导：doctor + install CLI

### 变更
- 新增 src/archilinkai/cli.py：archilinkai 命令升级为子命令 CLI（serve/doctor/install），
  无子命令时默认 serve（向后兼容）
- 新增 src/archilinkai/doctor.py：四项检查（Python 版本/依赖完整/实例探测/Tapir 探测），
  逐项给修复建议；实例未发现时 Tapir 检查自动跳过
- 新增 src/archilinkai/data/clients.json：客户端配置矩阵外置
  （claude/cursor/cline/witsy/cherry/codex，含 macOS 路径变体）
- install <client>：写 mcpServers.archilinkai 配置，写前 .bak 备份，不覆盖既有 server；
  codex 为 toml 格式输出手动片段；generic 打印通用 JSON 片段
- pyproject：入口改 archilinkai.cli:main，package-data 收 data/*.json
- tests/unit/test_cli.py：+9 用例（doctor 检查/exit code/install 写入与备份/toml 提示）
- readme：新增「环境自检与客户端配置」节

### 验证
- 546 单测全过（537+9）
- 真机缺省：doctor 正确报实例/Tapir FAIL 并给出修复提示；install generic 输出正常

---

## 2026-10-18 V0.41（S3）HTTP 网关：远程/平台接入模式

### 变更
- 新增 src/archilinkai/gateway.py：
  - BearerAuthMiddleware（纯 ASGI，无框架依赖）：Bearer 鉴权，错误 token 401；
    正确请求透传并用 spy_send 捕获真实状态码
  - 全量审计 → output/http_audit.jsonl（时间/方法/路径/状态/token 前缀，不含正文）
  - build_http_app：兼容 FastMCP streamable_http_app / http_app 两种工厂名
  - run_http 安全默认：无 token（参数或 ALAI_TOKEN 环境变量）拒绝启动；
    缺 uvicorn 给明确安装提示；默认绑 127.0.0.1
- cli.py：serve 子命令加 --http/--host/--port/--token
- pyproject：optional-dependencies 新增 http = uvicorn>=0.30
- tests/unit/test_gateway.py：+7 用例（401 两种/透传/审计/非 http scope/启动守卫）
- readme：新增「HTTP 远程模式（平台接入）」节；.gitignore 补 output/

### 验证
- 553 单测全过（546+7）
- 真机冒烟：错 token 401；对 token + MCP initialize 200；审计两条记录正确

---

## 2026-10-18 V0.42（S2）桌面安装器

### 变更
- installer/archilinkai.iss：Inno Setup 6 安装脚本（中/英双语、现代向导），
  装嵌入式 Python + 本地 wheel（pip --no-index 离线）+ 写客户端配置
- installer/build_installer.py：一键编译，自动从 __init__.py 读版本注入 ISCC
- installer/download_tapir.py：按 AC 主版本从 GitHub release 下载对应 apx
  （release_tag 可 latest/具体 tag，资产名含 ACxx 自动匹配）
- src/archilinkai/data/tapir_versions.json：AC26–30 → Tapir release 映射（外置可维护）
- docs/s2_installer.md：构建步骤 + payload 准备 + Tapir 处理手册
- readme 加桌面安装器节；.gitignore 补 installer/payload/

### 验证
- 553 单测全过
- build_installer.py：版本读取正常，缺 ISCC 时给明确下载提示（exit 2）
- download_tapir.py / build_installer.py py_compile 通过

### 备注
- 未实际编译 iss（本机无 Inno Setup）；.iss 语法基于 Inno 6 文档核对，
  真实编译需用户装 Inno Setup 后跑 build_installer.py

---

## 2026-10-18 V0.38.1 doctor 探测命令修正

### 变更
- doctor.check_tapir 探测命令 GetProductInfo → GetProjectInfo（前者非 Tapir 命令，
  导致 Tapir 已加载却误报未加载）
- 补 import importlib.util（Python 3.14 下 find_spec 需显式导入）

### 验证
- 真机 AC28：GetProjectInfo 返回 dict，Tapir 探测 PASS

### 备注
- 用户反馈 Tapir 已加载但 doctor 报 FAIL，根因是探测命令选错

---

## 2026-10-18 Mac 平台适配（Tapir 下载 + 文档）

### 变更
- installer/download_tapir.py
  - 新增 detect_platform()（sys.platform==darwin → mac）
  - pick_asset 加 platform 参数：Win 筛 *_Win.apx，Mac 筛 *_Mac.zip
  - download 加 platform 参数，Mac 下 .zip 自动解压出 .bundle
  - CLI 新增 --platform 参数（默认自动检测）
- data/tapir_versions.json
  - 修复 bug：AC26/27 原 release_tag "v0.66.0" 已 404，统一改为 "latest"
  - 注释更新资产命名规律（_Win.apx / _Mac.zip）
- readme.md
  - 运行前提-Tapir 段补 Win/Mac 分平台说明 + Add-Ons 目录路径
  - 桌面安装器段注明 macOS 无 Inno Setup 安装器，走 pip + download_tapir.py

### 验证
- pick_asset 单测式验证：win ac28 → TapirAddOn_AC28_Win.apx，mac ac28/29 → 对应 _Mac.zip
- GitHub API 实测 latest release 1.7.1 含 AC25–30 × Win/Mac 全部 14 资产

### 备注
- Mac 上 archilinkai 本体无需改动（Python/FastMCP/archicad 包均跨平台）
- CI 已含 macOS × py3.10/3.12 矩阵

---

## 2026-10-18 Win/Mac 双平台并存分发

### 变更
- 新增 src/archilinkai/download_tapir.py（包内模块，pip 可用）
- cli.py 新增 download-tapir 子命令（archilinkai download-tapir 28 [--platform win|mac|all]）
- installer/download_tapir.py 改为薄壳转发（向后兼容）
- readme 安装段重构为 Windows/macOS 两个并列完整流程，用户按系统自选

### 备注
- download() 返回 list[Path]，all 模式 Win+Mac 各下一份并存
- pip 包纯 Python wheel，Win/Mac 通用

---

## 2026-10-18 readme 安装指引更新

### 变更
- 运行前提：去重 Tapir 详细下载说明（改指向分平台流程），修顺序问题（原前提里就用 download-tapir 但包未装）
- 客户端配置：5 个客户端全部改用 "command": "archilinkai"（旧 server.py 源码路径写法废弃），补 Mac 配置文件路径与绝对路径回退说明
- 桌面安装器：引用改为 archilinkai.download_tapir / CLI 命令
- WorkBuddy 段：残留旧名 archicad → archilinkai

### 备注
- pip 包为推荐安装方式后，源码路径式配置已无必要

---

## 2026-10-18 真机验证批次（AC28 办公楼改造）+ 2 个 bug 修复

### 真机验证结果（ac28-1，端到端）
- V0.33：GetConnectedElements / GetElementPreviewImage / GetBuildingMaterialPhysicalProperties / MoveElements-Preview / RotateElements-Preview 全 PASS
- V0.34：GetLayerCombinations（49 组合）PASS；CreateLayerCombinations-Preview PASS
- V0.36：list_stories / list_all_properties / get_calculation_units / get_navigator_tree / list_mep_elements / get_element_relations / get_gdl_parameters 全 PASS（项目无 MEP 构件，列表为空属正常）
- Zone 复测：get_zone_boundaries 在无 Zone 项目返回结构化空结果（count=0），历史报错确认为旧项目数据问题，非 Tapir 限制
- estimate_project 全链路 PASS：masonry_volume + wall_paint_area + formwork_area → 细算 2 项精确、formwork 未覆盖自动跳过并标注（覆盖率 66.7%），含税合计 6261.84 元，xlsx 导出成功（验证后已删）

### 修复 1：success_result() 拒收自定义关键字参数
- 现象：list_attributes / get_connected_elements 等真机报 "success_result() got an unexpected keyword argument"
- 根因：schemas.py success_result 签名固定 5 参，V0.33+ 多个工具传自定义键（attribute_type / connected_elements / **data 展开等）
- 修复：schemas.py 加 **extra 形参，额外键并入 data，一处改动覆盖全部坏调用点
- 波及面核对：read_tools.py 中 attribute_type=、connected_elements=、type_id=、**data 展开均随此修复生效

### 修复 2：profile 墙无 floorPlanPolygons 时 bounding_box 缺失
- 现象：真机集成测试 test_get_element_geometry_info KeyError 'bounding_box'
- 根因：办公楼改造项目中带 profile 的墙，Tapir GetDetailsOfElements 不返回 floorPlanPolygons，_bounding_box 返回 None 导致键缺省
- 修复：geometry_service.py 新增 _fallback_wall_points()——直墙用参考线起止点沿法线扩厚度/2 推算矩形 4 角点兜底

### 验证
- 单测 553 全过；真机集成测试重跑 PASS（含 bounding_box 断言）

### 备注
- 待办：Python314 重装包 + 重启 Trae 后，MCP 层复测修复项
- 待确认：GetProjectInfo 返回项目名"未命名项目"（导航树内容与 1.1办公楼改造 一致），疑路径解析或用户侧另存
- 遗留：UpdateZones 需含 Zone 的项目才能复测

---

## 2026-10-18 V0.39 算量估价深度补强

### 变更
- cost_estimator.py：消耗量表 15→23 条，补 8 个编码
  - 011406001 墙面喷刷涂料 / 010801001 木质门 / 010807001 金属窗 /
    010805001 幕墙 / 011001001 保温隔热墙面 / 010803001 保温隔热屋面 /
    011702001 现浇混凝土模板 / 011102001 地面找平层 / 011302001 天棚喷刷涂料
- cost_estimator.py PRICE_BOOK：+22 项材料市场价
  （涂料/腻子/铝合金型材/中空玻璃/密封胶/木材/门窗五金/保温板/粘结抹面砂浆/
  木模板/钢模板/模板支撑等）
- aggregate_service.py：算量模板 29→40，+11 个模板
  - 墙面抹灰/内墙涂料/屋面保温/屋面找平/地面找平/地砖/天棚涂料/
    踢脚线/风管面积/管道长度/桥架长度
- aggregate_service.py：已有模板补 code_override
  - wall_paint_area→011406001、wall_insulation_area→011001001、
    formwork_area→011702001

### 真机验证（AC28 测试文件，1 面墙）
- 5 模板全链路：masonry_volume / wall_paint_area / formwork_area /
  wall_insulation_area / wall_plaster_area
- 覆盖率 66.7% → 100%（formwork/涂料/保温全部从 skipped 变 detailed）
- 含税合计 3259.54 元

### 验证
- 单测 553 全过（模板数断言 29→40）
- 注：本机 pip install -e 因 archilinkai.exe 被运行中 MCP 服务占用失败，
  但源码已加载（aggregate_service.__file__ 指向 src），重启 Trae 后正式生效

---

## 2026-10-18 V0.40 自定义定额库导入

### 变更
- cost_estimator.py：
  - 新增 merge_custom_consumption(custom)：内置表与用户自定义定额合并，
    自定义优先覆盖同编码；materials/machines 由 list 转 tuple
  - CostEstimator.__init__ 加 custom_consumption 参数，存为 self.consumption
  - estimate_item 用 self.consumption 替代模块级 CONSUMPTION
  - estimate_from_flat_rows 加 custom_consumption 透传
- read_tools.py：
  - estimate_project 加 custom_consumption 参数（编码→{labor_qty,materials,machines}）
  - 新增 import_custom_quota 工具：校验自定义定额条目，返回 accepted/invalid/
    overridden/merged_total/sample 预览

### 真机验证（AC28 测试文件，砖砌体 2.4m³）
- import_custom_quota：接收 2 条、拒 2 条（非对象/缺 labor_qty）、
  覆盖内置 010402001、合并后 25 条
- estimate_project 传 custom_consumption 覆盖 010402001：
  人工费 405.6→468.0、总价 1244.16→648.0，证明自定义消耗量生效

### 验证
- 单测 88 全过（cost_estimator + estimate_schema + aggregate）

---

## 2026-10-18 V0.41 机电/装修定额补全 + 自定义定额持久化

### 变更
- cost_estimator.py PRICE_BOOK：+22 项机电/装修材料市场价
  - 块料：地砖/墙砖/粘结剂/填缝剂/踢脚线/壁纸/壁纸胶
  - 给排水：镀锌钢管/PPR管/PVC排水管/阀门/水龙头/坐便器/洗脸盆/淋浴器
  - 暖通：镀锌钢板/风管保温棉/风口/消声器/风机盘管
  - 电气：桥架/电力电缆/PVC线管/BV电线/开关插座/吸顶灯/LED灯带
- cost_estimator.py CONSUMPTION：23→38 条（+15 条机电/装修定额）
  - 装修：块料楼地面/墙面块料面层/踢脚线/墙面壁纸
  - 给排水：镀锌钢管/卫生器具
  - 暖通：通风管道/通风空调设备
  - 电气：桥架/电力电缆/配管/配线/开关插座/照明灯具
- cost_estimator.py 自定义定额持久化：
  - load_persisted_consumption / save_persisted_consumption / clear_persisted_consumption
  - 路径：~/.archilinkai/custom_quota.json
  - CostEstimator.__init__ 自动加载持久化定额（优先级：传入 > 持久化 > 内置）
- read_tools.py import_custom_quota：preview 参数改为 save/clear
  - save=true 持久化，clear=true 删除

### 真机验证（AC28 测试文件，砖砌体 2.4m³）
- import_custom_quota(save=true)：持久化 1 条到 ~/.archilinkai/custom_quota.json
- 不传 custom_consumption 跑估价：自动加载持久化定额，
  labor 405.6→624.0（自定义 labor_qty=2.0 生效）
- import_custom_quota(clear=true)：清除后恢复内置 labor=405.6

### 验证
- 单测 88 全过
- 文件行数 774（未超 800）

---

## 2026-10-18 V0.42 规范审查（方向2 MVP）

### 新增模块
- code_review_service.py（295 行）：4 条规范强条审查规则
  - wall_thickness：墙厚 ≥ 隔墙限值 0.09m（承重墙 0.18m）
  - openings：门洞高≥2.0m/宽≥0.8m、外窗窗台高≥0.9m
  - headroom：净高 ≥ 2.4m（按楼层标高 - 梁/板高度估算）
  - collisions：结构(柱梁墙板) vs 机电(MEPRoutingElement) 碰撞
- code_review_tools.py：注册 run_code_review + list_code_review_limits
- server.py：注册 code_review_tools
- tests/integration/conftest.py：收集 code_review_tools

### 真机验证（AC28 测试文件，1 面墙厚 0.2m）
- run_code_review(['wall_thickness'])：0 违规（0.2m ≥ 0.09m）
- 严格限值 wall_min_thickness=0.3：检出 1 条违规（墙厚 0.2m）
- 全规则：per_rule 全 0，passed=True
- list_code_review_limits：返回 10 项默认限值

### 待验证（需办公楼项目）
- 门窗洞口属性名（Door_Height/Door_Width/Window_SillHeight）
- 净高属性名（Beam_Height/Slab_Thickness）及楼层标高对齐
- 碰撞检查需有机电构件

### 验证
- 全量单测 553 全过

---

## 2026-10-18 V0.43 规范审查增强（+3 条规则）

### 变更
- code_review_service.py：新增 3 条审查规则
  - fire_zone_area：防火分区面积（高层 1500㎡ / 多层 2500㎡），用 Zone 面积
  - stair_width：楼梯梯段宽度 ≥ 1.1m
  - railing_height：栏杆高度 ≥ 1.05m（高层 ≥ 1.10m）
- DEFAULT_LIMITS：+5 项限值（fire_zone/stair/railing）
- run_review：加 building_type(high/multi)、high_rise 参数
- code_review_tools.py run_code_review：透传 building_type / high_rise

### 真机验证（AC28 测试文件）
- 7 条规则全跑通，per_rule 全 0，passed=True
- 测试文件无 Zone/Stair/Railing，新增规则返回空列表（无异常）

### 待办公楼项目验证
- fire_zone_area 的 Zone 面积属性名（General_NetArea/General_Area）
- stair_width 的 Stair_Width 属性名
- railing_height 的 Railing_Height 属性名

---

## 2026-10-19 V0.44 规范审查增强（+2 条规则，办公楼项目验证）

### 变更
- code_review_service.py：新增 2 条审查规则
  - stair_tread：踏步高 ≤ 0.175m(公共)/0.15m(住宅)、踏步深 ≥ 0.28m/0.26m
  - window_floor_ratio：窗地比 ≥ 1/7(居住)/1/8(办公)，按楼层汇总
- DEFAULT_LIMITS：+6 项限值（riser/tread/window_floor_ratio）
- run_review：all_rules 扩到 9 条
- code_review_tools.py：更新工具描述

### 真机验证（办公楼改造项目）
- 9 条规则全跑通，total=2820 violations
- wall_thickness：588 条（检出 0.05m/0.02m 装饰薄墙）
- collisions：2222 条（柱 vs 机电管线）
- railing_height：10 条（1.0m 栏杆 < 1.05m，真实违规）
- stair_width/railing_height 属性名验证通过
- 其余规则因办公楼项目无对应构件返回 0

### 验证
- 全量单测 553 全过
- code_review_service.py 547 行（合规）

---

## 2026-10-19 V0.45 门净宽扣门框修正

### 问题
用户指出 check_openings 用的门宽是洞口宽（含门框），未扣门框算净宽。
探测发现 ArchiCAD 只暴露 General_Width/General_Height（洞口尺寸），
原代码用 Door_Width/Door_Height 属性名错误（返回 None），
导致办公楼项目 openings 规则始终返回 0。

### 变更
- code_review_service.py check_openings：
  - 属性名改 General_Width/General_Height（ArchiCAD 实际可用）
  - 新增门框余量参数 door_frame_allowance（默认 0.10m，两侧合计）
  - 新增上框余量参数 door_head_allowance（默认 0.05m）
  - 净宽 = 洞口宽 - door_frame_allowance，净高 = 洞口高 - door_head_allowance
  - 违规信息同时显示洞口/净宽/扣除值，便于复核
  - 窗台高度加 General_SillHeight 兜底
- DEFAULT_LIMITS：+2 项（door_frame_allowance / door_head_allowance）

### 真机验证（办公楼改造项目）
- openings 从 0 → 53 条违规
- 检出样本：洞口 0.80m - 门框 0.10m = 净宽 0.70m < 0.8m
- 单测 553 全过

---

## 2026-10-19 V0.46 楼梯净宽扣扶手 + 属性名修正

### 问题
用户指出：楼梯净宽要考虑扶手宽度影响（扶手在踏面边缘上方时扣除）。
探测发现：
- 原 stair_width 用 Stair_Width/General_Width（不存在，返回 None）
- 原 stair_tread 用 Stair_RiserHeight/Stair_TreadDepth（不存在）
- 属性中文名「默认楼梯宽度」存在但 get_property_id 用英文 nonLocalizedName 匹配，中文查不到

### 正确属性名（BuiltIn，英文 nonLocalizedName）
- Stair_FlightWidth：梯段构造宽度
- Stair_DefaultGoing：踏面深度（踏步深）
- Stair_DefaultRiserHeight：踏步高度

### 变更
- code_review_service.py：
  - DEFAULT_LIMITS +2 项：stair_handrail_deduction_per_side=0.06、stair_handrail_count=2
  - check_stair_width：用 Stair_FlightWidth，净宽 = 构造宽 - 单侧扶手扣除 × 扶手数（默认 0.12m）
  - check_stair_tread：用 Stair_DefaultRiserHeight/Stair_DefaultGoing

### 真机验证（办公楼改造项目）
- stair_width 12 条违规：构造宽 1.00m - 扶手 0.12m = 净宽 0.88m < 1.1m
- stair_tread 18 条违规：踏步深 0.26-0.27m < 0.28m（公共建筑限值）

### 验证
- 单测 553 全过

---

## 2026-10-19 V0.47 疏散距离估算检查

### 新增规则
- evacuation_distance：疏散距离估算
  - 用 Zone 面积估算最大疏散距离：sqrt(面积) × 1.5（保守系数）
  - 限值：办公 40m（有喷淋 50m）、住宅 22m
  - 参数：has_sprinkler（是否有自动喷淋）
  - 说明：精确计算需 Zone 边界几何 + 疏散门位置，当前 Tapir
    GetZoneBoundaries 参数格式不支持，先用估算方案

### 变更
- code_review_service.py：
  - DEFAULT_LIMITS +3 项疏散距离限值
  - check_evacuation_distance()：用 Zone 面积估算
  - run_review：all_rules 扩到 10 条，加 has_sprinkler 参数
- code_review_tools.py：run_code_review 加 has_sprinkler 参数

### 真机验证（办公楼改造项目）
- evacuation_distance：0 违规（Zone 面积最大 168㎡，估算 ≈19.4m < 40m）
- 单测 553 全过

---

## 2026-10-19 V0.48 层高检查 + 楼梯踏步级数限制

### 新增规则
- floor_height：层高 ≥ 办公 3.0m / 住宅 2.8m
  - 层高 = 相邻楼层标高差；顶层用本层最高楼板标高 - 楼层标高
- stair_riser_count：踏步级数 ≤ 18 级（超过需设平台）
  - 注意：ArchiCAD 的 Stair_NumberOfRisers 属性不存在，此规则当前无法生效

### 变更
- code_review_service.py：DEFAULT_LIMITS +3 项（floor_height/stair_riser_count）
- code_review_service.py：新增 check_floor_height / check_stair_riser_count
- code_review_service.py：run_review all_rules 扩到 12 条
- code_review_tools.py：更新工具描述

### 真机验证（办公楼改造项目）
- floor_height：0 违规（层高满足要求）
- stair_riser_count：0 违规（属性不存在，返回空）
- 单测 553 全过

### 备注
- 规则总数 10 → 12 条
- stair_riser_count 待后续找到正确属性名后生效

---

## 2026-10-19 待完善项（用户确认后续做）

1. **精确疏散距离** — 需要 Zone 边界多边形 + Door 坐标 + 多边形内最短路径算法（图论/计算几何）
2. **疏散门数量检查** — 需要 Zone-Door 空间关联（判断门在哪个 Zone 内）
3. **拆除/新建分别算量** — ArchiCAD 的 Renovation Status 不直接暴露，需 IFC 导出或 C++ 插件

---

## 2026-10-19 V0.49 P0 优化（碰撞过滤 + 材料统计 + 报告导出）

### 碰撞检查优化
- 去重：同一对元素的碰撞只报一次
- 实体碰撞过滤：hasBodyCollision=True 才报（当前 Tapir 无碰撞体积字段）
- 统计汇总：详细碰撞只保留前 100 条，其余用统计汇总
- 结果：4205 条碰撞 → 去重后 4205 条（所有碰撞都是实体碰撞），详细列出前 100 条

### 材料统计模块（新建）
- material_report.py：按构件类型汇总材料用量
  - Wall → 砖砌体/涂料/保温/防水
  - Beam/Column/Slab/Stair → 混凝土/钢筋/模板
  - Roof → 防水卷材/保温板/混凝土
- material_report_tools.py：generate_material_report / export_material_excel 工具
- 真机验证：砖砌体 1496m³、内墙涂料 15463㎡、混凝土 93m³

### 估价报告导出优化
- 增加人材机占比饼图
- 增加取费构成柱状图
- build_estimate_report 加 with_chart 参数

### 变更文件
- code_review_service.py：check_collisions 优化
- material_report.py（新建）：材料统计服务
- material_report_tools.py（新建）：材料统计工具注册
- server.py：注册 material_report_tools
- cost_estimator.py：build_estimate_report 增加图表

### 验证
- 单测 553 全过
- 材料统计真机验证通过
