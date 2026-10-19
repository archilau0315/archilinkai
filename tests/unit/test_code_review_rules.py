"""code_review_rules_a 新增规则单元测试（V0.53）。

mock _fetch_elements 与 _get_props，不依赖真机连接。
"""

from archilinkai import code_review_rules_a as rules_a


def _patch(monkeypatch, elements_by_type, props):
    """挂假数据：elements_by_type={类型: [元素]}，props={guid: {属性: 值}}。"""
    monkeypatch.setattr(
        rules_a, "_fetch_elements",
        lambda etype, instance: elements_by_type.get(etype, []))
    monkeypatch.setattr(
        rules_a, "_get_props",
        lambda guids, names, instance: {g: props.get(g, {}) for g in guids})


# --- check_slab_thickness -------------------------------------------------

def test_slab_thickness_violation(monkeypatch):
    _patch(
        monkeypatch,
        {"Slab": [{"guid": "S1", "name": "Slab-1", "story_index": 0}]},
        {"S1": {"General_Thickness": 0.08}},
    )
    out = rules_a.check_slab_thickness(None)
    assert len(out) == 1
    assert out[0]["guid"] == "S1"
    assert out[0]["value"] == 0.08
    assert out[0]["limit"] == 0.10
    assert "楼板厚度不足" in out[0]["rule"]


def test_slab_thickness_ok(monkeypatch):
    _patch(
        monkeypatch,
        {"Slab": [{"guid": "S1", "name": "Slab-1", "story_index": 0}]},
        {"S1": {"General_Thickness": 0.12}},
    )
    assert rules_a.check_slab_thickness(None) == []


def test_slab_thickness_no_slabs(monkeypatch):
    _patch(monkeypatch, {}, {})
    assert rules_a.check_slab_thickness(None) == []


def test_slab_thickness_missing_prop_skipped(monkeypatch):
    _patch(
        monkeypatch,
        {"Slab": [{"guid": "S1", "name": "Slab-1", "story_index": 0}]},
        {"S1": {}},
    )
    assert rules_a.check_slab_thickness(None) == []


# --- check_bearing_wall_thickness ------------------------------------------

_WALLS = [
    {"guid": "W1", "name": "Wall-Ext", "story_index": 0},
    {"guid": "W2", "name": "Wall-Int", "story_index": 0},
]


def test_bearing_wall_external_violation(monkeypatch):
    """外墙（General_External=True）且厚 0.15 < 0.18 → 违规。"""
    _patch(
        monkeypatch, {"Wall": _WALLS},
        {"W1": {"General_External": True, "General_Thickness": 0.15}},
    )
    out = rules_a.check_bearing_wall_thickness(None)
    assert len(out) == 1
    assert out[0]["guid"] == "W1"
    assert out[0]["value"] == 0.15
    assert out[0]["limit"] == 0.18
    assert "承重/外墙厚度不足" in out[0]["rule"]


def test_bearing_wall_inner_wall_no_violation(monkeypatch):
    """内墙（External=False）即使很薄也不在本规则违规。"""
    _patch(
        monkeypatch, {"Wall": _WALLS},
        {"W2": {"General_External": False, "General_Thickness": 0.10}},
    )
    assert rules_a.check_bearing_wall_thickness(None) == []


def test_bearing_wall_missing_prop_no_violation(monkeypatch):
    """外墙属性全部缺失时不误报。"""
    _patch(
        monkeypatch, {"Wall": _WALLS},
        {"W1": {"General_Thickness": 0.10}},
    )
    assert rules_a.check_bearing_wall_thickness(None) == []


def test_bearing_wall_string_external_values(monkeypatch):
    """字符串型外墙标记："是"/"Yes" 判真，"否" 判假。"""
    walls = [
        {"guid": "W1", "name": "A", "story_index": 0},
        {"guid": "W2", "name": "B", "story_index": 0},
        {"guid": "W3", "name": "C", "story_index": 0},
    ]
    _patch(
        monkeypatch, {"Wall": walls},
        {
            "W1": {"Wall_External": "是", "General_Thickness": 0.10},
            "W2": {"Wall_External": "Yes", "General_Thickness": 0.20},
            "W3": {"Wall_External": "否", "General_Thickness": 0.10},
        },
    )
    out = rules_a.check_bearing_wall_thickness(None)
    assert [v["guid"] for v in out] == ["W1"]


