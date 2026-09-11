"""``definitions`` 模块契约函数与 ``TASK_CATALOG`` 的自洽性测试。"""

from __future__ import annotations

import inspect

import pytest

from alt_celery3_contract.constants import TASK_GROUP_BY_NAME, TASK_NAMES, TaskName
from alt_celery3_contract.definitions import (
    TASK_CATALOG,
    build_payload,
    get_task_spec,
)
from alt_celery3_contract.schemas import AddPayload, SimulationPayload, TaskPayload

SPECS = sorted(TASK_CATALOG.values(), key=lambda spec: spec.name)


def test_catalog_covers_every_task_name() -> None:
    """``TASK_CATALOG`` 的键集合必须与 ``TASK_NAMES`` 完全一致。"""
    assert set(TASK_CATALOG) == set(TASK_NAMES)


def test_catalog_is_read_only() -> None:
    """``TASK_CATALOG`` 是只读映射，防止运行期被意外改写。"""
    with pytest.raises(TypeError):
        TASK_CATALOG["tasks.hacked"] = None  # type: ignore[index]


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.name)
def test_spec_metadata_is_consistent(spec: object) -> None:
    """每个契约条目的名称、模块、分组、描述等元数据自洽。"""
    entry = spec
    assert entry.name in TASK_CATALOG
    assert TASK_CATALOG[entry.name] is entry
    assert entry.func.__name__ == entry.name.rsplit(".", 1)[-1]
    assert entry.source_module.startswith("app.tasks.")
    assert entry.group is TASK_GROUP_BY_NAME[entry.name]
    assert entry.description
    assert entry.signature.return_annotation is not inspect.Signature.empty


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.name)
def test_contract_function_declares_only(spec: object) -> None:
    """契约函数只做声明：以任意参数调用都应抛出 ``NotImplementedError``。"""
    entry = spec
    kwargs = {name: None for name in entry.signature.parameters}
    with pytest.raises(NotImplementedError):
        entry.func(**kwargs)


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.name)
def test_payload_matches_signature(spec: object) -> None:
    """入参 Schema 的字段名与顺序必须与契约函数参数一致。"""
    entry = spec
    names = list(entry.signature.parameters)
    if entry.payload is None:
        assert len(names) <= 1
        return
    assert issubclass(entry.payload, TaskPayload)
    assert list(entry.payload.model_fields) == names


def test_all_tasks_keep_key_defaults() -> None:
    """抽查关键默认值：入参清洗后不应丢失源任务声明的默认值。"""
    assert get_task_spec(TaskName.GET_UN_GROUPS).signature.parameters["count"].default == 3
    exam_params = get_task_spec(TaskName.SIMU_EXAM).signature.parameters
    assert exam_params["min_exams"].default == 5
    assert exam_params["max_exams"].default == 10


def test_get_task_spec_raises_for_unknown_task() -> None:
    """未知任务名应抛出带排查提示的 ``KeyError``。"""
    with pytest.raises(KeyError) as excinfo:
        get_task_spec("tasks.not_exist")
    assert "tasks.not_exist" in str(excinfo.value)


def test_build_payload_success() -> None:
    """``build_payload`` 应返回已校验的强类型模型实例。"""
    payload = build_payload(TaskName.ADD.value, x=1, y=2)
    assert isinstance(payload, AddPayload)
    assert payload == AddPayload(x=1, y=2)


def test_build_payload_returns_none_without_schema() -> None:
    """无业务参数的任务没有入参 Schema，应返回 ``None``。"""
    assert build_payload(TaskName.HEARTBEAT.value) is None


def test_build_payload_reports_validation_error() -> None:
    """入参不满足约束时应抛出 ``ValidationError``。"""
    with pytest.raises(ValueError):
        build_payload(TaskName.SIMU_NCEE.value, year="not-a-year")


def test_simulation_payloads_share_structure() -> None:
    """三个入参相同的升学模拟任务共用 ``SimulationPayload`` 基类。"""
    for name in (TaskName.SIMU_NCEE, TaskName.SIMU_ADMISSION, TaskName.SIMU_GRADUATE):
        payload = get_task_spec(name).payload
        assert payload is not None
        assert issubclass(payload, SimulationPayload)
        assert set(payload.model_fields) == {"year", "threads", "limit"}
