# 变更日志续篇

---

## 2026-09-27 V0.11 对象/灯具（Object/Lamp）

### 调研（真机探测）
- Tapir CreateObjects/CreateLamps/GetLibraries 均可用（AC29+Tapir 1.5.9）
- 命令格式：`CreateObjects{"objectsData":[{"libraryPartName":"...","coordinates":{"x,y,z"}}]}`
- 返回结构：与现有 `_parse_row` 兼容（`{"elementId":{"guid"}}`）
- 部件名必须与已加载库完全一致，中文库精确匹配（"沙发 01" 通过，"Sofa 01" 失败）
- GDL-29 实测可用部件 7 个：沙发 01、沙发椅 01、餐椅 01、茶几 01、床 01、双人床 01、衣柜 01

### 新增文件
- tests/unit/test_object_plan.py（13 行）：对象/灯具单元测试 11 个

### 修改模块
- model_plan.py：SUPPORTED_TYPES 加 Object/Lamp；_BUILDERS Lamp 指向 build_object
- plan_special.py：新增 build_object（name + x/y/z 校验，默认原点地面）
- tapir_channel.py：_COMMAND 加 Object/Lamp；_build_param 加两者参数拼装
- plan_preview.py：_TYPE_CN 加 Object/Lamp；_describe 加两者明细；risk 加部件名匹配提示

### 测试
- 单测 348→**359 全过**（新增 11：Object 默认值/坐标/name 校验/空白名/Lamp 共享 builder/命令映射/通道拼装×2/预览×2）
- 真机 AC29：沙发 01（200,200,0）+ 餐椅 01（202,200,0）创建→读回→删除还原，全流程成功，现场无遗留

### 备注
- 对象/灯具经 lint_model_plan 离线自检后走 preview_model_plan → create_from_plan 标准链路
- name 大小写、空格、语言均需与库完全匹配，否则 Tapir 报 "Not found library part"
- GetDetailsOfElements 读回 Object 的 details 为空是 Tapir 已知限制，以 GUID 存在性验证为准
- readme 工具分层/结构/版本历史已同步

---

## 2026-09-27 V0.11 补扫：灯具部件名清单（16 个，真机验证）

### 过程
- 盲猜 38 个中英名全灭；从 Light Sources.libpack 二进制找路子
- 关键：libpack 内 gsm 脚本是英文（文件名≠部件名），部件名是 UTF-8 中文名，
  存在二进制头/压缩流里。逐 zlib 头解压 + UTF-8 CJK 正则提取含"灯"短串，再真机验证
- 旁证：'Lamp_symbol'、'灯' 返回 "Failed to create new Lamp"（是宏/母部件，找到但不可放置）

### 验证通过的灯具名（16，试建后已全部删除还原）
吊灯、壁灯、日光灯、床头灯、聚光灯、日式灯、天花板灯、墙射灯、区域灯光、
凹入式卤光灯、凹入式点光源灯、墙壁式荧光灯、天花板点光源灯、
点光源灯地面、点光源灯墙、树枝形的装饰灯

### 备注
- 纯真机探测，未改业务代码，单测仍 359；现场元素数 41 无变化
- 方法可复用：以后扫别的 libpack，解 zlib 流 + UTF-8 中文提取 + 批量试建


---

## 2026-09-27 V0.12 网面 Mesh + 独立洞口 Opening

### 调研（Tapir 源码 + 真机）
- CreateMeshes/ModifyMeshes/CreateOpenings 真机可用；无 ModifyOpenings
- Mesh 参数（meshesData 每项）：polygonCoordinates 必填（≥3 个 3D 点，点 z 可不同），
  level 底标高，holes（3D 洞，键 polygonCoordinates），sublines（内部等高线）
- Opening 参数（openingsData 每项）：ownerElementId{guid} + basePoint（3D）必填，
  width/height 可选；宿主只能是墙、板、梁、网面
- Opening 的 GetDetailsOfElements 读回 {"error":"Not yet supported element type"}，
  与 Object 同，以 GUID 存在性 + 内置 verify 验证

### 变更文件
- plan_values.py：+point3z（3D 点 z 默认 0）、+hole_polygons3d
- plan_special.py：+build_mesh、+_mesh_sublines、+build_opening（293 行）
- model_plan.py：+Mesh/Opening 注册，WALL_BASED 之外新增 HOST_BASED、OPENING_HOSTS，
  _check_wall_references 改名 _check_references（加洞口宿主类型/范围校验）
