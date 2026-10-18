"""S1 CLI / doctor 单测（V0.40）。"""

from __future__ import annotations

import json
import sys

import pytest

from archilinkai import cli, doctor


class TestDoctorChecks:
    def test_python_check_ok(self):
        r = doctor.check_python()
        assert (sys.version_info[:2] >= (3, 10)) == r.ok

    def test_dependencies_check(self):
        r = doctor.check_dependencies()
        assert r.name == "依赖完整"
        if not r.ok:
            assert "pip install" in r.fix

    def test_instances_check_no_crash(self):
        """无真机环境也应返回结构化结果而非抛异常。"""
        r = doctor.check_instances()
        assert r.name == "ArchiCAD 实例"
        assert isinstance(r.ok, bool)

    def test_run_checks_skips_tapir_without_instance(self, monkeypatch):
        monkeypatch.setattr(
            doctor, "check_instances",
            lambda: doctor.CheckResult("ArchiCAD 实例", False, "x"))
        results = doctor.run_checks()
        tapir = [r for r in results if r.name == "Tapir Add-On"]
        assert tapir and not tapir[0].ok and "跳过" in tapir[0].detail

    def test_main_exit_code(self, monkeypatch):
        monkeypatch.setattr(doctor, "run_checks", lambda: [
            doctor.CheckResult("a", True, ""), doctor.CheckResult("b", True, "")])
        assert doctor.main() == 0
        monkeypatch.setattr(doctor, "run_checks", lambda: [
            doctor.CheckResult("a", False, "", "fix")])
        assert doctor.main() == 1


class TestCliInstall:
    def test_generic_snippet(self):
        out = cli.install_client("generic")
        assert "archilinkai" in out and "mcpServers" in out

    def test_unknown_client(self):
        out = cli.install_client("no_such_client")
        assert "未知客户端" in out and "generic" in out

    def test_write_json_client(self, tmp_path, monkeypatch):
        cfg = tmp_path / "cfg.json"
        cfg.write_text(json.dumps({"mcpServers": {"old": {}}}), encoding="utf-8")
        monkeypatch.setattr(cli, "_clients_table",
                            lambda: {"t": {"name": "T", "config": str(cfg)}})
        out = cli.install_client("t")
        assert "已写入" in out
        data = json.loads(cfg.read_text(encoding="utf-8"))
        assert data["mcpServers"]["archilinkai"]["command"] == "archilinkai"
        assert "old" in data["mcpServers"]  # 不覆盖既有配置
        assert cfg.with_suffix(".json.bak").exists()  # 备份存在

    def test_toml_client_hint(self):
        out = cli.install_client("codex")
        assert "mcp_servers.archilinkai" in out
