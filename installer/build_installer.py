"""Inno Setup 安装脚本：筑元智联 ArchiLinkAI 桌面安装器。

由 build_installer.py 读取版本并注入 #define MyAppVersion 后编译。
默认安装 {pf}\\ArchiLinkAI，内容：
- 嵌入式 Python（由构建阶段从 python-3.12.*-embed 解压）
- archilinkai 包（pip install 本地 wheel）
- install 脚本写入 MCP 客户端配置

Tapir：下载脚本 installer/download_tapir.py，安装时/手动按 AC 版本下载并
放入 ArchiCAD Add-Ons 目录。
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ISS = Path(__file__).parent / "archilinkai.iss"


def _version() -> str:
    pkg = (ROOT / "src/archilinkai/__init__.py").read_text(encoding="utf-8")
    for line in pkg.splitlines():
        if "__version__" in line:
            return line.split("=")[1].strip().strip('"').strip("'")
    raise RuntimeError("无法读取版本")


def build() -> int:
    iscc = shutil.which("ISCC")
    if not iscc:
        print("未找到 ISCC.exe。安装 Inno Setup 并加入 PATH：", file=sys.stderr)
        print("https://jrsoftware.org/isdl.php", file=sys.stderr)
        return 2
    version = _version()
    print(f"构建 ArchiLinkAI v{version} 安装器…")
    cmd = [iscc, str(ISS), f"/DMyAppVersion={version}", f"/O{ROOT / 'dist'}"]
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(build())
