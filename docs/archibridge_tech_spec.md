# 筑联（ArchiBridge）技术开发文档

> 产品定位与技术实现蓝图。配套：[调研报告](archibridge_research.md) · [阶段计划](archibridge_plan.md)
> 基线：V0.38（66 工具 / 29 算量模板 / 537 单测 / AC26–29 兼容）· 2026-10-18

---

## 1. 产品定位（结论）

**形态**：本地桥梁服务（无头常驻）+ AC 侧通道插件（Tapir→自研）+ 分发壳（安装器）。

```
AI 智能体（Trae/Claude/Cursor，智能层，不做）
      ↕ MCP（stdio / Streamable HTTP）
筑联 ArchiBridge 桥梁服务（产品主体）
      ↕ TCP 19723+ / 官方 Python API
ArchiCAD 26–30 + Tapir Add-On（通道层）
```

**与 Trae 等产品的三层结合**：

| 层级 | 形态 | 实现阶段 |
|---|---|---|
| 协议层 | MCP 配置接入，AI 直接获得全部工具 | S0（已具备能力） |
| 场景层 | 工作流封装为自定义智能体/技能（如「造价助手」） | S1 附带模板 |
| 平台层 | HTTP+token，团队/云 Agent 接入 | S3 |

**不做的事**：不做 GUI 重应用；不做 AC 内嵌 AI 面板（远期可选）；不自研 LLM。

---

## 2. 现状基线（S0 迁移对象）

```
archicad-mcp/
├── server.py              # FastMCP 入口 + _safe 包装 + 6 层工具注册
├── *.py                   # 37 个业务模块（平铺，顶层 import）
│   ├── 工具层   read_tools write_tools modify_tools delete_tools plan_tools diagnostic_tools
│   ├── 服务层   aggregate_service report_service cost_estimator estimate_schema
│   │           query_engine property_service operation_service create_service
│   │           modify_service delete_service gdl_service geometry_service quota_matcher
│   ├── 通道层   tapir_adapter tapir_channel channel_base instance_manager
│   ├── 计划层   model_plan plan_values plan_framing plan_openings plan_preview
│   │           plan_special modify_plan delete_plan plan_tools
│   ├── 基础层   errors schemas audit_log formula_eval code_table
├── regression.py benchmark.py    # 开发工具脚本（不进发行包）
├── tests/{unit,integration,compatibility}/   # 537 用例
└── readme.md debug_log_4.md
```

- 模块间为平铺 import：`import aggregate_service` / `from errors import X`
- 延迟导入存在（函数内 `from cost_estimator import ...`），替换需全文件扫描
- tests 用 `monkeypatch.setattr(aggregate_service.property_service, ...)`，依赖模块单例

---

## 3. S0 包产品化技术方案

### 3.1 目标目录结构

```
archicad-mcp/
├── pyproject.toml              # 新增：包定义 + 元数据 + 入口
├── CHANGELOG.md                # 新增：版本历史迁移
├── server.py                   # 保留：薄壳（兼容现有 `python server.py` 配置）
├── regression.py benchmark.py  # 保留原位（开发脚本）
├── src/archibridge/
│   ├── __init__.py             # __version__ = "0.38.0" 单源
│   ├── __main__.py             # python -m archibridge 支持
│   ├── server.py               # main() 入口 + mcp 实例 + 注册逻辑
│   └── *.py                    # 37 模块平移（git mv 保留历史）
├── tests/                      # 原位不动，仅改 import
└── .github/workflows/ci.yml    # 新增：测试+发布
```

