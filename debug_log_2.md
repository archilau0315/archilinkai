# debug_log_2（续 debug_log.md）

> 本文件自 2026-09-24 起续记，规则同 debug_log.md：时间、模块、变更简述、备注。

---

## 2026-09-24 适配三个 Agent 客户端（Codex / WorkBuddy / TRAE Work）

### 背景
用户要求 archicad-mcp 同时能被 Codex、WorkBuddy、Trae Work 三个客户端使用。

### 关键前提（已确认）
archicad-mcp 是**本地 stdio server**，必须在用户电脑本地启动、才能连本机 ArchiCAD（端口 19723/19724）。
- Codex CLI：本地终端启动 → 可用
- WorkBuddy：桌面版本地 stdio → 可用；云端企业智能体/手机端需桌面端在运行做桥接
- TRAE Work：桌面版本地环境 → 可用；网页版（纯云端）连不到本机 ArchiCAD

### 变更 1：Codex
- 文件：`C:\Users\user\.codex\config.toml`（追加，未动原有配置）
- 追加：
  ```toml
  [mcp_servers.archicad]
  command = "C:/Python314/python.exe"
  args = ["E:/works/Aidev/Kbitai绝对安全/kbitai_com_cn/aitools/acmcp/archicad-mcp/server.py"]
  ```
- 验证：`codex.exe mcp list`（实际路径 C:\Users\user\.codex\.sandbox-bin\codex.exe）→ archicad **enabled** ✓
- 备注：codex 命令未加进系统 PATH（该 codex 是应用内置分发），需用绝对路径调；但配置文件本身在标准位置，应用启动时会自动加载

### 变更 2：WorkBuddy
- 新建：`C:\Users\user\.workbuddy\mcp.json`（注意是 .workbuddy 目录里无点前缀的 mcp.json）
- 内容：mcpServers.archicad，type=stdio，command=C:/Python314/python.exe 绝对路径，args=server.py
- **待用户操作**：WorkBuddy 安全机制要求对每个自定义连接器手动"信任"（连接器管理页 → 自定义连接器 → archicad → 信任）；改动 command/args 后需重新信任
- 备注：用 python.exe 绝对路径，避免 WorkBuddy 启动子进程时不继承系统 PATH 导致找不到 Python

### 变更 3：TRAE Work
- 无需新增：项目根 `.trae/mcp.json` 昨天已建好，TRAE Work 桌面版本地环境直接生效
- 网页版（云端）不适用，见上方前提

### 统一细节
- 三个配置 command 一律用 `C:/Python314/python.exe` 绝对路径（不依赖 PATH）
- args 指向同一份 server.py，三处共用一个 server

### 同步更新
- readme.md：「客户端配置」节增加 Codex（TOML）与 WorkBuddy 配置；说明本地/云端限制
- debug_log.md：末尾加指引，后续日志记本文件

---

## 2026-09-24 优先级第 1 项：真机测试套件全部修复跑绿

### 背景
旧测试套件长期"假绿/失真"：集成测试用后来被证伪的 API，兼容性测试断言与实际返回不符。目标：真机测试真实反映功能、全部跑绿。

### Bug 8：query_engine 属性过滤整链失效
文件：query_engine.py
- `_get_guids_by_type` 返回 UUID 对象（`e.elementId.guid`），传给 Tapir 时
  `Object of type UUID is not JSON serializable` → 统一 `str()` 转换
- 属性过滤旧实现用错误的 `conn.types.PropertyUserId(name=,type=)` 构造
  + 不存在的 `conn.utilities.GetPropertyValuesDictionary`，永远取不到值
- 修复：`_filter_by_properties` 直接复用 property_service 已验证的
  `get_values(guids, field_names, instance)`；删除 `_resolve_property_id` /
  `_get_property_values` / `_extract_value` / `_extract_guid` 重复且错误的代码
- 附带修复：`story_idx = d.get("floorIndex") or ...` 在楼层为 0 时把 0 误判空
  → 改 `d.get("floorIndex", d.get("storyIndex"))`
- 验证：耐火等级=2小时命中 8 / 不命中 0 / 分页 3 / 楼层0 过滤 8

### Bug 9：HighlightElements 参数结构错误
文件：server.py + 经真机验证
- 旧入参 `{"elementIds":[{"guid":...}]}` schema 拒绝（additionalProperties）
- 查得正确结构（multiconn_archicad 文档）并真机验证成功：
  elements + highlightedColors(RGBA) + wireframe3D + nonHighlightedColor
- 默认颜色：高亮绿 [50,255,100,100]，非高亮蓝 [0,0,255,128]

### Bug 10：get_classifications 命令名错误 + 返回被转成字符串
文件：server.py + tapir_adapter.py
- 旧命令 `conn.commands.GetAllClassifications()` 不存在
  → 改 `GetAllClassificationSystems()`
- archicad 类型用 `__slots__`（__dict__ 为空），_to_dict 兜底成字符串
  → _to_dict 增加 __slots__ 处理
- 新增 __slots__ 处理后触发"递归超限"：UUID 的 slot 含 SafeUUID 枚举，
  枚举内部自指 → _to_dict 增加特判：uuid.UUID→str、enum.Enum→value
  （顶部加 import enum / uuid）
- 验证：返回规整 dict，guid 为 36 位字符串

### 测试重写
- tests/integration/test_real_instance.py：整体重写，走 server 完整工具链；
  无真机自动 skip；写操作只验证 confirm=False 拦截，不实际改模型 → **19/19 全绿**
- tests/compatibility/test_ac26_29_matrix.py：整体重写
  - class-scoped fixture 改为模块级（消除 2 个 ERROR）
  - guid 断言改 str() 后 36 位
  - ElementType("Object") 改直接传字符串
  - 两个"记录性"测试改用 property_service 正确通道
  → **9 过 / 1 skip**（无 GDL 对象，合理）

### 最终测试结果（真机环境 AC28+AC29）
- 单元测试：**126/126 全过**（无回归）
- 集成测试：**19/19 全绿**
- 兼容性测试：**9 过 / 1 skip**

### 模块行数（均 <500，符合规则）
server.py 397 / query_engine.py 209 / tapir_adapter.py 155 /
property_service.py 350 / operation_service.py 188

### 同步更新
- readme.md 测试说明同步
- 本文件追加本记录

---

## 2026-09-24 优先级第 2 项：补 attach_classification 分类挂接工具

### 背景
开发清单 P1 层缺 attach_classification（计划 19 工具实际 18）。目标：给元素挂分类项，走与属性写入相同的"预览+确认"安全机制。

### API 探查结论（真机验证）
- 读：`GetAllClassificationSystems()` / `GetAllClassificationsInSystem(sid)`
  / `GetClassificationsOfElements(elements, systemIds)`
