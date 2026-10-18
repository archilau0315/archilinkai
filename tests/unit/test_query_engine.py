"""query_engine.py 单元测试：apply_operator 9 种操作符 + cursor round-trip。

只测纯函数，不连真机（QueryEngine.query 需 archicad 实例，留给集成测试）。
"""

import pytest

from archilinkai.errors import PaginationInvalidError
from archilinkai.query_engine import (
    _normalize,
    _to_number,
    apply_operator,
    decode_cursor,
    encode_cursor,
)
from archilinkai.schemas import Operator


# --- apply_operator：9 种操作符 -------------------------------------------


def test_eq_string():
    assert apply_operator("A", Operator.EQ, "A") is True
    assert apply_operator("A", Operator.EQ, "B") is False


def test_eq_numeric_string_normalized():
    """数值字符串应归一化比较：'5' == 5。"""
    assert apply_operator("5", Operator.EQ, 5) is True


def test_ne():
    assert apply_operator("A", Operator.NE, "B") is True
    assert apply_operator("A", Operator.NE, "A") is False


def test_gt_ge_lt_le():
    assert apply_operator(20, Operator.GT, 3) is True
    assert apply_operator(3, Operator.GT, 20) is False
    assert apply_operator(20, Operator.GE, 20) is True
    assert apply_operator(19, Operator.GE, 20) is False
    assert apply_operator(3, Operator.LT, 20) is True
    assert apply_operator(20, Operator.LT, 3) is False
    assert apply_operator(20, Operator.LE, 20) is True
    assert apply_operator(21, Operator.LE, 20) is False


def test_numeric_string_comparison():
    """'20' > '3' 应为 True（转 float 比较）。"""
    assert apply_operator("20", Operator.GT, "3") is True


def test_contains_case_insensitive():
    assert apply_operator("Fire Rating A", Operator.CONTAINS, "a") is True
    assert apply_operator("Fire Rating A", Operator.CONTAINS, "B") is False


def test_starts_with():
    assert apply_operator("FireRating", Operator.STARTS_WITH, "fire") is True
    assert apply_operator("RatingFire", Operator.STARTS_WITH, "fire") is False


def test_in_with_list():
    assert apply_operator("A", Operator.IN, ["A", "B"]) is True
    assert apply_operator("C", Operator.IN, ["A", "B"]) is False


def test_in_with_scalar():
    assert apply_operator("A", Operator.IN, "A") is True


def test_gt_non_numeric_returns_false():
    """非数值比较应保守返回 False，不抛异常。"""
    assert apply_operator("abc", Operator.GT, "xyz") is False


# --- cursor round-trip --------------------------------------------------


def test_encode_decode_cursor_roundtrip():
    for offset in (0, 1, 100, 9999):
        cursor = encode_cursor(offset)
        assert decode_cursor(cursor) == offset


def test_decode_cursor_none_is_zero():
    assert decode_cursor(None) == 0


def test_decode_cursor_invalid_raises():
    with pytest.raises(PaginationInvalidError):
        decode_cursor("not-a-valid-cursor")


def test_decode_cursor_negative_offset_raises():
    """构造非法 offset 的 cursor 应被拒。"""
    import base64
    import json
    bad = base64.urlsafe_b64encode(
        json.dumps({"o": -5}).encode()
    ).decode()
    with pytest.raises(PaginationInvalidError):
        decode_cursor(bad)


# --- 辅助函数 ------------------------------------------------------------


def test_to_number_handles_types():
    assert _to_number(5) == 5.0
    assert _to_number("3.14") == 3.14
    assert _to_number("abc") is None
    assert _to_number(True) is None  # bool 不当数字


def test_normalize_string_and_number():
    assert _normalize("  5 ") == 5.0
    assert _normalize("Hello") == "hello"
    assert _normalize(3.14) == 3.14
