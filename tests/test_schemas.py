"""``schemas`` 模块入参模型的校验行为测试。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from alt_celery3_contract.schemas import (
    AddPayload,
    GenerateManyStudentsPayload,
    GetUnGroupsPayload,
    SimuAdmissionPayload,
    SimuExamPayload,
    SimuNceePayload,
)


def test_add_payload_accepts_numeric_strings() -> None:
    """加法任务是 ``float()`` 宽松语义，字符串数字应被接受。"""
    payload = AddPayload(x="1", y="2")
    assert (payload.x, payload.y) == (1.0, 2.0)


def test_payload_rejects_unknown_field() -> None:
    """契约模型拒绝未知字段，避免静默传错参数名。"""
    with pytest.raises(ValidationError):
        AddPayload(x=1, y=2, z=3)  # type: ignore[call-arg]


def test_payload_is_frozen() -> None:
    """契约模型不可变，避免任务投递过程中被意外篡改。"""
    payload = AddPayload(x=1, y=2)
    with pytest.raises(ValidationError):
        payload.x = 10  # type: ignore[misc]


def test_get_un_groups_default_count() -> None:
    """``count`` 默认值为 3。"""
    assert GetUnGroupsPayload().count == 3


@pytest.mark.parametrize("count", [0, -1, 1.5, "3", True])
def test_get_un_groups_rejects_invalid_count(count: object) -> None:
    """``count`` 必须为严格正整数（字符串与布尔值均不接受）。"""
    with pytest.raises(ValidationError):
        GetUnGroupsPayload(count=count)  # type: ignore[arg-type]


def test_generate_many_students_defaults() -> None:
    """批量生成任务的缺省值与源任务签名一致。"""
    payload = GenerateManyStudentsPayload(numbers=10)
    assert payload.birthday_min is None
    assert payload.birthday_max is None
    assert payload.threads is None


@pytest.mark.parametrize("threads", [0, 65, -1, "8", True])
def test_generate_many_students_rejects_bad_threads(threads: object) -> None:
    """``threads`` 必须为 1~64 的严格整数。"""
    with pytest.raises(ValidationError):
        GenerateManyStudentsPayload(numbers=1, threads=threads)  # type: ignore[arg-type]


def test_generate_many_students_rejects_bad_date_format() -> None:
    """出生日期必须为 ``YYYY-MM-DD``。"""
    with pytest.raises(ValidationError):
        GenerateManyStudentsPayload(numbers=1, birthday_min="01-01-2000")


def test_generate_many_students_rejects_reversed_range() -> None:
    """出生日期下限不得晚于上限。"""
    with pytest.raises(ValidationError):
        GenerateManyStudentsPayload(
            numbers=1, birthday_min="2012-12-31", birthday_max="2005-01-01"
        )


def test_generate_many_students_uses_default_when_one_side_missing() -> None:
    """只给定一侧时，另一侧按服务端默认值参与区间校验。"""
    payload = GenerateManyStudentsPayload(numbers=1, birthday_min="2001-01-01")
    assert payload.birthday_min == "2001-01-01"
    with pytest.raises(ValidationError):
        GenerateManyStudentsPayload(numbers=1, birthday_min="2100-01-01")


@pytest.mark.parametrize("year", [1999, 2101, "2026", True])
def test_simulation_payload_rejects_bad_year(year: object) -> None:
    """升学模拟任务的年份必须落在 2000~2100 且为严格整数。"""
    with pytest.raises(ValidationError):
        SimuNceePayload(year=year)  # type: ignore[arg-type]


def test_simulation_payload_defaults() -> None:
    """升学模拟任务的可选参数缺省值均为 ``None``。"""
    for payload in (SimuNceePayload(year=2026), SimuAdmissionPayload(year=2026)):
        assert payload.threads is None
        assert payload.limit is None


def test_simu_exam_payload_defaults_and_range() -> None:
    """日常考试任务的考试次数区间需满足 ``1 <= min <= max <= 20``。"""
    payload = SimuExamPayload(year=2026)
    assert (payload.min_exams, payload.max_exams) == (5, 10)

    with pytest.raises(ValidationError):
        SimuExamPayload(year=2026, min_exams=10, max_exams=5)
    with pytest.raises(ValidationError):
        SimuExamPayload(year=2026, max_exams=21)
