# S2 桌面安装器

让非技术用户双击安装筑元智联 ArchiLinkAI，无需手动装 Python/写配置。

## 交付物

| 文件 | 作用 |
|---|---|
| `installer/archilinkai.iss` | Inno Setup 安装脚本（中文/英文双语，现代向导） |
| `installer/build_installer.py` | 一键编译：自动读版本 → 调 ISCC.exe |
| `installer/download_tapir.py` | 按 AC 主版本从 GitHub 下载对应 Tapir apx |
| `src/archilinkai/data/tapir_versions.json` | AC 版本→Tapir 版本映射（可维护） |

## 构建步骤

### 1. 准备 payload 目录

```powershell
cd installer
mkdir payload
# 嵌入式 Python（无管理员权限也能装）
Invoke-WebRequest https://www.python.org/ftp/python/3.12.9/python-3.12.9-embed-amd64.zip -OutFile python.zip
Expand-Archive python.zip -DestinationPath payload/python
# 给嵌入式 Python 装 pip
payload/python/python.exe -m ensurepip
# 生成 archilinkai wheel
cd ..; python -m build
Copy-Item dist/archilinkai-*.whl installer/payload/wheel/
```

### 2. 安装 Inno Setup 并编译

下载 [Inno Setup 6](https://jrsoftware.org/isdl.php)（自带 ISCC 加入 PATH）：

```powershell
python installer/build_installer.py
# 输出 dist/ArchiLinkAI-Setup-<版本>.exe
```

## 安装器行为

1. 解压嵌入式 Python 到 `C:\Program Files\ArchiLinkAI\`
2. 用本地 wheel 安装 archilinkai（`pip install --no-index`，无需外网）
3. 写入 Claude Desktop 等 MCP 客户端配置（失败不阻塞）
4. 开始菜单加「ArchiLinkAI 命令行」入口

## Tapir Add-On 处理

Tapir 与 ArchiCAD 大版本一一绑定，安装器不内置 apx（避免版本错配）。两种方式：

```powershell
# 方式一：命令行下载（需外网）
python -m archilinkai.cli install generic   # 先确认 archilinkai 可用
python installer/download_tapir.py 28 --out "C:/Graphisoft/Archicad28/Add-Ons/"

# 方式二：让安装器脚本调用（安装向导页中选 AC 版本后自动下载）
```

下载后在 ArchiCAD 中 **选项 → Add-On 管理器 → 添加** 加载该 apx。

## 版本映射维护

编辑 `src/archilinkai/data/tapir_versions.json` 的 `versions` 字典：
```json
{"28": {"release_tag": "latest"}, "29": {"release_tag": "latest"}}
```
`release_tag` 可填 `latest` 或具体 tag（如 `v0.66.0`）。
