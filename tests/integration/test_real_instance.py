"""真机集成测试：走 server.py 完整工具链（FastMCP 装饰器返回原函数）。

这些测试必须在 ArchiCAD 真机开启时才跑；无真机自动跳过整个文件。
所有写操作只验证 confirm=False 的拦截，不实际改模型。

跑法（项目根目录）：
    python -m pytest tests/integration/ -v
"""

import pytest

import instance_manager
import server

# 模块加载时尝试发现真机；失败则标记整文件跳过
try:
    instance_manager.manager.discover_instances()
    _ALL = [i.instance_id for i in instance_manager.manager.list_instances()]
except Exception:
    _ALL = []

pytestmark = pytest.mark.skipif(
    not _ALL, reason="无可用 ArchiCAD 真机，跳过集成测试"
)

# 主测实例：优先用已知有 8 面墙的 ac29-1
PRIMARY = "ac29-1" if "ac29-1" in _ALL else _ALL[0]
FIRE_PROP = "耐火等级"


@pytest.fixture(scope="module")
def wall_guids() -> list[str]:
    """取主实例所有墙 GUID。"""
    r = server.get_elements_by_type("Wall", PRIMARY)
    assert r["status"] == "success", r
    return [str(it["guid"]) for it in r["items"]]


# --- P0 只读工具 -----------------------------------------------------------


def test_list_instances():
    r = server.list_instances()
    assert r["status"] == "success", r
    assert r["count"] >= 1
    ids = [it["instance_id"] for it in r["items"]]
    assert PRIMARY in ids


def test_project_summary():
    r = server.project_summary(PRIMARY)
    assert r["status"] == "success", r
    assert r["count"] >= 1
    assert r["data"]["properties"] >= 1


def test_get_selected_elements_structure():
    # 不依赖用户是否选中，只验证返回结构稳定
    r = server.get_selected_elements(PRIMARY)
    assert r["status"] == "success", r
    assert "count" in r and "items" in r


def test_get_elements_by_type_wall(wall_guids):
    assert len(wall_guids) >= 1


def test_get_element_properties(wall_guids):
    r = server.get_element_properties(wall_guids, [FIRE_PROP], PRIMARY)
    assert r["status"] == "success", r
    assert r["count"] == len(wall_guids)
    for item in r["items"]:
        assert FIRE_PROP in item["properties"]


def test_search_by_type_and_pagination(wall_guids):
    total = len(wall_guids)
    r = server.search_elements_by_criteria(
        element_type="Wall", limit=total, instance=PRIMARY
    )
    assert r["status"] == "success", r
    assert r["count"] == total


def test_search_by_property_value(wall_guids):
    # 先读第一面墙的实际耐火等级，再按该值过滤（不依赖所有墙都已赋值的假设）
    read = server.get_element_properties(wall_guids[:1], [FIRE_PROP], PRIMARY)
    actual = read["items"][0]["properties"].get(FIRE_PROP)
    if actual in (None, ""):
        pytest.skip(f"第一面墙无 {FIRE_PROP} 值，无法验证值过滤")
    r = server.search_elements_by_criteria(
        element_type="Wall",
        filters=[{"field": FIRE_PROP, "operator": "=", "value": str(actual)}],
        limit=100, instance=PRIMARY,
    )
    assert r["status"] == "success", r
    assert r["count"] >= 1


def test_search_by_property_no_match():
    r = server.search_elements_by_criteria(
        element_type="Wall",
        filters=[{"field": FIRE_PROP, "operator": "=", "value": "不存在的值X"}],
        limit=100, instance=PRIMARY,
    )
    assert r["status"] == "success", r
    assert r["count"] == 0


def test_search_pagination_cursor(wall_guids):
    if len(wall_guids) < 2:
        pytest.skip("墙不足 2 面，无法测分页")
    r = server.search_elements_by_criteria(
        element_type="Wall", limit=1, instance=PRIMARY
    )
    assert r["count"] == 1
    assert r["data"]["next_cursor"]


def test_list_floors():
    r = server.list_floors(PRIMARY)
    assert r["status"] == "success", r
    assert r["count"] >= 1


def test_get_classifications():
    r = server.get_classifications(PRIMARY)
    assert r["status"] == "success", r
    assert "items" in r


def test_get_element_geometry_info(wall_guids):
    r = server.get_element_geometry_info(wall_guids[:1], PRIMARY)
    assert r["status"] == "success", r
    assert r["count"] == 1
    item = r["items"][0]
    assert item["type"] == "Wall"
    # 完整几何：长度/起止点/包围盒齐全
    assert item["summary"]["length"] > 0
    assert item["base_point"] and item["end_point"]
    bbox = item["bounding_box"]
    assert bbox["size"]["x"] > 0
    assert bbox["size"]["z"] == item["summary"]["height"]


# --- P1 写入工具（只验证拦截，不实际写入）-----------------------------------


def test_preview_property_change(wall_guids):
    r = server.preview_property_change(
        wall_guids, FIRE_PROP, "3小时", PRIMARY
    )
    assert r["status"] == "success", r
    data = r["data"]
    assert data["target_count"] == len(wall_guids)
    assert len(data["before_values"]) == len(wall_guids)


def test_set_property_requires_confirm(wall_guids):
    r = server.set_element_properties(
        wall_guids, FIRE_PROP, "3小时", confirm=False, instance=PRIMARY
    )
    assert r["status"] == "error"
    assert r["error_code"] == "CONFIRM_REQUIRED"


def test_set_gdl_requires_confirm(wall_guids):
    r = server.set_gdl_parameters(
        wall_guids, "acWidth", 1.0, confirm=False, instance=PRIMARY
    )
    assert r["status"] == "error"
    assert r["error_code"] == "CONFIRM_REQUIRED"


def test_preview_classification(wall_guids):
    r = server.preview_classification(
        wall_guids[:1], "标准墙", instance=PRIMARY
    )
    assert r["status"] == "success", r
    data = r["data"]
    assert data["target_count"] == 1
    assert "标准墙" in data["target_item"]
    assert data["system_id"]


def test_attach_classification_requires_confirm(wall_guids):
    r = server.attach_classification(
        wall_guids[:1], "标准墙", confirm=False, instance=PRIMARY
    )
    assert r["status"] == "error"
    assert r["error_code"] == "CONFIRM_REQUIRED"


def test_attach_classification_bad_item(wall_guids):
    r = server.attach_classification(
        wall_guids[:1], "不存在的分类X", confirm=True, instance=PRIMARY
    )
    assert r["status"] == "error"
    assert r["error_code"] == "CLASSIFICATION_NOT_FOUND"


def test_highlight_elements(wall_guids):
    r = server.highlight_elements(wall_guids[:1], PRIMARY)
    assert r["status"] == "success", r


# --- P2 诊断运维工具 -------------------------------------------------------


def test_validate_instance():
    r = server.validate_instance(PRIMARY)
    assert r["status"] == "success", r
    assert r["data"]["status"] in ("healthy", "connected")


def test_get_operation_log():
    r = server.get_operation_log(5)
    assert r["status"] == "success", r
    assert "items" in r


def test_get_operation_status_not_found():
    r = server.get_operation_status("OP-00000000-99999")
    assert r["status"] == "error"
    assert r["error_code"] == "OPERATION_NOT_FOUND"
