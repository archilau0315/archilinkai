"""archilinkai doctor：环境自检（六项检查，逐项给出修复建议）。

只做检查与提示，不改动环境。检查结果以表格打印到 stdout。
"""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass

from archilinkai import __version__


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    fix: str = ""


def check_python() -> CheckResult:
    v = sys.version_info
    ok = (v.major, v.minor) >= (3, 10)
    return CheckResult(
        "Python 版本", ok, f"{v.major}.{v.minor}.{v.micro}",
        "" if ok else "需 Python ≥ 3.10：https://www.python.org/downloads/")


def check_dependencies() -> CheckResult:
    missing = [m for m in ("mcp", "archicad", "openpyxl")
               if importlib.util.find_spec(m) is None]
    if missing:
        return CheckResult("依赖完整", False, f"缺少：{', '.join(missing)}",
                           "pip install archilinkai 或 pip install -e .")
    return CheckResult("依赖完整", True, "mcp / archicad / openpyxl 均在")


def check_instances() -> CheckResult:
    """探测 ArchiCAD 实例端口（19723-19743）。"""
    try:
        from archilinkai import instance_manager
        instance_manager.manager.discover_instances()
        reg = list(instance_manager.manager._registry)
        if reg:
            return CheckResult("ArchiCAD 实例", True, f"发现：{', '.join(reg)}")
        return CheckResult(
            "ArchiCAD 实例", False, "未发现实例",
            "启动 ArchiCAD 并打开项目；选项→工作环境→启用连接端口")
    except Exception as exc:  # noqa: BLE001 自检不抛
        return CheckResult("ArchiCAD 实例", False, f"探测失败：{exc}",
                           "确认 ArchiCAD 已启动且连接端口已启用")


def check_tapir() -> CheckResult:
    """Tapir Add-On 加载探测（依赖实例已发现）。"""
    try:
        from archilinkai.tapir_adapter import adapter
        adapter.execute("GetProductInfo", None, None)
        return CheckResult("Tapir Add-On", True, "命令通道正常")
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            "Tapir Add-On", False, str(exc)[:80],
            "下载对应大版本 Tapir .apx（ENZYME-APD/tapir-archicad-automation），"
            "选项→Add-On 管理器→添加 加载")


def run_checks() -> list[CheckResult]:
    """按序执行全部检查；实例未发现时跳过 Tapir 检查。"""
    results = [check_python(), check_dependencies()]
    inst = check_instances()
    results.append(inst)
    if inst.ok:
        results.append(check_tapir())
    else:
        results.append(CheckResult(
            "Tapir Add-On", False, "跳过（实例未发现）", "先解决实例发现"))
    return results


def print_report(results: list[CheckResult]) -> None:
    print(f"\n筑元智联 ArchiLinkAI v{__version__} 环境自检\n" + "=" * 60)
    for r in results:
        mark = "PASS" if r.ok else "FAIL"
        print(f"[{mark}] {r.name}：{r.detail}")
        if not r.ok and r.fix:
            print(f"       修复：{r.fix}")
    n_fail = sum(1 for r in results if not r.ok)
    print("=" * 60)
    print("全部通过。" if n_fail == 0 else f"{n_fail} 项未通过，按修复提示处理后重跑。")


def main() -> int:
    results = run_checks()
    print_report(results)
    return 0 if all(r.ok for r in results) else 1
