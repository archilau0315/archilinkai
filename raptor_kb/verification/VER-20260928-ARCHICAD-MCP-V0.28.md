# 核验确认单 VER-20260928-ARCHICAD-MCP-V0.28

**核验对象**：ArchiCAD MCP Server V0.28 (FastMCP + Tapir Add-On)  
**核验人**：知识策展人 @curator  
**核验时间**：2026-09-28  
**核验编号**：VER-20260928-ARCHICAD-MCP-V0.28  
**来源路径**：`E:/works/Aidev/Kbitai绝对安全/kbitai_com_cn/aitools/acmcp/archicad-mcp/`  
**Git 提交**：待补充（需 `git log -1 --format="%H %s"`）

---

## 三级核验结论

| 核验项 | 结论 | 证据定位 | 风险提示 |
|--------|------|----------|----------|
| **来源溯源** | ✅ 通过 | 完整代码库 30+ 模块，README V0.28 标注，.operations.jsonl 记录演进 | 无 |
| **时效性确认** | ✅ 通过 | 文件修改时间 2026-09-27/28，V0.28 为最新版本标识 | 依赖 `archicad>=29.3000` SDK 需匹配 AC29 运行环境 |
| **交叉比对** | ⚠️ 部分通过 | 代码实现与技术实现官陈述一致（34工具/15构件/四阶段/GB50500/16模板）；**测试矩阵（462/25/12）需真机环境复核，本地不可跑** | 测试报告依赖 AC28+AC29 双实例真机，非本地可复现；集成/兼容测试有跳过项 |

---

## 核验明细

### 1. 34 个 MCP 工具清单（代码实测统计）

| 分层 | 模块 | 工具数 | 工具名（注册入口） |
|------|------|--------|-------------------|
| **P0 只读** | `read_tools.py` | **10** | `list_instances`、`project_summary`、`get_selected_elements`、`get_elements_by_type`、`get_element_properties`、`search_elements_by_criteria`、`get_gdl_parameters`、`list_floors`、`get_classifications`、`get_element_geometry_info`、`get_element_quantities`、`get_property_definition`、`aggregate_quantities`、`list_quantity_templates`、`aggregate_by_template`、`aggregate_by_custom_template`、`export_table` |
| **P1 写入** | `write_tools.py` | **8** | `preview_property_change`、`set_element_properties`、`set_gdl_parameters`、`preview_classification`、`attach_classification`、`highlight_elements`、`preview_model_plan`、`create_from_plan` |
| **修改** | `modify_tools.py` | **2** | `preview_modify_plan`、`modify_from_plan` |
| **删除** | `delete_tools.py` | **2** | `preview_delete_plan`、`delete_from_plan` |
| **计划** | `plan_tools.py` | **1** | `lint_model_plan` |
| **诊断** | `diagnostic_tools.py` | **4** | `refresh_instances`、`validate_instance`、`get_operation_status`、`get_operation_log` |
| **合计** | | **27** | 注：read_tools 实际注册 17 个（含算量链 7 个），技术实现官口径“10+7”合计 34 与代码一致 |

> **核验备注**：`read_tools.py` 注册 17 个工具（基础只读 10 + 算量链 7），`write_tools.py` 8 个，`modify_tools.py` 2 个，`delete_tools.py` 2 个，`plan_tools.py` 1 个，`diagnostic_tools.py` 4 个，**代码实测总计 34 个**，与陈述一致。

### 2. 15 类构件建模覆盖（`tapir_channel.py` `_COMMAND` 表 + `model_plan.py` `ModelPlan`）

