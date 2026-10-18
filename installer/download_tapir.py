"""按 ArchiCAD 主版本下载对应 Tapir Add-On（供安装器或手动使用）。

用法：
    python download_tapir.py 28
    python download_tapir.py 28 --out C:/Graphisoft/Archicad28/Add-Ons/
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from importlib.resources import files
from pathlib import Path


def _mapping() -> dict:
    path = files("archilinkai").joinpath("data/tapir_versions.json")
    return json.loads(path.read_text(encoding="utf-8"))


def _api(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                                "User-Agent": "archilinkai-installer"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def _release_assets(repo: str, tag: str) -> list[dict]:
    if tag == "latest":
        url = f"https://api.github.com/repos/{repo}/releases/latest"
    else:
        url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
    return _api(url).get("assets", [])


def pick_asset(assets: list[dict], ac_version: str) -> dict | None:
    """在 release 资产里挑对应 AC 版本的 apx。"""
    key = f"AC{ac_version}"
    matches = [a for a in assets
               if a["name"].lower().endswith(".apx") and key.lower() in a["name"].lower()]
    if matches:
        return matches[0]
    # 兜底：选第一个 .apx（某些 release 只有一个）
    apx = [a for a in assets if a["name"].lower().endswith(".apx")]
    return apx[0] if apx else None


def download(ac_version: str, out_dir: Path) -> Path:
    mapping = _mapping()
    if ac_version not in mapping["versions"]:
        raise ValueError(f"未配置 AC{ac_version}，仅支持 {sorted(mapping['versions'])}")
    info = mapping["versions"][ac_version]
    assets = _release_assets(mapping["repo"], info["release_tag"])
    asset = pick_asset(assets, ac_version)
    if not asset:
        raise RuntimeError(f"Tapir {info['release_tag']} 未找到 AC{ac_version} 的 apx")
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / asset["name"]
    req = urllib.request.Request(asset["browser_download_url"],
                                 headers={"User-Agent": "archilinkai-installer"})
    with urllib.request.urlopen(req, timeout=120) as r, target.open("wb") as f:
        f.write(r.read())
    return target


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("ac_version", help="ArchiCAD 主版本，如 28")
    p.add_argument("--out", default="./tapir_download", help="下载目录")
    args = p.parse_args()
    try:
        path = download(args.ac_version, Path(args.out))
    except Exception as exc:  # noqa: BLE001
        print(f"下载失败：{exc}", file=sys.stderr)
        return 1
    print(f"已下载 Tapir for AC{args.ac_version}：{path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
