"""audit_log.py 单元测试：generate_id / log / get / list_recent。

用独立 OperationLogger 实例，避免污染全局单例计数器。
"""

import os
import tempfile

import pytest

from audit_log import OperationLogger
from schemas import OperationLog


@pytest.fixture
def logger(tmp_path):
    """每个测试用独立 logger + 临时日志文件。"""
    log_file = str(tmp_path / "ops.jsonl")
    return OperationLogger(log_file=log_file)


def _make_log(op_id="OP-20260923-00001", tool="set_element_properties"):
    return OperationLog(
        operation_id=op_id,
        timestamp="2026-09-23T10:00:00",
        instance="ac29-1",
        project="Demo.pln",
        tool=tool,
        target_count=5,
        property="Fire Rating",
        before={"A": "B"},
        after={"A": "A"},
        execute_status="success",
        verify_status="success",
    )


def test_generate_id_format():
    logger = OperationLogger(log_file=os.devnull)
    op_id = logger.generate_id()
    assert op_id.startswith("OP-")
    # 形如 OP-YYYYMMDD-NNNNN
    parts = op_id.split("-")
    assert len(parts) == 3
    assert len(parts[1]) == 8  # 日期 8 位
    assert len(parts[2]) == 5  # 序号 5 位


def test_generate_id_increments(logger):
    a = logger.generate_id()
    b = logger.generate_id()
    c = logger.generate_id()
    assert a < b < c
    # 序号递增
    assert int(a[-5:]) == 1
    assert int(b[-5:]) == 2
    assert int(c[-5:]) == 3


def test_log_and_get(logger):
    log = _make_log()
    logger.log(log)
    assert logger.get("OP-20260923-00001") is log


def test_get_missing_returns_none(logger):
    assert logger.get("does-not-exist") is None


def test_to_dict_helper(logger):
    logger.log(_make_log())
    d = logger.to_dict("OP-20260923-00001")
    assert d["operation_id"] == "OP-20260923-00001"
    assert d["tool"] == "set_element_properties"


def test_to_dict_missing_returns_none(logger):
    assert logger.to_dict("missing") is None


def test_list_recent_ordered(logger):
    for i in range(5):
        logger.log(_make_log(op_id=f"OP-20260923-{i+1:05d}"))
    recent = logger.list_recent(limit=3)
    # 倒序：最新在前
    assert recent[0].operation_id == "OP-20260923-00005"
    assert recent[-1].operation_id == "OP-20260923-00003"
    assert len(recent) == 3


def test_list_recent_empty(logger):
    assert logger.list_recent() == []


def test_log_persists_to_file(logger, tmp_path):
    logger.log(_make_log())
    log_file = tmp_path / "ops.jsonl"
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "OP-20260923-00001" in content
    assert "set_element_properties" in content


def test_log_file_failure_does_not_raise(monkeypatch, tmp_path):
    """日志文件写入失败不应影响主操作流程。"""
    logger = OperationLogger(log_file=str(tmp_path / "subdir" / "ops.jsonl"))
    # 不创建子目录，直接 log，_append_to_file 内部 try/except 吞掉异常
    logger.log(_make_log())  # 不应抛异常
    assert logger.get("OP-20260923-00001") is not None
