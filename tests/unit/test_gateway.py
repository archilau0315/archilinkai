"""S3 HTTP 网关单测（V0.41）：鉴权中间件与审计。"""

from __future__ import annotations

import asyncio
import json

import pytest

from archilinkai import gateway


def _scope(headers: list[tuple[bytes, bytes]] | None = None) -> dict:
    return {"type": "http", "method": "POST", "path": "/mcp",
            "headers": headers or []}


class _DummyApp:
    def __init__(self, status: int = 200):
        self.status = status
        self.called = False

    async def __call__(self, scope, receive, send):
        self.called = True
        await send({"type": "http.response.start", "status": self.status,
                    "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})


def _run(app, scope):
    sent: list[dict] = []

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(msg):
        sent.append(msg)

    asyncio.run(app(scope, receive, send))
    return sent


class TestBearerAuth:
    def test_no_token_401(self, tmp_path):
        app = gateway.BearerAuthMiddleware(_DummyApp(), "secret", tmp_path / "a.jsonl")
        sent = _run(app, _scope())
        assert sent[0]["status"] == 401
        body = json.loads(sent[1]["body"])
        assert body["error"] == "unauthorized"

    def test_wrong_token_401(self, tmp_path):
        app = gateway.BearerAuthMiddleware(_DummyApp(), "secret", tmp_path / "a.jsonl")
        sent = _run(app, _scope([(b"authorization", b"Bearer nope")]))
        assert sent[0]["status"] == 401

    def test_correct_token_passes(self, tmp_path):
        inner = _DummyApp(status=201)
        app = gateway.BearerAuthMiddleware(inner, "secret", tmp_path / "a.jsonl")
        sent = _run(app, _scope([(b"authorization", b"Bearer secret")]))
        assert inner.called
        assert sent[0]["status"] == 201  # 真实状态透传

    def test_audit_log_written(self, tmp_path):
        audit = tmp_path / "a.jsonl"
        app = gateway.BearerAuthMiddleware(_DummyApp(), "secret", audit)
        _run(app, _scope())  # 401
        _run(app, _scope([(b"authorization", b"Bearer secret")]))  # 200
        lines = audit.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        r0, r1 = (json.loads(l) for l in lines)
        assert r0["status"] == 401 and r0["path"] == "/mcp"
        assert r1["status"] == 200 and r1["token_hint"].endswith("secret")
        assert "body" not in r1  # 审计不含正文

    def test_non_http_scope_passthrough(self, tmp_path):
        inner = _DummyApp()
        app = gateway.BearerAuthMiddleware(inner, "secret", tmp_path / "a.jsonl")
        sent = _run(app, {"type": "lifespan"})
        assert inner.called


class TestRunHttpGuard:
    def test_no_token_refuses(self, monkeypatch):
        monkeypatch.delenv("ALAI_TOKEN", raising=False)
        with pytest.raises(SystemExit) as exc:
            gateway.run_http("127.0.0.1", 8000, None)
        assert exc.value.code == 2

    def test_missing_uvicorn_refuses(self, monkeypatch):
        monkeypatch.setitem(__import__("sys").modules, "uvicorn", None)
        with pytest.raises(SystemExit) as exc:
            gateway.run_http("127.0.0.1", 8000, "tok")
        assert exc.value.code == 2