| 序号 | 构件类型 | 英文标识 | 创建支持 | 修改支持 | 删除支持 | 备注 |
|------|----------|----------|----------|----------|----------|------|
| 1 | 墙 | Wall | ✅ | ✅ (端点/高/厚) | ✅ | 复合结构/图层组合/参数化构件 |
| 2 | 柱 | Column | ✅ | ✅ (平移/高/截面) | ✅ | |
| 3 | 梁 | Beam | ✅ | ✅ (平移/高/截面) | ✅ | |
| 4 | 板 | Slab | ✅ | ✅ (标高/厚/开洞) | ✅ | 支持 holes 多边形开洞 |
| 5 | 门 | Door | ✅ | ✅ (洞口/门槛) | ✅ | 仅直墙，挂墙索引或 GUID |
| 6 | 窗 | Window | ✅ | ✅ (洞口/窗台) | ✅ | 仅直墙 |
| 7 | 楼梯 | Stair | ✅ | ❌ | ✅ | 直梯/L型/多段 path |
| 8 | 屋顶 | Roof | ✅ | ✅ (厚/檐出) | ✅ | 单坡/多平面，holes 仅单坡 |
| 8 | 变形体 | Morph | ✅ | ❌ | ✅ | 方块基础形状 |
| 10 | 网面 | Mesh | ✅ | ❌ | ✅ | |
| 11 | 独立洞口 | Opening | ✅ | ❌ | ✅ | |
| 12 | 房间区域 | Zone | ✅ | ❌ | ✅ | |
| 13 | 机电管线 | MEPRoutingElement | ✅ | ❌ | ✅ | 风管/水管/桥架 |
| 14 | 对象 | Object | ✅ | ❌ | ✅ | GDL 对象放置 |
| 15 | 灯具 | Lamp | ✅ | ❌ | ✅ | GDL 灯具 |

> **核验备注**：`tapir_channel.py` 定义 15 类创建命令，`modify_service.py` 覆盖 6 类修改，`delete_service.py` 全类型删除。与“15 类构件建模”一致。

### 3. 四阶段安全写入协议（`operation_service.py`）

| 阶段 | 实现位置 | 关键动作 | 验证机制 |
|------|----------|----------|----------|
| **Preview** | `preview_property_change()` / `preview_classification_change()` | 读取 before 值、校验目标值、风险提示、不可改元素识别 | 抛异常拦截（类型不符/属性不存在/分类项未找到） |
| **Confirm** | 所有写入工具 `confirm: bool = False` 参数 | `confirm=false` 抛 `ConfirmRequiredError`，**绝不执行** | 强制显式确认，防误触 |
| **Execute** | `execute_property_change()` / `execute_classification_change()` | 调 Tapir 原生命令（`SetPropertyValuesOfElements` / `SetClassificationsOfElements`），Tapir 内部 `ACAPI_CallUndoableCommand` 可撤销 | 记录 `operation_id`、时间戳、实例/项目身份强校验 (`check_project_identity`) |
| **Verify** | `_verify_property_change()` / 执行后重读分类 | 重新读回，**逐元素核对 requested/executed/verified/failed**，状态 ∈ {success, partial_success, failed} | `VerifyResult` 结构化返回，写入 `audit_log.OperationLog` 审计日志 |

> **核验备注**：代码严格实现 Preview→Confirm→Execute→Verify 闭环，**项目身份强校验（文件路径+GUID）防写错项目**，Operation ID 全链路审计，符合生产级安全要求。

### 4. GB 50500 算量覆盖（`code_table.py` + `aggregate_service.py`）

| 维度 | 覆盖情况 | 证据 |
|------|----------|------|
| **清单编码映射** | 16 类构件 → 9 位编码/名称/单位 | `code_table.CODE_TABLE` 16 项（Wall/Column/Beam/Slab/Stair/Roof/Door/Window/CurtainWall/Zone/MEPRoutingElement/Morph/Opening/Railing/Shell/Skylight） |
| **预设模板** | 16 个模板 | `aggregate_service.QUANTITY_TEMPLATES`：concrete_volume/wall_area/wall_length/slab_area/door_count/zone_area/column_count/mep_length/wall_summary/wall_paint_area/wall_composite_layers/wall_insulation_area/wall_core_volume/curtain_wall_area 等 |
| **公式引擎** | 支持 `formula` 字符串表达式 | `formula_eval.eval_formula()`，如 `General_NetVolume * 1.03` |
| **损耗系数** | `waste_factor` 字段，自动生成 `sum_with_waste` | 模板/自定义模板均支持 |
| **多量合并** | `quantities: list[str]` 同时汇总多指标 | `wall_summary` 模板演示体积+面积+长度 |
| **分类筛选** | `classification` 参数按分类项过滤 | `_classification_guids()` 实现 |
| **清单报表导出** | `export_table fmt=report` 生成 GB 50500 格式 | `report_service.build_report()`，含标题/项目信息/表头/数据/合计 |

> **核验备注**：清单编码参考 GB 50500-2008，**16 类覆盖主流土建/装饰/机电**，模板 16 个含公式/损耗/多量/分层，**满足清单级算量出表需求**。

### 5. 测试矩阵（真机验证，本地不可复现）

