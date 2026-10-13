"""tapir_adapter.py 单元测试：_to_dict 对象转换纯函数。

TapirAdapter.execute 需 archicad 连接，留给集成测试。
"""

from dataclasses import dataclass

from tapir_adapter import _to_dict


# --- 基础类型原样返回 --------------------------------------------------


def test_none():
    assert _to_dict(None) is None


def test_primitives():
    assert _to_dict("hello") == "hello"
    assert _to_dict(42) == 42
    assert _to_dict(3.14) == 3.14
    assert _to_dict(True) is True
    assert _to_dict(False) is False


# --- 容器递归 ----------------------------------------------------------


def test_dict_recursive():
    out = _to_dict({"a": 1, "b": {"c": 2}})
    assert out == {"a": 1, "b": {"c": 2}}


def test_list_recursive():
    assert _to_dict([1, "x", {"k": "v"}]) == [1, "x", {"k": "v"}]


def test_tuple_becomes_list():
    """元组在 JSON 序列化上等同 list，便于统一处理。"""
    out = _to_dict((1, 2, 3))
    assert out == [1, 2, 3]


def test_nested_mixed():
    out = _to_dict({"items": [{"guid": "A"}], "count": 1})
    assert out == {"items": [{"guid": "A"}], "count": 1}


# --- 对象转换 ----------------------------------------------------------


def test_object_with_dict():
    class Obj:
        def __init__(self):
            self.name = "Wall"
            self.guid = "A1"

    out = _to_dict(Obj())
    assert out == {"name": "Wall", "guid": "A1"}


def test_dataclass_conversion():
    @dataclass
    class Detail:
        type: str
        floorIndex: int

    out = _to_dict(Detail(type="Wall", floorIndex=3))
    assert out == {"type": "Wall", "floorIndex": 3}


def test_object_with_none_dict_falls_back_to_str():
    """无 __dict__ 或为空时兜底为 str。"""

    class Empty:
        __dict__ = {}

    out = _to_dict(Empty())
    assert isinstance(out, str)


def test_object_in_list():
    class Item:
        def __init__(self, guid):
            self.guid = guid

    out = _to_dict([Item("A"), Item("B")])
    assert out == [{"guid": "A"}, {"guid": "B"}]


def test_deeply_nested_object():
    class Leaf:
        def __init__(self, value):
            self.value = value

    class Root:
        def __init__(self):
            self.leaf = Leaf("x")
            self.items = [Leaf("a"), Leaf("b")]

    out = _to_dict(Root())
    assert out == {
        "leaf": {"value": "x"},
        "items": [{"value": "a"}, {"value": "b"}],
    }


# --- get_attributes ----------------------------------------------------


def test_get_attributes_layers(monkeypatch):
    """GetAttributes Layer：dict 返回取 attributes 键。"""
    import tapir_adapter

    fake = {
        "attributes": [
            {"attributeId": {"guid": "L1"}, "name": "结构"},
            {"attributeId": {"guid": "L2"}, "name": "隔墙"},
        ]
    }
    monkeypatch.setattr(
        tapir_adapter.adapter, "execute",
        lambda cmd, params, instance: fake)
    rows = tapir_adapter.adapter.get_attributes("Layer", "ac28-1")
    assert len(rows) == 2
    assert rows[0]["name"] == "结构"
    assert rows[0]["attributeId"]["guid"] == "L1"


def test_get_attributes_empty(monkeypatch):
    """无该类型属性时返回空列表。"""
    import tapir_adapter

    monkeypatch.setattr(
        tapir_adapter.adapter, "execute",
        lambda cmd, params, instance: {"attributes": []})
    assert tapir_adapter.adapter.get_attributes("Pen") == []


