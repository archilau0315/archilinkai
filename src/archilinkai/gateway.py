"""HTTP 网关（V0.41，S3）：远程/平台接入模式。

把 MCP server 以 streamable-http 暴露，供 Dify/Coze/n8n 等非 stdio 平台
及远程智能体接入。安全默认：
- 必须提供 token（--token 或环境变量 ALAI_TOKEN），否则拒绝启动
- Bearer 鉴权中间件，未带/错误 token 一律 401
- 全量请求审计（JSONL：时间/方法/路径/状态/token 前缀，不含正文）
- 默认只绑 127.0.0.1，跨机访问需显式 --host 0.0.0.0
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AUDIT_PATH = Path("output") / "http_audit.jsonl"


class BearerAuthMiddleware:
    """纯 ASGI Bearer 鉴权 + 审计中间件（不依赖任何 Web 框架）。"""

    def __init__(self, app: Any, token: str,
                 audit_path: Path | None = None) -> None:
        self.app = app
        self._token = token
        self._audit = audit_path or AUDIT_PATH

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode().lower(): v.decode()
                   for k, v in scope.get("headers", [])}
        auth = headers.get("authorization", "")
        ok = auth == f"Bearer {self._token}"
        if not ok:
            await self._reply(send, 401,
                              {"error": "unauthorized",
                               "message": "missing or invalid Bearer token"})
            self._log(scope, 401, auth)
            return
        status_box: list[int] = [200]

        async def spy_send(message):
            if message["type"] == "http.response.start":
                status_box[0] = message["status"]
            await send(message)
        try:
            await self.app(scope, receive, spy_send)
        finally:
            self._log(scope, status_box[0], auth)

    async def _reply(self, send, status: int, body: dict) -> None:
        payload = json.dumps(body).encode()
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"application/json")]})
        await send({"type": "http.response.body", "body": payload})

    def _log(self, scope, status: int, auth: str) -> None:
        self._audit.parent.mkdir(parents=True, exist_ok=True)
        token_hint = auth[-8:] if auth.startswith("Bearer ") else "-"
        rec = {"ts": datetime.now(timezone.utc).isoformat(),
               "method": scope.get("method"), "path": scope.get("path"),
               "status": status, "token_hint": token_hint}
        with self._audit.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def build_http_app(token: str, audit_path: Path | None = None) -> Any:
    """构造带鉴权的 HTTP ASGI app。"""
    from archilinkai.server import mcp
    factory = (getattr(mcp, "streamable_http_app", None)
               or getattr(mcp, "http_app", None))
    if factory is None:
        raise RuntimeError("当前 FastMCP 版本不提供 HTTP app 工厂")
    inner = factory()
    return BearerAuthMiddleware(inner, token, audit_path)


def run_http(host: str, port: int, token: str | None,
             audit_path: Path | None = None) -> None:
    """启动 HTTP 模式。token 为空时拒绝启动。"""
    import os
    token = token or os.environ.get("ALAI_TOKEN")
    if not token:
        print("[archilinkai] HTTP 模式必须提供 token："
              "--token <值> 或环境变量 ALAI_TOKEN", file=sys.stderr)
        sys.exit(2)
    try:
        import uvicorn
    except ImportError:
        print("[archilinkai] HTTP 模式需 uvicorn：pip install 'archilinkai[http]'",
              file=sys.stderr)
        sys.exit(2)
    app = build_http_app(token, audit_path)
    bind_note = "仅本机" if host in ("127.0.0.1", "localhost") else "跨机可达，注意防火墙"
    print(f"[archilinkai] HTTP 模式 http://{host}:{port}（{bind_note}，"
          f"审计 → {audit_path or AUDIT_PATH}）", file=sys.stderr, flush=True)
    uvicorn.run(app, host=host, port=port)
