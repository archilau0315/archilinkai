# tests/compatibility/test_ac26_29_matrix.py
"""ArchiCAD AC26–29 兼容性测试矩阵（V0.3 8.13）。

需在装有 AC26–29 的环境运行，或 CI 矩阵多机并行。
覆盖：连接、基础命令、Tapir 命令、属性类型解析、属性取值。
无真机时 discover 抛错，整个模块报错即提示环境不满足。
"""

import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.insert(0, PROJECT_ROOT)

import property_service
from instance_manager import manager as im
from tapir_adapter import adapter as tapir


# 模块级 fixture（不能写成类里的 class-scoped 实例方法，新版 pytest 会报错）
@pytest.fixture(scope="module")
def instances():
    """发现当前环境所有实例：{instance_id: InstanceInfo}。"""
    return im.discover_instances()


def _first_prop_name(conn):
    """取第一个属性的 nonLocalizedName；没有返回 None。"""
    names = conn.commands.GetAllPropertyNames()
    if not names:
        return None
    return getattr(names[0], "nonLocalizedName", None)


class TestACVersionCompatibility:
    """各版本基础兼容性。"""

    def test_ac_version_detected(self, instances):
        versions = [info.version for info in instances.values()]
        print(f"\n检测到版本: {versions}")
        for v in versions:
            assert 26 <= v <= 29, f"不支持的版本: {v}（支持 26-29）"

    def test_get_product_info(self, instances):
        for iid, info in instances.items():
            conn = im.get_conn(iid)
            version, build, lang = conn.commands.GetProductInfo()
            print(f"{iid}: version={version}, build={build}, lang={lang}")
            assert (version, build, lang) == (
                info.version, info.build, info.language
            )

    def test_tapir_get_project_info(self, instances):
        for iid in instances:
            result = tapir.execute("GetProjectInfo", None, iid)
            print(f"{iid} GetProjectInfo: {result}")
            # 实测返回 {isUntitled, isTeamwork}；宽松断言
            if isinstance(result, dict):
                assert ("isUntitled" in result
                        or "projectName" in result
                        or "project_name" in result)

    def test_get_all_elements(self, instances):
        for iid in instances:
            conn = im.get_conn(iid)
            elements = conn.commands.GetAllElements()
            print(f"{iid} 元素总数: {len(elements)}")
            assert isinstance(elements, list)
            if elements:
                # archicad 包返回 UUID 对象，转字符串后应为 36 位
                guid = str(elements[0].elementId.guid)
                assert len(guid) == 36

    def test_get_all_property_names(self, instances):
        for iid in instances:
            conn = im.get_conn(iid)
            props = conn.commands.GetAllPropertyNames()
            print(f"{iid} 属性总数: {len(props)}")
            assert isinstance(props, list)

    def test_tapir_get_details_of_elements(self, instances):
        for iid in instances:
            conn = im.get_conn(iid)
            elements = conn.commands.GetAllElements()
            if not elements:
                pytest.skip(f"{iid} 项目无元素")
            guids = [str(e.elementId.guid) for e in elements[:3]]
            details = tapir.get_details_of_elements(guids, iid)
            print(f"{iid} GetDetailsOfElements: {len(details)} 项")
            assert len(details) == len(guids)

    def test_tapir_get_stories(self, instances):
        for iid in instances:
            result = tapir.execute("GetStories", None, iid)
            print(f"{iid} GetStories: {result}")
            assert result is not None

    def test_tapir_get_gdl_parameters(self, instances):
        """需有 Object 类型元素；当前环境没有会自动跳过。"""
        for iid in instances:
            conn = im.get_conn(iid)
            # elementType 直接传字符串，不存在 ElementType 类
            objects = conn.commands.GetElementsByType("Object")
            if not objects:
                pytest.skip(f"{iid} 项目无 GDL 对象")
            guids = [str(o.elementId.guid) for o in objects[:2]]
            # 注：参数 schema 待有 Object 时真机校验
            params = {"elementIds": [{"guid": g} for g in guids]}
            result = tapir.execute("GetGDLParametersOfElements", params, iid)
            assert result is not None


class TestACVersionSpecificBehavior:
    """版本特定行为：用 property_service 已验证通道，确保真能跑通。"""

    def test_property_type_resolvable(self, instances):
        for iid in instances:
            conn = im.get_conn(iid)
            pname = _first_prop_name(conn)
            if not pname:
                continue
            ptype = property_service.service.get_property_type(pname, iid)
            print(f"{iid} {pname} -> {ptype}")
            assert ptype is not None

    def test_property_values_readable(self, instances):
        for iid in instances:
            conn = im.get_conn(iid)
            elements = conn.commands.GetAllElements()
            pname = _first_prop_name(conn)
            if not elements or not pname:
                continue
            guid = str(elements[0].elementId.guid)
            values = property_service.service.get_values(
                [guid], [pname], iid
            )
            print(f"{iid} {pname}: {values.get(guid)}")
            assert guid in values


class TestQuantityCompatibility:
    """算量兼容性（V0.18）：量属性与 MEP 命令在各版本可用。"""

    # 通用量：各版本都应存在且类型正确
    GENERAL_QUANTITIES = {
        "General_GrossVolume": "volume",
        "General_NetVolume": "volume",
        "General_Height": "length",
        "General_Thickness": "length",
        "General_SurfaceArea": "area",
        "General_3DLength": "length",
    }

    def test_general_quantities_resolvable(self, instances):
        for iid in instances:
            for name, expect in self.GENERAL_QUANTITIES.items():
                ptype = property_service.service.get_property_type(name, iid)
                assert ptype.value == expect, (
                    f"{iid} {name}: 期望 {expect}，实际 {ptype.value}"
                )

    def test_quantities_readable_on_wall(self, instances):
        for iid in instances:
            conn = im.get_conn(iid)
            walls = conn.commands.GetElementsByType("Wall")
            if not walls:
                pytest.skip(f"{iid} 项目无墙")
            guid = str(walls[0].elementId.guid)
            q = property_service.service.get_quantities(
                [guid], ["General_GrossVolume"], iid)
            v = q[guid]["General_GrossVolume"]
            assert v["unit"] == "m³"
            assert v["value"] is None or v["value"] > 0

    def test_mep_commands_available(self, instances):
        """MEP 三命令在 AC26-29 应都存在（Tapir 支持）。"""
        for iid in instances:
            for cmd in ("CreateMEPRoutingElements",
                        "GetMEPRoutingElements",
                        "GetMEPDistributionSystems"):
                # 对空请求执行：命令不存在会抛错；存在则返回 dict 或业务错误
                try:
                    tapir.execute(cmd, {}, iid)
                except Exception as e:
                    msg = str(e)
                    assert "not found" not in msg.lower() \
                        and "unknown command" not in msg.lower(), (
                        f"{iid} 缺少 MEP 命令 {cmd}: {msg}"
                    )
