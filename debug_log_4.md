# Debug Log 4

> 接续 debug_log_3.md（902 行已满）

---

## 2026-10-13 V0.32 P1 Tapir 命令批：碰撞/图层/收藏夹/IFC/区域边界/详情修改

### 变更
- tapir_adapter.py：新增 12 个便捷方法
  - get_collisions(g1, g2, volume_tolerance, perform_surface_check, surface_tolerance)
  - get_layers(attribute_ids, fields=None)
  - create_layers(layer_data_array, overwrite_existing=False)
  - delete_attributes(attributes_to_delete)
  - get_favorites_by_type(element_type)
  - apply_favorites_to_elements(favorites, apply_settings, apply_classifications, apply_categories, apply_properties)
  - get_ifc_ids_of_elements(guids)
  - get_elements_by_ifc_ids(ifc_ids)
  - get_ifc_properties_of_elements(guids)
  - set_details_of_elements(elements_with_details)
  - get_zone_boundaries(zone_guids)
  - update_zones(keep_stamp_position, undo_top_trim, undo_bottom_trim)
- read_tools.py：+6 只读工具（get_collisions / list_favorites / get_ifc_ids /
  get_elements_by_ifc_ids / get_ifc_properties / get_zone_boundaries）
- write_tools.py：+5 写入工具（create_layers / delete_attributes / apply_favorites /
  set_element_details / update_zones），全部 confirm=False 预览模式
- tests/unit/test_tapir_adapter.py：+13 用例（各命令 cmd/params/返回值透传）

### 真机验证（AC28 build 6003，办公楼改造项目）
- GetCollisions：Wall vs Column 各 10 个，检出 2 对碰撞（body=True）
- GetLayers：初版 attributeIds 裸字符串列表返回空；修正为 [{"attributeId":{"guid"}}] 后成功，返回 5 项（含 name/isHidden/isLocked/intersectionGroupNr）
- GetFavoritesByType("Wall")：17 项收藏夹（如"01 建筑 内墙_加气混凝土砌块_瓷砖(双侧)"）
- GetIFCIdsOfElements：3 面墙均返回 IFC ID
- GetElementsByIFCIds：用 IFC ID 反查成功，GUID 大小写不敏感
- GetIFCPropertiesOfElements：返回 Pset_BuildingElementProxyCommon 等 IFC 属性集
- GetZoneBoundaries：报错 -2130313110（Failed to execute zone boundary query），项目有 5 个 Zone 但查询失败，疑似 Zone 数据损坏或 Tapir 版本限制
- UpdateZones：报错 -2130312312（Failed to update zones），与 GetZoneBoundaries 同因

### 备注
- 单测 493 → 506 全过（+13）
- 工具数 37 → 48
- apply_favorites_to_elements 默认 True 的开关参数不传参（Tapir 默认 true），仅 False 时传参
- Zone 相关 2 个命令在当前项目报错，单测通过，参数格式正确，属项目数据或 Tapir 版本限制

---

## 2026-10-17 V0.33 P0 Tapir 命令批：连接关系/移动旋转/预览图/材料物理性能

### 变更
- tapir_adapter.py：+5 便捷方法
  - get_connected_elements(guids, connected_element_type)
  - move_elements(elements_with_move_vectors)
  - rotate_elements(elements_with_rotations)
  - get_element_preview_image(guid, image_type, image_format, width, height)
  - get_building_material_physical_properties(attribute_ids)
- read_tools.py：+3 只读工具
  - get_connected_elements（墙→窗、幕墙→框架、楼梯→踏踢板等）
  - get_element_preview_image（2D/Section/3D，png/jpg，返回 base64）
  - get_building_material_properties（建筑材料物理性能）
- write_tools.py：+2 写入工具（confirm 模式）
  - move_elements(guids, dx, dy, dz, copy, confirm)
  - rotate_elements(guids, origin, begin_point, end_point, copy, confirm)
- tests/unit/test_tapir_adapter.py：+5 用例

### 备注
- 单测 506 → 511 全过
- 工具数 48 → 53
- 真机验证：AC28 未启动，跳过；单测已覆盖参数格式
- MoveElements/RotateElements 输出为 ExecutionResults（批量执行结果）
- GetBuildingMaterialPhysicalProperties 的 attributeIds 用 [{attributeId:{guid}}] 包装（与 GetLayers 一致）

---

## 2026-10-18 V0.34 P1 收尾：图层组合

### 变更
- tapir_adapter.py：+2 便捷方法
  - get_layer_combinations(attribute_ids)（注意入参 key 是 attributes 非 attributeIds）
  - create_layer_combinations(layer_combination_data_array, overwrite_existing=False)
- read_tools.py：+1 只读工具 get_layer_combination_details
- write_tools.py：+1 写入工具 create_layer_combinations（confirm 模式）
- tests/unit/test_tapir_adapter.py：+2 用例

### 备注
- 单测 511 → 513 全过
- 工具数 53 → 55
- 图层组合每层字段全必填：attributeId/isHidden/isLocked/isWireframe/intersectionGroupNr
- 真机验证跳过（AC 未启动）

---

## 2026-10-18 V0.35 算量模板扩充（23→29）

### 变更
- aggregate_service.py：QUANTITY_TEMPLATES +6 模板
  - roof_waterproof_area（屋面防水，Roof 表面积，010902001）
  - stair_concrete_volume（楼梯混凝土，Stair 净体积，010506001）
  - column_concrete_volume（柱混凝土，含 3% 损耗，010502001）
  - beam_concrete_volume（梁混凝土，含 3% 损耗，010505001）
  - ceiling_area（天棚抹灰，板净底面，011301001）
  - floor_finish_area（楼地面面层，板净顶面，011101001）
- tests/unit/test_aggregate.py：模板计数断言 23→29

### 备注
- 单测 513 全过
- 全部带 code_override（GB 50500 清单编码）

---
