"""archilinkai CLI：serve / doctor / install / download-tapir。

- serve（默认）：启动 MCP server（stdio），等价 python -m archilinkai
- doctor：环境自检（doctor.py）
- install <client>：向 MCP 客户端写入 server 配置（客户端矩阵见 data/clients.json）
- install generic：打印通用 MCP JSON 片段
- download-tapir <版本>：下载对应平台 Tapir（win/mac/all）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from importlib.resources import files
from pathlib import Path

SERVER_KEY = "archilinkai"


def _clients_table() -> dict:
    path = files("archilinkai").joinpath("data/clients.json")
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_path(spec: dict) -> Path:
    """按平台选择 config/config_mac，展开 ~ 与环境变量。"""
    s = spec.get("config_mac") if (os.name != "nt" and spec.get("config_mac")) \
        else spec["config"]
    return Path(os.path.expandvars(os.path.expanduser(s)))


def _mcp_entry() -> dict:
    return {"command": "archilinkai", "args": []}


def _generic_snippet() -> str:
    return json.dumps(
        {"mcpServers": {SERVER_KEY: _mcp_entry()}}, indent=2, ensure_ascii=False)


def _write_json_client(client: str, spec: dict) -> str:
    cfg_path = _resolve_path(spec)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {}
    if cfg_path.exists():
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
            cfg_path.with_suffix(cfg_path.suffix + ".bak").write_text(
                cfg_path.read_text(encoding="utf-8"), encoding="utf-8")
        except json.JSONDecodeError:
            data = {}
    data.setdefault("mcpServers", {})[SERVER_KEY] = _mcp_entry()
    cfg_path.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    return f"已写入 {spec['name']}：{cfg_path}"


def install_client(client: str) -> str:
    """写入指定客户端配置；返回结果描述。"""
    if client == "generic":
        return "通用 MCP 配置片段（粘贴到任意支持 MCP 的客户端）：\n" + _generic_snippet()
    table = _clients_table()
    if client not in table:
        return (f"未知客户端 {client}。已知：{', '.join(table)}；"
                "或用 generic 打印通用片段")
    spec = table[client]
    if spec.get("fmt") == "toml":
        return (f"{spec['name']} 请手动在 {_resolve_path(spec)} 中添加：\n"
                f"[mcp_servers.{SERVER_KEY}]\ncommand = \"archilinkai\"\nargs = []")
    return _write_json_client(client, spec)


def cmd_doctor(_args) -> int:
    from archilinkai import doctor
    return doctor.main()


def cmd_install(args) -> int:
    print(install_client(args.client))
    return 0


def cmd_serve(args) -> int:
    lang = getattr(args, "lang", None)
    if lang:
        os.environ["ALAI_LANG"] = lang
    if getattr(args, "http", False):
        from archilinkai import gateway
        gateway.run_http(args.host, args.port, args.token)
        return 0
    from archilinkai.server import main as serve_main
    serve_main()
    return 0


def cmd_download_tapir(args) -> int:
    from archilinkai import download_tapir
    try:
        paths = download_tapir.download(args.ac_version, Path(args.out),
                                        args.platform)
    except Exception as exc:  # noqa: BLE001
        print(f"下载失败：{exc}", file=sys.stderr)
        return 1
    for p in paths:
        print(f"已下载：{p}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="archilinkai",
        description="筑元智联 ArchiLinkAI：AI 智能体与 ArchiCAD 的 MCP 桥梁")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("doctor", help="环境自检")
    p_inst = sub.add_parser("install", help="向 MCP 客户端写入配置")
    p_inst.add_argument("client", nargs="?", default="generic",
                        help="claude/cursor/cline/witsy/cherry/codex/generic")
    p_dt = sub.add_parser("download-tapir", help="下载 Tapir Add-On")
    p_dt.add_argument("ac_version", help="ArchiCAD 主版本，如 28")
    p_dt.add_argument("--out", default="./tapir_download", help="下载目录")
    p_dt.add_argument("--platform", choices=["win", "mac", "all"], default=None,
                      help="目标平台，默认按当前系统检测；all 双平台并存")
    p_serve = sub.add_parser("serve", help="启动 MCP server（默认 stdio）")
    p_serve.add_argument("--http", action="store_true",
                         help="HTTP 模式（远程/平台接入，需 token）")
    p_serve.add_argument("--host", default="127.0.0.1",
                         help="HTTP 绑定地址，默认仅本机")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.add_argument("--token", default=None,
                         help="Bearer token；缺省读环境变量 ALAI_TOKEN")
    p_serve.add_argument("--lang", choices=["zh", "en"], default=None,
                         help="输出语言，默认 zh（也可用环境变量 ALAI_LANG）")
    args = parser.parse_args()
    if args.cmd == "doctor":
        return cmd_doctor(args)
    if args.cmd == "install":
        return cmd_install(args)
    if args.cmd == "download-tapir":
        return cmd_download_tapir(args)
    return cmd_serve(args)


if __name__ == "__main__":
    sys.exit(main())