- 写：`SetClassificationsOfElements([ElementClassification])` → ExecutionResult.success
- 分类树子项字段名是 `children`（此前误用 childItems）
- 元素当前分类读取路径：`r.classificationIds[0].classificationId.classificationItemId.guid`
- 实测项目：系统"Archicad 类别"；墙当前挂"元素 > 构造元素 > 墙面"，
  可挂子项如"标准墙/剪力墙/实心墙"等

### 变更 1：errors.py
- 新增错误码 CLASSIFICATION_NOT_FOUND + 异常类 ClassificationNotFoundError(name, kind)

### 变更 2：operation_service.py（188 → 351 行）
新增分类四阶段：
- `_find_classification_system(name, instance)`：按名称找系统；None 时要求唯一系统
- `_find_classification_item(system, item_name, instance)`：树中递归精确匹配（含子项），返回 (item, 完整路径)
- `_read_classifications(guids, system_id_guid, instance)`：批量读当前分类
- `preview_classification_change(...)`：返回 system/system_id/target_item/target_item_id/target_count/before/risk
- `execute_classification_change(..., confirm)`：confirm=False 抛 ConfirmRequiredError；
  写入后重新读回核对，复用 _record 记 OperationLog

### 变更 3：server.py（397 → 434 行）
新增 2 个 P1 工具（工具数 18 → 20）：
- `preview_classification(element_guids, item_name, system_name, instance)`：先看后写
- `attach_classification(element_guids, item_name, system_name, confirm, instance)`：执行挂接

### 真机验证（AC29）
1. confirm=False → CONFIRM_REQUIRED ✓
2. 挂"标准墙" → verify success，路径"元素 > 构造元素 > 墙面 > 标准墙"，
   operation_id=OP-20260924-00001 ✓；随后挂回"墙面"恢复原状 ✓
3. 错误项名 → CLASSIFICATION_NOT_FOUND ✓
4. preview_classification → 12 元素 before 齐全 ✓

### 测试更新
- 单元 +2：分类 confirm 拦截（不触发连接）→ **128 全过**
- 集成 +3：preview / confirm 拦截 / 错误项名
- 修 test_search_by_property_value 过时断言：不再假设所有墙都赋过值
  （用户新增 4 面墙未赋耐火等级导致 8≠12），改为"先读实际值再过滤"，
  无值时 skip
- 最终：**单元 128 全过；集成+兼容 31 过 / 1 skip**

### 模块行数（均 <500）
server.py 434 / operation_service.py 351 / errors.py 250

### 同步更新
- readme.md：工具清单补 2 个分类工具、测试结果更新
- 本文件追加本记录

---

## 2026-09-25 优先级第 3 项：补完整几何信息（长度/起止点/包围盒）

### 背景
get_element_geometry_info 此前只返回原始详情并标注"顶点/包围盒待补充"。
真机探查确认 Tapir GetDetailsOfElements 返回已含全部所需数据，无需新命令。

### 实测数据字段（AC29 墙 SW-001）
- 顶层：type / floorIndex / layerIndex / id
- details：geometryType(Straight) / structureType(Composite) /
  zCoordinate / begCoordinate{x,y} / endCoordinate{x,y} /
  height / begThickness / endThickness / referenceLineLocation 等
- floorPlanPolygons：平面图全部多边形顶点（含洞口切分）

### 变更 1：新建 geometry_service.py（86 行，单一职责）
- `_wall_length(d)`：直墙取起止点欧氏距离（math.hypot）；
  曲墙不猜弧长，返回 None
- `_bounding_box(detail, d)`：平面投影包围盒取自全部多边形顶点
  min/max；z 取 zCoordinate ~ zCoordinate+height
- `summarize(detail)`：输出 guid/type/id/floor_index +
  summary(length/height/thickness/structure_type) +
  base_point/end_point/elevation + bounding_box/polygon_count；
  字段缺失自动跳过，适配板等非墙元素
- `summarize_all(details)`：批量规整

### 变更 2：server.py（434 → 436 行）
- import geometry_service
- get_element_geometry_info 改为 details → geometry_service.summarize_all
  → 规整 items；删除"待扩展"note；docstring 更新坐标约定
  （x/y 项目坐标，z 相对楼层）

### 真机验证（AC29 SW-001）
- length=14.1543m，高 3m，两端厚 0.3m，Composite ✓
- base/end point 坐标与原始数据一致 ✓
- 包围盒 size x=14.2543 / y=0.3 / z=3（含参考线外侧偏移，真实顶点计算）✓
- polygon_count=8 ✓

### 测试
- 新建 tests/unit/test_geometry_service.py（8 个）：
  3-4-5 验证长度、尺寸字段、起止点、包围盒、曲墙不猜长度、
  缺 details 不崩、板类只出包围盒、批量
- 集成 test_get_element_geometry_info 增强：length>0、起止点、
  bbox.size.z == height
- 最终：**单元 136 全过（128+8）；集成+兼容 31 过 / 1 skip**

### 模块行数（均 <500）
server.py 436 / geometry_service.py 86

### 同步更新
- readme.md：项目结构补 geometry_service、几何验证结果、测试数字
- 本文件追加本记录

---

## 2026-09-25 优先级第 4 项：写入前项目身份强校验

### 背景
原写入流程只核对产品版本 + 用 project_name 做弱校验；项目被关闭/另存为/
切换后端口仍在、名字可能相同，存在写错项目风险。
真机探查发现项目已保存（E:\TEST\GDL-29.pln），Tapir GetProjectInfo
实际返回完整字段（此前未见是因为当时项目未保存）：
projectPath / projectLocation / projectName / isUntitled / isTeamwork。

### 校验规则
1. discover/refresh 时为每个实例建立"项目身份基线"，核心是文件完整路径
2. 写入前重新读身份：路径与基线不一致 → 拦截
3. 未保存基线（无路径）当前突然出现路径，或未命名变已命名 → 拦截
4. 目标元素 GUID 必须全部存在（archicad 原生 GetAllElements，
   不依赖 Tapir）；换项目后相同 GUID 不可能存在
5. 拦截后提示用户调 refresh_instances 建立新基线再重试
6. 旧条目无基线时现场建立，不阻塞

### 变更 1：errors.py（250 → 265 行）
- 新增错误码 PROJECT_IDENTITY_CHANGED
- 新增 ProjectIdentityChangedError(instance, baseline, current)，
  retryable=True，details 记录双方身份

### 变更 2：instance_manager.py（246 → 254 行）
- InstanceEntry 增加 project_identity 字段
- 新增模块函数 read_project_identity(conn)：读并规整 GetProjectInfo
  → {path, name, is_untitled, is_teamwork}；Tapir 不可用返 {}
- _tapir_get_project_name 改为复用该函数（消除重复实现）
- _build_entry / refresh_instances 建立基线，project_name 取实名
- 新增 check_project_identity(element_guids, instance)：
  路径比对 + GUID 存在性比对，通过返当前身份

