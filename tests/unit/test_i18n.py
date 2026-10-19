"""i18n 单元测试：语言归一化、目录命中/回退、默认中文逐字不变。"""

import pytest

from archilinkai import i18n


@pytest.fixture(autouse=True)
def _reset_locale(monkeypatch):
    """每个用例前后清空覆盖与 env，避免语言状态串味。"""
    monkeypatch.delenv("ALAI_LANG", raising=False)
    i18n.set_locale(None)
    yield
    i18n.set_locale(None)


def test_default_locale_is_zh():
    assert i18n.get_locale() == "zh"


def test_env_en():
    assert i18n.get_locale() == "zh"
    for value in ("en", "EN", "en-US", " en "):
        i18n.set_locale(None)
        _set_env(value)
        assert i18n.get_locale() == "en", value


def test_env_invalid_falls_back_zh():
    for value in ("fr", "jp", "xx", ""):
        i18n.set_locale(None)
        _set_env(value)
        assert i18n.get_locale() == "zh", value


def test_set_locale_override():
    i18n.set_locale("en")
    assert i18n.get_locale() == "en"
    i18n.set_locale("zh")
    assert i18n.get_locale() == "zh"
    i18n.set_locale(None)
    assert i18n.get_locale() == "zh"


def test_zh_returns_default_verbatim():
    """zh 直接返回中文默认，不做 format（含花括号也不报错）。"""
    raw = "总量 {sum}，含 {k:v} 键"
    assert i18n.t("any.key", raw) == raw
    assert i18n.t("any.key", raw, **{"sum": "1"}) == raw


def test_en_hits_catalog():
    i18n.set_locale("en")
    assert i18n.t("type.Wall", "墙") == "Wall"
    assert i18n.t("type.Beam", "梁") == "Beam"
    assert i18n.t("material.混凝土", "混凝土") == "Concrete"
    assert i18n.t("review.wall_thickness.rule", "墙厚不足") == \
        "Insufficient wall thickness"


def test_en_missing_key_falls_back_to_zh():
    i18n.set_locale("en")
    assert i18n.t("no.such.key", "回退中文") == "回退中文"


def test_en_format_substitutes_kwargs():
    i18n.set_locale("en")
    got = i18n.t("error.INSTANCE_NOT_FOUND", "中文默认",
                 instance="a1", avail="b2")
    assert got == "Instance 'a1' not found. Available: b2"


def test_en_missing_format_arg_returns_template():
    """模板占位符缺参时原样返回，不抛异常。"""
    i18n.set_locale("en")
    got = i18n.t("error.INSTANCE_NOT_FOUND", "中文默认")
    assert isinstance(got, str) and "instance" in got


def test_helpers_zh_unchanged():
    assert i18n.type_name("Wall", "墙") == "墙"
    assert i18n.code_name("现浇混凝土板") == "现浇混凝土板"
    assert i18n.template_desc("custom", "自定义模板") == "自定义模板"


def test_helpers_en():
    i18n.set_locale("en")
    assert i18n.type_name("Wall", "墙") == "Wall"
    assert i18n.code_name("现浇混凝土板") == "Cast-in-place Concrete Slab"
    assert i18n.template_desc("custom", "自定义模板") == "Custom template"


def test_supported_locales_and_catalog_size():
    assert i18n.supported_locales() == ["zh", "en"]
    assert i18n.catalog_size() > 0


def test_catalog_groups_present():
    """英文目录应覆盖各主要分组（类型/清单名/材料/审查/错误）。"""
    catalog = i18n._catalog().get("en", {})
    groups = ("type.", "code_name.", "material.", "review.", "error.")
    for prefix in groups:
        assert any(k.startswith(prefix) for k in catalog), prefix


def _set_env(value: str) -> None:
    import os
    os.environ["ALAI_LANG"] = value
