<div align="center">

# 筑元智联 ArchiLinkAI（ALAI）

AI 智能体与 ArchiCAD 之间的 MCP 桥梁。任何支持 MCP 的智能体（Claude Desktop、Cursor、Trae、Kimi、Codex、Dify、Coze 等）都能通过自然语言查询、建模、算量、估价 ArchiCAD 26–29 项目。

[![Python](https://img.shields.io/badge/python-3.10+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![ArchiCAD](https://img.shields.io/badge/ArchiCAD-26--29-orange?logo=archicad&logoColor=white)](https://graphisoft.com/)
[![MCP](https://img.shields.io/badge/MCP-Protocol-black?logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0iI2ZmZiIgZD0iTTEyIDJhMTAgMTAgMCAxIDAgMCAyMCAxMCAxMCAwIDAgMCAwLTIweiIvPjwvc3ZnPg==)](https://modelcontextprotocol.io/)
[![FastMCP](https://img.shields.io/badge/FastMCP-server-green)](https://github.com/jlowin/fastmcp)
[![Tapir](https://img.shields.io/badge/Tapir-Add--On-yellow)](https://github.com/ENZYME-APD/tapir-archicad-automation)
[![Tests](https://img.shields.io/badge/tests-537%20pass-brightgreen)](tests/)
[![Status](https://img.shields.io/badge/status-active-success)](#)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-lightgrey)](#)

[核心特性](#核心特性) · [快速开始](#快速开始) · [工具一览](#工具一览) · [配置](#客户端配置) · [版本历史](#版本历史) · [参考文档](#参考文档)

</div>

---

## 目录

- [核心特性](#核心特性)
- [架构](#架构)
- [快速开始](#快速开始)
  - [运行前提](#运行前提)
  - [安装](#安装)
  - [启动](#启动)
  - [AC28 + AC29 双版本并存](#ac28--ac29-双版本并存说明)
- [客户端配置](#客户端配置)
- [沙箱白名单](#沙箱白名单python-site-packages)
- [验证连接](#验证连接)
- [测试与基准](#测试与基准)
- [项目结构](#项目结构)
- [工具一览](#工具一览)
- [图片识别 → 建模计划](#图片识别--建模计划p2-工作流)
- [安全设计](#安全设计)
- [版本历史](#版本历史)
- [实机验证进度](#实机验证进度2026-09-23)
- [参考文档](#参考文档)

---

## 核心特性

| 能力 | 说明 |
|---|---|
| 🛠 **66 个 MCP 工具** | 覆盖只读查询、安全写入、修改、删除、计划辅助、诊断运维 |
| 🏗 **15 类构件建模** | 墙、柱、梁、板、门、窗、楼梯、屋顶、变形体、家具、灯具、网面、洞口、房间区域、机电管线 |
| 📊 **29 个算量模板** | 混凝土体积、墙体分层、幕墙、栏杆、门窗洞口面积、模板估算、外檐真石漆、砌体工程等 |
| 📋 **GB 50500 清单** | 自动映射清单编码、出标准清单报表（xlsx + 标题/项目信息/合计行） |
| 🔒 **四阶段写入** | Preview → Confirm → Execute → Verify，支持 Ctrl+Z 撤销 |
| 🆔 **项目身份强校验** | 写入前核对项目路径 + 元素 GUID，防止项目被切换导致误写 |
| 🧪 **537 单测全过** | 单元 + 集成 + AC26–29 兼容矩阵 + 一键回归脚本 |
| 🖥 **多版本多实例** | 同一套代码兼容 AC26–29，支持双实例并存（ac29-1 / ac28-1） |

---

## 架构

```mermaid
flowchart TB
    subgraph Client["MCP 客户端"]
        C[Claude Desktop / Cursor / Kimi / Trae / Codex / WorkBuddy]
    end
    subgraph Server["ArchiCAD MCP Server"]
        S[Python FastMCP<br/>66 工具]
    end
    subgraph AC["ArchiCAD 实例"]
        A1[AC29 + Tapir]
        A2[AC28 + Tapir]
    end
    C -->|stdio| S
    S -->|TCP 19723| A1
    S -->|TCP 19724| A2
    style C fill:#4a90e2,color:#fff
    style S fill:#7ed321,color:#fff
    style A1 fill:#f5a623,color:#fff
    style A2 fill:#f5a623,color:#fff
```

**技术栈**：Python ≥ 3.10 · FastMCP · 官方 `archicad` Python 包 · Tapir Add-On

---

## 快速开始

### 运行前提

1. **ArchiCAD 26–29** 已启动并打开项目（主目标 AC29 build 3000+）
2. 选项 → 工作环境 → 连接端口 已启用
3. **Python ≥ 3.10**
4. 对应版本的 **Tapir Add-On** 已加载
   - 下载：https://github.com/ENZYME-APD/tapir-archicad-automation
   - 通过 选项 → Add-On 管理器 → 添加 加载

### 安装

**方式一：从 PyPI 安装（推荐，发布后可用）**

```bash
pip install archilinkai
# 启动（archilinkai 命令）
archilinkai
# 或
python -m archilinkai
```

**方式二：从源码安装（当前开发态）**

```bash
pip install -e ".[dev]"
```

### 启动

三种启动方式等价：

```bash
archilinkai          # PyPI 安装后的命令入口（等价 archilinkai serve）
python -m archilinkai
python server.py     # 源码目录兼容壳（保留旧配置可用）
```

无 ArchiCAD 实例时 server 仍会启动并打印提示，工具调用时返回结构化错误（`NO_INSTANCE_AVAILABLE`，`retryable=true`），便于 LLM 引导排查。

### 环境自检与客户端配置

```bash
archilinkai doctor            # 六项环境自检：Python/依赖/实例/Tapir，逐项给修复建议
archilinkai install claude    # 自动写入 Claude Desktop 配置（先备份原文件）
archilinkai install cursor    # 写入 Cursor ~/.cursor/mcp.json
archilinkai install generic   # 打印通用 MCP JSON 片段，任意客户端手动粘贴
```

支持的客户端矩阵见 `src/archilinkai/data/clients.json`（Claude/Cursor/Cline/Witsy/Cherry Studio/Codex 等，可随版本扩充）。

### AC28 + AC29 双版本并存说明

本项目支持同时连接多个 ArchiCAD 大版本实例。装的是 AC28 和 AC29 时需注意：

- **Tapir Add-On 与大版本一一绑定**：AC29 的 Tapir 不适用于 AC28，反之亦然。必须分别下载 AC28 和 AC29 对应版本的 `.apx`，在各自 ArchiCAD 里通过 `选项 → Add-On 管理器 → 添加` 加载。
- **端口分配**：每个 ArchiCAD 实例占用 19723–19743 中的一个端口。先启动的实例占 19723，第二个占 19724，依此类推。建议先开 AC29 再开 AC28，便于按端口顺序识别。
- **实例 ID 规则**：MCP Server 启动时扫描全部端口，按 `ac + 主版本号 + 序号` 命名，例如 `ac29-1`、`ac28-1`。多实例并存时，所有工具调用须带 `instance` 参数指定目标（仅一个实例时可省略）。
- **客户端切换**：在 Kimi / Trae 里调用 `list_instances` 可看到当前所有实例；调 `project_summary` 等工具时传 `instance="ac29-1"` 或 `instance="ac28-1"`。

---

## 客户端配置

MCP Server 用 stdio 通信，主流客户端配置如下。`server.py` 路径换成你的绝对路径（Windows 用正斜杠或双反斜杠）。

<details>
<summary><b>Claude Desktop / Cursor</b></summary>

配置文件位置：
- Claude Desktop：`%APPDATA%\Claude\claude_desktop_config.json`
- Cursor：设置 → MCP → 新增

```json
{
  "mcpServers": {
    "archicad": {
      "command": "python",
      "args": ["E:/works/Aidev/kbitai绝对安全/kbitai_com_cn/aitools/acmcp/archilinkai/server.py"]
    }
  }
}
```
</details>

<details>
<summary><b>Kimi（Kimi-Desktop / Kimi AI 助手）</b></summary>

Kimi 桌面端支持 MCP，在设置 → MCP 服务器中添加，或编辑配置文件：

```json
{
  "mcpServers": {
    "archicad": {
      "command": "python",
      "args": ["E:/works/Aidev/kbitai绝对安全/kbitai_com_cn/aitools/acmcp/archilinkai/server.py"]
    }
  }
}
```
</details>

<details>
<summary><b>Trae（Trae CN / Trae IDE）</b></summary>

Trae 在 `设置 → MCP → 添加 MCP Server` 中以表单填写，或直接编辑 `.trae/mcp.json`。项目内已用 Trae 内置变量 `${workspaceFolder}`（启动时自动替换为本机项目根目录），同一份配置 Windows / Mac 通用：

```json
{
  "mcpServers": {
    "archicad": {
      "command": "python",
      "args": ["${workspaceFolder}/archilinkai/server.py"]
    }
  }
}
```

Mac 上若提示找不到 `python`，把 `"python"` 改成 `"python3"`（或 Python 完整路径）即可。
</details>

<details>
<summary><b>Codex CLI（OpenAI）</b></summary>

Codex 用 **TOML** 配置（不是 JSON），文件：`C:\Users\<用户名>\.codex\config.toml`。在文件末尾追加：

```toml
[mcp_servers.archicad]
command = "C:/Python314/python.exe"
args = ["E:/works/Aidev/kbitai绝对安全/kbitai_com_cn/aitools/acmcp/archilinkai/server.py"]
```

验证：`codex mcp list`（若 `codex` 不在 PATH，用实际安装路径的 codex.exe），看到 archicad 状态 `enabled` 即可。本项目已配置完成。
</details>

<details>
<summary><b>WorkBuddy（腾讯）</b></summary>

WorkBuddy 桌面版读取的用户级配置：`C:\Users\<用户名>\.workbuddy\mcp.json`（注意是 `.workbuddy` 文件夹里、不带点前缀的 `mcp.json`）。

```json
{
  "mcpServers": {
    "archicad": {
      "type": "stdio",
      "command": "C:/Python314/python.exe",
      "args": [
        "E:/works/Aidev/kbitai绝对安全/kbitai_com_cn/aitools/acmcp/archilinkai/server.py"
      ]
    }
  }
}
```

**保存后必须手动信任**：打开 WorkBuddy → 连接器管理 → 右上角"自定义连接器" → 找到 archicad → 点"信任"。之后改动 command/args 需重新信任。本项目配置文件已创建，信任步骤需本人操作。
</details>

### ⚠️ 重要：本地 server 限制

本 server 在本机运行、连本机 ArchiCAD，因此：

- **本地客户端可用**：Codex CLI、WorkBuddy 桌面版、TRAE Work/Trae 桌面版
- **纯云端环境连不到本机**：TRAE Work 网页版、WorkBuddy 云端智能体/手机端（WorkBuddy 手机远程指挥时，需电脑桌面端开着做桥接）

---

## 沙箱白名单（Python site-packages）

Trae CN 自带沙箱会拦截对 `C:\Python314\Lib\site-packages` 的写操作，导致跑 `pytest` 时报 `hit restricted`，必须 `dangerouslyDisableSandbox=true` 才能跑。沙箱配置按会话 ID 管理，重启 IDE 后会回到默认白名单（只放行 `docx` 子目录）。

仓库根提供了一键脚本 `enable_pypath_sandbox.ps1`，每次重启 Trae CN 后双击执行即可把 `C:\Python314\Lib\site-packages` 重新注入当前会话的沙箱白名单。脚本是幂等的，已存在会跳过。

```powershell
powershell -ExecutionPolicy Bypass -File .\enable_pypath_sandbox.ps1
```

若以后装了新 Python 版本（如 3.15），把脚本里 `$PySitePackages` 参数改成对应路径再跑：

```powershell
powershell -ExecutionPolicy Bypass -File .\enable_pypath_sandbox.ps1 `
  -PySitePackages "C:\Python315\Lib\site-packages"
```

---

## 验证连接

1. 启动 ArchiCAD 28 / 29 并打开项目，确认 Tapir Add-On 已加载
2. 在客户端里让模型调用 `list_instances`，应返回两个实例
3. 调 `project_summary` 传 `instance="ac29-1"` 看元素总数
4. 已实测：Trae 桌面端自然语言调用成功（2 实例 / 12 墙）

---

## 测试与基准

### 跑测试（在项目根目录）

```powershell
python -m pytest tests/unit/           # 单元测试，无需真机
python -m pytest tests/integration/    # 集成测试，需开 ArchiCAD
python -m pytest tests/compatibility/  # AC 版本兼容矩阵，需真机
python regression.py                   # 一键回归（单测+集成+兼容+基准），--json 存报告
```

无真机时集成/兼容性测试会自动跳过。当前结果（AC28+AC29 真机）：

| 测试类型 | 通过 | 跳过 | 失败 |
|---|---|---|---|
| 单元测试 | 537 | 0 | 0 |
| 集成测试 | 25 | 2 | 0 |
| 兼容性测试 | 12 | 1 | 0 |

### 性能基准

测常用只读命令多次调用的平均/最小/最大耗时（毫秒）：

```powershell
python benchmark.py --instance ac29-1 --rounds 3
```

结果自动存为 `benchmark_results.json` 和 `benchmark_results.md`。真机实测：轻命令 <1–15ms，批量读取（全部元素/属性名/分类）50–70ms，均在百毫秒级，适合对话式调用。

---

## 项目结构

```
archilinkai/
├── server.py              # FastMCP 入口：异常包装 + 四层工具注册
├── read_tools.py          # P0 只读工具注册（35 个，从 server.py 拆出）
├── write_tools.py         # P1 安全写入工具注册（16 个，从 server.py 拆出）
├── modify_tools.py        # 构件修改工具注册（2 个，V0.4）
├── delete_tools.py        # 构件删除工具注册（2 个，V0.7）
├── plan_tools.py          # 计划辅助工具注册（1 个，V0.10）
├── diagnostic_tools.py    # P2 诊断工具注册（4 个，从 server.py 拆出）
├── instance_manager.py    # ArchiCAD 实例发现/连接/重连/健康检查
├── tapir_adapter.py       # Tapir 命令统一封装
├── channel_base.py        # 建模通道抽象基类（可插拔通道）
├── tapir_channel.py       # 通道实现：Tapir（15类创建 + 7类修改 + 删除 + 存在性查询）
├── model_plan.py          # 建模计划：数据结构 + 类型注册表（15 类构件）
├── plan_values.py         # 计划基础数值/坐标校验（含 3D 点、3D 洞）
├── plan_framing.py        # 计划校验：墙/柱/梁/板
├── plan_openings.py       # 计划校验：门/窗
├── plan_special.py        # 计划校验：楼梯/屋顶/变形体/网面/洞口/区域/机电管线
├── modify_plan.py         # 构件修改计划：数据结构 + 校验（V0.4）
├── delete_plan.py         # 构件删除计划：GUID 列表校验（V0.7）
├── plan_preview.py        # 建模计划预览（人能看懂的明细）
├── create_service.py      # 建模计划调度：能力闸门/创建/验证
├── modify_service.py      # 修改调度：读当前值/修改/逐字段验证（V0.4）
├── delete_service.py      # 删除调度：预检/删除/details 读回确认（V0.7）
├── query_engine.py        # BIM 条件查询引擎（含分页）
├── property_service.py    # Property 读取/写入与类型校验
├── aggregate_service.py   # 工程量分组汇总（V0.16）
├── code_table.py          # GB 50500 构件类型→清单编码映射（V0.26）
├── report_service.py      # 工程量清单报表排版（V0.26）
├── formula_eval.py        # 算量规则公式安全求值（V0.25）
├── geometry_service.py    # 几何规整：长度/起止点/高程/包围盒
├── benchmark.py           # 性能基准：命令耗时统计（avg/min/max）
├── regression.py          # 一键回归：单测+集成+兼容+基准，汇总报告
├── gdl_service.py         # GDL 参数读写（从 server.py 拆出）
├── operation_service.py   # Preview / Confirm / Execute / Verify 四阶段
├── audit_log.py           # 操作日志（Operation ID）
├── schemas.py             # 输入/输出数据结构
├── errors.py              # 统一异常与错误码
├── requirements.txt
├── debug_log.md           # 变更日志（已满，续记见下）
├── debug_log_2.md         # 变更日志续篇（已满，2026-09-24 起）
├── debug_log_3.md         # 变更日志续篇三（2026-09-27 起）
├── benchmark_results.md   # 性能基准结果（跑 benchmark 自动生成）
├── benchmark_results.json
└── tests/
    ├── unit/              # 单元测试
    ├── integration/       # 集成测试（需真机）
    └── compatibility/     # AC26–29 兼容性测试矩阵
```

---

## 工具一览

### P0 只读工具（35 个）

| 工具 | 说明 |
|---|---|
| `list_instances` | 列出所有 ArchiCAD 实例 |
| `project_summary` | 项目概览（元素数/属性数/楼层） |
| `get_selected_elements` | 获取当前选中元素 |
| `get_elements_by_type` | 按类型取元素 |
| `get_element_properties` | 读元素属性（含 UserDefined） |
| `search_elements_by_criteria` | 条件查询元素 |
| `get_element_geometry_info` | 几何信息（长度/起止点/高程/包围盒） |
| `get_classifications` | 系统分类树 |
| `list_floors` | 楼层列表 |
| `get_gdl_parameters` | GDL 参数读写 |
| `get_element_quantities` | 工程量读取（毛/净体积、表面积、长度等，带单位） |
| `aggregate_quantities` | 按 type/story/属性分组汇总（count/sum/avg，支持分类过滤和 formula 公式） |
| `get_property_definition` | 属性类型/单位/枚举可选项（报错带相近名建议） |
| `list_quantity_templates` | 列出 23 个预设算量模板 |
| `aggregate_by_template` | 按模板名一键算量（含 with_code 时附 GB 50500 清单编码） |
| `aggregate_by_custom_template` | 传 JSON 自定义模板（支持 formula 公式和 with_code） |
| `list_attributes` | 按类型列项目属性（Layer/Pen/BuildingMaterial/Composite 等，Tapir GetAttributes） |
| `list_library_parts` | 列出项目可用库部件（可选 type_id 过滤：Door/Window/Object/Lamp），返回 guid/documentName/fileName/typeId |
| `get_subelements_of_hierarchical` | 取层级构件子构件（幕墙拆框架/面板/分隔条，楼梯拆踏板/踢板/结构） |
| `export_table` | 导出 CSV/Excel/工程量清单报表（支持多表、fmt=report 出 GB 50500 格式） |
| `get_collisions` | 检测两组元素碰撞（含体积/表面碰撞） |
| `list_favorites` | 按类型列收藏夹（如 Wall 的 17 个收藏夹） |
| `get_ifc_ids` | 取元素的 IFC ID |
| `get_elements_by_ifc_ids` | 用 IFC ID 反查元素 |
| `get_ifc_properties` | 读元素 IFC 属性集 |
| `get_zone_boundaries` | 读 Zone 边界（关联元素/相邻 Zone） |
| `get_connected_elements` | 查宿主元素上挂的子元素（墙→门窗、幕墙→框架等） |
| `get_element_preview_image` | 取元素预览图（2D/Section/3D，返回 base64） |
| `get_building_material_properties` | 读建筑材料物理性能 |
| `get_layer_combination_details` | 读图层组合详情（每层显隐/锁定/线框/交叉组） |
| `list_stories` | 列楼层：索引、标高、楼层名 |
| `get_gdl_parameters` | 读元素 GDL 参数（配合写入前读值） |
| `list_mep_elements` | 列全部 MEP 元素（可选类型/专业过滤） |
| `get_mep_routing_elements` | 读 MEP 管线详情（普通接口看不到的用这个） |
| `get_mep_ports` | 读 MEP 元素端口（位置/形状/尺寸/连接，AC28+） |
| `get_element_relations` | 读元素关系（宿主/连接等） |
| `list_all_properties` | 列全部属性定义+属性组（算量属性名排查） |
| `get_calculation_units` | 读项目计算单位与精度 |
| `get_navigator_tree` | 读导航树（楼层/视图/图册/发布集） |
| `estimate_cost` | 成本估算细算：算量结果 → 人材机分解 → 取费 → 总价（含覆盖率） |
| `estimate_project` | 一键全链路：模板算量 → 细算 → 可选导出概算 xlsx（同编码自动去重防双算） |

### P1 安全写入工具（16 个）

| 工具 | 说明 |
|---|---|
| `preview_property_change` | 预览属性变更（不写入） |
| `set_element_properties` | 设置元素属性（需 confirm=true） |
| `preview_classification` | 预览分类挂接 |
| `attach_classification` | 挂接分类（可撤销） |
| `set_gdl_parameters` | 设置 GDL 参数 |
| `highlight_elements` | 高亮元素 |
| `preview_model_plan` | 预览建模计划 |
| `create_from_plan` | 执行建模计划（需 confirm=true） |
| `create_layers` | 创建/覆盖图层（需 confirm=true） |
| `delete_attributes` | 删除属性（需 confirm=true） |
| `apply_favorites` | 应用收藏夹到已有元素（需 confirm=true） |
| `set_element_details` | 改元素楼层/图层/绘制顺序（需 confirm=true） |
| `update_zones` | 更新所有 Zone 几何与印章（需 confirm=true） |
| `move_elements` | 按向量批量移动元素（需 confirm=true） |
| `rotate_elements` | 绕参考点批量旋转元素（需 confirm=true） |
| `create_layer_combinations` | 创建/覆盖图层组合（需 confirm=true） |

### 构件修改 / 删除 / 计划辅助（5 个）

| 工具 | 说明 |
|---|---|
| `preview_modify_plan` | 预览修改计划（V0.4） |
| `modify_from_plan` | 执行修改（V0.4） |
| `preview_delete_plan` | 预览删除（V0.7） |
| `delete_from_plan` | 执行删除（V0.7） |
| `lint_model_plan` | 离线校验建模计划（V0.10，不连 ArchiCAD） |

### P2 诊断运维（4 个）

| 工具 | 说明 |
|---|---|
| `refresh_instances` | 刷新实例列表 |
| `validate_instance` | 校验实例连接 |
| `get_operation_status` | 查操作状态 |
| `get_operation_log` | 查操作日志 |

> 工具总数：**66 个**

### 已支持建模构件（15 类）

墙 · 柱 · 梁 · 板 · 门 · 窗 · 楼梯 · 屋顶 · 变形体 · 对象（家具）· 灯具 · 网面 · 独立洞口 · 房间区域 · 机电管线（风管/水管/桥架）

### 只读可算量构件（Tapir 不支持创建）

幕墙（CurtainWall）· 栏杆（Railing）· 壳体（Shell）· 天窗（Skylight）——可查询、可取工程量、可分组汇总，但不能通过建模计划创建（Tapir 未实现对应 Create 命令）。

---

## 图片识别 → 建模计划（P2 工作流）

识图由 LLM 客户端完成（把平面图照片/截图发给 Claude/Kimi 等视觉模型），server 负责消化计划。标准流程：

1. **标定比例**：先问用户图上一个已知尺寸（如"这面墙 6 米"），建立像素→米换算；无已知尺寸时先用假设比例并在预览时声明
2. **定原点**：选平面图左下角或某个房间角点为 (0,0)，所有坐标转成相对原点的米制坐标
3. **按序提取**：先墙（起止点），再柱梁板，再门窗（wall 填墙序号），最后楼梯/屋顶/变形体。门窗必须落在某面墙上
4. **lint 自检**：调 `lint_model_plan` 离线校验，按报错修正，直到 ok=true。这步不连 ArchiCAD，可反复迭代
5. **预览确认**：调 `preview_model_plan` 给用户看明细，用户确认后调 `create_from_plan(confirm=true)` 执行

常见坑：坐标别用像素直接填（必须是米）；墙起止点顺序影响门窗 offset 方向；屋顶/板建在非当前楼层会假成功（level 填当前楼层标高）。

---

## 安全设计

- **写操作统一四阶段**：Preview → Confirm → Execute → Verify
- 写入默认 `confirm=false`，需明确 `confirm=true` 才执行
- **项目身份强校验**：discover/refresh 时记录项目文件路径基线；写入前重新核对路径 + 目标元素 GUID 是否仍存在，项目被关闭/另存为/切换时拦截（错误码 `PROJECT_IDENTITY_CHANGED`），调 `refresh_instances` 建立新基线后才能继续
- 写入走 archicad 原生 API（`SetPropertyValuesOfElements`，内部已包 ACAPI_CallUndoableCommand，Ctrl+Z 可撤销）；读操作走 Tapir 通道（Tapir 写命令的参数 schema 与原生不一致，实测会拒绝，见 debug_log.md）
- 构件修改（V0.4）：项目身份与构件存在性分开校验，构件已删除时报直白错误；改后用 GetDetailsOfElements 逐字段读回比对（容差 1 厘米）
- 所有写操作生成唯一 Operation ID 并记录日志

---

## 版本历史

完整版本历史已迁移至 [CHANGELOG.md](CHANGELOG.md)。里程碑摘要：

| 版本 | 里程碑 |
|---|---|
| 0.38 | 算量估价链路补强（warnings/覆盖率/概算 xlsx/一键 estimate_project） |
| 0.37 | 成本估算细算引擎（消耗量×市场价→人材机→取费） |
| 0.30-0.36 | Tapir 命令补全收官（属性/库部件/碰撞/IFC/图层组合/MEP/导航树） |
| 0.21-0.29 | 算量体系成型（29 模板、GB 50500 清单报表、多表 Excel） |
| 0.10-0.20 | 建模计划 15 类构件、工程量读取与汇总 |
| 0.1-0.3 | 架构奠基（四阶段写入、多实例、双版本真机验证） |

---

## 实机验证进度（2026-09-23）

以下全部在真机（AC29 build 5003 + AC28 build 6003 双实例）验证通过：

| 验证项 | 结果 |
|---|---|
| 实例发现（list_instances 双版本） | ✓ ac29-1 + ac28-1 |
| 项目概览（project_summary） | ✓ 8 元素 / 809 属性 |
| 按类型取元素（get_elements_by_type Wall） | ✓ 8 面墙 |
| 属性读取（get_element_properties） | ✓ 含 UserDefined 属性 |
| 预览（preview_property_change） | ✓ 不写入，before/target/risk |
| 确认门禁（confirm=false 拒绝） | ✓ CONFIRM_REQUIRED |
| 完整四阶段写入（confirm=true） | ✓ 8 墙耐火等级"1 小时"→"2小时"，verify 8/8 |
| Operation Log（OP-20260923-00001） | ✓ 自动生成 |
| MCP 协议传输层（stdio 客户端实测） | ✓ initialize / list_tools(20) / call_tool 全通 |
| 分类挂接（preview_classification / attach_classification） | ✓ 挂"标准墙"verify success，可撤销，OP-20260924-00001 |
| 完整几何（get_element_geometry_info） | ✓ 长度 14.15m / 高 3m / 厚 0.3m / 起止点 / 包围盒 |
| 项目身份强校验（check_project_identity） | ✓ 路径一致通过；篡改路径/假 GUID 均拦截 |

MCP 传输层验证方式：`_probe_mcp_client.py`（mcp SDK 客户端，stdio 启动 server.py 子进程，走 initialize → list_tools → call_tool 完整协议）。

剩余可选项：把本 server 接入真实 LLM 客户端（Claude Desktop / Kimi / Trae，配置见「客户端配置」节）。

---

## 参考文档

| 文档 | 链接 |
|---|---|
| ArchiCAD Python API | https://archicadapi.graphisoft.com/Documentation/api/ |
| archicad PyPI | https://pypi.org/project/archicad/ |
| MCP 协议规范 | https://modelcontextprotocol.io/ |
| Tapir Add-On | https://github.com/ENZYME-APD/tapir-archicad-automation |
| Tapir 命令文档 | https://enzyme-apd.github.io/tapir-archicad-automation/ |

---

<div align="center">

[⬆ 回到顶部](#archilinkai-server)

</div>