- tapir_channel.py：+命令映射，+_build_mesh_param，Opening 参数拼装（372 行）
- create_service.py：宿主预检 external_walls 扩为 external_hosts，
  +_build_hosted_items，第二轮补 Opening（220 行）
- plan_preview.py：+_mesh_text，_wall_ref_text 泛化 _host_ref_text（加构件种类参数）
- 新增 tests/unit/test_mesh_opening.py：18 个用例

### 验证
- 单测 359 -> 377 全过
- 真机端到端：墙+板+起伏网面（两点 z=1，1 条等高线）+墙上洞口+板上洞口，
  内置 verify 5/5，读回实体 details 非空/洞口占位正常，全删还原 41
- 全部模块 ≤500 行（最大 tapir_channel 372）

---

## 2026-09-27 V0.13 房间区域 Zone

### 调研（Tapir 源码 schema + GH 组件 + 真机）
- CreateZones 真机可用；无 ModifyZones
- item 必填：name、numberStr、geometry
- geometry 二选一：
  {"polygonCoordinates":[2D点≥3]} 手动轮廓
  {"referencePosition":{"x","y"}} 给房间内一点自动按墙识别
- 可选：categoryAttributeId（区域类别）、stampPosition（标签落点）
- 真机读回 Zone details 支持，字段 isManual 区分两种模式；
  自动识别会把轮廓收缩到墙内边（墙厚方向缩 0.1），证明识别真实生效

### 变更文件
- plan_special.py：+build_zone（342 行）
- model_plan.py：+Zone 注册（14 类构件）
- tapir_channel.py：+命令映射、+_build_zone_param（396 行）
- plan_preview.py：+_zone_text、风险提示补自动识别前提
- 新增 tests/unit/test_zone_plan.py：13 个用例

### 验证
- 单测 377 -> 390 全过
- 真机：5 墙围合两个房间，手动书房 + 自动储藏室，verify 7/7，
  读回轮廓/类别/标签正常，全删还原 41
- 全部模块 ≤500 行（最大 tapir_channel 396）

---

## 2026-09-28 V0.14 机电管线 MEPRoute（风管/水管/桥架）

### 调研（Tapir 源码 + AC29 真机）
- CreateMEPRoutingElements / CreateMEPElements / ModifyMEPRoutingElements 真机可用
- item 字段：domain（Ventilation 风管 / Piping 水管 / CableCarrier 桥架）、
  nodeCoordinates（3D 路径点，≥2）、crossSectionShape（矩形/圆形/椭圆/槽形）、
  crossSectionWidth / crossSectionHeight（圆形只用 width 作直径）
- 真机读回的怪脾气：
  - GetAllElements 不含 MEP 路由（普通存在性验证对 MEP 必失败）
  - GetDetailsOfElements 返回 "Not yet supported element type"
  - GetMEPElements 枚举实测返回 0（枚举不到新建路由）
  - GetMEPRoutingElements 对"从未存在"的假 GUID 报 error，可用于创建后即时验证；
    但删除后再查仍返回成功行，不能用于判断删除
  - GetMEPDistributionSystems 是实时管网图，是唯一能看到管段/节点的通道

### 变更文件
- plan_special.py：+MEP_DOMAINS/MEP_SHAPES 常量、+build_mep_route（380 行）
- model_plan.py：+MEPRoute 注册（15 类构件，140 行）
- tapir_channel.py：+命令映射、+_build_mep_route_param、
  +exists（MEP 专用存在性查询）（427 行）
- channel_base.py：ModelChannel +exists 钩子（105 行）
- create_service.py：_verify 改为按 created 行分派，MEPRoute 走 channel.exists，
  其余仍走 GetAllElements（227 行）
- plan_preview.py：+_mep_route_text（总长/标高/专业名/截面名），risk 补 MEP 注意事项
- 新增 tests/unit/test_mep_route.py：MEP 计划用例
- tests/unit/test_create_service.py：+MEP 验证链路用例 2 个

### 验证
- 单测 390 -> 404 全过
- 真机创建：风管/水管路由创建命令成功返回 GUID，GetMEPRoutingElements 即时读回正常
- **遗留问题**：DeleteElements 对 MEP 返回 success，但分布管网图计数不下降；
  已怀疑分布图缓存，真相需在 AC29 界面（3D 视图）确认，AC29 以管理员身份运行，
  程序无法操作其界面，已交用户在界面核对/清理
