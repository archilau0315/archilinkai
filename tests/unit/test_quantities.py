"""get_quantities 单元测试：不连真机，mock get_values/get_property_type。"""

import pytest

from archilinkai.property_service import PropertyService, PropertyType


@pytest.fixture()
def svc(monkeypatch):
    s = PropertyService(mgr=None)

    def fake_values(guids, names, instance=None):
        data = {
            "g1": {"General_GrossVolume": 10.4, "General_Height": 3.0},
            "g2": {"General_GrossVolume": 2.0},
        }
        return {g: dict(data.get(g, {})) for g in guids}

    monkeypatch.setattr(s, "get_values", fake_values)
    monkeypatch.setattr(
        s, "get_property_type",
        lambda name, instance=None: {
            "General_GrossVolume": PropertyType.VOLUME,
            "General_Height": PropertyType.LENGTH,
        }[name],
    )
    return s


def test_quantities_have_value_and_unit(svc):
    out = svc.get_quantities(
        ["g1"], ["General_GrossVolume", "General_Height"])
    assert out["g1"]["General_GrossVolume"] == {"value": 10.4, "unit": "m³"}
    assert out["g1"]["General_Height"] == {"value": 3.0, "unit": "m"}


def test_missing_quantity_value_is_none(svc):
    out = svc.get_quantities(
        ["g2"], ["General_GrossVolume", "General_Height"])
    assert out["g2"]["General_GrossVolume"]["value"] == 2.0
    assert out["g2"]["General_Height"] == {"value": None, "unit": "m"}


def test_every_guid_present_even_empty(svc):
    out = svc.get_quantities(["g9"], ["General_Height"])
    assert "g9" in out
    assert out["g9"]["General_Height"]["value"] is None
