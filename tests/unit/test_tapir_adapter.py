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


# --- P1 命令：get_collisions --------------------------------------------


def test_get_collisions_cmd_and_params(monkeypatch):
    import tapir_adapter

    calls = {}

    def _fake(cmd, params, instance):
        calls["cmd"] = cmd
        calls["params"] = params
        return {"collisions": []}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    g1 = [{"elementId": {"guid": "G1"}}]
    g2 = [{"elementId": {"guid": "G2"}}]
    tapir_adapter.adapter.get_collisions(g1, g2)
    assert calls["cmd"] == "GetCollisions"
    assert calls["params"]["elementsGroup1"] == g1
    assert calls["params"]["elementsGroup2"] == g2
    assert calls["params"]["settings"]["volumeTolerance"] == 0.001
    assert calls["params"]["settings"]["performSurfaceCheck"] is False


def test_get_collisions_result(monkeypatch):
    import tapir_adapter

    fake = {
        "collisions": [
            {"elementId1": {"guid": "A"}, "elementId2": {"guid": "B"},
             "hasBodyCollision": True, "hasClearenceCollision": False},
        ],
    }
    monkeypatch.setattr(
        tapir_adapter.adapter, "execute",
        lambda cmd, params, instance: fake)
    out = tapir_adapter.adapter.get_collisions([], [])
    assert len(out["collisions"]) == 1


# --- P1 命令：get_layers / create_layers / delete_attributes -------------


def test_get_layers_cmd_and_params(monkeypatch):
    import tapir_adapter

    calls = {}

    def _fake(cmd, params, instance):
        calls["cmd"] = cmd
        calls["params"] = params
        return {"layers": []}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    tapir_adapter.adapter.get_layers(["L1", "L2"], ["name"])
    assert calls["cmd"] == "GetLayers"
    assert calls["params"]["attributeIds"] == [
        {"attributeId": {"guid": "L1"}},
        {"attributeId": {"guid": "L2"}},
    ]
    assert calls["params"]["fields"] == ["name"]


def test_create_layers_cmd_and_params(monkeypatch):
    import tapir_adapter

    calls = {}

    def _fake(cmd, params, instance):
        calls["cmd"] = cmd
        calls["params"] = params
        return {"attributeIds": []}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    layer_data = [{"name": "测试层", "isHidden": False}]
    tapir_adapter.adapter.create_layers(layer_data, True)
    assert calls["cmd"] == "CreateLayers"
    assert calls["params"]["layerDataArray"] == layer_data
    assert calls["params"]["overwriteExisting"] is True


def test_delete_attributes_cmd_and_params(monkeypatch):
    import tapir_adapter

    calls = {}

    def _fake(cmd, params, instance):
        calls["cmd"] = cmd
        calls["params"] = params
        return {"executionResults": []}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    attrs = [{"attributeType": "Layer", "attributeId": "L1"}]
    tapir_adapter.adapter.delete_attributes(attrs)
    assert calls["cmd"] == "DeleteAttributes"
    assert calls["params"]["attributesToDelete"] == attrs


# --- P1 命令：favorites -------------------------------------------------


def test_get_favorites_by_type(monkeypatch):
    import tapir_adapter

    calls = {}

    def _fake(cmd, params, instance):
        calls["cmd"] = cmd
        calls["params"] = params
        return {"favorites": ["标准墙", "隔墙"]}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    rows = tapir_adapter.adapter.get_favorites_by_type("Wall")
    assert calls["cmd"] == "GetFavoritesByType"
    assert calls["params"]["elementType"] == "Wall"
    assert rows == ["标准墙", "隔墙"]


def test_apply_favorites_to_elements(monkeypatch):
    import tapir_adapter

    calls = {}

    def _fake(cmd, params, instance):
        calls["cmd"] = cmd
        calls["params"] = params
        return {"executionResults": []}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    pairs = [{"elementId": {"guid": "E1"}, "favorite": "标准墙"}]
    tapir_adapter.adapter.apply_favorites_to_elements(pairs, False, True, True, False)
    assert calls["cmd"] == "ApplyFavoritesToElements"
    assert calls["params"]["favoritesToApply"] == pairs
    assert calls["params"]["applySettings"] is False
    # 默认值 True 时不传参（Tapir 默认 true）
    assert "applyClassifications" not in calls["params"]
    assert "applyCategories" not in calls["params"]
    assert calls["params"]["applyProperties"] is False


