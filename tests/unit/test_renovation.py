"""renovation_service 单元测试：状态归一化、批量读取、类型×状态统计。"""

from archilinkai import renovation_service as rsvc
from archilinkai import property_service


# --- normalize_status ---------------------------------------------------

def test_normalize_none_and_all():
    assert rsvc.normalize_status(None) is None
    assert rsvc.normalize_status("all") is None
    assert rsvc.normalize_status("ALL") is None
    assert rsvc.normalize_status("") is None


def test_normalize_en_aliases():
    assert rsvc.normalize_status("existing") == "Existing"
    assert rsvc.normalize_status("toBeDemolished") == "ToBeDemolished"
    assert rsvc.normalize_status("demolished") == "ToBeDemolished"
    assert rsvc.normalize_status("new") == "New"
    assert rsvc.normalize_status("undefined") == "Undefined"


def test_normalize_zh_aliases():
    assert rsvc.normalize_status("现有") == "Existing"
    assert rsvc.normalize_status("拆除") == "ToBeDemolished"
    assert rsvc.normalize_status("新建") == "New"
    assert rsvc.normalize_status("未定义") == "Undefined"


def test_normalize_invalid_is_none():
    assert rsvc.normalize_status("bogus") is None


# --- get_status_map ------------------------------------------------------

def _fake_values(mapping):
    def _get(guids, names, instance=None):
        return {
            g: ({rsvc.RENOVATION_PROP: mapping[g]} if g in mapping else {})
            for g in guids
        }
    return _get


def test_status_map_reads_values(monkeypatch):
    monkeypatch.setattr(
        property_service.service, "get_values",
        _fake_values({"g1": "New", "g2": "ToBeDemolished"}),
    )
    m = rsvc.get_status_map(["g1", "g2", "g3"])
    assert m["g1"] == "New"
    assert m["g2"] == "ToBeDemolished"
    # 缺失键补 Undefined
    assert m["g3"] == "Undefined"


def test_status_map_invalid_value_defaults_undefined(monkeypatch):
    monkeypatch.setattr(
        property_service.service, "get_values",
        _fake_values({"g1": "Weird"}),
    )
    assert rsvc.get_status_map(["g1"])["g1"] == "Undefined"


def test_status_map_empty():
    assert rsvc.get_status_map([]) == {}


# --- label ---------------------------------------------------------------

def test_label_uses_status_cn_by_default():
    from archilinkai import i18n
    i18n.set_locale("zh")
    try:
        assert rsvc.label("New") == "新建"
        assert rsvc.label("ToBeDemolished") == "拆除"
    finally:
        i18n.set_locale(None)


def test_label_en_from_catalog():
    from archilinkai import i18n
    i18n.set_locale("en")
    try:
        assert rsvc.label("New") == "New"
    finally:
        i18n.set_locale(None)


# --- summarize -----------------------------------------------------------

def test_summarize_counts_by_type_and_status(monkeypatch):
    from archilinkai import aggregate_service
    base = [
        {"guid": "g1", "element_type": "Wall"},
        {"guid": "g2", "element_type": "Wall"},
        {"guid": "g3", "element_type": "Slab"},
        {"guid": "g4", "element_type": "Slab"},
    ]
    monkeypatch.setattr(
        aggregate_service, "_fetch_all", lambda req, instance: list(base))
    monkeypatch.setattr(
        property_service.service, "get_values",
        _fake_values({"g1": "ToBeDemolished", "g2": "New", "g3": "New"}),
    )
    out = rsvc.summarize()
    assert out["total"] == 4
    assert out["by_status"]["ToBeDemolished"] == 1
    assert out["by_status"]["New"] == 2
    assert out["by_status"]["Undefined"] == 1
    assert out["by_status"]["Existing"] == 0
    assert out["by_type"]["Wall"]["ToBeDemolished"] == 1
    assert out["by_type"]["Wall"]["New"] == 1
    assert out["by_type"]["Slab"]["New"] == 1
    assert out["by_type"]["Slab"]["Undefined"] == 1
    assert out["element_count"] == {"Wall": 2, "Slab": 2}


def test_summarize_fetches_per_element_type(monkeypatch):
    from archilinkai import aggregate_service
    calls = []

    def fake_fetch(req, instance):
        calls.append(req.element_type)
        if req.element_type == "Wall":
            return [{"guid": "g1", "element_type": "Wall"}]
        return [{"guid": "g2", "element_type": "Slab"}]

    monkeypatch.setattr(aggregate_service, "_fetch_all", fake_fetch)
    monkeypatch.setattr(
        property_service.service, "get_values",
        lambda guids, names, instance=None: {g: {} for g in guids},
    )
    out = rsvc.summarize(["Wall", "Slab"])
    assert calls == ["Wall", "Slab"]
    assert out["total"] == 2


# --- 别名注册 -------------------------------------------------------------

def test_alias_registered():
    from archilinkai.property_alias import candidates_for
    assert candidates_for("renovation_status") == ["Category_RenovationStatus"]