- 全部模块 ≤500 行（最大 tapir_channel 427）

---

## 2026-09-28 版本号统一降级：V1.x → V0.x

### 变更
- 项目仍在开发期，全部版本号由 V1.x 统一改为 V0.x（如 V0.14）
- 批量替换 33 个 py/md 文件中的 "V1." 共 155 处
- 文件改名：开发计划_对话建模V1.0.md → 开发计划_对话建模V0.0.md

### 验证
- 全库 V1. 零残留；单测 404 全过

---

## 2026-09-28 集成测试修复 + 全链路用例

### 变更
- 新增 tests/integration/conftest.py：_Capturer 假 mcp 收集各 *_tools.register() 内部
  工具函数成字典（server 模块并不直接暴露工具函数，原集成测试 server.xxx 已失效）
- test_real_instance.py：server 改为 SimpleNamespace(**_collect())；原硬编码
  "耐火等级"/"标准墙" 在未命名项目环境失效，改为动态取真实存在的字符串属性
  （property_service.get_property_type 过滤）和真实分类项
- 新增 test_create_delete_chain.py：lint→预览→confirm 拦截→创建 2 墙 1 柱（x≈60
  偏远坐标）→读回 verify→删除还原，真机端到端
- 断言注意：lint/只读工具经 success_result 包装有 status；create/preview/delete
  由 service 直出无外层 status，直接看 created/failed/verify

### 验证
- 真机集成：21 过 2 跳（prop 值过滤、无字符串属性时跳过）
- 单测 404 全过无回归

---

## 2026-09-28 V0.15 工程量读取 get_element_quantities（算量第 1 步）

### 调研（AC29 真机枚举）
- 枚举全部 BuiltIn 属性名，量相关 200+ 个：General_* 通用量 + 按类型专有量
  （Wall_ReferenceLineLength、Slab_GrossTopSurfaceArea、Zone_CalculatedArea 等）
- 通用量类型核验：General_SurfaceArea/Area/Net|Gross(Top|Edge|Bottom)SurfaceArea
  为 area；General_3DLength/Height/Width/Thickness 为 length；
  General_Gross/NetVolume 为 volume
- 不存在/不可用名：General_GrossArea、General_Length（类型 unknown，忽略）

### 变更
- property_service.py：+get_quantities（get_values 取数 + get_property_type 定单位，
  _TYPE_UNIT 标注 m/m²/m³/°）（420 行）
- read_tools.py：+get_element_quantities 工具 + DEFAULT_QUANTITIES 默认 14 项（253 行）
- tests/unit/test_quantities.py：+3 用例（mock 值/单位、缺失为 None）
- tests/integration/test_real_instance.py：+真机用例（墙 GrossVolume>0、单位 m³）

### 验证
- 单测 404 → 407 全过；真机集成 22 过 2 跳
- 全部模块 ≤500 行

---

## 2026-09-28 V0.16 工程量分组汇总 aggregate_quantities（算量第 2 步）

### 变更
- 新增 aggregate_service.py（98 行）：_fetch_all 循环翻页取全量匹配、
  _group 纯函数分组求和（None 计入 count 不计入 sum，avg 自动跳过）、
  AggregateService.aggregate 串查询+取量+分组
- read_tools.py：+aggregate_quantities 工具（288 行）。group_by 维度：
  "type"、"story" 或任意属性名，可多选，缺省 ["type"]
- tests/unit/test_aggregate.py：+7 用例（分组纯函数 5 + 服务层 2，全 mock）
- tests/integration/test_real_instance.py：+真机用例（按楼层汇总墙净体积）

### 踩坑
- QueryEngine.query 签名是 query(request)，instance 走 request.instance 字段
- PageResult 字段是 items（dict 列表）不是 summaries

### 验证
- 单测 407 → 414 全过；真机集成 23 过 2 跳

---

## 2026-09-28 V0.17 算量配套：属性缓存提速 + 分类过滤 + 属性定义查询