# --- P1 命令：IFC --------------------------------------------------------


def test_get_ifc_ids_of_elements(monkeypatch):
    import tapir_adapter

    calls = {}

    def _fake(cmd, params, instance):
        calls["cmd"] = cmd
        calls["params"] = params
        return {"elementIFCIds": [{"elementId": {"guid": "E1"}, "ifcId": "2x3$abc"}]}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    rows = tapir_adapter.adapter.get_ifc_ids_of_elements(["G1"])
    assert calls["cmd"] == "GetIFCIdsOfElements"
    assert calls["params"]["elements"] == [{"elementId": {"guid": "G1"}}]
    assert rows[0]["ifcId"] == "2x3$abc"


def test_get_elements_by_ifc_ids(monkeypatch):
    import tapir_adapter

    calls = {}

    def _fake(cmd, params, instance):
        calls["cmd"] = cmd
        calls["params"] = params
        return {"elementsByIFCIds": [{"ifcId": "2x3$abc", "elementId": {"guid": "E1"}}]}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    rows = tapir_adapter.adapter.get_elements_by_ifc_ids(["2x3$abc"])
    assert calls["cmd"] == "GetElementsByIFCIds"
    assert calls["params"]["ifcIds"] == ["2x3$abc"]
    assert rows[0]["elementId"]["guid"] == "E1"


def test_get_ifc_properties_of_elements(monkeypatch):
    import tapir_adapter

    calls = {}

    def _fake(cmd, params, instance):
        calls["cmd"] = cmd
        calls["params"] = params
        return {"elementIFCProperties": [{"elementId": {"guid": "E1"}, "ifcProperties": []}]}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    rows = tapir_adapter.adapter.get_ifc_properties_of_elements(["G1"])
    assert calls["cmd"] == "GetIFCPropertiesOfElements"
    assert rows[0]["elementId"]["guid"] == "E1"


# --- P1 命令：set_details / get_zone_boundaries / update_zones ---------


def test_set_details_of_elements(monkeypatch):
    import tapir_adapter

    calls = {}

    def _fake(cmd, params, instance):
        calls["cmd"] = cmd
        calls["params"] = params
        return {"executionResults": []}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    items = [{"elementId": {"guid": "E1"}, "details": {"floorIndex": 1}}]
    tapir_adapter.adapter.set_details_of_elements(items)
    assert calls["cmd"] == "SetDetailsOfElements"
    assert calls["params"]["elementsWithDetails"] == items


def test_get_zone_boundaries(monkeypatch):
    import tapir_adapter

    calls = {}

    def _fake(cmd, params, instance):
        calls["cmd"] = cmd
        calls["params"] = params
        return {"zoneBoundaries": []}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    tapir_adapter.adapter.get_zone_boundaries(["Z1"])
    assert calls["cmd"] == "GetZoneBoundaries"
    assert calls["params"]["zones"] == [{"elementId": {"guid": "Z1"}}]


def test_update_zones(monkeypatch):
    import tapir_adapter

    calls = {}

    def _fake(cmd, params, instance):
        calls["cmd"] = cmd
        calls["params"] = params
        return {"executionResult": "success"}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    tapir_adapter.adapter.update_zones(False, True, True)
    assert calls["cmd"] == "UpdateZones"
    assert calls["params"]["keepStampPosition"] is False
    assert calls["params"]["undoTopTrim"] is True
    assert calls["params"]["undoBottomTrim"] is True


def test_get_connected_elements(monkeypatch):
    import tapir_adapter

    calls = {}

    def _fake(cmd, params, instance):
        calls["cmd"] = cmd
        calls["params"] = params
        return {"connectedElements": [[{"elementId": {"guid": "W1"}}]]}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    rows = tapir_adapter.adapter.get_connected_elements(["H1", "H2"], "Window")
    assert calls["cmd"] == "GetConnectedElements"
    assert calls["params"]["connectedElementType"] == "Window"
    assert calls["params"]["elements"] == [
        {"elementId": {"guid": "H1"}},
        {"elementId": {"guid": "H2"}},
    ]
    assert rows == [[{"elementId": {"guid": "W1"}}]]


