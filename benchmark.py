"""Benchmark 性能基准模块（V0.3 8.12）。

测常用只读命令（archicad 原生 + Tapir）多次调用耗时，
输出 avg / min / max（毫秒），结果同时存 benchmark_results.json。

跑法（项目根目录）：
    python benchmark.py                         # 默认实例，3 轮
    python benchmark.py --instance ac29-1 --rounds 5
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

# 源码态（未 pip install）从项目根直接跑时补 src 路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from archilinkai import instance_manager
from archilinkai.tapir_adapter import adapter as _tapir


def measure(fn: Callable[[], Any], rounds: int = 3) -> dict[str, Any]:
    """计时执行 fn 共 rounds 次，返回 ms 统计 {rounds, avg, min, max}。"""
    costs: list[float] = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        fn()
        costs.append((time.perf_counter() - t0) * 1000)
    return {
        "rounds": rounds,
        "avg": round(sum(costs) / rounds, 2),
        "min": round(min(costs), 2),
        "max": round(max(costs), 2),
    }


def _build_calls(instance: str | None) -> list[tuple[str, Callable[[], Any]]]:
    """组装待测命令：名称 → 零参调用（需要参数的提前备好）。"""
    conn = instance_manager.manager.get_conn(instance)
    c = conn.commands
    calls: list[tuple[str, Callable[[], Any]]] = [
        ("GetProductInfo", c.GetProductInfo),
        ("GetAllElements", c.GetAllElements),
        ("GetAllPropertyNames", c.GetAllPropertyNames),
        ("GetElementsByType(Wall)", lambda: c.GetElementsByType("Wall")),
        ("GetAllClassificationSystems", c.GetAllClassificationSystems),
        # Tapir 通道命令
        ("Tapir GetProjectInfo",
         lambda: _tapir.execute("GetProjectInfo", None, instance)),
        ("Tapir GetStories",
         lambda: _tapir.execute("GetStories", None, instance)),
    ]
    # GetDetailsOfElements 需要 GUID：取前 3 个元素
    elems = c.GetAllElements()
    if elems:
        guids = [str(e.elementId.guid) for e in elems[:3]]

        def _details():
            return _tapir.get_details_of_elements(guids, instance)

        calls.append(("Tapir GetDetailsOfElements(3个)", _details))
    return calls


def run(instance: str | None = None, rounds: int = 3) -> dict[str, Any]:
    """跑全部命令基准，返回完整结果（可序列化 dict）。"""
    info = instance_manager.manager.get_info(instance)
    rows = []
    for name, fn in _build_calls(info.instance_id):
        rows.append({"command": name, **measure(fn, rounds)})
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "instance": info.instance_id,
        "project": info.project_name,
        "version": info.version,
        "rounds": rounds,
        "items": rows,
    }


def to_markdown(result: dict[str, Any]) -> str:
    """结果转 markdown 表格文本。"""
    lines = [
        f"# Benchmark 结果（{result['timestamp']}）",
        "",
        f"实例：{result['instance']} / {result['project']} / "
        f"AC{result['version']}；每命令 {result['rounds']} 轮，单位 ms",
        "",
        "| 命令 | 平均 | 最小 | 最大 |",
        "|---|---|---|---|",
    ]
    for r in result["items"]:
        lines.append(f"| {r['command']} | {r['avg']} | {r['min']} | {r['max']} |")
    return "\n".join(lines)


def _save(result: dict[str, Any]) -> None:
    """结果存 JSON；同时刷新 markdown 版便于人看。"""
    with open("benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    with open("benchmark_results.md", "w", encoding="utf-8") as f:
        f.write(to_markdown(result) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="archicad-mcp 性能基准")
    parser.add_argument("--instance", default=None, help="实例 ID，默认唯一实例")
    parser.add_argument("--rounds", type=int, default=3, help="每命令轮数，默认 3")
    args = parser.parse_args()

    instance_manager.manager.discover_instances()
    result = run(args.instance, args.rounds)
    _save(result)
    print(to_markdown(result))
    print("\n已保存：benchmark_results.json / benchmark_results.md")


if __name__ == "__main__":
    main()
