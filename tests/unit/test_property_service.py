"""property_service.py 单元测试：validate_and_encode + parse_property_type。

只测纯函数，不连真机（PropertyService 实例方法需 archicad 连接）。
"""

import pytest

from errors import PropertyTypeMismatchError, PropertyTypeUnknownError
from property_service import (
    PropertyType,
    parse_property_type,
    validate_and_encode,
)


# --- validate_and_encode：各类型 ----------------------------------------


def test_string():
    assert validate_and_encode(PropertyType.STRING, "hello") == "hello"
    assert validate_and_encode(PropertyType.STRING, 123) == "123"


def test_integer():
    assert validate_and_encode(PropertyType.INTEGER, 5) == "5"
    assert validate_and_encode(PropertyType.INTEGER, "7") == "7"


def test_integer_rejects_bool():
    with pytest.raises(PropertyTypeMismatchError):
        validate_and_encode(PropertyType.INTEGER, True, "Count")


def test_integer_rejects_non_numeric():
    with pytest.raises(PropertyTypeMismatchError):
        validate_and_encode(PropertyType.INTEGER, "abc", "Count")


def test_float_and_length_area_volume_angle():
    assert validate_and_encode(PropertyType.FLOAT, "3.14") == "3.14"
    assert validate_and_encode(PropertyType.LENGTH, 600) == "600.0"
    assert validate_and_encode(PropertyType.AREA, "12.5") == "12.5"
    assert validate_and_encode(PropertyType.VOLUME, 2) == "2.0"
    assert validate_and_encode(PropertyType.ANGLE, "90") == "90.0"


def test_length_rejects_non_numeric():
    with pytest.raises(PropertyTypeMismatchError):
        validate_and_encode(PropertyType.LENGTH, "wide", "Depth")


def test_boolean_true_false():
    assert validate_and_encode(PropertyType.BOOLEAN, True) == "true"
    assert validate_and_encode(PropertyType.BOOLEAN, False) == "false"
    assert validate_and_encode(PropertyType.BOOLEAN, "True") == "true"


def test_boolean_rejects_invalid():
    with pytest.raises(PropertyTypeMismatchError):
        validate_and_encode(PropertyType.BOOLEAN, "maybe", "Flag")


def test_enum_accepts_string():
    assert validate_and_encode(PropertyType.ENUM, "A") == "A"


def test_enum_rejects_empty():
    with pytest.raises(PropertyTypeMismatchError):
        validate_and_encode(PropertyType.ENUM, "", "Class")


def test_date_rejects_empty():
    with pytest.raises(PropertyTypeMismatchError):
        validate_and_encode(PropertyType.DATE, "", "Date")


def test_unknown_type_rejects():
    """类型未知必须拒绝执行，不猜测转换（V0.3 8.6）。"""
    with pytest.raises(PropertyTypeUnknownError):
        validate_and_encode(PropertyType.UNKNOWN, "x", "Mystery")


# --- parse_property_type：尽力兼容各种定义对象 --------------------------


class _Def:
    """模拟 archicad 属性定义对象。"""

    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_parse_string_variants():
    assert parse_property_type(_Def(type="string")) == PropertyType.STRING
    assert parse_property_type(_Def(type="Text")) == PropertyType.STRING


def test_parse_number_variants():
    assert parse_property_type(_Def(type="integer")) == PropertyType.INTEGER
    assert parse_property_type(_Def(type="number")) == PropertyType.FLOAT
    assert parse_property_type(_Def(type="real")) == PropertyType.FLOAT
    assert parse_property_type(_Def(type="double")) == PropertyType.FLOAT


def test_parse_boolean_enum():
    assert parse_property_type(_Def(type="boolean")) == PropertyType.BOOLEAN
    assert parse_property_type(_Def(type="bool")) == PropertyType.BOOLEAN
    assert parse_property_type(_Def(type="enum")) == PropertyType.ENUM
    assert parse_property_type(_Def(type="enumeration")) == PropertyType.ENUM


def test_parse_length_area_volume_angle():
    assert parse_property_type(_Def(type="length")) == PropertyType.LENGTH
    assert parse_property_type(_Def(type="area")) == PropertyType.AREA
    assert parse_property_type(_Def(type="volume")) == PropertyType.VOLUME
    assert parse_property_type(_Def(type="angle")) == PropertyType.ANGLE


def test_parse_unknown_type_field():
    assert parse_property_type(_Def(type="Mystery")) == PropertyType.UNKNOWN


# --- 缓存与定义查询（V0.17，mock 连接）--------------------------------------


class _FakeTypes:
    class BuiltInPropertyUserId:
        def __init__(self, nonLocalizedName):
            self.nonLocalizedName = nonLocalizedName


class _FakeCommands:
    def __init__(self):
        self.calls = 0
        self._def = _Def(
            type="enum", name="结构类型", description="d",
            possibleEnumValues=[
                _Def(displayValue="承重"), _Def(displayValue="非承重"),
            ],
        )

    def GetPropertyIds(self, uids):
        self.calls += 1
        # 模拟"不存在的属性"：返回无 propertyId 的 ErrorItem
        if uids[0].nonLocalizedName == "不存在的属性":
            return [_Def(error={"code": -1})]
        return [_Def(propertyId=_Def(guid="x"))]

    def GetDetailsOfProperties(self, ids):
        return [_Def(propertyDefinition=self._def)]

    def GetAllPropertyNames(self):
        return []


class _FakeConn:
    def __init__(self):
        self.types = _FakeTypes()
        self.commands = _FakeCommands()


class _FakeMgr:
    def __init__(self, conn):
        self._conn = conn

    def get_conn(self, instance=None):
        return self._conn


@pytest.fixture()
def fake_service():
    from property_service import PropertyService
    conn = _FakeConn()
    return PropertyService(_FakeMgr(conn)), conn


def test_resolve_user_id_cached(fake_service):
    svc, conn = fake_service
    svc._resolve_user_id("结构类型", "inst")
    svc._resolve_user_id("结构类型", "inst")
    assert conn.commands.calls == 1  # 第二次走缓存


def test_property_type_cached(fake_service):
    svc, conn = fake_service
    t1 = svc.get_property_type("结构类型", "inst")
    calls_after_first = conn.commands.calls
    t2 = svc.get_property_type("结构类型", "inst")
    assert t1 == t2 == PropertyType.ENUM
    assert conn.commands.calls == calls_after_first


def test_get_property_definition_enum(fake_service):
    svc, _ = fake_service
    d = svc.get_property_definition("结构类型", "inst")
    assert d["type"] == "enum"
    assert d["enum_options"] == ["承重", "非承重"]


def test_get_property_definition_missing(fake_service):
    svc, _ = fake_service
    assert svc.get_property_definition("不存在的属性", "inst") is None


def test_parse_missing_type_field():
    assert parse_property_type(_Def(name="NoType")) == PropertyType.UNKNOWN


def test_parse_none():
    assert parse_property_type(None) == PropertyType.UNKNOWN


def test_parse_dict_input():
    """支持 dict 形式的定义（部分版本返回 dict）。"""
    assert parse_property_type({"type": "integer"}) == PropertyType.INTEGER


def test_parse_enum_object_with_name():
    """type 字段是带 name 的对象（如 EnumType）。"""

    class _EnumType:
        name = "enum"

    assert parse_property_type(_Def(type=_EnumType())) == PropertyType.ENUM
