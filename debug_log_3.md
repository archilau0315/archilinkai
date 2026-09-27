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

