"""一键回归（V0.18）：单测 → 集成 → 兼容性 → 性能基准，输出汇总报告。

跑法（项目根目录）：
    python regression.py                 # 全自动（有真机跑真机，无真机自动跳）
    python regression.py --no-benchmark  # 跳过性能基准
    python regression.py --json out.json # 结果存文件
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime


def _run_pytest(path: str) -> dict:
    """跑一个测试目录，解析 pytest 输出行（passed/failed/skipped）。"""
    t0 = time.perf_counter()
    r = subprocess.run(
        [sys.executable, "-m", "pytest", path, "-q", "--tb=no"],
        capture_output=True, text=True, timeout=600,
    )
    elapsed = time.perf_counter() - t0
    # 末行形如 "419 passed in 44.68s" 或 "25 passed, 2 skipped in 88s"
    last = (r.stdout.strip().splitlines() or [""])[-1]
    stats = {"passed": 0, "failed": 0, "skipped": 0}
    tokens = last.replace(",", " ").split()
    for i, tok in enumerate(tokens[:-1]):
        if tokens[i + 1] in stats and tok.isdigit():
            stats[tokens[i + 1]] = int(tok)
    return {
        "path": path, "exit_code": r.returncode, "seconds": round(elapsed, 1),
        **stats, "last_line": last,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="archicad-mcp 一键回归")
    ap.add_argument("--no-benchmark", action="store_true", help="跳过性能基准")
    ap.add_argument("--json", metavar="FILE", help="结果存 JSON 文件")
    args = ap.parse_args()

    print("=" * 60)
    print("archicad-mcp 回归报告", datetime.now().isoformat(timespec="seconds"))
    print("=" * 60)

    stages = []
    for name, path in [("单元测试", "tests/unit"),
                       ("真机集成", "tests/integration"),
                       ("版本兼容", "tests/compatibility")]:
        print(f"\n[{name}] {path} ...")
        res = _run_pytest(path)
        stages.append((name, res))
        mark = "OK" if res["exit_code"] == 0 else "FAIL"
        print(f"  {mark}  {res['last_line']}  ({res['seconds']}s)")

    report: dict = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "stages": {name: res for name, res in stages},
    }

    if not args.no_benchmark:
        print("\n[性能基准] benchmark ...")
        try:
            import benchmark
            import instance_manager
            mgr = instance_manager.manager
            mgr.discover_instances()
            ids = [i.instance_id for i in mgr.list_instances()]
            # 优先最新版（AC30），回退到 AC29，再回退第一个可用
            inst = ("ac30-1" if "ac30-1" in ids
                    else "ac29-1" if "ac29-1" in ids
                    else (ids[0] if ids else None))
            b = benchmark.run(instance=inst)
            report["benchmark"] = b
            print(f"  OK  {len(b['items'])} 项命令，实例 {b['instance']}")
        except Exception as e:
            report["benchmark"] = {"error": str(e)}
            print(f"  SKIP  {e}")

    total_fail = sum(r["failed"] for _, r in stages)
    total_pass = sum(r["passed"] for _, r in stages)
    print("\n" + "=" * 60)
    print(f"汇总：{total_pass} 通过，{total_fail} 失败")
    report["total"] = {"passed": total_pass, "failed": total_fail}

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"报告已存：{args.json}")

    return 1 if total_fail else 0


if __name__ == "__main__":
    sys.exit(main())
