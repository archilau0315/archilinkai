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


# --- 梁跨度水平投影（V0.57） -----------------------------------------------

def _patch_beam_details(monkeypatch, details_by_guid):
    """挂假梁详情：details_by_guid={guid: 整条详情 dict}。"""
    monkeypatch.setattr(
        rules_a, "_fetch_beam_details",
        lambda guids, instance: {g: details_by_guid.get(g) for g in guids
                                 if g in details_by_guid})


def test_beam_span_uses_horizontal_projection(monkeypatch):
    """有起止点时用水平投影跨度：投影 6.2 vs 3D 长度 5.9。"""
    _patch(
        monkeypatch, {"Beam": [_BEAM]},
        {"B1": {"General_Height": 0.5, "General_3DLength": 5.9}},
    )
    _patch_beam_details(monkeypatch, {"B1": {"details": {
        "begCoordinate": {"x": 0.0, "y": 0.0},
        "endCoordinate": {"x": 6.2, "y": 0.0}}}})
    out = rules_a.check_beam_span_ratio(None)  # concrete ≤ 12
    assert len(out) == 1
    assert out[0]["value"] == 12.4  # 6.2 / 0.5，来自投影而非 5.9


def test_beam_span_projection_shortens_slanted_span(monkeypatch):
    """斜梁投影短于 3D 长度时按投影算，不虚高误报。"""
    _patch(
        monkeypatch, {"Beam": [_BEAM]},
        {"B1": {"General_Height": 0.5, "General_3DLength": 7.0}},
    )
    _patch_beam_details(monkeypatch, {"B1": {"details": {
        "begCoordinate": {"x": 0.0, "y": 0.0},
        "endCoordinate": {"x": 5.0, "y": 0.0}}}})
    assert rules_a.check_beam_span_ratio(None) == []  # 5.0/0.5=10 ≤ 12


def test_beam_span_fallback_without_details(monkeypatch):
    """详情缺失（空 dict）时兜底用 General_3DLength。"""
    _patch(
        monkeypatch, {"Beam": [_BEAM]},
        {"B1": {"General_Height": 0.5, "General_3DLength": 6.2}},
    )
    _patch_beam_details(monkeypatch, {})
    out = rules_a.check_beam_span_ratio(None)
    assert len(out) == 1
    assert out[0]["value"] == 12.4  # 6.2 / 0.5，来自 3DLength


def test_beam_span_detail_without_coords_falls_back(monkeypatch):
    """详情无起止点字段时兜底用 General_3DLength。"""
    _patch(
        monkeypatch, {"Beam": [_BEAM]},
        {"B1": {"General_Height": 0.5, "General_3DLength": 6.2}},
    )
    _patch_beam_details(monkeypatch, {"B1": {"details": {"height": 0.5}}})
    out = rules_a.check_beam_span_ratio(None)
    assert len(out) == 1
    assert out[0]["value"] == 12.4


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


# --- 柱长细比按结构类型细分（V0.57） ---------------------------------------

def test_column_slenderness_steel_limit_ok_concrete_violates(monkeypatch):
    """H/W=25：钢结构（≤43）达标，混凝土（≤20）违规。"""
    _patch(
        monkeypatch, {"Column": [_COL]},
        {"C1": {"General_Height": 5.0, "General_Width": 0.2}},
    )
    steel = rules_a.check_column_slenderness(None, structure_type="steel")
    assert steel == []
    concrete = rules_a.check_column_slenderness(None, structure_type="concrete")
    assert len(concrete) == 1
    assert concrete[0]["value"] == 25.0
    assert concrete[0]["limit"] == 20.0


def test_column_slenderness_steel_violation(monkeypatch):
    """H/W=50 > 钢结构限值 43 → 违规。"""
    _patch(
        monkeypatch, {"Column": [_COL]},
        {"C1": {"General_Height": 5.0, "General_Width": 0.1}},
    )
    out = rules_a.check_column_slenderness(None, structure_type="steel")
    assert len(out) == 1
    assert out[0]["value"] == 50.0
    assert out[0]["limit"] == 43.0


def test_column_slenderness_default_is_concrete(monkeypatch):
    """不传 structure_type 时按混凝土限值 20。"""
    _patch(
        monkeypatch, {"Column": [_COL]},
        {"C1": {"General_Height": 5.0, "General_Width": 0.2}},
    )
    out = rules_a.check_column_slenderness(None)
    assert len(out) == 1 and out[0]["limit"] == 20.0


# --- check_wall_slenderness（V0.63 新增） ---------------------------------

def test_wall_slenderness_violation(monkeypatch):
    """墙高 6.0m / 墙厚 0.15m = 40 > 30 → 违规。"""
    _patch(
        monkeypatch,
        {"Wall": [{"guid": "W1", "name": "Q1", "story_index": 0}]},
        {"W1": {"Wall_MaximumHeight": 6.0, "General_Thickness": 0.15}},
    )
    out = rules_a.check_wall_slenderness(None)
    assert len(out) == 1
    assert out[0]["guid"] == "W1"
    assert out[0]["value"] == 40.0
    assert out[0]["limit"] == 30.0
    assert "墙高厚比" in out[0]["rule"]


