"""Property 读取/写入与类型校验模块（V0.3 8.6）。

V0.3 不再把写入值统一转字符串。应根据 Property 定义做类型处理：
    Property Name → Get Property Definition → Resolve Type →
    Validate Value → Convert / Encode → Tapir

对于无法确定类型的 Property，拒绝执行，不猜测转换。
"""

from __future__ import annotations

from enum import Enum
from typing import Any

import instance_manager
from errors import (
    PropertyNotFoundError,
    PropertyTypeMismatchError,
    PropertyTypeUnknownError,
)
from schemas import PreviewResult
from tapir_adapter import adapter as _tapir


class PropertyType(str, Enum):
    """V0.3 8.6 支持的 Property 类型。"""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ENUM = "enum"
    DATE = "date"
    LENGTH = "length"
    AREA = "area"
    VOLUME = "volume"
    ANGLE = "angle"
    UNKNOWN = "unknown"


def validate_and_encode(
    prop_type: PropertyType, value: Any, prop_name: str = ""
) -> str:
    """按类型校验并编码为 Tapir 可接受的"显示文本"值。

    Tapir SetPropertyValuesOfElements 按"显示文本"传入，由 Tapir 转换类型。
    本函数先做严格校验，避免把错误类型直接送进模型。

    Raises:
        PropertyTypeMismatchError: 类型不符
        PropertyTypeUnknownError: 类型未知（拒绝执行）
    """
    if prop_type == PropertyType.UNKNOWN:
        raise PropertyTypeUnknownError(prop_name)
    if prop_type == PropertyType.STRING:
        return str(value)
    if prop_type in (PropertyType.INTEGER,):
        if isinstance(value, bool):
            raise PropertyTypeMismatchError(prop_name, "integer", "boolean")
        try:
            return str(int(value))
        except (ValueError, TypeError):
            raise PropertyTypeMismatchError(prop_name, "integer", type(value).__name__)
    if prop_type in (PropertyType.FLOAT, PropertyType.LENGTH, PropertyType.AREA,
                     PropertyType.VOLUME, PropertyType.ANGLE):
        try:
            return str(float(value))
        except (ValueError, TypeError):
            raise PropertyTypeMismatchError(prop_name, prop_type.value, type(value).__name__)
    if prop_type == PropertyType.BOOLEAN:
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, str) and value.strip().lower() in ("true", "false"):
            return value.strip().lower()
        raise PropertyTypeMismatchError(prop_name, "boolean", type(value).__name__)
    if prop_type == PropertyType.ENUM:
        # 枚举按字符串显示文本传入；有效性应在 Property 定义里校验
        if value is None or value == "":
            raise PropertyTypeMismatchError(prop_name, "enum", "empty")
        return str(value)
    if prop_type == PropertyType.DATE:
        # 日期按字符串传入，格式由 Tapir 解析；这里只做非空校验
        if not str(value).strip():
            raise PropertyTypeMismatchError(prop_name, "date", "empty")
        return str(value)
    raise PropertyTypeUnknownError(prop_name)


def parse_property_type(definition: Any) -> PropertyType:
    """从 archicad 属性定义对象解析类型。

    archicad 包的属性定义对象字段名因版本而异，本函数尽力兼容。
    无法确定时返回 UNKNOWN，调用方据此拒绝写入。
    """
    if definition is None:
        return PropertyType.UNKNOWN
    # 尝试常见字段名
    type_value = None
    for attr in ("type", "propertyType", "valueType"):
        if hasattr(definition, attr):
            type_value = getattr(definition, attr)
            break
        if isinstance(definition, dict) and attr in definition:
            type_value = definition[attr]
            break
    if type_value is None:
        return PropertyType.UNKNOWN
    # type_value 可能是枚举/字符串/带 name 的对象
    if hasattr(type_value, "name"):
        type_value = type_value.name
    elif hasattr(type_value, "value"):
        type_value = type_value.value
    elif isinstance(type_value, dict) and "name" in type_value:
        type_value = type_value["name"]
    text = str(type_value).lower()
    mapping = {
        "string": PropertyType.STRING,
        "text": PropertyType.STRING,
        "integer": PropertyType.INTEGER,
        "int": PropertyType.INTEGER,
        "number": PropertyType.FLOAT,
        "real": PropertyType.FLOAT,
        "float": PropertyType.FLOAT,
        "double": PropertyType.FLOAT,
        "boolean": PropertyType.BOOLEAN,
        "bool": PropertyType.BOOLEAN,
        "enum": PropertyType.ENUM,
        "enumeration": PropertyType.ENUM,
        "choice": PropertyType.ENUM,
        "singleenum": PropertyType.ENUM,
        "multienum": PropertyType.ENUM,
        "date": PropertyType.DATE,
        "length": PropertyType.LENGTH,
        "linearlength": PropertyType.LENGTH,
        "area": PropertyType.AREA,
        "volume": PropertyType.VOLUME,
        "angle": PropertyType.ANGLE,
    }
    return mapping.get(text, PropertyType.UNKNOWN)


