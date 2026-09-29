"""概算表 schema + 定额匹配引擎 单元测试（V0.32）。"""

import pytest

from estimate_schema import create_estimate_item, create_estimate_table
from quota_matcher import QuotaMatcher, extract_specs, convert_unit, similarity


class TestExtractSpecs:
    def test_concrete_grade(self):
        assert extract_specs("C30") == {"强度等级": "C30"}
        assert extract_specs("c25") == {"强度等级": "c25"}

    def test_multiple_specs(self):
        r = extract_specs("现浇混凝土柱 矩形柱 C40 P8")
        assert r["强度等级"] == "C40"
        assert r["抗渗等级"] == "P8"
        assert r["截面类型"] == "矩形"
        assert r["材料"] == "混凝土"
        assert r["施工工艺"] == "现浇"

    def test_insulation(self):
        r = extract_specs("干挂岩棉板 δ50")
        assert r["施工工艺"] == "干挂"

    def test_empty(self):
        assert extract_specs("普通文字") == {}


class TestConvertUnit:
    def test_same_unit(self):
        assert convert_unit(10, "m³", "m³") == 10

    def test_m3_to_10m3(self):
        assert convert_unit(100, "m³", "10m³") == 10

    def test_m2_to_100m2(self):
        assert convert_unit(50, "m²", "100m²") == 0.5

    def test_reverse(self):
        assert convert_unit(10, "10m³", "m³") == 100

    def test_unknown(self):
        # 无法换算时返回原值
        assert convert_unit(10, "m³", "樘") == 10


class TestSimilarity:
    def test_exact(self):
        assert similarity("abc", "abc") == 1.0

    def test_partial(self):
        assert 0 < similarity("abc", "abd") < 1

    def test_different(self):
        assert similarity("abc", "xyz") < 0.5


class TestQuotaMatcher:
    def test_match_basic(self):
        db = [
            {"code": "5-12", "name": "现浇混凝土柱 矩形柱 C40", "unit": "10m³"},
            {"code": "5-13", "name": "现浇混凝土梁 矩形梁 C35", "unit": "10m³"},
        ]
        m = QuotaMatcher(db)
        r = m.match("现浇混凝土柱 C40", "m³", 100)
        assert len(r) == 1
        assert r[0]["quota"]["code"] == "5-12"
        assert r[0]["similarity"] > 0.8
        assert r[0]["converted_quantity"] == 10

    def test_match_with_specs(self):
        db = [
            {"code": "5-12", "name": "柱 C40", "unit": "10m³", "specs": {"强度等级": "C40"}},
            {"code": "5-13", "name": "柱 C30", "unit": "10m³", "specs": {"强度等级": "C30"}},
        ]
        m = QuotaMatcher(db)
        r = m.match("柱 C40", "m³", 100)
        assert r[0]["quota"]["code"] == "5-12"
        assert "强度等级" in r[0]["matched_specs"]

    def test_match_best(self):
        db = [{"code": "5-12", "name": "混凝土柱", "unit": "10m³"}]
        m = QuotaMatcher(db)
        best = m.match_best("混凝土柱", "m³", 100)
        assert best["quota"]["code"] == "5-12"

    def test_no_match(self):
        m = QuotaMatcher([])
        assert m.match("不存在", "m³", 100) == []
        assert m.match_best("不存在", "m³", 100) is None


class TestCreateEstimateItem:
    def test_basic(self):
        item = create_estimate_item("010502001", "墙", "m³", 8.55)
        assert item["code"] == "010502001"
        assert item["name"] == "墙"
        assert item["unit"] == "m³"
        assert item["quantity"] == 8.55
        assert item["unit_price"] is None  # 无价格
        assert item["specs"] == {}

    def test_with_specs(self):
        item = create_estimate_item("010502001", "墙", "m³", 8.55, specs={"强度": "C40"})
        assert item["specs"]["强度"] == "C40"


class TestCreateEstimateTable:
    def test_basic(self):
        items = [create_estimate_item("010502001", "墙", "m³", 8.55)]
        table = create_estimate_table("测试工程", items, region="辽宁")
        assert table["project_name"] == "测试工程"
        assert table["region"] == "辽宁"
        assert table["summary"]["direct_cost"] == 0.0  # 无价格
        assert len(table["items"]) == 1
