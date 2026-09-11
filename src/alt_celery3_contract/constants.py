"""任务名常量与分组元数据。

本模块是 ``alt_celery3`` 全部 Celery 任务「全局注册名」的唯一权威来源。
生产端与消费端都应通过 :class:`TaskName` 引用任务名，禁止继续散落硬编码字符串。

Example:
    生产端投递任务::

        from alt_celery3_contract import TaskName

        celery_app.send_task(TaskName.ADD.value, args=[1, 2])

    消费端注册任务::

        from alt_celery3_contract import TaskName

        @celery_app.task(name=TaskName.ADD.value)
        def add(x: float, y: float) -> float: ...
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final

__all__ = [
    "TASK_GROUP_BY_NAME",
    "TASK_NAMES",
    "TASK_NAME_PREFIX",
    "TASK_NAME_SET",
    "TaskGroup",
    "TaskName",
]

#: 所有任务名共有的前缀（Celery 任务命名空间）
TASK_NAME_PREFIX: Final[str] = "tasks."


class TaskName(StrEnum):
    """``alt_celery3`` 中全部 Celery 任务的全局注册名。

    成员值即装饰器 ``name=...`` 的原始字符串，也是消息队列中的路由键；
    使用 :class:`enum.StrEnum` 使其可直接参与字符串比较与 JSON 序列化。
    """

    ADD = "tasks.add"
    """加法示例任务（``app/tasks/math_tasks.py``）。"""

    HEARTBEAT = "tasks.heartbeat"
    """定时心跳任务（``app/tasks/periodic_tasks.py``）。"""

    TRY_MYSQL = "tasks.try_mysql"
    """web_db 连通性测试任务（``app/tasks/db_tasks.py``）。"""

    GET_ONE_STUDENT = "tasks.get_one_student"
    """生成单个学生并入库（``app/tasks/student_tasks.py``）。"""

    GENERATE_MANY_STUDENTS = "tasks.generate_many_students"
    """多线程批量生成学生（``app/tasks/bulk_student_tasks.py``）。"""

    GET_UN_GROUPS = "tasks.get_un_groups"
    """LLM 生成高校与专业组信息并入库（``app/tasks/un_tasks.py``）。"""

    INIT_WEB_DB = "tasks.init_web_db"
    """破坏性重建 web_db / log_db（``app/tasks/init_db_tasks.py``）。"""

    SIMU_NCEE = "tasks.simu_ncee"
    """升学模拟 · 高考评测（``app/tasks/simu_tasks.py``）。"""

    SIMU_ADMISSION = "tasks.simu_admission"
    """升学模拟 · 高校录取（``app/tasks/simu_tasks.py``）。"""

    SIMU_EXAM = "tasks.simu_exam"
    """升学模拟 · 高校日常考试（``app/tasks/simu_tasks.py``）。"""

    SIMU_GRADUATE = "tasks.simu_graduate"
    """升学模拟 · 本科毕业（``app/tasks/simu_tasks.py``）。"""


class TaskGroup(StrEnum):
    """任务按业务域的粗粒度分组，便于在目录与文档中归类展示。"""

    GENERAL = "general"
    """通用示例任务。"""

    PERIODIC = "periodic"
    """由 Beat 按计划派发的定时任务。"""

    DATABASE = "database"
    """MySQL 读写与数据库维护任务。"""

    LLM = "llm"
    """依赖大模型外部调用的任务。"""

    SIMULATION = "simulation"
    """升学全流程模拟任务链。"""


#: 全部任务名（``str`` 形态）的不可变元组，顺序与 :class:`TaskName` 声明一致
TASK_NAMES: Final[tuple[str, ...]] = tuple(member.value for member in TaskName)

#: 全部任务名的只读集合，用于 O(1) 成员判断与契约漂移检测
TASK_NAME_SET: Final[frozenset[str]] = frozenset(TASK_NAMES)

#: 任务名 -> 业务分组 的只读映射
TASK_GROUP_BY_NAME: Final[Mapping[str, TaskGroup]] = MappingProxyType(
    {
        TaskName.ADD.value: TaskGroup.GENERAL,
        TaskName.HEARTBEAT.value: TaskGroup.PERIODIC,
        TaskName.TRY_MYSQL.value: TaskGroup.DATABASE,
        TaskName.GET_ONE_STUDENT.value: TaskGroup.DATABASE,
        TaskName.GENERATE_MANY_STUDENTS.value: TaskGroup.DATABASE,
        TaskName.GET_UN_GROUPS.value: TaskGroup.LLM,
        TaskName.INIT_WEB_DB.value: TaskGroup.DATABASE,
        TaskName.SIMU_NCEE.value: TaskGroup.SIMULATION,
        TaskName.SIMU_ADMISSION.value: TaskGroup.SIMULATION,
        TaskName.SIMU_EXAM.value: TaskGroup.SIMULATION,
        TaskName.SIMU_GRADUATE.value: TaskGroup.SIMULATION,
    }
)
