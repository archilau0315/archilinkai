"""真机全链路集成测试：lint → 预览 → 创建 → 读回验证 → 删除 → 确认还原。

无真机自动跳过。构件建在偏远坐标（x≈60），避免与项目已有内容冲突。
跑法（项目根目录，ArchiCAD 在线时）：
    python -m pytest tests/integration/test_create_delete_chain.py -v
"""

import pytest

from archilinkai import instance_manager

try:
    instance_manager.manager.discover_instances()
    _ALL = [i.instance_id for i in instance_manager.manager.list_instances()]
except Exception:
    _ALL = []

pytestmark = pytest.mark.skipif(
    not _ALL, reason="无可用 ArchiCAD 真机，跳过集成测试"
)

INSTANCE = "ac29-1" if "ac29-1" in _ALL else _ALL[0]

# 偏远坐标小模型：2 墙 + 1 柱
PLAN = {
    "elements": [
        {"type": "Wall",
         "start": {"x": 60, "y": 60}, "end": {"x": 64, "y": 60}},
        {"type": "Wall",
         "start": {"x": 64, "y": 60}, "end": {"x": 64, "y": 64}},
        {"type": "Column", "x": 60, "y": 64},
    ]
}


def test_full_chain(mcp_tools):
    # 1. 离线校验
    lint = mcp_tools.lint_model_plan(PLAN)
    assert lint["status"] == "success", lint
    assert lint["data"]["ok"]

    # 2. 预览（不创建；service 直出：无外层 status 包装）
    preview = mcp_tools.preview_model_plan(PLAN, INSTANCE)
    assert preview["total"] == 3, preview

    # 3. confirm=false 必须拦截（异常经 _safe 包装成结构化错误）
    blocked = mcp_tools.create_from_plan(PLAN, confirm=False, instance=INSTANCE)
    assert blocked["status"] == "error"
    assert blocked["error_code"] == "CONFIRM_REQUIRED"

    # 4. 真创建 + 读回验证（service 直出：无外层 status 包装）
    created = mcp_tools.create_from_plan(PLAN, confirm=True, instance=INSTANCE)
    assert created["created"] and len(created["created"]) == 3, created
    assert not created["failed"]
    assert created["verify"]["status"] == "success"

    # 5. 删除还原
    guids = [r["guid"] for r in created["created"]]
    deleted = mcp_tools.delete_from_plan(
        {"guids": guids}, confirm=True, instance=INSTANCE)
    assert not deleted["failed"], deleted
    assert deleted["verify"]["status"] == "success"
