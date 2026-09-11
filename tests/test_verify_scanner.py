"""静态扫描器的提取规则测试（基于临时构造的迷你源项目）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from alt_celery3_contract.verify import discover_source_tasks

DEMO_MODULE = '''"""临时演示任务模块。"""

from __future__ import annotations

from typing import Any

from alt_celery3_contract import TaskName


@celery_app.task(name="tasks.add")
def add(x: float, y: float) -> float:
    """字面量任务名。"""
    return x + y


@celery_app.task(name=TaskName.SIMU_NCEE.value, bind=True)
def simu_ncee(self: Any, year: int, threads: int | None = None) -> dict[str, Any]:
    """契约常量任务名 + bind 首参剥离。"""
    return {}


@shared_task(name=TaskName.HEARTBEAT.value)
def heartbeat() -> dict[str, Any]:
    """shared_task 装饰器形态。"""
    return {}


def plain_helper(value: int) -> int:
    """非任务函数，不应被识别。"""
    return value
'''


def _build_source_tree(tmp_path: Path) -> Path:
    """构造一个最小的源项目目录树。

    Args:
        tmp_path: pytest 提供的临时目录。

    Returns:
        Path: 源项目根目录。
    """
    tasks_dir = tmp_path / "app" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tmp_path / "app" / "__init__.py").write_text("", encoding="utf-8")
    (tasks_dir / "__init__.py").write_text("", encoding="utf-8")
    (tasks_dir / "demo_tasks.py").write_text(DEMO_MODULE, encoding="utf-8")
    return tmp_path


def test_scanner_resolves_task_names_and_bind(tmp_path: Path) -> None:
    """扫描器应解析字面量与 ``TaskName.X.value`` 两种任务名，并剥离 bind 首参。"""
    source_root = _build_source_tree(tmp_path)
    tasks, backend = discover_source_tasks(source_root, "ast")
    found = {task.name: task for task in tasks}

    assert backend == "ast"
    assert set(found) == {"tasks.add", "tasks.simu_ncee", "tasks.heartbeat"}

    assert [param.name for param in found["tasks.add"].params] == ["x", "y"]
    # bind=True：self 必须被剥离
    assert [param.name for param in found["tasks.simu_ncee"].params] == ["year", "threads"]
    assert found["tasks.heartbeat"].params == ()
    assert found["tasks.heartbeat"].returns == "dict[str,Any]"


def test_scanner_ignores_plain_functions(tmp_path: Path) -> None:
    """未被任务装饰器修饰的函数不应进入任务清单。"""
    source_root = _build_source_tree(tmp_path)
    tasks, _ = discover_source_tasks(source_root, "ast")
    assert "plain_helper" not in {task.func_name for task in tasks}


def test_scanner_extracts_defaults_and_annotations(tmp_path: Path) -> None:
    """默认值与类型注解应按源文本归一化提取。"""
    source_root = _build_source_tree(tmp_path)
    tasks, _ = discover_source_tasks(source_root, "ast")
    simu = next(task for task in tasks if task.name == "tasks.simu_ncee")
    year_param, threads_param = simu.params

    assert simu.bind is True
    assert simu.module == "app.tasks.demo_tasks"
    assert (year_param.annotation, year_param.default) == ("int", None)
    # ``int | None`` 归一化后联合成员按字典序排列
    assert (threads_param.annotation, threads_param.default) == ("None|int", "None")


def test_scanner_reports_missing_source_root(tmp_path: Path) -> None:
    """源项目目录不存在时应抛出 ``FileNotFoundError``。"""
    with pytest.raises(FileNotFoundError):
        discover_source_tasks(tmp_path / "not-exist", "ast")


def test_scanner_rejects_unknown_mode(tmp_path: Path) -> None:
    """非法的签名后端取值应抛出 ``ValueError``。"""
    with pytest.raises(ValueError, match="mode"):
        discover_source_tasks(_build_source_tree(tmp_path), "magic")