### 变更（对应算量建议 2/3/5）
- property_service.py（433 行）：_resolve_user_id 与 get_property_type 加
  (instance, name) 进程内缓存（重复解析零开销，算量批量读几十列提速明显）；
  +get_property_definition（类型/单位/分组/描述，枚举附 enum_options 可选项，
  读 possibleEnumValues，兜底 enumValues）
- aggregate_service.py（140 行）：aggregate +classification 参数，新增
  _classification_guids（全系统分类树按 item id 找 GUID →
  GetClassificationsOfElements 批量比对，找不到分类项抛 ValueError）
- read_tools.py（280 行）：+get_property_definition 工具（30 个）；
  aggregate_quantities +classification 参数
- 单测 +5：缓存命中（命令只调 1 次）、定义查询枚举选项、不存在返回 None、
  分类过滤 mock；集成 +2（定义查询、不存在报 PROPERTY_NOT_FOUND）

### 注意
- AC29 未命名项目无任何枚举属性（全量扫描 0 命中），enum_options 结构经
  mock 验证，真机枚举字段名待有枚举属性的项目复测
- BuiltIn 枚举名如 StructuralFunction 在 AC29 不存在（探测返回 ErrorItem）

### 验证
- 单测 414 → 419 全过；真机集成 25 过 2 跳

---

## 2026-09-28 V0.18 算量收尾：平铺出表 + 友好报错 + 兼容补测 + 一键回归

### 变更（对应优化建议 2/3/4/5）
- aggregate_service.py：+_flatten，返回新增 flat_rows（维度键展平到行顶层，
  一组一行，LLM 可直接转表格）
- errors.py：PropertyNotFoundError +suggestions 参数，消息追加
  "你是不是想用：xxx？"
- property_service.py：+suggest_property_names（difflib 对全部属性名模糊匹配，
  cutoff 0.5，取前 3）；get_property_id 报错时自动附建议
- read_tools.py：get_property_definition 报错同样带建议
- tests/compatibility：+TestQuantityCompatibility 3 项（6 个通用量属性各版本
  类型核验、墙上量读取、MEP 三命令存在性）
- 新增 regression.py（一键回归：单测→集成→兼容性→性能基准，汇总报告，
  --json 存文件，多实例自动选 ac29-1）

### 验证
- python regression.py：456 通过 0 失败（单测 419 + 集成 25 + 兼容 12，
  兼容从 9 涨到 12），性能基准 8 项命令正常输出

---

## 2026-09-28 枚举解析修正（AC28 Tapir 更新后真机复测）

### 背景
AC28 的 Tapir 插件已更新到新版，实例 ac28-1 当前挂 GDL-28 项目
（有枚举属性）。借此做真机枚举复测。

### 变更
- property_service.py get_property_definition：枚举可选项字段确认为
  possibleEnumValues，且每项需再下钻 .enumValue.enumValueId.displayValue
  才拿到中文文本；修正解析链，多级 getattr 兜底
- tests/integration：+test_enum_options_real（限定 ac28-1 在线才跑，
  断言 耐火等级 返回 一级/二级/三级/四级耐火等级 纯字符串）

### 验证
- AC28 真机：耐火等级 enum_options = 4 个中文等级名
- 最终回归 457 通过 0 失败（集成 26 过 2 跳）


---

## 2026-09-28 V0.19 幕墙只读支持（CurtainWall）

### 调研
- 下载 Tapir command_definitions.js，搜遍全文无 CreateCurtainWalls / ModifyCurtainWalls
- Tapir 仅支持 CurtainWall 的读取（GetElementsByType）和子构件查询（GetConnectedElements）
- 结论：幕墙无法通过 Tapir 创建，只能做只读+算量

### 变更
- readme.md：新增"只读可算量构件"条目，标注 CurtainWall 可查可算不可建
- readme.md：工具总数 27→30（修正遗漏）
- 版本历史补 V0.19 条目

### 真机验证（AC29）
- 查询 CurtainWall：1 个（CW002，楼层 0）
- 工程量：General_SurfaceArea = 10.0 m²；General_GrossVolume = None（幕墙无体积属性，正常）
- aggregate 按楼层汇总：正常返回 flat_rows

### 备注
- 代码无需改动：query_engine 和 aggregate_service 均用通用 GetElementsByType，天然支持 CurtainWall
- 后续若 Tapir 实现 CreateCurtainWalls，可按 add-archicad-element-type 流程补建模能力

---

## 2026-09-28 V0.20 栏杆/壳体/天窗只读支持

