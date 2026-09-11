"""契约与 ``alt_celery3`` 源任务签名的端到端一致性测试。

若同级目录下不存在 ``alt_celery3`` 源项目，则整组用例自动跳过。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from alt_celery3_contract.constants import TASK_NAMES
from alt_celery3_contract.verify import verify

#: 同级目录下的源项目根目录
SOURCE_ROOT = Path(__file__).resolve().parents[2] / "alt_celery3"

pytestmark = pytest.mark.skipif(
    not (SOURCE_ROOT / "app" / "tasks").is_dir(),
    reason=f"未找到 alt_celery3 源项目: {SOURCE_ROOT}",
)


def _source_dependencies_available() -> bool:
    """判断源项目的运行时依赖是否齐备（决定能否使用 inspect 后端）。

    Returns:
        bool: 全部依赖可导入返回 ``True``。
    """
    return all(
        importlib.util.find_spec(module) is not None
        for module in ("celery", "dotenv", "sclog_lite", "sedb_mysql")
    )


def test_ast_backend_reports_full_conformance() -> None:
    """纯静态扫描下，契约与源任务签名应完全一致。"""
    report = verify(SOURCE_ROOT, "ast")

    assert report.backend == "ast"
    assert not report.missing_in_catalog, f"契约缺失任务: {report.missing_in_catalog}"
    assert not report.extra_in_catalog, f"契约多余任务: {report.extra_in_catalog}"
    assert {task.name for task in report.source_tasks} == set(TASK_NAMES)
    assert report.ok, [result for result in report.results if not result.ok]


def test_ast_backend_extracts_expected_inventory() -> None:
    """静态扫描应提取到 11 个任务，且 ``bind`` 首参均被正确剥离。"""
    report = verify(SOURCE_ROOT, "ast")
    tasks = {task.name: task for task in report.source_tasks}

    assert len(tasks) == 11
    # bind=True 的任务不应把 self 带进契约参数
    assert [param.name for param in tasks["tasks.simu_ncee"].params] == ["year", "threads", "limit"]
    assert [param.name for param in tasks["tasks.init_web_db"].params] == []
    assert [param.name for param in tasks["tasks.add"].params] == ["x", "y"]


@pytest.mark.skipif(
    not _source_dependencies_available(),
    reason="源项目运行时依赖（celery 等）未安装，跳过 inspect 后端校验",
)
def test_inspect_backend_reports_full_conformance() -> None:
    """源依赖齐备时，运行时 ``inspect`` 校验同样应全部通过。"""
    report = verify(SOURCE_ROOT, "inspect")
    assert report.backend == "inspect"
    assert report.ok, [result for result in report.results if not result.ok]
    sys.modules.pop("app", None)