### 变更 3：operation_service.py（351 → 355 行）
- execute_property_change：validate_instance 后加 check_project_identity
- execute_classification_change：同上；删除重复的 guids 定义
- preview 阶段不做身份校验（不写入，保持轻量；关键时间窗
  "preview 后项目被切换"由 execute 校验覆盖）

### 真机验证（AC29）
1. 正常身份（GDL-29.pln）→ 通过 ✓
2. 篡改基线路径为 fake.pln → PROJECT_IDENTITY_CHANGED ✓
3. 假 GUID → PROJECT_IDENTITY_CHANGED ✓
4. 恢复基线 → 通过 ✓
5. 完整写入链路：挂"标准墙" success → 改回"墙面" success（无误伤）✓

### 测试
- 单元 +5：身份一致通过 / 路径变化拦截 / GUID 缺失拦截 /
  无基线自建立 / 未保存变已保存拦截（monkeypatch read_project_identity
  + mock GetAllElements）
- 最终：**单元 141 全过（136+5）；集成+兼容 31 过 / 1 skip**

### 模块行数（均 <500）
instance_manager.py 254 / operation_service.py 355 /
errors.py 265 / server.py 436

### 同步更新
- readme.md：安全设计节加强校验说明、验证表、测试数字
- 本文件追加本记录

---

## 2026-09-25 优先级第 5 项：Benchmark 性能基准（V0.3 8.12）

### 新增 1：benchmark.py（约 130 行，<500）
- measure(fn, rounds)：perf_counter 计时，返 {rounds, avg, min, max}（ms）
- _build_calls：8 个常用只读命令（5 个 archicad 原生 + 3 个 Tapir；
  GetDetailsOfElements 取前 3 个元素）
- run：按实例跑全部命令，结果含时间戳/实例/项目/版本
- to_markdown：结果转 markdown 表格
- _save：同时存 benchmark_results.json（程序用）+ .md（人看）
- main：命令行参数 --instance / --rounds（默认 3）

### 真机数据（ac29-1 / GDL-29，3 轮，ms）
| 命令 | 平均 | 最小 | 最大 |
|---|---|---|---|
| GetProductInfo | 0.91 | 0.79 | 1.15 |
| GetAllElements | 70.49 | 38.45 | 108.55 |
| GetAllPropertyNames | 70.09 | 57.87 | 81.15 |
| GetElementsByType(Wall) | 47.25 | 33.22 | 74.19 |
| GetAllClassificationSystems | 51.51 | 29.08 | 82.06 |
| Tapir GetProjectInfo | 14.7 | 6.29 | 24.44 |
| Tapir GetStories | 14.8 | 4.36 | 24.37 |
| Tapir GetDetailsOfElements(3个) | 27.03 | 12.08 | 39.91 |

### 数据观察
- GetProductInfo <1ms（archicad 包连接时已缓存产品信息）
- 批量只读命令平均 50–70ms，波动大（min/max 差约 2–3 倍，
  本地 HTTP+AC 主线程忙闲导致），单次结果不代表稳定延迟
- Tapir 轻命令 15ms 左右；首轮偏慢（冷启动）
- 结论：所有只读命令均在百毫秒级，满足对话式调用

### 过程小问题
- 类型注解 `list[tuple[str, Callable[[], Any]]]` 两处少写右括号
  导致 SyntaxError，补齐后跑通

### 新增 2：tests/unit/test_benchmark.py（+3）
- measure 字段与 min≤avg≤max / 执行次数恰为 rounds /
  to_markdown 含实例名、命令名与表格分隔

### 测试
- 单元 **144 全过（141+3）**；未改集成依赖模块，真机集成无影响
- 模块行数：benchmark.py <500 ✓

### 同步更新
- readme.md：项目结构补 benchmark、性能基准节、测试数字
- 本文件追加本记录

---

## 2026-09-25 优先级第 6 项：GDL Engine 分层（纯整理）

### 背景
GDL 读写逻辑原来直接写在 server.py 里（get_gdl_parameters、
set_gdl_parameters 两处），server.py 膨胀到 508 行，接近上限。
本次只做位置迁移，功能一字未改。

### 新增：gdl_service.py（77 行，<500）
- GDLService(mgr)：
  - get_parameters(element_guids, instance)：构造 elementIds，
    调 Tapir GetGDLParametersOfElements，结果经 _to_dict 规整
  - set_parameters(element_guids, parameter_name, value, confirm,
    instance)：confirm=false 抛 ConfirmRequiredError；通过后
    validate_instance + generate_id + 调 Tapir 写入，
    返 {operation_id, instance, project, verify}（verify 结构原样保留）
- 模块级单例 service = GDLService(instance_manager.manager)

### 修改：server.py（508 → 483 行）
- 新增 import gdl_service
- get_gdl_parameters：改调 gdl_service.service.get_parameters
- set_gdl_parameters：改调 gdl_service.service.set_parameters
- 删除已无人使用的辅助函数 _require_confirm（confirm 拦截
  已统一由 service 内部处理）
- _tapir_normalize 仍被 list_floors / get_classifications 使用，保留

### 新增测试：tests/unit/test_gdl_service.py（+3）
- confirm=false 抛 ConfirmRequiredError
- confirm=true 时调 Tapir 写入、返回 operation_id 和 verify
- get_parameters 正确传 elementIds（用 GDLService.__new__ 避开真实 manager，
  monkeypatch Tapir 与 generate_id）

### 测试
- 单元 **147 全过（144+3）**
- 真机集成+兼容 **31 过 / 1 合理跳过**（含 GDL confirm 拦截集成用例）
- py_compile：server.py / gdl_service.py 均通过

### 模块行数（均 <500）
server.py 483 / gdl_service.py 77

### 同步更新
- readme.md：项目结构补 gdl_service、分层说明、测试数字
- 本文件追加本记录

### 备注
至此 readme「待实机验证」与六项遗留全部清零；20 个工具功能完整、
真机验证、三客户端可接入。

---

## 2026-09-25 新增增强版开发计划文档（对话生成模型 V1.0）

### 新增文件
- 开发计划_对话建模V1.0.md（规划文档，无代码变更）

### 文档要点
- 目标：自然语言 / 图片输入 → ArchiCAD 自动生成模型
- 实测事实：
  - archicad 官方包无创建几何元素命令
  - Tapir 仅支持 CreateWalls/Columns/Beams/Slabs 四种
  - 图片由多模态 LLM 直接识别，server 不处理图片
- 核心设计：两条输入路径汇合为统一"建模计划 JSON"，
  复用四阶段（预览→确认→创建→验证）
- 规划新增 4 模块（model_plan/create_service/plan_preview/
  image_guide，各 <500 行）+ 3 工具（共 23 个）
- 分四阶段：V1.0 墙柱最小闭环 → V1.1 梁板 →
  V1.2 图片识别 → V1.3 门窗等扩展
- 安全：默认不创建、可撤销、项目指纹校验、单次 ≤200 构件

