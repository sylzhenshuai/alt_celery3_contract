"""``constants`` 模块的任务名常量一致性测试。"""

from __future__ import annotations

import pytest

from alt_celery3_contract.constants import (
    TASK_GROUP_BY_NAME,
    TASK_NAME_PREFIX,
    TASK_NAME_SET,
    TASK_NAMES,
    TaskGroup,
    TaskName,
)


def test_task_names_match_enum_members() -> None:
    """``TASK_NAMES`` 应与 ``TaskName`` 成员顺序、取值完全一致。"""
    assert TASK_NAMES == tuple(member.value for member in TaskName)


def test_task_name_set_matches_tuple() -> None:
    """``TASK_NAME_SET`` 应与 ``TASK_NAMES`` 等价。"""
    assert TASK_NAME_SET == frozenset(TASK_NAMES)
    assert len(TASK_NAME_SET) == len(TASK_NAMES)


def test_all_names_share_expected_prefix() -> None:
    """所有任务名都应带有统一的命名空间前缀。"""
    assert all(name.startswith(TASK_NAME_PREFIX) for name in TASK_NAMES)


def test_task_name_is_str_enum() -> None:
    """``TaskName`` 应可直接当字符串使用（便于路由键拼接与 JSON 序列化）。"""
    assert TaskName.ADD == "tasks.add"
    assert f"{TaskName.ADD}" == "tasks.add"


def test_group_mapping_covers_every_task() -> None:
    """分组映射必须覆盖全部任务且取值合法。"""
    assert set(TASK_GROUP_BY_NAME) == set(TASK_NAMES)
    assert all(isinstance(group, TaskGroup) for group in TASK_GROUP_BY_NAME.values())


def test_task_name_set_is_immutable() -> None:
    """``TASK_NAME_SET`` 为 ``frozenset``，不可被就地修改。"""
    with pytest.raises(AttributeError):
        TASK_NAME_SET.add("tasks.not_exist")  # type: ignore[attr-defined]
