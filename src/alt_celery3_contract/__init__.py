"""alt-celery3-contract：``alt_celery3`` 的纯声明式强类型任务契约包。

本包由静态扫描 ``alt_celery3`` 的 Celery 任务生成，只承载 **契约**，
不承载任何业务实现，也不依赖 Celery / 数据库 / LLM SDK：

* :mod:`alt_celery3_contract.constants` —— 任务名常量（``TaskName``）；
* :mod:`alt_celery3_contract.schemas` —— Pydantic 入参模型（``*Payload``）；
* :mod:`alt_celery3_contract.definitions` —— 契约函数与 ``TASK_CATALOG``；
* :mod:`alt_celery3_contract.verify` —— 基于 :mod:`inspect` 的契约一致性校验器。

Example:
    生产端按契约投递任务::

        from alt_celery3_contract import TaskName, AddPayload

        payload = AddPayload(x=1, y=2)
        celery_app.send_task(TaskName.ADD.value, kwargs=payload.model_dump())

    消费端按契约注册任务::

        from alt_celery3_contract import TaskName

        @celery_app.task(name=TaskName.ADD.value)
        def add(x: float, y: float) -> float:
            return float(x) + float(y)
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from alt_celery3_contract.constants import (
    TASK_GROUP_BY_NAME,
    TASK_NAME_PREFIX,
    TASK_NAME_SET,
    TASK_NAMES,
    TaskGroup,
    TaskName,
)
from alt_celery3_contract.definitions import (
    TASK_CATALOG,
    TaskSpec,
    add,
    build_payload,
    generate_many_students,
    get_one_student,
    get_task_spec,
    get_un_groups,
    heartbeat,
    init_web_db,
    simu_admission,
    simu_exam,
    simu_graduate,
    simu_ncee,
    try_mysql,
)
from alt_celery3_contract.schemas import (
    DEFAULT_BIRTHDAY_MAX,
    DEFAULT_BIRTHDAY_MIN,
    AddPayload,
    GenerateManyStudentsPayload,
    GetUnGroupsPayload,
    SimuAdmissionPayload,
    SimuExamPayload,
    SimuGraduatePayload,
    SimulationPayload,
    SimuNceePayload,
    TaskPayload,
)

try:  # pragma: no cover - 仅在未安装（纯源码路径导入）时回退
    __version__ = version("alt-celery3-contract")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0.dev0"

__all__ = [
    "DEFAULT_BIRTHDAY_MAX",
    "DEFAULT_BIRTHDAY_MIN",
    "TASK_CATALOG",
    "TASK_GROUP_BY_NAME",
    "TASK_NAMES",
    "TASK_NAME_PREFIX",
    "TASK_NAME_SET",
    "AddPayload",
    "GenerateManyStudentsPayload",
    "GetUnGroupsPayload",
    "SimuAdmissionPayload",
    "SimuExamPayload",
    "SimuGraduatePayload",
    "SimuNceePayload",
    "SimulationPayload",
    "TaskGroup",
    "TaskName",
    "TaskPayload",
    "TaskSpec",
    "__version__",
    "add",
    "build_payload",
    "generate_many_students",
    "get_one_student",
    "get_task_spec",
    "get_un_groups",
    "heartbeat",
    "init_web_db",
    "simu_admission",
    "simu_exam",
    "simu_graduate",
    "simu_ncee",
    "try_mysql",
]