### 3.2 pyproject.toml（完整）

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "archibridge"
version = "0.38.0"                 # 与 src/archibridge/__init__.py 同步（CI 校验）
description = "筑联 ArchiBridge：AI 智能体与 ArchiCAD 之间的 MCP 桥梁（查询/建模/算量/估价/报表）"
readme = "readme.md"
requires-python = ">=3.10"
license = { text = "MIT" }
keywords = ["archicad", "bim", "mcp", "ai", "quantity-takeoff", "estimate"]
classifiers = [
    "Programming Language :: Python :: 3.10",
    "Operating System :: Microsoft :: Windows",
    "Operating System :: MacOS",
    "Topic :: Scientific/Engineering :: CAD",
]
dependencies = [
    "mcp>=1.0",
    "archicad>=27.0.0",
    "openpyxl>=3.1",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
archibridge = "archibridge.server:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
archibridge = ["py.typed"]
```

### 3.3 import 改写规则（机械替换，脚本执行）

项目内 37 个模块名集合 `MODULES`。对 `src/archibridge/*.py` 与 `tests/**/*.py`：

| 原写法 | 新写法 |
|---|---|
| `import aggregate_service` | `from archibridge import aggregate_service` |
| `import aggregate_service as _agg` | `from archibridge import aggregate_service as _agg` |
| `from errors import X` | `from archibridge.errors import X` |
| `from cost_estimator import build_estimate_report`（函数内延迟导入同样处理） | `from archibridge.cost_estimator import build_estimate_report` |

- `archicad`、`mcp`、`openpyxl`、标准库不改
- 语义保证：`from archibridge import X` 与原 `import X` 绑定同一模块单例，`monkeypatch.setattr` 行为不变
- 替换后立即 `python -m pytest tests/unit -q` 验证

### 3.4 server.py 双入口设计

包内 `src/archibridge/server.py`：
- 现有逻辑整体平移；`mcp = FastMCP("archibridge")`
- 新增 `def main() -> None:` 包装现有 `if __name__ == "__main__"` 块（discover_instances + stdio 启动）
- 启动横幅改为 `[archibridge v0.38.0] 筑联 ArchiBridge 已启动`（stderr，协议规范）

根目录薄壳 `server.py`（向后兼容用户现有 MCP 配置）：

```python
"""兼容壳：等价于 python -m archibridge。"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent / "src"))
from archibridge.server import main
main()
```

- `__main__.py`：`from archibridge.server import main; main()`
- `__init__.py`：`__version__ = "0.38.0"` + `from archibridge.server import mcp  # noqa`（可选，避免循环导入则不导）

### 3.5 CHANGELOG.md

- 从 readme 版本历史迁移 V0.3→V0.38 全部条目（Keep a Changelog 格式：Added/Changed/Fixed 分节）
- readme 版本历史段改为折叠摘要 + 指向 CHANGELOG 链接

### 3.6 CI（.github/workflows/ci.yml）

```yaml
name: CI
on: [push, pull_request, workflow_dispatch]
jobs:
  test:
    strategy: { matrix: { os: [windows-latest, macos-latest], py: ["3.10", "3.12"] } }
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "${{ matrix.py }}" }
      - run: pip install -e ".[dev]"
      - run: python -m pytest tests/unit -q
  publish:                     # tag 触发
    if: startsWith(github.ref, 'refs/tags/v')
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install build && python -m build
      - uses: pypa/gh-action-pypi-publish@release/v1
        with: { password: "${{ secrets.PYPI_API_TOKEN }}" }
```

- 集成/兼容性测试依赖真机 ArchiCAD，不进 CI，保留本地 regression.py
- 版本一致性检查：CI 加一步校验 `pyproject version == __init__.__version__`

### 3.7 S0 验收清单

- [ ] `pip install -e .` 后 `archibridge` 命令启动、`python -m archibridge` 启动、根目录 `python server.py` 启动（三通道全通）
- [ ] 537 单测全绿（tests 仅 import 改动）
- [ ] 新干净虚拟机：`pip install archibridge` + 现有 MCP 配置指向薄壳 → 可列 66 工具
- [ ] CI 全绿；CHANGELOG 覆盖 V0.3–V0.38
- [ ] debug_log + git 提交（迁移用 git mv，历史可追溯）

---

## 4. S1 自检向导技术方案

### 4.1 `archibridge doctor`（新增 doctor.py，独立于 MCP 服务）

自检项顺序（可独立修复）：

| # | 检查 | 方法 | 修复输出 |
|---|---|---|---|
| 1 | Python ≥3.10 | `sys.version_info` | 升级链接 |
| 2 | 依赖完整 | import 探测（mcp/archicad/openpyxl） | `pip install archibridge` |
| 3 | ArchiCAD 安装与版本 | 注册表（Win）/应用目录（Mac）扫描 AC26–30 | 版本对应关系说明 |
| 4 | 实例监听端口 | 扫描 19723–19743（复用 instance_manager.discover_instances） | 检查「工作环境→连接」开关 |
| 5 | Tapir 加载 | ExecuteAddOnCommand 探测 GetProductInfo | 对应版本 .apx 下载链接 + 加载步骤 |
| 6 | 官方 API 连通 | conn.commands.GetProductInfo | 提示开启 API 服务 |

输出：体检表 + 每项 FAIL 的修复动作；`--fix` 尽力自动修（仅 2/3 项）。

### 4.2 `archibridge install <client>`

| 参数 | 写入目标 |
|---|---|
| claude | `%APPDATA%\Claude\claude_desktop_config.json` |
| cursor | `~/.cursor/mcp.json` |
| trae | Trae MCP 配置文件 |
| all | 逐个探测已安装并写入 |

- 写入前备份原文件（`.bak`）；已存在同名 server 时询问覆盖
- 命令体：Windows `python -m archibridge`（记录安装 Python 绝对路径）

### 4.3 场景技能模板

`docs/recipes/` 下提供 3 个 Trae/Claude 智能体提示词模板：建模助手 / 造价助手 / 审图助手（引用工具名与四阶段写入规范）。

---

## 5. S2 桌面安装器技术方案

| 组件 | 方案 |
|---|---|
| 打包 | Windows：Inno Setup（捆绑 WinPython/嵌入式 Python 3.12 + `pip install archibridge`）；macOS：dmg + zsh 脚本过渡 |
| Tapir 自动安装 | 版本映射表（AC26/27/28/29/30 → Tapir release 下载 URL，维护在 `src/archibridge/data/tapir_versions.json`）；下载后解压到 ArchiCAD Add-Ons 目录，注册表写入加载项，首次启动提示确认 |
| 客户端自动注册 | 复用 S1 install 逻辑，安装完成页勾选已检测到的客户端 |
| 自动更新 | 启动时查 PyPI 最新版（HTTP API），提示 `pip install -U archibridge`；安装器版本跟随 |
| 快捷方式 | 「ArchiBridge 配置向导」（doctor GUI 简化版：tkinter 单页） |

验收（重申）：无 Python 的干净 Windows 机器 → 双击安装 → 开 ArchiCAD → Trae 对话可用。

## 6. S3 HTTP 网关技术方案

| 项 | 方案 |
|---|---|
| 传输 | FastMCP `streamable-http` 模式，与 stdio 共存（`archibridge serve --http --port 8333`）；服务层零改动 |
| 鉴权 | token 中间件（`data/tokens.json`：token→用户→权限集）；`Authorization: Bearer` 头校验 |
| 命令排队 | 每实例一个 asyncio.Lock 串行队列（ArchiCAD 不支持并发写）；排队超时可配置 |
| 审计 | 写入类操作（write/modify/delete/plan 执行类）全量落 `audit_log`（已有模块）扩展 `actor` 字段（token 用户）；支持导出回放 JSON |
| 权限集 | token 可绑定工具白名单（如只读 token：read_tools+aggregate+estimate） |
| 文档 | Dify / Coze / OpenAPI 化 Agent 接入示例各一份 |

## 7. S4 生态技术方案

| 项 | 方案 |
|---|---|
| 数据外置 | `--data-dir` 参数：`quantity_templates.json` / `consumption.json` / `price_book.json` / `fee_rates.json`；内置默认+用户覆盖合并（deep merge） |
| 地区系数 | `regions.json`：region → {labor_coef, material_coef}；CostEstimator 增加 region 查表 |
| 模板市场 | Git 仓库存模板 JSON；`archibridge template add <url>` 拉取并入 data-dir |
| AC30 适配 | compatibility matrix 加 AC30 列；Tapir 版本映射表补条目 |

## 8. AC 侧通道长期方案

- 短期：Tapir（MIT）继续，命令已全部经 `tapir_adapter` 隔离
- 触发自研 Add-On 的条件（任一）：Tapir 停更 / 需要未提供命令（深度写入、视图操作）/ 商业授权要求
- 自研形态：C++ Add-On（Graphisoft DG Kit），最小集 = 现用 52 命令的桥接；`channel_base` 抽象已就位，替换只动 tapir_channel/tapir_adapter 两个模块

## 9. 里程碑

| 阶段 | 周期 | 出口标志 |
|---|---|---|
| S0 | 1–2 周 | PyPI 可 `uvx archibridge`；CI 绿 |
| S1 | +1 周 | doctor/install 全流程无文档跑通 |
| S2 | +2–3 周 | 干净 Windows 双击安装可用 |
| S3 | +2–4 周 | Dify 接入 + 审计回放 |
| S4 | 持续 | 模板市场首个外部贡献 |

## 10. 风险登记册

| 风险 | 等级 | 缓解 |
|---|---|---|
| 包化迁移破坏 import（延迟导入遗漏） | 高（一次性） | 全文件扫描替换 + 537 单测回归 + 三入口验证 |
| 现有用户配置失效 | 中 | 根目录薄壳 server.py 永久保留 |
| PyPI 重名 | 低 | 发布前 `pip index` 查名；备选 archibridge-mcp |
| Tapir 下载 URL 失效（S2） | 中 | 映射表版本化 + 本地镜像 |
| token 泄露（S3） | 中 | 权限白名单 + 审计 + 本地网关默认不开 HTTP |
| Graphisoft 官方 MCP | 中 | 聚焦行业工具层；通道抽象随时可换 |