### 过程
- 临时探查脚本 _probe_create.py 等已全部清理
- 待用户审阅计划后开始 V1.0 实施

---

## 2026-09-26 跨平台适配：自动识别操作系统（结论：无需写检测代码）

### 背景
用户要求加"自动识别操作系统"逻辑，让项目能在 Mac 上使用。

### 核查结论（代码层）
- 全部核心模块路径处理只用 os.path / os.path.abspath(__file__)
  （如 audit_log.py、tests/conftest.py），Windows/Mac 自动适配
- 实例发现靠扫描端口 19723–19743，跨平台，不依赖注册表
- 全项目无 winreg/.exe/盘符/反斜杠路径等 Windows 专属写法
- 结论：Python 代码天然跨平台，硬加 OS 判断是无效代码，不写

### 变更 1：.trae/mcp.json（唯一实际配置改动）
- args 从写死的 Windows 绝对路径改为 Trae 内置变量
  `${workspaceFolder}/archicad-mcp/server.py`
- 启动时自动替换为本机项目根目录，同一份配置 Win/Mac 通用
- 该文件受 Trae 保护、编辑器无法改写，用 PowerShell
  [IO.File]::WriteAllText（UTF8 无 BOM）写入

### 变更 2：readme.md
- Trae 配置节同步为 ${workspaceFolder} 版，补 Mac 说明

### Mac 使用前提（已联网核实）
- Tapir 官方提供 Mac 版：GitHub 1.5.9 发布资产含
  TapirAddOn_AC25/26/27/28_Mac.zip（AC29 在同批资产内，下载页核对）
- Mac 唯一手工差异：无 python 命令时配置里改 python3
- archicad 官方包是纯 Python HTTP 客户端，Win/Mac 均可 pip 安装

### 待验证（需用户操作）
- Trae MCP 面板把 archicad 开关关掉再开（或点刷新），
  发"列出所有 ArchiCAD 实例"确认重连成功

---

## 2026-09-26 根据 Tapir 新版修订 V1.0 开发计划（第二次修订）

### 背景
Tapir 1.5.9 新增门窗创建等能力，原计划"门窗屋顶不支持"的事实作废，
需重新核实全部命令并重排阶段。

### 真机实测结果
- ac29-1：Tapir 1.5.9，39 个候选 Create/Modify 命令 **39 个全可用**
- ac28-1：Tapir 1.2.0（旧版），仅 **7 个**可用
- 关键结论：命令能力取决于 **Tapir 插件版本**，与 ArchiCAD 版本无关；
  AC28 升级插件后能力相同
- 1.5.9 创建命令（实测）：墙柱梁板、楼梯、屋顶、Morph、Mesh、
  门窗、开洞、GDL 对象、灯具、区域、2D 线弧圆/文字标签、
  剖面、立面、图纸、图层；另有 9 个 Modify 命令
- 门窗要点：必须挂墙（ownerWallId）；1.5.9 已自动处理
  "平面图当前数据库"切换，调用方无需理会

### 变更文件
- 开发计划_对话建模V1.0.md（整体修订）：
  - 构件由 4 种扩到 13 种，计划 JSON 加门窗挂墙引用
  - 阶段重排：V1.0 墙柱 / V1.1 梁板 / V1.2 门窗开洞 /
    V1.3 楼梯屋顶 Morph / V1.4 图片识别（后移）/ V1.5 扩展
  - 新增"版本闸门"：目标实例 Tapir 不支持所需命令时预览即拦截
  - 模块拆分预案：create_service 只调度，参数拼装按构件族拆
    create_framing / create_openings / create_special（各 <500 行）
- 工具数不变：仍新增 3 个（共 23），构件增加不加工具

### 备注
- 探查脚本与下载的头文件均在系统临时目录，已清理
- 待办：ac28 的 Tapir 1.2.0 → 1.5.9 升级后再做双版本验证

---

## 2026-09-26 V1.0 对话建模第一阶段：通道抽象层 + 墙柱创建

### 新增模块（6 个，均 <500 行）
- channel_base.py：建模通道抽象基类 ModelChannel（get_version /
  supports / check_supports / create）+ CreateResult。业务层只认此接口，
  通道可插拔，为将来官方 MCP 通道预留
- tapir_channel.py：Tapir 通道实现。业务类型→Tapir 命令映射
  （Wall→CreateWalls、Column→CreateColumns），参数拼装 + 返回解析，
  含命令可用性缓存
- model_plan.py：建模计划数据结构与校验。V1.0 开放 Wall/Column；
  默认墙高 3m/厚 0.2m、柱高 3m；校验类型、坐标范围 ±10万m、
  正数、墙非零长、单次 ≤200
- plan_preview.py：计划转人能看懂的预览（分类计数、墙总长、逐构件明细）
- create_service.py：调度服务。confirm 闸门 → 实例/项目身份校验 →
  版本能力闸门 → 按类型分组创建 → 读回验证 → 记操作日志
- diagnostic_tools.py：P2 四个诊断工具从 server.py 拆出（控制行数）

### 修改模块
- server.py：接入 preview_model_plan、create_from_plan 两个工具；
  P2 拆出后由 521 行降回 477 行
- errors.py：新增错误码 CHANNEL_CAPABILITY_UNSUPPORTED 与
  ChannelCapabilityError（通道不支持某构件时拦截）
- readme.md：项目结构、工具分层、版本同步；工具总数 22
  （V1.0 落地 2 个；原计划第 3 个 describe_image_to_plan 随 V1.4 再做）

### 测试
- 单元测试 182/182 通过（原 147 + 新增 35）
- AC29 真机闭环：预览 → confirm=false 拦截 → confirm=true 创建
  墙 1（长 6m/高 3m/厚 0.2m）柱 2（高 3m）→ 几何读回全对

### 真机发现并修复的 Bug（重要）
- 现象：构件真实创建成功、几何正确，但 verify 判 3/3 failed
- 根因：GUID 大小写不一致——Tapir 返回大写
  （9CB4F553-…），GetAllElements 的 UUID 转字符串为小写
  （9cb4f553-…），集合比对直接不相等
- 修复：create_service._verify 比对前两边统一 lower()
- 已补防回归单测（通道返回大写、系统存小写仍判 success）

### 备注
- 真机测试在 (80,80) 偏远位置建了 3 个构件，已提示用户在 AC 按一次
  Ctrl+Z 撤销（同一可撤销单元，一次全撤销）；临时脚本已删除
- 经验：凡涉及外部通道返回 GUID 与本地 UUID 比对，一律先归一化
  （大小写 + 去连字符差异），不能假设格式一致
- 下一步：V1.1 扩展梁、板

---

## 2026-09-26 V1.1：建模计划扩展梁（Beam）和板（Slab）