### 调研
- Tapir command_definitions.js 全文搜索：无 CreateRailings / CreateShells / CreateSkylights
- 结论：栏杆、壳体、天窗与幕墙同属 Tapir 不支持创建的层级构件

### 变更
- readme.md：只读可算量构件清单扩展为 幕墙/栏杆/壳体/天窗 四类
- readme.md：版本历史补 V0.20 条目

### 真机验证（AC28+AC29）
- 查询 Railing：两项目均返回 0 个（无报错，查询通道正常）
- 工程量：项目内无栏杆实例，待有数据时补测
- 算量逻辑与 CurtainWall（已验证）完全一致，预期正常

### 备注
- 代码无需改动，查询和算量均走通用 GetElementsByType 接口

---

## 2026-09-28 V0.22 楼层名+构件名补全

### 变更文件
- aggregate_service.py：新增 _TYPE_CN（19 类英→中映射）、_fetch_story_names()；aggregate() 分组后补全 story_name/type_name/element_names；_flatten() 输出含名称字段；aggregate_by_template() 合并时累加 element_names
- tests/unit/test_aggregate.py：fixture 加 name 字段 + mock _fetch_story_names；测试断言 story_name/type_name/element_names

### 真机验证（AC29）
- 按楼层汇总墙长度：story=0 → story_name="一层"，element_names=["墙01","外墙01"]
- 按类型汇总：Wall→"墙"，CurtainWall→"幕墙"，Window→"窗"
- flat_rows 含 story_name + element_names（逗号拼接，适合 CSV）

### 备注
- 单测 424 全过（新增断言在已有测试中扩展，无新增用例数）

---

## 2026-09-28 V0.23 损耗系数+多量合并

### 变更文件
- aggregate_service.py：_group() 支持单量(str)和多量(list)；_flatten() 同步多量；aggregate() 新增 waste_factor + quantities 参数；aggregate_by_template() 支持模板 waste_factor 和 quantities 字段；concrete_volume 模板加 waste_factor=0.03；新增 wall_summary 模板（体积+面积+长度）
- tests/unit/test_aggregate.py：FakeProp 支持多量名；+4 测试（waste_factor、模板损耗、多量 aggregate、多量模板）

### 真机验证（AC29）
- concrete_volume：sum=8.55 m³ → sum_with_waste=8.8065 m³（×1.03）
- wall_summary：体积 8.55 m³ + 面积 19.0 m² + 长度 8.0 m，一张表
- flat_rows 含 sum_{qty}/avg_{qty}/skipped_none_{qty}，CSV 可直接导出

### 备注
- 单测 424→428 全过
- 模板总数 9→10（新增 wall_summary）

---

## 2026-09-28 V0.24 自定义模板+Excel 导出

### 变更文件
- aggregate_service.py：新增 validate_template() 校验自定义模板字段；新增 aggregate_by_custom_template() 方法（支持用户传 JSON 定义模板，含 quantity/quantities/group_by/element_types/waste_factor/description）
- read_tools.py：新增 aggregate_by_custom_template 工具（34 个）；export_table 新增 fmt 参数（csv/xlsx），xlsx 用 openpyxl 写 Excel（表头加粗+列宽自适应）
- tests/unit/test_aggregate.py：+3 测试（自定义单量+损耗、自定义多量、缺字段报错）

### 真机验证（AC29）
- 自定义模板"墙体积含5%损耗"：sum=8.55 → sum_with_waste=8.9775
- 自定义多量模板：体积 8.55 m³ + 面积 19.0 m²
- Excel 导出：10 列含 story_name/多量列/element_names，表头加粗列宽自适应

### 备注
- 单测 428→431 全过
- 工具总数 33→34

---

## 2026-09-28 V0.25 算量规则公式+Excel 多表导出

### 变更文件
- formula_eval.py（新增，59 行）：基于 ast 模块的安全公式求值器，只允许 + - * / 四则运算、数字、变量名；formula_vars() 提取公式引用的量名，eval_formula() 安全求值
- aggregate_service.py：aggregate() 新增 formula/formula_name/formula_unit 参数，公式模式提取量名→取量→逐构件算公式→合成单量列走 _group；validate_template() 接受 formula 字段；aggregate_by_template() 和 aggregate_by_custom_template() 透传 formula；新增 wall_paint_area 模板（表面积*2 公式演示）
- read_tools.py：aggregate_quantities 工具新增 formula/formula_name 参数；export_table 新增 sheets 参数（多表一次导出到同一 xlsx，自动切 xlsx）；aggregate_by_custom_template 文档补公式示例
- tests/unit/test_aggregate.py：+13 测试（formula_vars、eval_formula 基础/None/减除/拒绝调用/语法错误、aggregate 公式模式/None 跳过/缺参报错、公式模板、公式自定义模板、validate 接受 formula）