def test_wall_slenderness_ok(monkeypatch):
    """墙高 3.0m / 墙厚 0.2m = 15 ≤ 30 → 达标。"""
    _patch(
        monkeypatch,
        {"Wall": [{"guid": "W1", "name": "Q1", "story_index": 0}]},
        {"W1": {"Wall_MaximumHeight": 3.0, "General_Thickness": 0.2}},
    )
    assert rules_a.check_wall_slenderness(None) == []


def test_wall_slenderness_missing_prop_skipped(monkeypatch):
    """缺墙高（属性不可用）→ 跳过，不误报。"""
    _patch(
        monkeypatch,
        {"Wall": [{"guid": "W1", "name": "Q1", "story_index": 0}]},
        {"W1": {"General_Thickness": 0.15}},
    )
    assert rules_a.check_wall_slenderness(None) == []


def test_wall_slenderness_zero_thickness_skipped(monkeypatch):
    _patch(
        monkeypatch,
        {"Wall": [{"guid": "W1", "name": "Q1", "story_index": 0}]},
        {"W1": {"Wall_MaximumHeight": 6.0, "General_Thickness": 0.0}},
    )
    assert rules_a.check_wall_slenderness(None) == []


def test_wall_slenderness_no_walls(monkeypatch):
    _patch(monkeypatch, {}, {})
    assert rules_a.check_wall_slenderness(None) == []


# --- check_evacuation_door_width（V0.63 新增） ----------------------------

def test_evacuation_door_width_violation(monkeypatch):
    """疏散门洞口 0.9m → 净宽 0.8m < 0.9m → 违规。"""
    _patch(
        monkeypatch,
        {"Door": [{"guid": "D1", "name": "疏散门-1", "story_index": 0}]},
        {"D1": {"General_Width": 0.9}},
    )
    out = rules_a.check_evacuation_door_width(None)
    assert len(out) == 1
    assert out[0]["guid"] == "D1"
    assert out[0]["value"] == 0.8
    assert out[0]["limit"] == 0.9
    assert "疏散门" in out[0]["rule"]


def test_evacuation_door_width_ok(monkeypatch):
    """疏散门洞口 1.1m → 净宽 1.0m ≥ 0.9m → 达标。"""
    _patch(
        monkeypatch,
        {"Door": [{"guid": "D1", "name": "安全出口", "story_index": 0}]},
        {"D1": {"General_Width": 1.1}},
    )
    assert rules_a.check_evacuation_door_width(None) == []


def test_evacuation_door_non_evac_skipped(monkeypatch):
    """普通房门（名称无疏散关键词）不参与检查，避免误报。"""
    _patch(
        monkeypatch,
        {"Door": [{"guid": "D1", "name": "卫生间门", "story_index": 0}]},
        {"D1": {"General_Width": 0.7}},
    )
    assert rules_a.check_evacuation_door_width(None) == []


def test_evacuation_door_no_doors(monkeypatch):
    _patch(monkeypatch, {}, {})
    assert rules_a.check_evacuation_door_width(None) == []


# --- check_beam_section_width（V0.64 新增，仅混凝土） -----------------------

def test_beam_section_width_violation(monkeypatch):
    """梁宽 0.15m < 0.20m → 违规（默认 concrete）。"""
    _patch(
        monkeypatch, {"Beam": [_BEAM]},
        {"B1": {"General_Width": 0.15, "General_Height": 0.5,
                "General_3DLength": 4.2}},
    )
    out = rules_a.check_beam_section_width(None)
    assert len(out) == 1
    assert out[0]["guid"] == "B1"
    assert out[0]["value"] == 0.15
    assert out[0]["limit"] == 0.20
    assert "梁截面宽度" in out[0]["rule"]


def test_beam_section_width_ok(monkeypatch):
    """梁宽 0.25m ≥ 0.20m → 达标。"""
    _patch(
        monkeypatch, {"Beam": [_BEAM]},
        {"B1": {"General_Width": 0.25, "General_Height": 0.5,
                "General_3DLength": 4.2}},
    )
    assert rules_a.check_beam_section_width(None) == []


def test_beam_section_width_steel_skipped(monkeypatch):
    """钢结构（steel/continuous/any）直接跳过，避免窄翼缘 H 梁误报。"""
    _patch(
        monkeypatch, {"Beam": [_BEAM]},
        {"B1": {"General_Width": 0.15, "General_Height": 0.5,
                "General_3DLength": 4.2}},
    )
    for st in ("steel", "continuous", "any"):
        assert rules_a.check_beam_section_width(None, structure_type=st) == []


def test_beam_section_width_fake_beam_skipped(monkeypatch):
    """装饰段假梁（0.13 宽 × 0.06 高 × 0.17 长）被过滤，不误报。"""
    _patch(
        monkeypatch, {"Beam": [_BEAM]},
        {"B1": {"General_Width": 0.13, "General_Height": 0.06,
                "General_3DLength": 0.17}},
    )
    assert rules_a.check_beam_section_width(None) == []