### 修改模块
- model_plan.py：SUPPORTED_TYPES 增加 Beam/Slab；新增 _build_beam /
  _build_slab 校验。默认梁截面 0.2×0.3m 顶标高 0、板顶标高 0 厚 0.2m；
  梁板起止点/顶点校验（梁非零长、板 ≥3 顶点、梁顶标高可为负）
- tapir_channel.py：命令映射新增 CreateBeams/CreateSlabs；
  梁参数拼装含 isWidthAndHeightLinked=False（宽高独立必关）；
  板含 referencePlaneLocation=Top
- plan_preview.py：中文名表加梁/板；梁明细含截面+顶标高；
  板明细含顶点数+包围盒；risk 提示加"复合结构板厚以结构为准"
- server.py：两个计划工具 docstring 补梁板示例与默认值说明
- readme.md：单测数 194

### 测试
- 单元测试 194/194（新增 12：梁默认值/显式值/零长/负标高/坏截面；
  板默认值/显式值/点数不足/缺多边形/坏点/预览描述/包围盒）
- AC29 真机闭环：预览 → 创建梁 1（截面 0.25×0.4 顶标高 3m）
  板 1（矩形 4 顶点）→ 读回验证 2/2 success

### 真机发现（重要经验）
- 梁必填字段：begCoordinate / endCoordinate / **zCoordinate**（顶标高），
  与墙不同（墙是 height）。来源：Tapir 源码 ExtendedElementCommands.cpp
  CreateBeamsCommand::GetInputParametersSchema
- 板结构为"复合"时，thickness 参数被复合层定义覆盖（计划 0.2 →
  实际 0.3），CreateSlabs schema 无结构选择字段，属 Tapir 行为限制，
  已在预览 risk 中提示
- 梁截面宽高独立必须传 isWidthAndHeightLinked=False，
  否则改一个另一个跟着变（Archicad 默认联动）
- 探查教训：盲试字段名低效，直接读源码 GetInputParametersSchema
  一次拿全；大文件下载要等待完成再 grep，避免文件锁

### 备注
- 真机测试在 (80,80) 区域建了梁板各 1，需用户在 AC 按 Ctrl+Z 撤销
  （V1.0 的 3 个 + V1.1 的 2 个，分别一次撤销）
- 下一步：V1.2 门窗开洞（需墙上挂接，先确认 Tapir 命令名与参数）

---

## 2026-09-26 V1.2：建模计划扩展门（Door）、窗（Window），支持挂墙

### 核心设计：墙引用双写法
门窗必须挂墙，但墙可能是本计划新建（解析时无 GUID）或项目已有（有 GUID）。
计划里门窗字段 wall：
- 整数 → 本计划中墙的序号（引用将新建的墙），如 0
- 字符串 → 项目中已有墙的 GUID
调度层 create_service 负责把序号解析成真实 GUID，通道只收已解析的参数。

### 修改模块
- model_plan.py：SUPPORTED_TYPES 加 Door/Window；新增 WALL_BASED 集合、
  _build_opening（校验 wall 类型、offset≥0、宽高正数、窗台/门槛≥0）、
  _check_wall_references（交叉校验：序号引用的目标必须是墙）、
  _non_negative（允许 0）。默认门 1.0×2.1 门槛0，窗 1.2×1.5 窗台0.9，
  门窗默认距墙起点 1m
- tapir_channel.py：命令映射加 CreateDoors/CreateWindows；
  门窗 _build_param 用 ownerWallId/centerOffset/sillHeight
- create_service.py：_create_all 改两轮——先建独立构件（墙柱梁板），
  再建门窗；新增 _build_opening_items（解析墙引用，墙失败的门窗挑出
  blocked）、_resolve_wall、_run_group、_collect_rows；
  execute 时对"引用已有墙"的 GUID 做项目存在性校验
- plan_preview.py：门窗明细（挂的墙+距墙起点+洞口+窗台/门槛），
  risk 加"门窗只支持直墙"；新增 _wall_ref_text
- server.py：preview_model_plan docstring 补门窗示例与双引用说明
- readme.md：版本历史加 V1.1/V1.2，单测数 212

### 测试
- 单元测试 212/212（新增 18）：
  - model_plan 门窗 12（默认值/显式值/GUID引用/序号非墙/越界/缺wall/
    wall类型错/空GUID/负offset/零offset/坏宽高/负窗台）
  - plan_preview 2（门窗明细+双引用文字）
  - create_service 4（窗挂新墙解析GUID/门挂已有GUID/先墙后窗顺序/
    墙失败窗blocked）
- AC29 真机闭环：墙 1（6m）+ 门（中心1m）+ 窗（中心3m）→
  创建成功，验证 3/3

### 真机确认
- 门 details.ownerElementId.guid = 新建墙 GUID，ownerElementType="Wall"
  （Tapir 字段名是 ownerElementId，不是 ownerWallId；入参才叫 ownerWallId）
- 门窗平面图多边形 x=80.5（门中心1m、宽1m → 0.5~1.5），位置准确
- 门窗用项目默认库对象（不填 favoriteName 时走工具默认设置）

### 经验
- 门窗入参 schema 在源码 ExtendedElementCommands.cpp
  CreateWindowsCommand/CreateDoorsCommand::GetInputParametersSchema
  （约 3885/4055 行）；两者字段完全一致
- Tapir 源码大文件（336KB）raw.githubusercontent 下载易超时，
  改用 cdn.jsdelivr.net/gh/... 稳定快速
- 入参 ownerWallId 与读回 ownerElementId 命名不同，写比对时注意
- 强依赖构件（门窗）必须排在被依赖构件（墙）之后创建，
  且被依赖方失败时依赖方要优雅降级而非整批崩

### 备注
- 真机测试在 (80,100) 建了墙+门+窗，需用户在 AC 按一次 Ctrl+Z 撤销
- 至此建模计划支持 6 类构件：墙/柱/梁/板/门/窗
- 下一步：V1.3 楼梯、屋顶、Morph（Tapir CreateStairs/CreateRoofs 等）

---

## 2026-09-26 V1.3：建模计划扩展楼梯、屋顶、变形体

### 修改模块
- model_plan.py：SUPPORTED_TYPES 加 Stair/Roof/Morph（共 9 类）。
  新增 _build_stair（基线起止点+底标高+总高+梯宽，steps 可选、
  ≥1 整数）、_build_roof（多边形+底标高+厚度；给 slope 度=单坡，
  可配 pivot 转轴，不给=多平面；slope 限定 0~90 不含）、
  _build_morph（只支持方块：基点 position+尺寸 size）、
  _point3d（3D 点校验）。默认值：楼梯总高3/梯宽1.2/底0，
  屋顶底0厚0.3，变形体 1m 方块
- tapir_channel.py：命令映射加 CreateStairs/CreateRoofs/CreateMorphs；
  楼梯 baseLinePoints+zCoordinate+totalHeight+flightWidth(+stepNum)；
  变形体 basePoint+size；屋顶新增 _build_roof_param，单坡时
  pivotLine（显式 pivot 优先，否则多边形第1边）+ angle（度→弧度）