def test_bearing_wall_numeric_external(monkeypatch):
    """数字型外墙标记：非 0 判真。"""
    _patch(
        monkeypatch, {"Wall": _WALLS},
        {"W1": {"General_External": 1, "General_Thickness": 0.12}},
    )
    out = rules_a.check_bearing_wall_thickness(None)
    assert len(out) == 1 and out[0]["guid"] == "W1"


def test_bearing_wall_external_ok_thickness(monkeypatch):
    """外墙厚度达标不违规。"""
    _patch(
        monkeypatch, {"Wall": _WALLS},
        {"W1": {"General_External": True, "General_Thickness": 0.20}},
    )
    assert rules_a.check_bearing_wall_thickness(None) == []


def test_bearing_wall_no_walls(monkeypatch):
    _patch(monkeypatch, {}, {})
    assert rules_a.check_bearing_wall_thickness(None) == []


# --- check_column_section（V0.54） -----------------------------------------

_COL = {"guid": "C1", "name": "Column-1", "story_index": 0}


def test_column_section_violation(monkeypatch):
    """截面宽 0.25 < 0.3 → 一条违规（仅宽度侧，见规则 docstring）。"""
    _patch(
        monkeypatch, {"Column": [_COL]},
        {"C1": {"General_Width": 0.25, "General_Height": 3.0}},
    )
    out = rules_a.check_column_section(None)
    assert len(out) == 1
    assert out[0]["guid"] == "C1"
    assert out[0]["value"] == 0.25
    assert out[0]["limit"] == 0.30
    assert "柱截面不足" in out[0]["rule"]


def test_column_section_ok(monkeypatch):
    _patch(
        monkeypatch, {"Column": [_COL]},
        {"C1": {"General_Width": 0.35, "General_Height": 3.0}},
    )
    assert rules_a.check_column_section(None) == []


def test_column_section_missing_prop_skipped(monkeypatch):
    _patch(monkeypatch, {"Column": [_COL]}, {"C1": {}})
    assert rules_a.check_column_section(None) == []


def test_column_section_fake_column_skipped(monkeypatch):
    """story<0 或 height<0.5m 的假柱应跳过。"""
    fake_cols = [
        {"guid": "CF1", "name": "Anchor", "story_index": -1},
        {"guid": "CF2", "name": "Anchor-2", "story_index": 0},
    ]
    _patch(
        monkeypatch, {"Column": fake_cols},
        {
            "CF1": {"General_Width": 0.1, "General_Height": 0.05},
            "CF2": {"General_Width": 0.1, "General_Height": 0.3},
        },
    )
    assert rules_a.check_column_section(None) == []


# --- check_beam_span_ratio（V0.54 → V0.55 框架化） -------------------------

_BEAM = {"guid": "B1", "name": "Beam-1", "story_index": 0}


def test_beam_span_ratio_concrete_violation(monkeypatch):
    """混凝土（默认）：span/h=15 > 12 → 违规。"""
    _patch(
        monkeypatch, {"Beam": [_BEAM]},
        {"B1": {"General_Height": 0.28, "General_3DLength": 4.2}},
    )
    out = rules_a.check_beam_span_ratio(None)  # 默认 concrete
    assert len(out) == 1
    assert out[0]["guid"] == "B1"
    assert out[0]["value"] == 15.0  # 4.2 / 0.28
    assert out[0]["limit"] == 12.0
    assert "梁跨高比超限" in out[0]["rule"]


def test_beam_span_ratio_concrete_ok(monkeypatch):
    """混凝土：span/h=10 ≤ 12 → 达标。"""
    _patch(
        monkeypatch, {"Beam": [_BEAM]},
        {"B1": {"General_Height": 0.42, "General_3DLength": 4.2}},
    )
    assert rules_a.check_beam_span_ratio(None) == []


def test_beam_span_ratio_steel_ok(monkeypatch):
    """钢结构：span/h=13 ≤ 60 → 达标（V0.55 消除钢结构误报）。"""
    _patch(
        monkeypatch, {"Beam": [_BEAM]},
        {"B1": {"General_Height": 0.32, "General_3DLength": 4.16}},
    )
    out = rules_a.check_beam_span_ratio(None, structure_type="steel")
    assert out == []


