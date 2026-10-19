"""property_alias.py 单元测试：候选映射 + AliasResolver。

AliasResolver 的 _exists 依赖真机连接，这里用假 resolver 测候选与缓存逻辑。
"""

from archilinkai.property_alias import (
    PROPERTY_ALIASES,
    AliasResolver,
    candidates_for,
)


# --- candidates_for ------------------------------------------------------

def test_candidates_for_semantic_key():
    assert candidates_for("wall_thickness")[0] == "General_Thickness"
    assert "Wall_Thickness" in candidates_for("wall_thickness")


def test_candidates_for_known_name():
    # 传入候选之一，应返回其所属键的候选，且该名提到最前
    c = candidates_for("Wall_Thickness")
    assert c[0] == "Wall_Thickness"
    assert "General_Thickness" in c


def test_candidates_for_unknown_name():
    assert candidates_for("Foo_Bar") == ["Foo_Bar"]


def test_alias_table_keys_present():
    for key in ("wall_thickness", "opening_width", "stair_flight_width",
                "zone_area"):
        assert key in PROPERTY_ALIASES


# --- AliasResolver -------------------------------------------------------

class _FakeResolver(AliasResolver):
    """重写 _exists，用预设可用名集合模拟真机。"""

    def __init__(self, available):
        super().__init__(mgr=None)
        self._available = set(available)

    def _exists(self, name, instance):
        return name in self._available


def test_resolve_first_candidate():
    r = _FakeResolver({"General_Thickness"})
    assert r.resolve("wall_thickness") == "General_Thickness"


def test_resolve_fallback():
    # 首选不存在，回退到第二个候选
    r = _FakeResolver({"Wall_Thickness"})
    assert r.resolve("wall_thickness") == "Wall_Thickness"


def test_resolve_none_when_all_missing():
    r = _FakeResolver(set())
    assert r.resolve("wall_thickness") is None


def test_resolve_cache_hit():
    r = _FakeResolver({"General_Thickness"})
    assert r.resolve("wall_thickness") == "General_Thickness"
    # 清空可用集合后仍返回缓存结果
    r._available = set()
    assert r.resolve("wall_thickness") == "General_Thickness"


def test_resolve_many():
    r = _FakeResolver({"General_Thickness", "General_Width"})
    out = r.resolve_many(["wall_thickness", "opening_width", "no_such_key"])
    assert out["wall_thickness"] == "General_Thickness"
    assert out["opening_width"] == "General_Width"
    assert out["no_such_key"] is None


def test_describe_marks_fallback():
    r = _FakeResolver({"Wall_Thickness"})
    rep = r.describe(["wall_thickness"])
    assert rep["wall_thickness"]["resolved"] == "Wall_Thickness"
    assert rep["wall_thickness"]["fallback_used"] is True


def test_describe_no_fallback():
    r = _FakeResolver({"General_Thickness"})
    rep = r.describe(["wall_thickness"])
    assert rep["wall_thickness"]["fallback_used"] is False