- plan_preview.py：三类明细；risk 加屋顶楼层限制、多平面/
  方块限制说明
- server.py：docstring 补三类示例与默认值
- readme.md：版本历史加 V1.3，单测 228

### 踩坑：屋顶 level=3 "假成功"
- 现象：CreateRoofs 返回 elementId GUID，但 GetAllElements 没有，
  get_details 报 -2130313115。连续两次必现
- 触发条件：level=3（弹"元素已在看不见的楼层创建"警告）
- 对照：level=0 的同参数屋顶真实存在
- 处理：屋顶默认底标高从 3 改为 0；risk 与文档明确
  "底标高要填当前楼层（首层 0）"
- 教训：不能只信返回的 GUID，创建后必须读回存在性——
  _verify 机制正是干这个的

### 另一个 Tapir 限制
- 楼梯 get_details 返回 "Not yet supported element type"，
  即 Tapir 1.5.9 不支持读楼梯详情；楼梯本身创建正常，
  以存在性验证为准
- 变形体基点读回字段名是 origin（不是 basePoint），
  实测 (212,100,0) 准确

### 远程处理模态对话框（用户不在电脑前）
- 用 TRAE-computer-use-ptc 操作：list_apps 找 AC29 pid=39100，
  get_app_state 读对话框
- click 对该对话框多次无效（焦点在 360壁纸等其他窗口时），
  press_key Enter 有效关闭
- 注意区分回车默认按钮；本次以"创建后读回"兜底，
  没被误导

### 测试
- 单元 228/228（新增 16）：model_plan 13（楼梯4/屋顶6/变形体3）、
  plan_preview 2、create_service 1（三类独立构件一轮创建+
  结果按序号排）
- AC29 真机：楼梯（基线4m/16级）+ 单坡屋顶（30°）+
  变形体方块 → 验证 3/3

### 备注
- 真机测试构件分布 (120~212,100~116) 区域，含：
  V1.3 首次跑的楼梯1、变形体1（屋顶已假成功不存在）、
  手动探查的成功屋顶1（160,100）、最终验证的楼梯+屋顶+变形体。
  需用户回电脑后在 AC 按 Ctrl+Z 逐次撤销
- 至此建模计划支持 9 类构件：墙/柱/梁/板/门/窗/楼梯/屋顶/变形体
- server.py 493 行，下次加工具前必须先拆
- 下一步方向：变形体任意形状（MorphBody）、屋顶开洞/
  L形楼梯，或构件修改（Tapir 已有 Modify* 系列）

---

## 2026-09-26 V1.3.1 重构：拆 server.py，统一工具注册模式

### 背景
server.py 涨到 493 行，逼近 500 上限，再加工具必须先拆。
P2 诊断工具此前已用 register(mcp, safe) 模式拆出，
本次把同样模式推广到 P0、P1。

### 拆分方案
- server.py（493→62 行）：纯入口，只留
  建 FastMCP、_safe 异常包装、启动发现实例、三次 register 调用
- 新建 read_tools.py：P0 只读 10 个（list_instances /
  project_summary / get_selected_elements / get_elements_by_type /
  get_element_properties / search_elements_by_criteria /
  get_gdl_parameters / list_floors / get_classifications /
  get_element_geometry_info）
- 新建 write_tools.py：P1 写入 8 个（preview/set 属性、
  set GDL、preview/attach 分类、highlight、preview/create 计划）；
  原 server._instance_info 随迁为 write_tools._info
- diagnostic_tools.py：保持不变（P2 4 个）
- 三个注册模块同一签名：register(mcp, safe)，
  safe 由 server 传入，异常包装只有一份

### 同步处理
- _tapir_normalize 辅助删除，read_tools 直接用 tapir_adapter._to_dict
- readme.md：项目结构补两个新文件、server 注释更新；
  版本历史加 V1.3.1

### 测试
- 单元 228/228：
  - test_server 两处引用 server._instance_info 改为 write_tools._info
  - 顺带补全 InstanceInfo 测试构造缺的 language 参数
    （该用例此前因 AttributeError 提前失败，掩盖了此问题）
- 导入 server 实测：注册工具仍 22 个，名称逐一核对无缺失
- 纯结构调整，无行为变化，不涉及真机

### 备注
- read_tools.py 216 行、write_tools.py 207 行，均 <500
- 入口瘦身后，下次加工具只需往对应层 register 里加，
  server.py 不再增长
- 下一步：构件修改能力（Tapir Modify* 系列）

---

## 2026-09-26 V1.4：构件修改能力（墙/柱/门/窗）

### 目标
建模后能用对话调整已有构件：改墙长/高、挪柱子、改门窗洞口。
与创建链路同构，走 预览→确认→执行→读回验证。

### 新增文件
- modify_plan.py（206 行）：修改计划校验。每项 {type, guid, 改什么}，
  GUID 锁定构件；字段白名单，未知字段/空修改直接拒
- modify_service.py（295 行）：调度。preview 读回当前值列 旧→新；
  execute 按类型分组调通道，改完 GetDetailsOfElements 逐字段比对
  （容差 0.01m）；记 operation 日志
- modify_tools.py（39 行）：preview_modify_plan / modify_from_plan
- server.py：加一层 register（62→63 行）

### 通道改动（channel_base / tapir_channel）
- tapir_channel 加 supports_modify / modify：
  ModifyWalls/ModifyColumns/ModifyDoors/ModifyWindows；
  返回解析 executionResults（success true/false）
- supports 的命令可用性查询抽成 _command_available，创建/修改共用缓存
- 基类新方法给安全默认（supports_modify=False、modify 抛
  NotImplementedError），旧 FakeChannel 测试不受影响

### 踩坑与修正（真机证据驱动）
1. details 返回项 id 是元素编号（"SW-001"）不是 GUID，
   最初拿它当键全部读空；改为按请求顺序 zip 对应
2. 官方包 e.elementId.guid 是 UUID 对象，拼 JSON 报不可序列化；
   读取时统一 str()
3. Tapir 坐标缺分量按 0 处理（mask 整个点）：计划强制
   墙端点 x/y 给全、柱 x/y 成对出现
4. 假 GUID 最初走 check_project_identity 报"项目变化"，误导；
   拆成两道校验：项目身份（空列表）+ 构件存在性预检，
   缺失时报"构件当前项目中不存在"

### 验证
- 真机 AC29：4 类混合一次提交
  墙高3→4、柱(80,80)→(81,81)、窗宽0.9→1.2、门高2.1→2.2，
  读回 4/4 matched；再全部改回 4/4
- 墙改端点 (86→90→86) 2/2；假 GUID 报直白错误
- 单测 228→265（新增 37：计划 21、通道拼装 10、服务 6）
- 仅修改值且已全部还原，无新增遗留构件