def test_move_elements(monkeypatch):
    import tapir_adapter

    calls = {}

    def _fake(cmd, params, instance):
        calls["cmd"] = cmd
        calls["params"] = params
        return {"executionResults": []}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    items = [{"elementId": {"guid": "E1"},
              "moveVector": {"x": 1.0, "y": 2.0, "z": 0.0}, "copy": False}]
    tapir_adapter.adapter.move_elements(items)
    assert calls["cmd"] == "MoveElements"
    assert calls["params"]["elementsWithMoveVectors"] == items


def test_rotate_elements(monkeypatch):
    import tapir_adapter

    calls = {}

    def _fake(cmd, params, instance):
        calls["cmd"] = cmd
        calls["params"] = params
        return {"executionResults": []}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    rot = {"beginPoint": {"x": 1, "y": 0}, "endPoint": {"x": 0, "y": 1},
           "origin": {"x": 0, "y": 0}}
    items = [{"elementId": {"guid": "E1"}, "rotation": rot, "copy": True}]
    tapir_adapter.adapter.rotate_elements(items)
    assert calls["cmd"] == "RotateElements"
    assert calls["params"]["elementsWithRotations"] == items


def test_get_element_preview_image(monkeypatch):
    import tapir_adapter

    calls = {}

    def _fake(cmd, params, instance):
        calls["cmd"] = cmd
        calls["params"] = params
        return {"previewImage": "aGVsbG8="}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    b64 = tapir_adapter.adapter.get_element_preview_image("E1", "2D", "jpg", 256, 256)
    assert calls["cmd"] == "GetElementPreviewImage"
    assert calls["params"]["elementId"] == {"guid": "E1"}
    assert calls["params"]["imageType"] == "2D"
    assert calls["params"]["format"] == "jpg"
    assert calls["params"]["width"] == 256
    assert b64 == "aGVsbG8="


def test_get_building_material_physical_properties(monkeypatch):
    import tapir_adapter

    calls = {}

    def _fake(cmd, params, instance):
        calls["cmd"] = cmd
        calls["params"] = params
        return {"properties": [{"density": 2400}]}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    rows = tapir_adapter.adapter.get_building_material_physical_properties(["B1"])
    assert calls["cmd"] == "GetBuildingMaterialPhysicalProperties"
    assert calls["params"]["attributeIds"] == [{"attributeId": {"guid": "B1"}}]
    assert rows == [{"density": 2400}]


def test_get_layer_combinations(monkeypatch):
    import tapir_adapter

    calls = {}

    def _fake(cmd, params, instance):
        calls["cmd"] = cmd
        calls["params"] = params
        return {"layerCombinations": [{"name": "01 组合", "layers": []}]}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    rows = tapir_adapter.adapter.get_layer_combinations(["LC1"])
    assert calls["cmd"] == "GetLayerCombinations"
    # 入参 key 是 attributes（非 attributeIds）
    assert calls["params"]["attributes"] == [{"attributeId": {"guid": "LC1"}}]
    assert rows == [{"name": "01 组合", "layers": []}]


def test_create_layer_combinations(monkeypatch):
    import tapir_adapter

    calls = {}

    def _fake(cmd, params, instance):
        calls["cmd"] = cmd
        calls["params"] = params
        return {"attributeIds": []}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    data = [{"name": "新组合", "layers": [
        {"attributeId": {"guid": "L1"}, "isHidden": False, "isLocked": False,
         "isWireframe": False, "intersectionGroupNr": 1}]}]
    tapir_adapter.adapter.create_layer_combinations(data, True)
    assert calls["cmd"] == "CreateLayerCombinations"
    assert calls["params"]["layerCombinationDataArray"] == data
    assert calls["params"]["overwriteExisting"] is True


def test_get_stories(monkeypatch):
    import tapir_adapter

    def _fake(cmd, params, instance):
        assert cmd == "GetStories"
        assert params is None
        return {"firstStory": -1, "lastStory": 4, "stories": []}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    data = tapir_adapter.adapter.get_stories()
    assert data["lastStory"] == 4


