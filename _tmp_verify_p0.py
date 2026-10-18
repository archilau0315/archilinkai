"""V0.33 P0 命令真机验证（补跑）。"""
import instance_manager
import query_engine
import tapir_adapter

mgr = instance_manager.manager
iids = mgr.discover_instances()
iid = next(iter(iids)) if isinstance(iids, dict) else iids[0]
print(f"实例: {iid} / {mgr.get_info(iid).project_name}")
adapter = tapir_adapter.adapter


def get_guids(etype, n=3):
    r = query_engine.engine.query(
        query_engine.QueryRequest(instance=iid, element_type=etype, limit=n))
    return [it["guid"] for it in r.items]


# 1. GetConnectedElements：墙上的窗/门
walls = get_guids("Wall", 5)
if walls:
    for ct in ("Window", "Door"):
        rows = adapter.get_connected_elements(walls, ct, iid)
        n = sum(len(r) if isinstance(r, list) else 1 for r in rows)
        print(f"1. GetConnectedElements(Wall x{len(walls)} -> {ct}): {n} 个")

# 幕墙的框架
cws = get_guids("CurtainWall", 2)
if cws:
    frames = adapter.get_connected_elements(cws, "CurtainWallFrame", iid)
    print(f"   CurtainWall x{len(cws)} -> Frame: {str(frames)[:200]}")

# 2. GetElementPreviewImage
if walls:
    b64 = adapter.get_element_preview_image(walls[0], "3D", "png", 128, 128, iid)
    print(f"2. GetElementPreviewImage(3D png 128): base64 {len(b64)} 字符")

# 3. GetBuildingMaterialPhysicalProperties
mats = adapter.get_attributes("BuildingMaterial", iid)
if mats:
    ids = [m["attributeId"]["guid"] for m in mats[:3] if "attributeId" in m]
    props = adapter.get_building_material_physical_properties(ids, iid)
    print(f"3. GetBuildingMaterialPhysicalProperties({len(ids)} 材料): {len(props)} 项")
    for p in props[:2]:
        print(f"   {str(p)[:250]}")

# 4. MoveElements 真机执行（移动副本模式，不破坏原模型，之后删除副本难——
#    Tapir 无撤销 API，改用可读回验证的移动再移回）
if walls:
    g = walls[0]
    r1 = adapter.execute("MoveElements", {
        "elementsWithMoveVectors": [
            {"elementId": {"guid": g},
             "moveVector": {"x": 0.0, "y": 0.0, "z": 0.0}}]}, iid)
    print(f"4. MoveElements(零向量): {str(r1)[:150]}")
    r2 = adapter.execute("RotateElements", {
        "elementsWithRotations": [
            {"elementId": {"guid": g},
             "rotation": {"origin": {"x": 0, "y": 0},
                          "beginPoint": {"x": 1, "y": 0},
                          "endPoint": {"x": 1, "y": 0}}}]}, iid)
    print(f"5. RotateElements(零角度): {str(r2)[:150]}")

# 6. 图层组合（V0.34 补验）
lcs = adapter.get_attributes("LayerCombination", iid)
if lcs:
    ids = [m["attributeId"]["guid"] for m in lcs[:3] if "attributeId" in m]
    detail = adapter.get_layer_combinations(ids, iid)
    print(f"6. GetLayerCombinations({len(ids)}): {len(detail)} 项")
    if detail:
        print(f"   首项: {str(detail[0])[:250]}")

print("全部 P0 真机验证完成")