### 备注
- modify_service 295 行，后续加梁/板修改时注意行数
- 下一步可选：梁/板/屋顶修改（ModifyBeams/Slabs/Roofs 已有）、
  构件删除（Tapir 仍无）、或变形体深化

---

## 2026-09-26 V1.5：修改扩梁/板/屋顶 + 变形体任意形状

### 模块 A：梁/板/屋顶修改
- modify_plan.py：SUPPORTED_TYPES 加 Beam/Slab/Roof。梁字段
  start/end（点，x/y 给全）+ width/height（正）；板 level（绝对
  标高，可为负）+ thickness（正）；屋顶 thickness + eavesOverhang。
  起止点相同校验泛化到墙和梁；梁不开放相对楼层 level
- tapir_channel.py：_MODIFY_COMMAND 加三类
  （ModifyBeams/beamsWithDetails 等）；_build_modify_param 加分支，
  板 level 映射 zCoordinate
- modify_service.py：_current_values 加三类（梁 beg/endCoordinate
  +宽高，板 zCoordinate→level，屋顶 thickness/eavesOverhang）

### 模块 B：变形体任意形状（MorphBody）
- model_plan.py（→488 行，逼近上限）：_build_morph 改为 position +
  size/body 二选一。新增 _build_morph_body（vertices 3D 点 + faces
  ≥1 + solid 默认 false；实体需 ≥4 点 ≥4 面）、_morph_vertex、
  _morph_face（≥3 整数序号、不越界，拒绝 bool 索引）
- tapir_channel.py：新增 _build_morph_param，body 翻译成 Tapir
  {vertices, polygons:[{vertexIds}], bodyType:"Solid"/"Surface"}；
  size 方块路径保留。业务 faces/solid ↔ Tapir polygons/bodyType
- plan_preview.py：变形体明细兼容 body（列出点/面数、实体或曲面），
  不再写死取 size

### 真机验证（AC29）
- 梁端点 86→90→86、截面高 0.4→0.5→0.4：全 success
- 板绝对标高 0→0.1→0：success
- 多平面屋顶檐出 eavesOverhang：success
- 变形体四面体（4点4面）创建成功，details 31 字段
- 重要坑：板/屋顶 thickness 对**复合结构（Composite）**改不动
  （Tapir 返回 success:true 但值不变），读回验证如实报 failed；
  本项目默认收藏夹建出来的板/屋顶都是复合，故未测到简单结构 thickness
- 3 个已有屋顶均为单坡，ModifyRoofs 只支持多平面，故走新建多平面屋顶验证

### 过程插曲
- 存在性预检一度误判梁"不存在"，实为硬编码 GUID 时第 22 位抄错；
  改真机脚本动态取 GUID。同时把 _check_targets_exist 从依赖
  GetAllElements 改为直接读 details 判断（更直接），相关单测同步调整

### 测试
- 单测 265→**287**（新增 22）：modify_plan 梁/板/屋顶 7、
  tapir_channel 三类拼装 3、新建 test_morph_body 12（含
  size/body 互斥、索引越界、实体缺面、bool 索引、通道 body/方块）
- 全量 pytest tests/unit 287 全过

### 备注
- 真机新建的板/屋顶/四面体变形体在 (200~206,100~116) 区域，
  需用户回电脑 Ctrl+Z 撤销；梁板/屋顶修改值已全部还原
- model_plan 488 行，下次加内容前必须先拆

---

## 2026-09-26 新增工作区技能 archicad-real-verify

### 变更
- 新建 `.trae/skills/archicad-real-verify/SKILL.md`（项目级，非业务代码）
- 内容：真机验证标准流程——沙箱外执行 + discover、动态取 GUID、
  读回核对（容差0.01）、修改双向还原、临时脚本即建即删；
  details 的编号/GUID/大小写坑；模态弹窗按 Enter；
  复合结构厚度、多平面屋顶等真机已知行为；附验证脚本骨架
- 备注：纯沉淀既有经验，不改任何模块行为，无需单测/真机

---

## 2026-09-26 V1.6 还债：清理探查脚本 + 拆 model_plan

### 变更 1：清理项目根历史探查脚本
- 删除 21 个：`_probe_*`（13）、`_read_*`（3）、`_set_*`（2）、
  `_find_*`（1）、`_list_*`（1）
- 删除前全项目 grep 确认无任何 import 引用，均为独立一次性脚本

### 变更 2：拆 model_plan.py（488 → 139 行）
model_plan 只留计划骨架：PlanElement/ModelPlan、SUPPORTED_TYPES、
WALL_BASED、MAX_ELEMENTS、类型→校验函数注册表 _BUILDERS。
新增 4 个子模块（均 <500）：
- plan_values.py（71 行）：基础数值/坐标校验，COORD_LIMIT +
  number/coord_number/positive/non_negative/point/point3d
- plan_framing.py（82 行）：墙/柱/梁/板校验，本族默认值自带
- plan_openings.py（55 行）：门/窗校验，build_door/build_window
  统一签名，复用内部 _build_opening
- plan_special.py（196 行）：楼梯/屋顶/变形体 + 变形体 body 辅助；
  屋顶 slope/pivot 抽成 _roof_slope，变形体 size 抽成 _morph_size

### 依赖方向（无环）
plan_values ← plan_framing / plan_openings / plan_special ← model_plan。
默认值不再放 model_plan 共享，改由各族模块自带，消除循环依赖隐患。

### 验证
- 纯结构整理、无行为变化：报错文案/校验规则保持原样
- 全量 pytest tests/unit：**287 全过**
- import server：24 工具不变
- 对外保留可导入：ModelPlan、WALL_BASED、MAX_ELEMENTS

### 备注
- readme 项目结构与版本历史（V1.6）已同步
- 不涉及真机改动

---

## 2026-09-26 V1.7 构件删除

### 调研
- 列官方包 commands：无删构件命令（只有删属性/导航项）
- IsAddOnCommandAvailable 探测：Tapir **DeleteElements 可用**
- 入参（传空/假 GUID 摸清）：`{"elements":[{"elementId":{"guid":...}}]}`，
  空列表成功；返回整批一个 `{"success":bool}`；不存在 GUID 报
  success:false + "Failed to delete elements."

### 新增 3 个模块（均 <500）
- delete_plan.py（64 行）：guids 列表校验，非空、字符串、≤200、去重保序
- delete_service.py（约 220 行）：preview 读 type/id 列清单+风险；
  execute 经 confirm、项目身份、构件存在性、能力四道闸门，
  _delete_until_gone 删后读回、没删掉重试（MAX_DELETE_ATTEMPTS=3）
- delete_tools.py（37 行）：preview_delete_plan / delete_from_plan
通道改动：
- channel_base.py：加 supports_delete / delete 默认方法
- tapir_channel.py：supports_delete 探测 DeleteElements；
  delete 拼 elements、解析整批 success → CreateResult
