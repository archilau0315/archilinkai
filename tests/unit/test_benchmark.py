"""benchmark.py 单元测试：计时统计 + markdown 渲染。"""

import benchmark


def test_measure_stats_shape():
    """measure 返回 4 个字段且数值合理。"""
    r = benchmark.measure(lambda: 1 + 1, rounds=4)
    assert r["rounds"] == 4
    assert 0 <= r["min"] <= r["avg"] <= r["max"]


def test_measure_calls_exactly_rounds():
    """用计数函数验证执行次数。"""
    counter = {"n": 0}

    def fn():
        counter["n"] += 1

    benchmark.measure(fn, rounds=5)
    assert counter["n"] == 5


def test_to_markdown_contains_rows():
    result = {
        "timestamp": "2026-09-25T00:00:00",
        "instance": "ac29-1", "project": "P", "version": 29,
        "rounds": 3,
        "items": [
            {"command": "GetProductInfo", "avg": 0.9, "min": 0.8, "max": 1.0},
        ],
    }
    md = benchmark.to_markdown(result)
    assert "ac29-1" in md
    assert "GetProductInfo" in md
    assert md.count("|") >= 8  # 表头+分隔+数据行