class PropertyService:
    """Property 读取、类型解析、写入预览。"""

    def __init__(self, mgr: instance_manager.InstanceManager) -> None:
        self._mgr = mgr
        # 属性名解析缓存：{(instance, name): user_id/类型}（V0.17 提速）
        self._uid_cache: dict[tuple, Any] = {}
        self._type_cache: dict[tuple, PropertyType] = {}

    # --- 属性 ID 与定义 ---------------------------------------------------

    def _resolve_user_id(self, name: str, instance: str | None = None) -> Any:
        """根据 name 找 PropertyUserId 对象；先 BuiltIn，再 UserDefined 遍历。

        - BuiltIn 属性：用 nonLocalizedName 直接构造
        - UserDefined 属性：遍历 GetAllPropertyNames 找 localizedName[1]==name
        结果按 (instance, name) 缓存，重复解析零开销。
        """
        key = (instance, name)
        if key in self._uid_cache:
            return self._uid_cache[key]
        uid = self._resolve_user_id_uncached(name, instance)
        self._uid_cache[key] = uid
        return uid

    def _resolve_user_id_uncached(self, name, instance):
        conn = self._mgr.get_conn(instance)
        # 1. BuiltIn
        try:
            uid = conn.types.BuiltInPropertyUserId(nonLocalizedName=name)
            ids = conn.commands.GetPropertyIds([uid])
            if ids and getattr(ids[0], "propertyId", None):
                return uid
        except Exception:
            pass
        # 2. UserDefined fallback
        try:
            for cand in conn.commands.GetAllPropertyNames():
                loc = getattr(cand, "localizedName", None)
                if loc and len(loc) >= 2 and loc[1] == name:
                    return cand
        except Exception:
            pass
        return None

    def get_property_id(self, name: str, instance: str | None = None) -> Any:
        """GetPropertyIds 把属性名换成属性 ID；找不到抛 PropertyNotFoundError。

        支持 BuiltIn（nonLocalizedName）和 UserDefined（localizedName[1]）两种属性。
        """
        conn = self._mgr.get_conn(instance)
        uid = self._resolve_user_id(name, instance)
        if uid is None:
            raise PropertyNotFoundError(name, instance)
        try:
            ids = conn.commands.GetPropertyIds([uid])
        except Exception as exc:
            raise PropertyNotFoundError(name, instance) from exc
        if not ids or not getattr(ids[0], "propertyId", None):
            raise PropertyNotFoundError(name, instance)
        return ids[0].propertyId

    def get_property_type(
        self, name: str, instance: str | None = None
    ) -> PropertyType:
        """解析属性类型；未知返回 UNKNOWN。

        archicad 包没有 GetPropertyDefinitions；正解：
            GetPropertyIds([PropertyUserId]) → PropertyId
            GetDetailsOfProperties([PropertyId]) → [PropertyDefinitionWrapper]
            wrapper.propertyDefinition → PropertyDefinition（含 type 字段）
        同时支持 BuiltIn 和 UserDefined 属性（经 _resolve_user_id）。
        结果按 (instance, name) 缓存。
        """
        key = (instance, name)
        if key in self._type_cache:
            return self._type_cache[key]
        t = self._property_type_uncached(name, instance)
        self._type_cache[key] = t
        return t

    def _property_type_uncached(self, name, instance) -> PropertyType:
        conn = self._mgr.get_conn(instance)
        uid = self._resolve_user_id(name, instance)
        if uid is None:
            return PropertyType.UNKNOWN
        try:
            prop_id = conn.commands.GetPropertyIds([uid])[0].propertyId
            details = conn.commands.GetDetailsOfProperties([prop_id])
        except Exception:
            return PropertyType.UNKNOWN
        if not details:
            return PropertyType.UNKNOWN
        # PropertyDefinitionWrapper → PropertyDefinition
        d = getattr(details[0], "propertyDefinition", details[0])
        return parse_property_type(d)

    def get_property_definition(
        self, name: str, instance: str | None = None
    ) -> dict[str, Any] | None:
        """属性定义：类型/分组/描述/枚举可选项。属性不存在返回 None。"""
        conn = self._mgr.get_conn(instance)
        uid = self._resolve_user_id(name, instance)
        if uid is None:
            return None
        try:
            prop_id = conn.commands.GetPropertyIds([uid])[0].propertyId
            details = conn.commands.GetDetailsOfProperties([prop_id])
        except Exception:
            return None
        if not details:
            return None
        d = getattr(details[0], "propertyDefinition", details[0])
        ptype = parse_property_type(d)
        out: dict[str, Any] = {
            "name": getattr(d, "name", name),
            "type": ptype.value,
            "unit": self._TYPE_UNIT.get(ptype),
            "group": getattr(getattr(d, "group", None), "name", None),
            "description": getattr(d, "description", None),
        }
        if ptype == PropertyType.ENUM:
            raw = (
                getattr(d, "possibleEnumValues", None)
                or getattr(d, "enumValues", None)
                or []
            )
            out["enum_options"] = [
                getattr(v, "displayValue", None) or str(v) for v in raw
            ]
        return out

    # --- 读取 -------------------------------------------------------------

    # 属性类型 → 单位标注（项目默认公制工作单位）
    _TYPE_UNIT = {
        PropertyType.LENGTH: "m",
        PropertyType.AREA: "m²",
        PropertyType.VOLUME: "m³",
        PropertyType.ANGLE: "°",
    }

    def get_quantities(
        self,
        element_guids: list[str],
        quantity_names: list[str],
        instance: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """批量读取工程量（内置属性），带单位标注。

        quantity_names 为 BuiltIn 属性名（如 General_GrossVolume）；
        元素不支持某项时该项为 None。返回：
        {guid: {name: {"value": 数值或None, "unit": "m/m²/m³/°/None"}}}
        """
        values = self.get_values(element_guids, quantity_names, instance)
        units = {
            n: self._TYPE_UNIT.get(self.get_property_type(n, instance))
            for n in quantity_names
        }
        out: dict[str, dict[str, Any]] = {}
        for g in element_guids:
            out[g] = {
                n: {"value": values.get(g, {}).get(n), "unit": units[n]}
                for n in quantity_names
            }
        return out


    def get_values(
        self,
        element_guids: list[str],
        property_names: list[str],
        instance: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """读取指定元素的指定属性，返回 {guid: {name: value}}。

        使用 GetPropertyValuesOfElements（返回 list[PropertyValuesWrapper]），
        比 GetPropertyValuesDictionary（返回 dict，key 是 ElementId 对象）更易处理。
        对 enum 值（NonLocalizedValueEnumId 对象）取 nonLocalizedValue 字段。
        """
        conn = self._mgr.get_conn(instance)
        types = conn.types
        elements = [types.ElementId(guid=g) for g in element_guids]
        # 按输入顺序映射属性名 → PropertyId；找不到的属性跳过
        name_to_id: dict[str, Any] = {}
        for n in property_names:
            try:
                pid = self.get_property_id(n, instance)
            except PropertyNotFoundError:
                continue
            name_to_id[n] = pid
        result: dict[str, dict[str, Any]] = {g: {} for g in element_guids}
        if not name_to_id:
            return result
        prop_ids = list(name_to_id.values())
        try:
            wrappers = conn.commands.GetPropertyValuesOfElements(
                elements, prop_ids
            )
        except Exception:
            return result
        # wrappers[i] 对应 element_guids[i]，其 propertyValues 与 prop_ids 顺序对齐
        for idx, guid in enumerate(element_guids):
            if idx >= len(wrappers):
                break
            wrapper = wrappers[idx]
            pvs = getattr(wrapper, "propertyValues", None) or []
            for (name, _pid), pv_item in zip(name_to_id.items(), pvs):
                inner = getattr(pv_item, "propertyValue", None)
                if inner is None:
                    continue
                value = getattr(inner, "value", None)
                # enum 的 value 是 EnumValueId 对象；
                # BuiltIn 用 nonLocalizedValue，UserDefined 用 displayValue
                if hasattr(value, "nonLocalizedValue") and value.nonLocalizedValue is not None:
                    value = value.nonLocalizedValue
                elif hasattr(value, "displayValue"):
                    value = value.displayValue
                result[guid][name] = value
        return result

    # --- 写入（archicad 原生 API）----------------------------------------

    def set_property_values(
        self,
        prop_type: PropertyType,
        encoded: str,
        element_guids: list[str],
        prop_id: Any,
        prop_name: str = "",
        instance: str | None = None,
    ) -> list[Any]:
        """用 archicad 原生 SetPropertyValuesOfElements 写入。

        按 prop_type 构造对应的 Normal*PropertyValue 对象。
        原生 API 也走 ACAPI_CallUndoableCommand（可撤销）。
        写入失败（success=False）时抛 RuntimeError。

        Raises:
            PropertyTypeUnknownError: 未知类型
            RuntimeError: 写入失败（部分或全部 success=False）
        """
        conn = self._mgr.get_conn(instance)
        types = conn.types
        # 按 prop_type 构造 propertyValue 对象
        if prop_type == PropertyType.ENUM:
            enum_id = types.DisplayValueEnumId(displayValue=str(encoded))
            pv = types.NormalSingleEnumPropertyValue(value=enum_id)
        elif prop_type == PropertyType.STRING:
            pv = types.NormalStringPropertyValue(value=str(encoded))
        elif prop_type == PropertyType.BOOLEAN:
            pv = types.NormalBooleanPropertyValue(
                value=(str(encoded).strip().lower() == "true")
            )
        elif prop_type == PropertyType.INTEGER:
            pv = types.NormalIntegerPropertyValue(value=int(encoded))
        elif prop_type == PropertyType.FLOAT:
            pv = types.NormalNumberPropertyValue(value=float(encoded))
        elif prop_type == PropertyType.LENGTH:
            pv = types.NormalLengthPropertyValue(value=float(encoded))
        elif prop_type == PropertyType.AREA:
            pv = types.NormalAreaPropertyValue(value=float(encoded))
        elif prop_type == PropertyType.VOLUME:
            pv = types.NormalVolumePropertyValue(value=float(encoded))
        elif prop_type == PropertyType.ANGLE:
            pv = types.NormalAnglePropertyValue(value=float(encoded))
        elif prop_type == PropertyType.DATE:
            # archicad 没有 date 类型，按 string 处理
            pv = types.NormalStringPropertyValue(value=str(encoded))
        else:
            raise PropertyTypeUnknownError(prop_name)
        # 构造 ElementPropertyValue 列表
        epvs = [
            types.ElementPropertyValue(
                elementId=types.ElementId(guid=g),
                propertyId=prop_id,
                propertyValue=pv,
            )
            for g in element_guids
        ]
        results = conn.commands.SetPropertyValuesOfElements(epvs)
        # 检查 success
        failed = [
            (i, getattr(results[i], "error", None))
            for i in range(len(results))
            if not getattr(results[i], "success", True)
        ]
        if failed:
            msgs = [f"{element_guids[i]}: {e}" for i, e in failed]
            raise RuntimeError(
                f"SetPropertyValuesOfElements 写入失败 {len(failed)}/"
                f"{len(element_guids)}: {msgs}"
            )
        return results

    # --- 写入预览 ---------------------------------------------------------

    def preview_change(
        self,
        element_guids: list[str],
        property_name: str,
        value: Any,
        instance: str | None = None,
    ) -> PreviewResult:
        """写操作预览：取 before 值 + 校验目标值 + 列出不可改元素。

        校验目标值类型；类型未知或不符时抛异常，绝不静默送入 Tapir。
        """
        prop_type = self.get_property_type(property_name, instance)
        # 提前校验，类型问题直接抛出
        encoded = validate_and_encode(prop_type, value, property_name)
        before_map = self.get_values(element_guids, [property_name], instance)
        before_values = [
            {"guid": g, property_name: before_map.get(g, {}).get(property_name)}
            for g in element_guids
        ]
        unchangeable = [
            g for g in element_guids
            if before_map.get(g, {}).get(property_name) is None
        ]
        return PreviewResult(
            target_count=len(element_guids),
            target_guids=list(element_guids),
            before_values=before_values,
            target_value=encoded,
            unchangeable=unchangeable,
            estimated_change=len(element_guids) - len(unchangeable),
            risk=(
                f"将批量修改 {len(element_guids)} 个元素的 {property_name}，"
                f"其中 {len(unchangeable)} 个当前无可读值。"
            ),
        )


# 模块级单例
service = PropertyService(instance_manager.manager)