- server.py：注册 delete_tools，工具 24 → 26

### 排错（本次主要耗时）
现象反复：删除有时报成功却"没删掉"。逐层排查后定位根因——
**构件删除后 Tapir 仍返回一项 `{"type","id","details":{}}` 的空占位**。
最初 _read_rows 存整项、用"项非空"判存在 → 误判没删；
实际构件第一次删除就已消失（独立按 details 读取确认）。
修复：新增 _present(row) = bool(row and row.get("details"))，
preview/存在预检/重试停止/验证四处统一改用它。
（modify_service 早就只取 details，未踩此坑）

### 验证
- 新增单测：test_delete_plan（10）、test_tapir_channel_delete（5）、
  test_delete_service（9，含重试成功/部分/失败/能力闸门）
- 全量 pytest tests/unit：**310 全过**
- 真机 AC29：单根、批量2根均 attempts=1、verify success、确认消失；
  本次所建测试构件全部删净，无遗留
- 已把该坑补进 .trae/skills/archicad-real-verify，并更新"无删除命令"旧说法

### 备注
- readme 工具分层/结构/版本历史（V1.7）已同步
- 命令在 ArchiCAD 里仍可 Ctrl+Z（删除本身可撤销）

---

## 2026-09-27 V1.8 板/屋顶开洞（holes）

### 调研（真机探测，探测后已清理）
| 能力 | 结果 |
|---|---|
| CreateSlabs + holes | ✅ 真生效（读回 details.holes 有内容） |
| ModifySlabs + holes | ✅ 真生效（既有板加洞成功，全量替换语义） |
| CreateRoofs 单坡 + holes | ✅ 真生效 |
| CreateRoofs 多平面 + holes | ❌ 静默忽略（返回 success 但 holes 为空） |
| ModifyRoofs + holes | ❌ 报 "No roof fields to modify." |
| CreateSkylights | ❌ 命令不存在（Tapir 1.5.9） |

注意坑：Tapir 读回的洞多边形会自动闭合（末点=首点）且起点可能轮换，
比对时必须去闭合点 + 按顶点集合匹配，不能逐点按下标比。

### 实现范围
- 板：创建 + 修改都支持 holes
- 单坡屋顶：仅创建时支持 holes
- 多平面屋顶：给 holes 直接报错（防静默忽略）
- 屋顶修改：不支持 holes（ModifyRoofs 限制）

### 变更模块
- plan_values.py：新增 hole_polygons（≥3 顶点闭合多边形校验）
- plan_framing.py：build_slab 加可选 holes
- plan_special.py：build_roof 加 holes（仅 slope 存在时；
  多平面给 holes 报错）
- tapir_channel.py：_build_param Slab/Roof 翻译 holes →
  [{"polygonCoordinates":...}]；_build_modify_param Slab 加 holes
- modify_plan.py：FIELD_RULES Slab 加 "holes"；新增 _hole_polygons
- modify_service.py：_current_values Slab 读 holes；新增 _read_holes
  （去闭合点）、_match_holes（数量+顶点集合容差匹配）、_same_polygon
- plan_preview.py：板/屋顶明细显示"开 N 个洞"；risk 提示多平面屋顶
  不支持开洞
- write_tools.py / modify_tools.py：docstring 补 holes 示例与限制

### 测试
- 新增 tests/unit/test_slab_holes.py（24 个）：plan_values 4、
  build_slab 3、build_roof 2、modify_plan 4、tapir_channel 6、
  modify_service 比对 5
- 全量 pytest tests/unit：**334 全过（310+24）**
- 真机 AC29：
  1. 创建带 1 洞板 → verify success，读回 holes 正确 ✓
  2. 创建带 1 洞单坡屋顶（30°）→ verify success，读回正确 ✓
  3. ModifySlabs 给既有板加第 2 个洞 → verify success，
     读回 2 洞（顶点轮换也匹配）✓
  4. 多平面屋顶 + holes → InvalidArgumentError 拦截 ✓
- 测试构件（x=200~214 区域）已用 DeleteElements 全部删净，无遗留

### 备注
- 修改 holes 是全量替换语义：传新列表会替换旧洞，不是追加
- readme 工具分层/结构/版本历史（V1.8）已同步

---

## 2026-09-27 V1.9 L 形楼梯（多段基线）

### 调研（真机探测）
- CreateStairs 的 baseLinePoints 支持 ≥2 点：2 点=直梯、3 点=L 形、
  4 点=U 形/多段，均一次创建成功
- 楼梯详情 Tapir 1.5.9 不支持读取（GetDetailsOfElements 返回 error），
  存在性验证以 GetElementsByType("Stair") 数量+GUID 为准

### 实现
- plan_special.py build_stair：新增 path 字段（≥2 点列表，连续点不可重复），
  给 path 时忽略 start/end；不给 path 时沿用 start/end（向后兼容）
- tapir_channel.py _build_param Stair：baseLinePoints 从 path 取
- plan_preview.py：楼梯描述改为"path 首点→末点，N 段基线长 Xm"
- write_tools.py：docstring 补 path 用法示例

### 测试
- 新增 tests/unit/test_l_stair.py（8 个）：path 校验 4、
  start/end 兼容 1、tapir 参数拼装 1、预览 2
- 全量 pytest tests/unit：**342 全过（334+8）**
- 真机 AC29：L 形楼梯（200,200→204,200→204,203）创建成功，
  楼梯数 4→5→4（删除后恢复），无遗留

### 备注
- 此前创建的 L 形楼梯测试构件已在调研阶段删除，无遗留
- readme 版本历史（V1.9）已同步


## 2026-09-27 V1.10 计划辅助：lint_model_plan（P2 识图起点）

### 定位
- 图片识别由 LLM 客户端视觉能力完成，server 端不做识图；
  提供离线校验工具 + readme 工作流指引，供识图生成计划后自检
- 不做 MCP prompt（各客户端支持不一），流程写进 readme

### 实现
- 新增 plan_tools.py：lint_model_plan 离线校验，复用
  ModelPlan.from_dict 完整校验链，不连接 ArchiCAD，
  返回 ok + 各类型构件计数；工具总数 26→27
- server.py：import plan_tools 并注册（第五层）
- readme.md：工具分层加"计划辅助（V1.10）"、项目结构加 plan_tools.py、
  新增「图片识别 → 建模计划（P2 工作流）」节
  （标定比例→定原点→按序提取→lint 自检→预览确认，含常见坑）

### 测试
- 新增 tests/unit/test_plan_tools.py（6 个）：lint 通过/坏计划/
  空计划/坏墙引用/多平面 holes 拦截/L 梯通过
- 全量 pytest tests/unit：**348 全过（342+6）**

### 备注
- success_result 只收 instance/project/count/items/data 五个参数，
  自定义键（如 ok）必须放 data，否则 TypeError 被 _safe 包成 error



