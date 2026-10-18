# 筑联（ArchiBridge）开发计划

> 配套文档：[archibridge_research.md](archibridge_research.md)（调研报告与技术路线）
> 原则：代码资产 100% 复用 acmcp，只换壳与分发层；每阶段独立交付价值。

---

## 总路线图

| 阶段 | 名称 | 交付物 | 验收标准 |
|---|---|---|---|
| S0 | 包产品化 | PyPI 包 + uvx 一键启动 | 新用户 3 条命令跑通 |
| S1 | 自检向导 | `archibridge doctor` + 配置生成 | 无文档自助完成安装 |
| S2 | 桌面安装器 | Windows/macOS 安装包 | 双击安装→打开 ArchiCAD→可对话 |
| S3 | HTTP 网关 | Streamable HTTP 传输 + token 鉴权 | Dify/Coze 平台接入成功 |
| S4 | 生态扩展 | 模板/价格库自定义 + 插件机制 | 第三方用户贡献模板 |

---

## S0 包产品化（1–2 周）

**目标**：`uvx archibridge` 一条命令启动。

| # | 任务 | 说明 |
|---|---|---|
| 0.1 | 重组为 Python 包 | `src/archibridge/`（pyproject.toml，console_scripts 入口 `archibridge=archibridge.server:main`）；现有模块平移，行数规则不变 |
| 0.2 | pyproject 元数据 | name=archibridge、中文描述、关键词（archicad/bim/mcp）、License（MIT，与 Tapir 一致） |
| 0.3 | 启动横幅与品牌 | server 启动打印「筑联 ArchiBridge vX.Y」，输出到 stderr（协议通道规范） |
| 0.4 | 版本号迁移 | 版本历史并入 CHANGELOG.md；单一代码源 `__version__` |
| 0.5 | CI | GitHub Actions：pytest + 多平台构建 + PyPI 发布（tag 触发） |
| 0.6 | readme 品牌化 | 双名呈现（筑联 ArchiBridge），加 uvx 快速开始段 |

**验收**：干净虚拟机 `pip install archibridge`（或 `uvx archibridge`）→ 启动 → Claude Desktop 配置后可列工具。

## S1 自检向导（1 周）

**目标**：安装问题不出对话，`archibridge doctor` 解决 90% 排障。

| # | 任务 | 说明 |
|---|---|---|
| 1.1 | doctor 自检 | 检测：Python 版本→ArchiCAD 安装与版本→端口扫描→Tapir 是否加载→官方 API 连通性；输出体检报告+修复建议 |
| 1.2 | Tapir 引导 | 未检测到 Tapir 时给出对应版本下载链接与加载步骤（自动安装 .apx 在 S2 实现） |
| 1.3 | 客户端配置生成 | `archibridge install claude/cursor/trae` 自动写对应 MCP 配置（备份原文件） |
| 1.4 | MCP 内置诊断工具 | 现有 list_instances/健康检查工具补充「首次使用引导」返回体 |

**验收**：无 BIM 背景用户按 doctor 输出完成配置，全程不看文档。

## S2 桌面安装器（2–3 周）

**目标**：设计师/造价员双击即用。

| # | 任务 | 说明 |
|---|---|---|
| 2.1 | Windows 安装器（Inno Setup） | 捆绑嵌入式 Python + 依赖；写注册表；生成开始菜单「Archibridge 配置向导」 |
| 2.2 | Tapir 自动安装 | 向导内自动下载对应版本 .apx（AC26–29 映射表）并调用 Add-On 管理器加载或提示手动加载 |
| 2.3 | 客户端自动注册 | 安装完成时探测已装 MCP 客户端，一键写入配置 |
| 2.4 | macOS（dmg + 脚本） | 首先保证 Windows（用户主场景），macOS 用安装脚本过渡 |
| 2.5 | 自动更新 | 启动时检查 PyPI 新版本提示升级 |

**验收**：无 Python 环境的干净 Windows 机器，双击安装 → 打开 ArchiCAD → AI 对话可用。

## S3 HTTP 网关（2–4 周）

**目标**：任意 Agent 平台可接入，团队可共享一台「模型工作站」。

| # | 任务 | 说明 |
|---|---|---|
| 3.1 | Streamable HTTP 传输 | FastMCP 双传输（stdio/HTTP 共存），服务层零改动 |
| 3.2 | 鉴权 | token 校验中间件；多 token 管理（团队每人一 token，可撤销） |
| 3.3 | 操作审计 | 写入类操作全量日志（谁/何时/改了什么/结果），可回放 |
| 3.4 | 并发与队列 | 单实例命令排队（ArchiCAD 不支持并发写），多实例路由 |
| 3.5 | 平台接入文档 | Dify / Coze / 自建 Agent 接入示例 |

**验收**：Dify 工作流通过 HTTP 调 `estimate_project` 出概算表；两个 token 并发不互踩。

## S4 生态扩展（持续）

| # | 任务 | 说明 |
|---|---|---|
| 4.1 | 数据文件外置 | 算量模板/消耗量表/价格库 → 用户可编辑 JSON + `--data-dir` 加载 |
| 4.2 | 地区系数 | region → 人工/材料调整系数表 |
| 4.3 | 模板市场 | 社区模板仓库 + `archibridge template add <url>` |
| 4.4 | AC30 适配 | 兼容矩阵升级（跟随 Graphisoft 发版节奏） |

---

## 横切任务（贯穿各阶段）

| 任务 | 频率 |
|---|---|
| 真机验证（含 V0.33/34/36 欠账、Zone 排查） | 每阶段开始前清一次 |
| 单测保持 100% 通过、regression.py 全绿 | 每次提交 |
| debug_log / readme / CHANGELOG 同步 | 每次变更 |
| Graphisoft 官方动态跟踪（MCP/API 政策） | 每月 |

## 里程碑时间轴（建议）

```
第 1–2 周   S0 包产品化 → PyPI 首发
第 3 周     S1 自检向导 → doctor + install 命令
第 4–6 周   S2 桌面安装器 → Windows 安装包
第 7–10 周  S3 HTTP 网关 → 平台接入
之后        S4 生态扩展（持续迭代）
```

> 真机验证依赖 ArchiCAD 环境，各阶段任务排期时预留缓冲；AC 在线时段优先清真机验证欠账。

---

## 近期立即行动（S0 启动清单）

1. 建 `pyproject.toml`，包名 `archibridge`，入口 `archibridge.server:main`
2. 模块平移进 `src/archibridge/`，同步修 import 与测试路径
3. 启动横幅加品牌与版本号
4. GitHub Actions：测试+发布流水线
5. readme 加「快速开始（uvx）」段
