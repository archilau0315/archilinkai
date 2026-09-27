"""真机集成测试：走 server.py 完整工具链（FastMCP 装饰器返回原函数）。

这些测试必须在 ArchiCAD 真机开启时才跑；无真机自动跳过整个文件。
所有写操作只验证 confirm=False 的拦截，不实际改模型。

跑法（项目根目录）：
    python -m pytest tests/integration/ -v
"""

import pytest
from types import SimpleNamespace

import conftest
import instance_manager

# 工具函数藏在各 *_tools.register() 内部，server 模块并不直接暴露；
# 用 conftest._collect 抓出全部工具，绑成 server 命名空间供下方调用
server = SimpleNamespace(**conftest._collect())

# 模块加载时尝试发现真机；失败则标记整文件跳过
try:
    instance_manager.manager.discover_instances()
    _ALL = [i.instance_id for i in instance_manager.manager.list_instances()]
except Exception:
    _ALL = []

pytestmark = pytest.mark.skipif(
    not _ALL, reason="无可用 ArchiCAD 真机，跳过集成测试"
)

# 主测实例：优先用已知有墙的 ac29-1
PRIMARY = "ac29-1" if "ac29-1" in _ALL else _ALL[0]
FIRE_PROP = "耐火等级"


@pytest.fixture(scope="module")
def prop_name() -> str:
    """取一个主实例真实存在的字符串类型属性名（环境无关）。"""
    import property_service
    conn = instance_manager.manager.get_conn(PRIMARY)
    names = conn.commands.GetAllPropertyNames()
    assert names, "项目无任何属性"
    for n in names:
        name = getattr(n, "nonLocalizedName", None) or str(n)
        t = property_service.service.get_property_type(name, PRIMARY)
        if getattr(t, "value", t) == "string":
            return name
    pytest.skip("项目无字符串类型属性")


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


def test_get_element_properties(wall_guids, prop_name):
    r = server.get_element_properties(wall_guids, [prop_name], PRIMARY)
    assert r["status"] == "success", r
    assert r["count"] == len(wall_guids)
    for item in r["items"]:
        assert prop_name in item["properties"]


def test_search_by_type_and_pagination(wall_guids):
    total = len(wall_guids)
    r = server.search_elements_by_criteria(
        element_type="Wall", limit=total, instance=PRIMARY
    )
    assert r["status"] == "success", r
    assert r["count"] == total


def test_search_by_property_value(wall_guids, prop_name):
    # 先读第一面墙的实际属性值，再按该值过滤（不依赖所有墙都已赋值的假设）
    read = server.get_element_properties(wall_guids[:1], [prop_name], PRIMARY)
    actual = read["items"][0]["properties"].get(prop_name)
    if actual in (None, ""):
        pytest.skip(f"第一面墙无 {prop_name} 值，无法验证值过滤")
    r = server.search_elements_by_criteria(
        element_type="Wall",
        filters=[{"field": prop_name, "operator": "=", "value": str(actual)}],
        limit=100, instance=PRIMARY,
    )
    assert r["status"] == "success", r
    assert r["count"] >= 1


def test_search_by_property_no_match(prop_name):
    r = server.search_elements_by_criteria(
        element_type="Wall",
        filters=[{"field": prop_name, "operator": "=", "value": "不存在的值X"}],
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


def test_get_element_quantities(wall_guids):
    r = server.get_element_quantities(wall_guids[:1], None, PRIMARY)
    assert r["status"] == "success", r
    q = r["items"][0]["quantities"]
    # 墙必有毛体积和高度，单位标注正确
    assert q["General_GrossVolume"]["value"] > 0
    assert q["General_GrossVolume"]["unit"] == "m³"
    assert q["General_Height"]["value"] > 0
    assert q["General_Height"]["unit"] == "m"


def test_aggregate_quantities(wall_guids):
    r = server.aggregate_quantities(
        "General_NetVolume", ["story"], "Wall", None, None, PRIMARY
    )
    assert r["status"] == "success", r
    assert r["data"]["unit"] == "m³"
    groups = r["data"]["groups"]
    assert len(groups) >= 1
    # 每面墙净体积为正，分组 sum 也必为正
    assert any(g["sum"] > 0 for g in groups)


def test_get_property_definition(prop_name):
    r = server.get_property_definition(prop_name, PRIMARY)
    assert r["status"] == "success", r
    d = r["data"]
    assert d["name"] and d["type"]


def test_get_property_definition_missing():
    r = server.get_property_definition("不存在的属性xyz", PRIMARY)
    assert r["status"] == "error"
    assert r["error_code"] == "PROPERTY_NOT_FOUND"


@pytest.mark.skipif("ac28-1" not in _ALL, reason="需 ac28-1 在线（GDL-28 有枚举属性）")
def test_enum_options_real():
    """真机枚举复测：GDL-28 的 耐火等级 应返回中文可选项。"""
    r = server.get_property_definition("耐火等级", "ac28-1")
    assert r["status"] == "success", r
    d = r["data"]
    assert d["type"] == "enum"
    assert "一级耐火等级" in d["enum_options"]
    # 可选项必须是纯字符串，不是对象 repr
    assert all(isinstance(o, str) and not o.startswith("PossibleEnum") for o in d["enum_options"])


# --- P1 写入工具（只验证拦截，不实际写入）-----------------------------------


def test_preview_property_change(wall_guids, prop_name):
    r = server.preview_property_change(
        wall_guids, prop_name, "3小时", PRIMARY
    )
    if r["status"] == "error" and r["error_code"] == "PROPERTY_TYPE_UNKNOWN":
        pytest.skip(f"属性 {prop_name} 类型无法确定")
    assert r["status"] == "success", r
    data = r["data"]
    assert data["target_count"] == len(wall_guids)
    assert len(data["before_values"]) == len(wall_guids)


def test_set_property_requires_confirm(wall_guids, prop_name):
    r = server.set_element_properties(
        wall_guids, prop_name, "3小时", confirm=False, instance=PRIMARY
    )
    assert r["status"] == "error"
    assert r["error_code"] == "CONFIRM_REQUIRED"


def test_set_gdl_requires_confirm(wall_guids):
    r = server.set_gdl_parameters(
        wall_guids, "acWidth", 1.0, confirm=False, instance=PRIMARY
    )
    assert r["status"] == "error"
    assert r["error_code"] == "CONFIRM_REQUIRED"


def _first_classification():
    """取项目里一个真实存在的（系统名，项名）；没有返回 (None, None)。"""
    r = server.get_classifications(PRIMARY)
    for sys_item in r.get("items", []):
        sys_name = sys_item.get("name") or sys_item.get("system_name")
        for it in sys_item.get("items", []) or sys_item.get("classifications", []):
            name = it.get("name") or it.get("id")
            if sys_name and name:
                return sys_name, name
    return None, None


def test_preview_classification(wall_guids):
    sys_name, item_name = _first_classification()
    if not item_name:
        pytest.skip("项目无可用分类项")
    r = server.preview_classification(
        wall_guids[:1], item_name, sys_name, instance=PRIMARY
    )
    assert r["status"] == "success", r
    data = r["data"]
    assert data["target_count"] == 1
    assert item_name in data["target_item"]
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