def test_beam_section_width_fake_beam_by_length_only(monkeypatch):
    """高正常但长度 < 0.5m 的碎梁也跳过。"""
    _patch(
        monkeypatch, {"Beam": [_BEAM]},
        {"B1": {"General_Width": 0.13, "General_Height": 0.5,
                "General_3DLength": 0.3}},
    )
    assert rules_a.check_beam_section_width(None) == []


def test_beam_section_width_missing_prop_skipped(monkeypatch):
    _patch(monkeypatch, {"Beam": [_BEAM]}, {"B1": {}})
    assert rules_a.check_beam_section_width(None) == []


def test_beam_section_width_no_beams(monkeypatch):
    _patch(monkeypatch, {}, {})
    assert rules_a.check_beam_section_width(None) == []


# --- check_beam_aspect_ratio（V0.64 新增，仅混凝土） ------------------------

def test_beam_aspect_ratio_violation(monkeypatch):
    """h/b = 0.9/0.2 = 4.5 > 4 → 违规。"""
    _patch(
        monkeypatch, {"Beam": [_BEAM]},
        {"B1": {"General_Width": 0.2, "General_Height": 0.9,
                "General_3DLength": 5.0}},
    )
    out = rules_a.check_beam_aspect_ratio(None)
    assert len(out) == 1
    assert out[0]["guid"] == "B1"
    assert out[0]["value"] == 4.5
    assert out[0]["limit"] == 4.0
    assert "高宽比" in out[0]["rule"]


def test_beam_aspect_ratio_ok(monkeypatch):
    """h/b = 0.5/0.25 = 2 ≤ 4 → 达标。"""
    _patch(
        monkeypatch, {"Beam": [_BEAM]},
        {"B1": {"General_Width": 0.25, "General_Height": 0.5,
                "General_3DLength": 4.2}},
    )
    assert rules_a.check_beam_aspect_ratio(None) == []


def test_beam_aspect_ratio_steel_skipped(monkeypatch):
    """钢结构直接跳过。"""
    _patch(
        monkeypatch, {"Beam": [_BEAM]},
        {"B1": {"General_Width": 0.2, "General_Height": 0.9,
                "General_3DLength": 5.0}},
    )
    assert rules_a.check_beam_aspect_ratio(None, structure_type="steel") == []


def test_beam_aspect_ratio_fake_beam_skipped(monkeypatch):
    """假梁（0.13 宽 0.06 高 0.17 长）过滤。"""
    _patch(
        monkeypatch, {"Beam": [_BEAM]},
        {"B1": {"General_Width": 0.13, "General_Height": 0.06,
                "General_3DLength": 0.17}},
    )
    assert rules_a.check_beam_aspect_ratio(None) == []


def test_beam_aspect_ratio_missing_prop_skipped(monkeypatch):
    _patch(monkeypatch, {"Beam": [_BEAM]}, {"B1": {}})
    assert rules_a.check_beam_aspect_ratio(None) == []


# --- check_fire_door_rating（V0.64 新增） -----------------------------------

def test_fire_door_rating_missing_violation(monkeypatch):
    """名称含「防火」的门 FireRating 为 null → 违规。"""
    _patch(
        monkeypatch,
        {"Door": [{"guid": "D1", "name": "FM-防火门-1", "story_index": 0}]},
        {"D1": {"WindowDoor_FireRating": None}},
    )
    out = rules_a.check_fire_door_rating(None)
    assert len(out) == 1
    assert out[0]["guid"] == "D1"
    assert "防火门" in out[0]["rule"]


def test_fire_door_rating_empty_string_violation(monkeypatch):
    """FireRating 为空字符串同样判违规。"""
    _patch(
        monkeypatch,
        {"Door": [{"guid": "D1", "name": "防火门-2", "story_index": 0}]},
        {"D1": {"WindowDoor_FireRating": "  "}},
    )
    assert len(rules_a.check_fire_door_rating(None)) == 1


def test_fire_door_rating_ok(monkeypatch):
    """已标耐火等级（甲级）→ 达标。"""
    _patch(
        monkeypatch,
        {"Door": [{"guid": "D1", "name": "防火门-3", "story_index": 0}]},
        {"D1": {"WindowDoor_FireRating": "甲级"}},
    )
    assert rules_a.check_fire_door_rating(None) == []


def test_fire_door_rating_normal_door_skipped(monkeypatch):
    """普通门（名称无防火关键词）不参与检查，避免误报。"""
    _patch(
        monkeypatch,
        {"Door": [{"guid": "D1", "name": "M1022", "story_index": 0}]},
        {"D1": {"WindowDoor_FireRating": None}},
    )
    assert rules_a.check_fire_door_rating(None) == []


def test_fire_door_rating_no_doors(monkeypatch):
    _patch(monkeypatch, {}, {})
    assert rules_a.check_fire_door_rating(None) == []
