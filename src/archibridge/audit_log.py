"""操作日志模块（V0.3 8.9）。

所有写操作生成唯一 Operation ID（OP-YYYYMMDD-NNNNN），
记录 before/after/execute_status/verify_status。
日志不记录不必要的敏感信息。

存储：内存索引 + JSONL 文件持久化（追加写入，单进程安全）。
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from typing import Any

from archibridge.schemas import OperationLog

# 默认日志文件位置：与 server.py 同目录的 .operations.jsonl
_DEFAULT_LOG_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".operations.jsonl"
)


class OperationLogger:
    """操作日志记录器（线程安全）。"""

    def __init__(self, log_file: str | None = None) -> None:
        self._lock = threading.Lock()
        self._index: dict[str, OperationLog] = {}
        self._counter: dict[str, int] = {}  # date_str -> 序号
        self._log_file = log_file or _DEFAULT_LOG_FILE

    # --- Operation ID 生成 ------------------------------------------------

    def generate_id(self) -> str:
        """生成 OP-YYYYMMDD-NNNNN，每天序号从 1 递增。"""
        date_str = datetime.now().strftime("%Y%m%d")
        with self._lock:
            self._counter[date_str] = self._counter.get(date_str, 0) + 1
            seq = self._counter[date_str]
        return f"OP-{date_str}-{seq:05d}"

    # --- 记录 -------------------------------------------------------------

    def log(self, operation: OperationLog) -> None:
        """记录一条操作日志到内存与文件。"""
        with self._lock:
            self._index[operation.operation_id] = operation
            self._append_to_file(operation)

    def _append_to_file(self, operation: OperationLog) -> None:
        """追加写 JSONL；失败不阻塞主流程（仅日志）。"""
        try:
            os.makedirs(os.path.dirname(self._log_file), exist_ok=True)
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(operation.to_dict(), ensure_ascii=False))
                f.write("\n")
        except Exception:
            # 日志写入失败不影响操作本身，避免把写操作搞挂
            pass

    # --- 查询 -------------------------------------------------------------

    def get(self, operation_id: str) -> OperationLog | None:
        """按 ID 查询操作记录。"""
        return self._index.get(operation_id)

    def list_recent(self, limit: int = 20) -> list[OperationLog]:
        """返回最近 N 条操作（按记录顺序倒序）。"""
        with self._lock:
            items = list(self._index.values())
        items.sort(key=lambda x: x.operation_id, reverse=True)
        return items[:limit]

    def to_dict(self, operation_id: str) -> dict[str, Any] | None:
        """便捷查询并转 dict；不存在返回 None。"""
        op = self.get(operation_id)
        return op.to_dict() if op else None


# 模块级单例
logger = OperationLogger()