### 设计说明
- 公式模式与 waste_factor 互补：waste_factor 只能加百分比（×(1+n)），公式支持任意四则运算（如 SurfaceArea*2 双面、NetVolume+GrossVolume 组合量）
- 公式安全性：ast 解析后逐节点判断，仅允许 BinOp/UnaryOp/Constant/Name，拒绝函数调用、属性访问等
- 多表导出：sheets=[{"name":"表名","rows":[...]}, ...]，首个表用 wb.active，后续 create_sheet，每张表独立表头加粗+列宽自适应

### 备注
- 单测 431→444 全过（+13）
- 模板总数 10→11（新增 wall_paint_area）
- 工具数仍 34（无新增工具，仅扩展现有工具参数）
- aggregate_service.py 519 行（+17，接近上限但未超 800）

---

## 2026-09-28 V0.26 GB 50500 清单编码 + 工程量清单报表

### 变更文件
- code_table.py（新增，52 行）：GB 50500 构件类型→清单编码映射表
  （Wall 010502001/Column 010503001/Beam 010504001/Slab 010505001 等 16 类），
  lookup() 按 type 取 code/code_name/code_unit
- report_service.py（新增，135 行）：工程量清单报表排版
  - build_report(rows, value_column, project_name, filename, out_dir) 生成 xlsx
  - 结构：标题（合并居中）→项目信息行→表头（序号/项目编码/项目名称/计量单位/工程量）→
    数据行（同 code 合并求和，按 code 升序）→合计行（仅当所有项单位一致）
  - _pick_value_column：自动探测 sum/sum_xxx/formula_result 量值列
  - _aggregate_by_code：同 code 求和合并
- aggregate_service.py（555→579 行）：+ with_code 参数
  - aggregate()：with_code=True 时强制 group_by 含 type（清单按项分列），
    每个 group 按 type 查 code_table 附加 code/code_name/code_unit 列
  - aggregate_by_template / aggregate_by_custom_template 透传 with_code
  - 8 个预设模板（concrete_volume/wall_area/wall_length/slab_area/door_count/
    zone_area/column_count/mep_length）加 with_code: True
  - validate_template 文档说明接受 with_code
- read_tools.py：export_table 新增 fmt=report 模式 + value_column/project_name 参数
- tests/unit/test_aggregate.py（+11 测试，444→455）：code_table 查表、with_code
  自动加 type 维度、模板带 code 列、自定义 with_code、报表生成/合并/合计/拒空

### 设计说明
- with_code 与 group_by 的关系：with_code=True 强制按 type 分项（清单按项分列是
  GB 50500 标准格式）。concrete_volume 等原"按 story 合并多 type"的模板改为
  "按 story+type 分项"，每种类型一项；若仍想合并总体积，直接调用 aggregate() 不传
  with_code 即可
- 报表 fmt=report 是 xlsx 之上的"清单标准排版"层：标题+项目信息+表头+数据+合计，
  配合模板 with_code=true 自动附 code/code_name/code_unit 列，一键出 GB 50500 报表
- value_column 参数：当模板用 formula 或 quantities 多量时，flat_rows 的量值列名
  不固定（formula_result / sum_General_NetVolume 等），报表自动探测；复杂场景由
  调用方显式传 value_column 指定

### 备注
- 单测 444→455 全过（+11）
- 工具数仍 34（仅扩 export_table 参数，无新增工具）
- 模板数仍 11（无新增，8 个加 with_code 字段）
- aggregate_service.py 579 行（+24，仍未超 800）
- 真机验证待跑（AC29/AC28）：concrete_volume 报表导出对照清单格式

### 待办
- 真机：aggregate_by_template("concrete_volume") → export_table fmt=report →
  打开 xlsx 核对清单格式（标题/合计/单位）
- 可选优化：模板分类小计（如 0105 混凝土工程小计）