def test_beam_span_ratio_steel_violation(monkeypatch):
    """钢结构：span/h=70 > 60 → 违规。"""
    _patch(
        monkeypatch, {"Beam": [_BEAM]},
        {"B1": {"General_Height": 0.08, "General_3DLength": 5.6}},
    )
    out = rules_a.check_beam_span_ratio(None, structure_type="steel")
    assert len(out) == 1
    assert out[0]["value"] == 70.0
    assert out[0]["limit"] == 60.0


def test_beam_span_ratio_continuous(monkeypatch):
    """钢结构连续梁：span/h=50 > 40 → 违规。"""
    _patch(
        monkeypatch, {"Beam": [_BEAM]},
        {"B1": {"General_Height": 0.1, "General_3DLength": 5.0}},
    )
    out = rules_a.check_beam_span_ratio(None, structure_type="continuous")
    assert len(out) == 1
    assert out[0]["limit"] == 40.0


def test_beam_span_ratio_any_skipped(monkeypatch):
    """structure_type="any" → 直接跳过返回空。"""
    _patch(
        monkeypatch, {"Beam": [_BEAM]},
        {"B1": {"General_Height": 0.05, "General_3DLength": 5.0}},
    )
    assert rules_a.check_beam_span_ratio(None, structure_type="any") == []


def test_beam_span_ratio_zero_span_skipped(monkeypatch):
    _patch(
        monkeypatch, {"Beam": [_BEAM]},
        {"B1": {"General_Height": 0.1, "General_3DLength": 0}},
    )
    assert rules_a.check_beam_span_ratio(None) == []


def test_beam_span_ratio_missing_prop_skipped(monkeypatch):
    _patch(monkeypatch, {"Beam": [_BEAM]}, {"B1": {}})
    assert rules_a.check_beam_span_ratio(None) == []


# --- check_column_slenderness（V0.55 新增） -------------------------------

def test_column_slenderness_violation(monkeypatch):
    """H=5.0m, W=0.2m → ratio=25 > 20 → 违规。"""
    _patch(
        monkeypatch, {"Column": [_COL]},
        {"C1": {"General_Height": 5.0, "General_Width": 0.2}},
    )
    out = rules_a.check_column_slenderness(None)
    assert len(out) == 1
    assert out[0]["guid"] == "C1"
    assert out[0]["value"] == 25.0
    assert out[0]["limit"] == 20.0
    assert "柱长细比过大" in out[0]["rule"]


def test_column_slenderness_ok(monkeypatch):
    """H=3.6m, W=0.2m → ratio=18 ≤ 20 → 达标。"""
    _patch(
        monkeypatch, {"Column": [_COL]},
        {"C1": {"General_Height": 3.6, "General_Width": 0.2}},
    )
    assert rules_a.check_column_slenderness(None) == []


def test_column_slenderness_fake_column_skipped(monkeypatch):
    """story=-1 锚栓标记 + height=0.05m 的假柱应跳过。"""
    fake_cols = [
        {"guid": "CF1", "name": "Anchor", "story_index": -1},
        {"guid": "CF2", "name": "Anchor-2", "story_index": 0},
    ]
    _patch(
        monkeypatch, {"Column": fake_cols},
        {
            "CF1": {"General_Height": 0.05, "General_Width": 0.02},
            "CF2": {"General_Height": 0.05, "General_Width": 0.02},
        },
    )
    assert rules_a.check_column_slenderness(None) == []


def test_column_slenderness_missing_prop_skipped(monkeypatch):
    _patch(monkeypatch, {"Column": [_COL]}, {"C1": {}})
    assert rules_a.check_column_slenderness(None) == []


def test_column_slenderness_zero_width_skipped(monkeypatch):
    _patch(
        monkeypatch, {"Column": [_COL]},
        {"C1": {"General_Height": 4.0, "General_Width": 0}},
    )
    assert rules_a.check_column_slenderness(None) == []


def test_column_slenderness_no_columns(monkeypatch):
    _patch(monkeypatch, {}, {})
    assert rules_a.check_column_slenderness(None) == []
