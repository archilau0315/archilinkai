"""轻量 i18n 层（V0.52）。

语言来源：环境变量 ALAI_LANG（默认 zh）；仅支持 zh / en。
中文文案保留在源码中作默认值，英文目录外置于 data/i18n.json。
默认 zh 时行为与改造前逐字一致（不影响既有断言）。
"""

from __future__ import annotations

import json
import os
from typing import Any

SUPPORTED = ("zh", "en")
_DEFAULT = "zh"
_OVERRIDE: str | None = None
_CATALOG: dict[str, dict[str, str]] | None = None


def _normalize(lang: str | None) -> str:
    """规范化语言标签：取前两位小写，命中 zh/en 才有效，否则回落默认。"""
    if not lang:
        return _DEFAULT
    code = str(lang).strip().lower()[:2]
    return code if code in SUPPORTED else _DEFAULT


def set_locale(lang: str | None) -> None:
    """显式覆盖语言（供 CLI / 测试）；传 None 清除覆盖，回到读 env。"""
    global _OVERRIDE
    _OVERRIDE = None if lang is None else _normalize(lang)


def get_locale() -> str:
    """当前语言。不缓存，每次读覆盖或 env，避免测试串味。"""
    if _OVERRIDE is not None:
        return _OVERRIDE
    return _normalize(os.environ.get("ALAI_LANG"))


def _catalog() -> dict[str, dict[str, str]]:
    """懒加载并缓存 data/i18n.json。"""
    global _CATALOG
    if _CATALOG is None:
        path = os.path.join(os.path.dirname(__file__), "data", "i18n.json")
        try:
            with open(path, encoding="utf-8") as f:
                _CATALOG = json.load(f)
        except Exception:
            _CATALOG = {}
    return _CATALOG


def reload_catalog() -> None:
    """清缓存，供测试或热更新。"""
    global _CATALOG
    _CATALOG = None


def _fmt(text: str, kw: dict[str, Any]) -> str:
    if not kw:
        return text
    try:
        return text.format(**kw)
    except (KeyError, IndexError, ValueError):
        return text


def t(key: str, default_zh: str, **kw: Any) -> str:
    """取本地化文案。

    zh → 直接返回 default_zh（中文默认已是成品，不做 format）。
    en → 命中目录则用英文模板并 format(**kw)，缺键回退 default_zh。
    """
    if get_locale() == "zh":
        return default_zh
    base = _catalog().get(get_locale(), {}).get(key, default_zh)
    return _fmt(base, kw)


def type_name(element_type: str, default_zh: str) -> str:
    """构件类型显示名（en 目录键 type.<English>）。"""
    return t(f"type.{element_type}", default_zh)


def code_name(zh_name: str, default_zh: str | None = None) -> str:
    """清单项显示名（en 目录键 code_name.<中文名>，同时覆盖 code_table 与 override）。"""
    return t(f"code_name.{zh_name}", default_zh or zh_name)


def template_desc(name: str, default_zh: str) -> str:
    """算量模板描述（en 目录键 template.<模板名>）。"""
    return t(f"template.{name}", default_zh)


def supported_locales() -> list[str]:
    return list(SUPPORTED)


def catalog_size() -> int:
    """已加载的英文条目总数（诊断用）。"""
    return sum(len(v) for v in _catalog().values())