def test_get_attributes_passes_command_and_type(monkeypatch):
    """校验命令名与 attributeType 参数透传正确。"""
    import tapir_adapter

    calls = {}

    def _fake(cmd, params, instance):
        calls["cmd"] = cmd
        calls["params"] = params
        return {"attributes": []}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    tapir_adapter.adapter.get_attributes("Composite", "ac29-1")
    assert calls["cmd"] == "GetAttributesByType"
    assert calls["params"] == {"attributeType": "Composite"}


# --- get_available_library_parts ----------------------------------------


def test_get_available_library_parts_all(monkeypatch):
    """无 filterByTypeId 时返回全部库部件。"""
    import tapir_adapter

    fake = {
        "libraryParts": [
            {"guid": "P1", "index": 1, "documentName": "门1", "fileName": "D1.gsm", "typeId": "Door"},
            {"guid": "P2", "index": 2, "documentName": "窗1", "fileName": "W1.gsm", "typeId": "Window"},
        ],
        "skippedCount": 0,
        "skippedSample": [],
    }
    monkeypatch.setattr(
        tapir_adapter.adapter, "execute",
        lambda cmd, params, instance: fake)
    out = tapir_adapter.adapter.get_available_library_parts()
    assert len(out["libraryParts"]) == 2
    assert out["skippedCount"] == 0


def test_get_available_library_parts_filtered(monkeypatch):
    """filterByTypeId 透传正确。"""
    import tapir_adapter

    calls = {}

    def _fake(cmd, params, instance):
        calls["cmd"] = cmd
        calls["params"] = params
        return {"libraryParts": [], "skippedCount": 0, "skippedSample": []}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    tapir_adapter.adapter.get_available_library_parts("Object")
    assert calls["cmd"] == "GetAvailableLibraryParts"
    assert calls["params"] == {"filterByTypeId": "Object"}


def test_get_available_library_parts_empty(monkeypatch):
    """无库部件时返回空列表。"""
    import tapir_adapter

    monkeypatch.setattr(
        tapir_adapter.adapter, "execute",
        lambda cmd, params, instance: {"libraryParts": [], "skippedCount": 0, "skippedSample": []})
    out = tapir_adapter.adapter.get_available_library_parts()
    assert out["libraryParts"] == []


# --- get_subelements_of_hierarchical ------------------------------------


def test_get_subelements_of_hierarchical(monkeypatch):
    """GetSubelementsOfHierarchicalElements：返回按类型分组。"""
    import tapir_adapter

    fake = {
        "subelements": [
            {
                "cWallSegments": [{"elementId": {"guid": "S1"}}],
                "cWallFrames": [{"elementId": {"guid": "F1"}}, {"elementId": {"guid": "F2"}}],
                "stairTreads": [],
                "stairRisers": [],
                "stairStructures": [],
            }
        ],
    }
    monkeypatch.setattr(
        tapir_adapter.adapter, "execute",
        lambda cmd, params, instance: fake)
    out = tapir_adapter.adapter.get_subelements_of_hierarchical(["G1"])
    assert len(out["subelements"]) == 1
    assert len(out["subelements"][0]["cWallFrames"]) == 2


def test_get_subelements_of_hierarchical_empty(monkeypatch):
    """无子构件时返回空列表。"""
    import tapir_adapter

    monkeypatch.setattr(
        tapir_adapter.adapter, "execute",
        lambda cmd, params, instance: {"subelements": []})
    out = tapir_adapter.adapter.get_subelements_of_hierarchical(["G1"])
    assert out["subelements"] == []


def test_get_subelements_of_hierarchical_guids_wrapped(monkeypatch):
    """校验 elements 参数包装正确。"""
    import tapir_adapter

    calls = {}

    def _fake(cmd, params, instance):
        calls["cmd"] = cmd
        calls["params"] = params
        return {"subelements": []}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    tapir_adapter.adapter.get_subelements_of_hierarchical(["A1", "A2"])
    assert calls["cmd"] == "GetSubelementsOfHierarchicalElements"
    assert calls["params"]["elements"] == [
        {"elementId": {"guid": "A1"}},
        {"elementId": {"guid": "A2"}},
    ]
