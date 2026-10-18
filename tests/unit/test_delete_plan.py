# -*- coding: utf-8 -*-
"""delete_plan.py 单元测试。"""

import pytest

from archibridge.delete_plan import DeletePlan
from archibridge.errors import InvalidArgumentError


def test_basic_ok():
    plan = DeletePlan.from_dict({"guids": ["G1", "G2"]})
    assert plan.guids == ["G1", "G2"]
    assert plan.instance is None


def test_instance_kept():
    plan = DeletePlan.from_dict(
        {"instance": "ac29-1", "guids": ["G1"]}
    )
    assert plan.instance == "ac29-1"


def test_empty_guids_rejected():
    with pytest.raises(InvalidArgumentError):
        DeletePlan.from_dict({"guids": []})


def test_missing_guids_rejected():
    with pytest.raises(InvalidArgumentError):
        DeletePlan.from_dict({})


def test_non_string_guid_rejected():
    with pytest.raises(InvalidArgumentError):
        DeletePlan.from_dict({"guids": [123]})


def test_blank_guid_rejected():
    with pytest.raises(InvalidArgumentError):
        DeletePlan.from_dict({"guids": ["   "]})


def test_guids_dedup_keep_order():
    plan = DeletePlan.from_dict({"guids": ["G1", "G2", "G1"]})
    assert plan.guids == ["G1", "G2"]


def test_guid_stripped():
    plan = DeletePlan.from_dict({"guids": ["  G1  "]})
    assert plan.guids == ["G1"]


def test_too_many_guids_rejected():
    with pytest.raises(InvalidArgumentError):
        DeletePlan.from_dict(
            {"guids": [f"G{i}" for i in range(201)]}
        )


def test_to_dict_roundtrip():
    plan = DeletePlan.from_dict(
        {"instance": "ac29-1", "guids": ["G1"]}
    )
    assert plan.to_dict() == {
        "instance": "ac29-1", "guids": ["G1"]
    }