| 测试层级 | 用例数 | 通过 | 跳过/失败 | 运行环境 | 核验状态 |
|----------|--------|------|-----------|----------|----------|
| 单元测试 | 462 | 462 | 0 | AC28 + AC29 双实例 | 🟡 **需真机复核**（本地缺 archicad SDK） |
| 集成测试 | 25 | 23 | 2 跳过 | AC28 + AC29 双实例 | 🟡 **需真机复核** |
| 兼容性测试 | 12 | 11 | 1 跳过 | AC26/27/28/29 矩阵 | 🟡 **需真机复核** |

> **核验备注**：测试依赖 `archicad` Python 包（Graphisoft Tapir SDK）、**仅在安装了 ArchiCAD + Tapir Add-On 的真机上可运行**。本地环境无法装载，核验仅确认测试文件存在（23 个 unit / 2 个 integration / 1 个 compatibility），**结论以真机报告为准**。

---

## 引用清单（含编号）

| 编号 | 来源文件 | 关键内容 | 核验状态 |
|------|----------|----------|----------|
| REF-001 | `server.py:48-53` | 6 大工具模块注册入口 | ✅ |
| REF-002 | `read_tools.py:26-382` | 17 个只读工具实现 | ✅ |
| REF-003 | `write_tools.py:24-205` | 8 个写入工具实现 | ✅ |
| REF-004 | `modify_tools.py:18-43` | 2 个修改工具实现 | ✅ |
| REF-005 | `delete_tools.py:18-36` | 2 个删除工具实现 | ✅ |
| REF-006 | `plan_tools.py:20-34` | 1 个计划校验工具 | ✅ |
| REF-007 | `diagnostic_tools.py:21-61` | 4 个诊断工具实现 | ✅ |
| REF-008 | `tapir_channel.py:17-200` | 15 类构件创建命令表 | ✅ |
| REF-009 | `operation_service.py:27-398` | 四阶段写入服务完整实现 | ✅ |
| REF-010 | `code_table.py:15-32` | GB 50500 16 项清单编码表 | ✅ |
| REF-011 | `aggregate_service.py:44-146` | 16 个预设算量模板 | ✅ |
| REF-012 | `tests/unit/*.py` (23 文件) | 单测用例集合 | 🟡 待真机 |
| REF-013 | `tests/integration/*.py` (2 文件) | 集成测试用例 | 🟡 待真机 |
| REF-014 | `tests/compatibility/*.py` (1 文件) | 兼容性测试用例 | 🟡 待真机 |

---

## 风险提示单

| 编号 | 风险等级 | 描述 | 影响范围 | 缓解建议 |
|------|----------|------|----------|----------|
| RISK-001 | 🔴 高 | **`archicad` SDK 仅在 ArchiCAD 安装环境可用**，本地/CI 无法跑测试 | 所有集成/回归验证 | 建立专用真机验证机（AC28+AC29），配置定时回归 |
| RISK-002 | 🟡 中 | Tapir 通道版本差异：AC28 不支持 `GetElementsByType('All')`、`GetStories` 返回格式差异 | 多版本兼容 | `read_tools.py:86-90` 已有兜底，持续维护兼容层 |
| RISK-003 | 🟡 中 | 屋顶开洞仅支持单坡屋顶创建时，多平面/既有屋顶不支持 | 修改服务 | 文档已标注（`modify_tools.py:31`），使用时规避 |
| RISK-004 | 🟢 低 | `door_count` 模板用 `General_3DLength` 计数，语义不精确 | 门窗计数报表 | 建议改用 `count` 聚合或自定义属性计数 |
| RISK-005 | 🟢 低 | `CurtainWall` 无体积属性，仅面积模板 | 幕墙算量 | 已有 `curtain_wall_area` 模板覆盖面积，体积需人工补 |

---

## 后续动作建议

1. **即刻可做**：基于 REF-001~011 封装 `archicad-mcp` Hermes Skill（工具注册、工作流模板、配置模板）
2. **真机验证**：安排 AC28/AC29 双实例跑全量测试矩阵，更新测试报告时间戳
3. **知识入库**：生成标准化知识卡片挂载至 `E:/啄之堂知识库/02_结构化知识库/BIM/ArchiCAD-MCP/`，建立与 `bim_engineer` skill 双向链接
4. **Orchestrator 接入**：BIM Engineer 数字员工绑定技能原子操作（算量、建模计划、识图生成计划）

---

**核验确认单生成时间**：2026-09-28  
**下次复核触发**：版本升级（V0.29+）、Tapir SDK 升级、ArchiCAD 大版本发布、GB 50500 规范修订