"""plan_preview.py 单元测试：统计、墙总长、预览文字。"""

from archilinkai.model_plan import ModelPlan
from archilinkai.plan_preview import build_preview


def _plan(elements):
    return ModelPlan.from_dict({"elements": elements})


def test_counts_and_total():
    plan = _plan([
        {"type": "Wall",
         "start": {"x": 0, "y": 0}, "end": {"x": 6, "y": 0}},
        {"type": "Column", "x": 0, "y": 0},
        {"type": "Column", "x": 6, "y": 0},
    ])
    preview = build_preview(plan, "Tapir", "1.5.9")
    assert preview["total"] == 3
    assert preview["counts"] == {"Wall": 1, "Column": 2}
    assert preview["wall_total_length"] == 6.0
    assert preview["channel"] == "Tapir 1.5.9"


def test_wall_total_length_sums_all_walls():
    plan = _plan([
        {"type": "Wall",
         "start": {"x": 0, "y": 0}, "end": {"x": 3, "y": 0}},
        {"type": "Wall",
         "start": {"x": 0, "y": 0}, "end": {"x": 0, "y": 4}},
    ])
    assert build_preview(plan)["wall_total_length"] == 7.0


def test_summary_text_mentions_walls_and_columns():
    plan = _plan([
        {"type": "Wall",
         "start": {"x": 0, "y": 0}, "end": {"x": 6, "y": 0}},
        {"type": "Column", "x": 0, "y": 0},
    ])
    summary = build_preview(plan)["summary"]
    assert "墙 1 面" in summary
    assert "柱 1 根" in summary
    assert "6.00m" in summary


def test_elements_have_readable_text():
    plan = _plan([
        {"type": "Wall",
         "start": {"x": 0, "y": 0}, "end": {"x": 6, "y": 0}},
        {"type": "Column", "x": 2, "y": 3},
    ])
    rows = build_preview(plan)["elements"]
    assert "长 6.00m" in rows[0]["text"]
    assert "(2,3)" in rows[1]["text"]
    assert rows[0]["index"] == 0 and rows[1]["index"] == 1


def test_no_channel_omits_field():
    plan = _plan([{"type": "Column", "x": 0, "y": 0}])
    assert "channel" not in build_preview(plan)


# --- 梁板（V0.1 新增）----------------------------------------------------


def test_beam_slab_summary_and_details():
    plan = _plan([
        {"type": "Beam",
         "start": {"x": 0, "y": 0}, "end": {"x": 6, "y": 0}, "z": 3.0},
        {"type": "Slab", "polygon": [
            {"x": 0, "y": 0}, {"x": 6, "y": 0},
            {"x": 6, "y": 4}, {"x": 0, "y": 4}]},
    ])
    preview = build_preview(plan, "Tapir", "1.5.9")
    assert preview["counts"] == {"Beam": 1, "Slab": 1}
    assert "梁 1 根" in preview["summary"]
    assert "板 1 块" in preview["summary"]
    rows = preview["elements"]
    assert "截面 0.2×0.3m" in rows[0]["text"]
    assert "顶标高 3m" in rows[0]["text"]
    assert "4 个顶点" in rows[1]["text"]
    assert "厚 0.2m" in rows[1]["text"]


def test_slab_detail_shows_bounding_box():
    plan = _plan([{"type": "Slab", "polygon": [
        {"x": 1, "y": 2}, {"x": 7, "y": 2}, {"x": 7, "y": 5}]}])
    text = build_preview(plan)["elements"][0]["text"]
    assert "(1,2)~(7,5)" in text


# --- 门 / 窗（V0.2 新增）-------------------------------------------------


def test_door_window_preview_details():
    plan = _plan([
        {"type": "Wall",
         "start": {"x": 0, "y": 0}, "end": {"x": 6, "y": 0}},
        {"type": "Window", "wall": 0, "offset": 3.0},
        {"type": "Door", "wall": "ABCDEF12-3456-7890-ABCD-EF1234567890",
         "offset": 1.0},
    ])
    preview = build_preview(plan, "Tapir", "1.5.9")
    assert preview["counts"] == {"Wall": 1, "Window": 1, "Door": 1}
    assert "窗 1 扇" in preview["summary"]
    assert "门 1 扇" in preview["summary"]

    win_text = preview["elements"][1]["text"]
    door_text = preview["elements"][2]["text"]
    assert "计划墙#0" in win_text
    assert "距墙起点 3m" in win_text
    assert "窗台高 0.9m" in win_text
    assert "已有墙 ABCDEF12…" in door_text
    assert "门槛高 0m" in door_text
    # risk 提到门窗挂直墙
    assert "直墙" in preview["risk"]


def test_window_guid_reference_text():
    plan = _plan([{"type": "Window", "wall": "12345678-ABCD"}])
    text = build_preview(plan)["elements"][0]["text"]
    assert "已有墙 12345678…" in text


def test_stair_roof_morph_preview_text():
    plan = _plan([
        {"type": "Stair",
         "start": {"x": 0, "y": 0}, "end": {"x": 4, "y": 0}, "steps": 13},
        {"type": "Roof",
         "polygon": [{"x": 0, "y": 0}, {"x": 6, "y": 0}, {"x": 6, "y": 4}],
         "slope": 30},
        {"type": "Morph"},
    ])
    texts = [e["text"] for e in build_preview(plan)["elements"]]
    assert "楼梯" in texts[0] and "13 级" in texts[0]
    assert "屋顶" in texts[1] and "单坡 30°" in texts[1]
    assert "转轴取第 1 条边" in texts[1]
    assert "变形体" in texts[2] and "方块" in texts[2]


def test_multiplane_roof_text():
    plan = _plan([
        {"type": "Roof",
         "polygon": [{"x": 0, "y": 0}, {"x": 6, "y": 0}, {"x": 6, "y": 4}]}
    ])
    text = build_preview(plan)["elements"][0]["text"]
    assert "多平面" in text
