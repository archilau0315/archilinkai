"""算量规则公式安全求值（V0.25）。

用 Python ast 模块解析表达式，只允许 + - * / 四则运算、数字、变量名。
变量名即 BuiltIn 量名（如 General_NetVolume），求值时从 vars 字典取值。
任意一项参与运算的值为 None，结果为 None（跳过该构件）。
"""

from __future__ import annotations

import ast
import operator as _op

#: 支持的二元运算
_OPS = {
    ast.Add: _op.add,
    ast.Sub: _op.sub,
    ast.Mult: _op.mul,
    ast.Div: _op.truediv,
}


def formula_vars(expr: str) -> list[str]:
    """提取公式中引用的变量名（量名），按出现顺序去重。"""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        raise ValueError(f"公式语法错误：{expr}")
    names: list[str] = []
    seen: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in seen:
            seen.add(node.id)
            names.append(node.id)
    return names


def eval_formula(expr: str, variables: dict[str, float | None]) -> float | None:
    """安全求值。variables 为变量名→数值映射，缺失或 None 视为跳过。

    只支持 + - * / 和数字字面量、变量引用。其余操作一律拒绝。
    """
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        raise ValueError(f"公式语法错误：{expr}")

    def _ev(node):
        if isinstance(node, ast.Expression):
            return _ev(node.body)
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            left = _ev(node.left)
            right = _ev(node.right)
            if left is None or right is None:
                return None
            return _OPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            val = _ev(node.operand)
            if val is None:
                return None
            return -val if isinstance(node.op, ast.USub) else val
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name):
            return variables.get(node.id)
        raise ValueError(f"公式不支持的表达式节点：{type(node).__name__}")

    return _ev(tree)
