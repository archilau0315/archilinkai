"""按 ArchiCAD 主版本下载对应 Tapir Add-On。

用法（pip 安装后）：
    archilinkai download-tapir 28                        # 自动检测平台
    archilinkai download-tapir 28 --platform mac         # 只下 Mac 资产
    archilinkai download-tapir 28 --platform all --out ./tapir  # Win+Mac 并存
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import zipfile
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


def detect_platform() -> str:
    """返回 'win' 或 'mac'。"""
    return "mac" if sys.platform == "darwin" else "win"


def pick_asset(assets: list[dict], ac_version: str, platform: str) -> dict | None:
    """在 release 资产里挑对应 AC 版本与平台的安装包。

    Win 资产命名 TapirAddOn_AC28_Win.apx；Mac 为 TapirAddOn_AC28_Mac.zip。
    """
    ext = ".apx" if platform == "win" else ".zip"
    key = f"AC{ac_version}"
    matches = [a for a in assets
               if a["name"].lower().endswith(ext) and key.lower() in a["name"].lower()]
    if matches:
        return matches[0]
    # 兜底：选第一个对应平台的资产（某些 release 只有一个）
    any_ext = [a for a in assets if a["name"].lower().endswith(ext)]
    return any_ext[0] if any_ext else None


def _extract_bundle(zip_path: Path) -> Path:
    """Mac 资产为 zip，解压后返回 .bundle 目录（找不到则返回解压目录）。"""
    out_dir = zip_path.parent / zip_path.stem
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(out_dir)
    bundles = list(out_dir.rglob("*.bundle"))
    return bundles[0] if bundles else out_dir


def download(ac_version: str, out_dir: Path, platform: str | None = None) -> list[Path]:
    """下载指定 AC 版本的 Tapir 安装包。platform 为 all 时 Win+Mac 双平台并存下载。"""
    platform = platform or detect_platform()
    platforms = ["win", "mac"] if platform == "all" else [platform]
    results: list[Path] = []
    for plat in platforms:
        results.append(_download_one(ac_version, out_dir, plat))
    return results


def _download_one(ac_version: str, out_dir: Path, platform: str) -> Path:
    mapping = _mapping()
    if ac_version not in mapping["versions"]:
        raise ValueError(f"未配置 AC{ac_version}，仅支持 {sorted(mapping['versions'])}")
    info = mapping["versions"][ac_version]
    assets = _release_assets(mapping["repo"], info["release_tag"])
    asset = pick_asset(assets, ac_version, platform)
    if not asset:
        raise RuntimeError(f"Tapir {info['release_tag']} 未找到 AC{ac_version} 的 {platform} 安装包")
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / asset["name"]
    req = urllib.request.Request(asset["browser_download_url"],
                                 headers={"User-Agent": "archilinkai-installer"})
    with urllib.request.urlopen(req, timeout=120) as r, target.open("wb") as f:
        f.write(r.read())
    if platform == "mac" and target.suffix == ".zip":
        return _extract_bundle(target)
    return target


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("ac_version", help="ArchiCAD 主版本，如 28")
    p.add_argument("--out", default="./tapir_download", help="下载目录")
    p.add_argument("--platform", choices=["win", "mac", "all"], default=None,
                   help="目标平台，默认按当前系统检测；all 表示 Win+Mac 并存下载")
    args = p.parse_args()
    try:
        paths = download(args.ac_version, Path(args.out), args.platform)
    except Exception as exc:  # noqa: BLE001
        print(f"下载失败：{exc}", file=sys.stderr)
        return 1
    for path in paths:
        print(f"已下载 Tapir for AC{args.ac_version}：{path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