def test_get_gdl_parameters_of_elements(monkeypatch):
    import tapir_adapter

    calls = {}

    def _fake(cmd, params, instance):
        calls["cmd"] = cmd
        calls["params"] = params
        return {"gdlParametersOfElements": [{"parameters": []}]}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    rows = tapir_adapter.adapter.get_gdl_parameters_of_elements(["E1"])
    assert calls["cmd"] == "GetGDLParametersOfElements"
    assert calls["params"]["elements"] == [{"elementId": {"guid": "E1"}}]
    assert rows == [{"parameters": []}]


def test_get_mep_elements(monkeypatch):
    import tapir_adapter

    calls = {}

    def _fake(cmd, params, instance):
        calls["cmd"] = cmd
        calls["params"] = params
        return {"elements": [{"type": "Duct"}]}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    rows = tapir_adapter.adapter.get_mep_elements(["Duct"], ["Mechanical"])
    assert calls["cmd"] == "GetMEPElements"
    assert calls["params"] == {"elementTypes": ["Duct"], "domains": ["Mechanical"]}
    assert rows == [{"type": "Duct"}]

    calls.clear()
    tapir_adapter.adapter.get_mep_elements()
    assert calls["params"] == {}


def test_get_mep_routing_elements(monkeypatch):
    import tapir_adapter

    calls = {}

    def _fake(cmd, params, instance):
        calls["cmd"] = cmd
        calls["params"] = params
        return {"routingElements": [{"segments": []}]}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    rows = tapir_adapter.adapter.get_mep_routing_elements(["M1"])
    assert calls["cmd"] == "GetMEPRoutingElements"
    assert rows == [{"segments": []}]


def test_get_mep_ports(monkeypatch):
    import tapir_adapter

    calls = {}

    def _fake(cmd, params, instance):
        calls["cmd"] = cmd
        calls["params"] = params
        return {"elementPorts": [{"ports": []}]}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    rows = tapir_adapter.adapter.get_mep_ports(["M1"])
    assert calls["cmd"] == "GetMEPPorts"
    assert rows == [{"ports": []}]


def test_get_relations_of_elements(monkeypatch):
    import tapir_adapter

    calls = {}

    def _fake(cmd, params, instance):
        calls["cmd"] = cmd
        calls["params"] = params
        return {"relations": [{"type": "Window"}]}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    rows = tapir_adapter.adapter.get_relations_of_elements(["E1"], "Window")
    assert calls["cmd"] == "GetRelationsOfElements"
    assert calls["params"]["otherElementType"] == "Window"
    assert rows == [{"type": "Window"}]


def test_get_all_properties(monkeypatch):
    import tapir_adapter

    def _fake(cmd, params, instance):
        assert cmd == "GetAllProperties"
        assert params is None
        return {"properties": [{"name": "General_Area"}], "propertyGroups": []}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    data = tapir_adapter.adapter.get_all_properties()
    assert data["properties"] == [{"name": "General_Area"}]


def test_get_calculation_units(monkeypatch):
    import tapir_adapter

    def _fake(cmd, params, instance):
        assert cmd == "GetCalculationUnits"
        return {"length": {"unit": "Meter", "decimals": 3}}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    data = tapir_adapter.adapter.get_calculation_units()
    assert data["length"]["unit"] == "Meter"


def test_get_navigator_item_tree(monkeypatch):
    import tapir_adapter

    calls = {}

    def _fake(cmd, params, instance):
        calls["cmd"] = cmd
        calls["params"] = params
        return {"navigatorItemTree": {"name": "0. 地下室"}}

    monkeypatch.setattr(tapir_adapter.adapter, "execute", _fake)
    data = tapir_adapter.adapter.get_navigator_item_tree("PublicViewMap")
    assert calls["cmd"] == "GetNavigatorItemTree"
    assert calls["params"]["navigatorMapId"] == "PublicViewMap"
    assert "publisherSetName" not in calls["params"]
    assert data["navigatorItemTree"]["name"] == "0. 地下室"


