"""任务契约函数的纯声明实现与全局任务目录 ``TASK_CATALOG``。

本模块为 ``alt_celery3`` 中的每一个 Celery 任务声明一个 **同名契约函数**：

* 函数签名（参数名、类型注解、默认值）与源任务逐一对应；
* 启用 ``bind=True`` 的任务，其首参（``self`` / ``task``）已被剥离，
  因此契约签名只保留业务参数；
* 函数体一律 ``raise NotImplementedError`` —— 契约包不承载任何业务实现
  （数据库读写、外部 API 调用、第三方依赖全部留在服务端）。

调用方据此获得 IDE 补全与静态类型检查；真正的执行仍然是通过 Celery
按 :data:`alt_celery3_contract.constants.TASK_NAMES` 中的任务名投递消息。
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final

from alt_celery3_contract.constants import TaskGroup, TaskName
from alt_celery3_contract.schemas import (
    AddPayload,
    GenerateManyStudentsPayload,
    GetUnGroupsPayload,
    SimuAdmissionPayload,
    SimuExamPayload,
    SimuGraduatePayload,
    SimuNceePayload,
    TaskPayload,
)

__all__ = [
    "TASK_CATALOG",
    "TaskSpec",
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


def _not_implemented(task: TaskName) -> NotImplementedError:
    """构造统一的 ``NotImplementedError``（契约层无实现）。

    Args:
        task: 触发异常的契约任务名。

    Returns:
        NotImplementedError: 携带排查指引的异常实例。
    """
    return NotImplementedError(
        f"契约函数 {task} 仅用于类型声明与任务名路由，不承载业务实现；"
        f"请以 {task!r} 为任务名投递真实 Celery 任务。"
    )


# ============================================================
# 通用任务（TaskGroup.GENERAL）
# ============================================================
def add(x: float, y: float) -> float:
    """计算两个数字之和。

    Args:
        x: 第一个加数。
        y: 第二个加数。

    Returns:
        两数之和（浮点数）。

    Raises:
        TypeError: 当参数无法转换为数字时抛出。
        NotImplementedError: 契约声明不承载实现。
    """
    raise _not_implemented(TaskName.ADD)


# ============================================================
# 定时任务（TaskGroup.PERIODIC）
# ============================================================
def heartbeat() -> dict[str, Any]:
    """定时心跳任务：记录执行时间与累计执行次数。

    由 Beat 按计划触发，并把最近一次结果写入 Redis 供外部随时查询。

    Returns:
        包含 ``timestamp``（执行时间）、``worker``（执行节点）、
        ``run_count``（累计次数）的结果字典。

    Raises:
        NotImplementedError: 契约声明不承载实现。
    """
    raise _not_implemented(TaskName.HEARTBEAT)


# ============================================================
# 数据库任务（TaskGroup.DATABASE）
# ============================================================
def try_mysql() -> dict[str, Any]:
    """测试 web_db 数据库连通性。

    Returns:
        包含 ``success``、``message``、``latency_ms``、``server_version``、
        ``error_type`` 的结果字典（连通性失败本身也视为有效结果，不抛异常）。

    Raises:
        NotImplementedError: 契约声明不承载实现。
    """
    raise _not_implemented(TaskName.TRY_MYSQL)


def get_one_student() -> dict[str, Any]:
    """生成单个学生并保存到 web_db。

    Returns:
        新入库学生的完整信息（含自增 ``id`` 与入库时间）。

    Raises:
        Exception: 数据库读写失败时由服务端抛出，任务被标记为失败。
        NotImplementedError: 契约声明不承载实现。
    """
    raise _not_implemented(TaskName.GET_ONE_STUDENT)


def generate_many_students(
    numbers: int,
    birthday_min: str | None = None,
    birthday_max: str | None = None,
    threads: int | None = None,
) -> dict[str, Any]:
    """多线程批量生成学生信息并写入 web_db.students 表。

    Args:
        numbers: 要生成的人数，正整数。
        birthday_min: 出生年月日下限（含），``"YYYY-MM-DD"`` 格式；
            为 ``None`` 时使用默认值 ``2000-01-01``。
        birthday_max: 出生年月日上限（含），``"YYYY-MM-DD"`` 格式；
            为 ``None`` 时使用默认值 ``2015-12-31``。
        threads: 并发线程数（1~64）；为 ``None`` 时使用默认值 8，
            实际分片数不超过 ``numbers``。

    Returns:
        统计结果字典，包含请求数量、实际插入数量、表内总数、线程数、
        生日范围、耗时与每秒插入行数。

    Raises:
        ValueError: ``numbers`` 非正整数、``threads`` 超出 1~64 范围，
            或生日范围格式非法 / 起止倒置。
        Exception: 数据库写入失败时由服务端抛出，任务被标记为失败。
        NotImplementedError: 契约声明不承载实现。
    """
    raise _not_implemented(TaskName.GENERATE_MANY_STUDENTS)


def init_web_db() -> dict[str, Any]:
    """删除并重建 web_db / log_db 与全部业务表（破坏性初始化任务）。

    注意:
        该任务会清空业务库中的全部数据，仅应在初始化环境或确认数据可
        丢弃时调用。

    Returns:
        初始化摘要，含 ``dropped_databases`` / ``dropped_users`` /
        ``created_users`` / ``tables`` / ``verification`` / ``elapsed_seconds``。

    Raises:
        ValueError: 必要的环境变量（管理员账号 / 用户密码）未配置时抛出。
        Exception: 数据库连接或 DDL 执行失败时由服务端抛出，任务被标记为失败。
        NotImplementedError: 契约声明不承载实现。
    """
    raise _not_implemented(TaskName.INIT_WEB_DB)


# ============================================================
# 大模型任务（TaskGroup.LLM）
# ============================================================
def get_un_groups(count: int = 3) -> list[dict[str, Any]]:
    """获取指定数量的高校信息（含专业组）并写入 test_db。

    Args:
        count: 要获取的高校数量，正整数（默认 3）。

    Returns:
        标准 JSON 数组，每项包含 ``name`` / ``code`` / ``type`` /
        ``nature`` / ``majors`` 字段。

    Raises:
        ValueError: ``count`` 非正整数，或上游返回的 JSON 结构非法。
        Exception: API 调用或数据库写入失败时由服务端抛出。
        NotImplementedError: 契约声明不承载实现。
    """
    raise _not_implemented(TaskName.GET_UN_GROUPS)


# ============================================================
# 升学全流程模拟（TaskGroup.SIMULATION）
# ============================================================
def simu_ncee(
    year: int,
    threads: int | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """模拟高考：为高三年龄段且未高考的学生生成高考成绩。

    Args:
        year: 高考年份（2000~2100）。
        threads: 并发线程数（1~64，默认 8）。
        limit: 可选的处理行数上限（调试用，``None`` 表示全部）。

    Returns:
        统计结果（年份、考试日期、处理人数、耗时等）。

    Raises:
        ValueError: 参数非法。
        NotImplementedError: 契约声明不承载实现。
    """
    raise _not_implemented(TaskName.SIMU_NCEE)


def simu_admission(
    year: int,
    threads: int | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """模拟高校录取：按高考成绩分批次录取到高校与专业组。

    录取按当年高考成绩排名分档：前 5% 录取 985、5%~15% 录取 211、
    15%~30% 录取一本、其余录取其他高校。

    Args:
        year: 高考 / 录取年份（2000~2100）。
        threads: 并发线程数（1~64，默认 8）。
        limit: 可选的处理行数上限（调试用）。

    Returns:
        统计结果（各批次录取人数、处理总数、耗时等）。

    Raises:
        ValueError: 参数非法。
        NotImplementedError: 契约声明不承载实现。
    """
    raise _not_implemented(TaskName.SIMU_ADMISSION)


def simu_exam(
    year: int,
    threads: int | None = None,
    limit: int | None = None,
    min_exams: int = 5,
    max_exams: int = 10,
) -> dict[str, Any]:
    """模拟高校日常考试：为在读学生生成一学年的课程成绩。

    Args:
        year: 学年（自然年，2000~2100）。
        threads: 并发线程数（1~64，默认 8）。
        limit: 可选的处理行数上限（调试用）。
        min_exams: 每名学生最少考试次数（默认 5）。
        max_exams: 每名学生最多考试次数（默认 10）。

    Returns:
        统计结果（处理人数、写入成绩条数、耗时等）。

    Raises:
        ValueError: 参数非法（含 ``min_exams`` / ``max_exams`` 区间非法）。
        NotImplementedError: 契约声明不承载实现。
    """
    raise _not_implemented(TaskName.SIMU_EXAM)


def simu_graduate(
    year: int,
    threads: int | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """模拟本科毕业：计算大四学生绩点并登记毕业信息。

    Args:
        year: 毕业年份（2000~2100）。
        threads: 并发线程数（1~64，默认 8）。
        limit: 可选的处理行数上限（调试用）。

    Returns:
        统计结果（处理人数、平均 GPA、耗时等）。

    Raises:
        ValueError: 参数非法。
        NotImplementedError: 契约声明不承载实现。
    """
    raise _not_implemented(TaskName.SIMU_GRADUATE)


@dataclass(frozen=True, slots=True)
class TaskSpec:
    """单个任务的契约描述条目（``TASK_CATALOG`` 的值类型）。

    Attributes:
        name: 任务的全局注册名，等价于 ``TaskName`` 成员值。
        func: 对应的契约函数（仅签名，无实现）。
        payload: 对应的 Pydantic 入参模型；无业务参数的任务为 ``None``。
        source_module: 服务端承载该任务的模块路径，便于排查与联调。
        bind: 源任务是否使用 ``bind=True``（``True`` 表示首参已剥离）。
        group: 任务所属业务分组。
        description: 任务的一句话描述（取自契约函数 docstring 首行）。
    """

    name: str
    func: Callable[..., Any]
    payload: type[TaskPayload] | None
    source_module: str
    bind: bool
    group: TaskGroup
    description: str

    @property
    def signature(self) -> inspect.Signature:
        """返回契约函数的签名对象（仅含业务参数）。

        Returns:
            契约函数的 :class:`inspect.Signature`。
        """
        return inspect.signature(self.func)


#: 全局任务目录：任务名 -> 契约函数与入参 Schema 的只读映射
TASK_CATALOG: Final[Mapping[str, TaskSpec]] = MappingProxyType(
    {
        TaskName.ADD.value: TaskSpec(
            name=TaskName.ADD.value,
            func=add,
            payload=AddPayload,
            source_module="app.tasks.math_tasks",
            bind=False,
            group=TaskGroup.GENERAL,
            description="计算两个数字之和。",
        ),
        TaskName.HEARTBEAT.value: TaskSpec(
            name=TaskName.HEARTBEAT.value,
            func=heartbeat,
            payload=None,
            source_module="app.tasks.periodic_tasks",
            bind=False,
            group=TaskGroup.PERIODIC,
            description="定时心跳任务：记录执行时间与累计执行次数。",
        ),
        TaskName.TRY_MYSQL.value: TaskSpec(
            name=TaskName.TRY_MYSQL.value,
            func=try_mysql,
            payload=None,
            source_module="app.tasks.db_tasks",
            bind=False,
            group=TaskGroup.DATABASE,
            description="测试 web_db 数据库连通性。",
        ),
        TaskName.GET_ONE_STUDENT.value: TaskSpec(
            name=TaskName.GET_ONE_STUDENT.value,
            func=get_one_student,
            payload=None,
            source_module="app.tasks.student_tasks",
            bind=False,
            group=TaskGroup.DATABASE,
            description="生成单个学生并保存到 web_db。",
        ),
        TaskName.GENERATE_MANY_STUDENTS.value: TaskSpec(
            name=TaskName.GENERATE_MANY_STUDENTS.value,
            func=generate_many_students,
            payload=GenerateManyStudentsPayload,
            source_module="app.tasks.bulk_student_tasks",
            bind=True,
            group=TaskGroup.DATABASE,
            description="多线程批量生成学生信息并写入 web_db.students 表。",
        ),
        TaskName.INIT_WEB_DB.value: TaskSpec(
            name=TaskName.INIT_WEB_DB.value,
            func=init_web_db,
            payload=None,
            source_module="app.tasks.init_db_tasks",
            bind=True,
            group=TaskGroup.DATABASE,
            description="删除并重建 web_db / log_db 与全部业务表（破坏性初始化任务）。",
        ),
        TaskName.GET_UN_GROUPS.value: TaskSpec(
            name=TaskName.GET_UN_GROUPS.value,
            func=get_un_groups,
            payload=GetUnGroupsPayload,
            source_module="app.tasks.un_tasks",
            bind=False,
            group=TaskGroup.LLM,
            description="获取指定数量的高校信息（含专业组）并写入 test_db。",
        ),
        TaskName.SIMU_NCEE.value: TaskSpec(
            name=TaskName.SIMU_NCEE.value,
            func=simu_ncee,
            payload=SimuNceePayload,
            source_module="app.tasks.simu_tasks",
            bind=True,
            group=TaskGroup.SIMULATION,
            description="模拟高考：为高三年龄段且未高考的学生生成高考成绩。",
        ),
        TaskName.SIMU_ADMISSION.value: TaskSpec(
            name=TaskName.SIMU_ADMISSION.value,
            func=simu_admission,
            payload=SimuAdmissionPayload,
            source_module="app.tasks.simu_tasks",
            bind=True,
            group=TaskGroup.SIMULATION,
            description="模拟高校录取：按高考成绩分批次录取到高校与专业组。",
        ),
        TaskName.SIMU_EXAM.value: TaskSpec(
            name=TaskName.SIMU_EXAM.value,
            func=simu_exam,
            payload=SimuExamPayload,
            source_module="app.tasks.simu_tasks",
            bind=True,
            group=TaskGroup.SIMULATION,
            description="模拟高校日常考试：为在读学生生成一学年的课程成绩。",
        ),
        TaskName.SIMU_GRADUATE.value: TaskSpec(
            name=TaskName.SIMU_GRADUATE.value,
            func=simu_graduate,
            payload=SimuGraduatePayload,
            source_module="app.tasks.simu_tasks",
            bind=True,
            group=TaskGroup.SIMULATION,
            description="模拟本科毕业：计算大四学生绩点并登记毕业信息。",
        ),
    }
)


def get_task_spec(name: str) -> TaskSpec:
    """按任务名获取契约条目。

    Args:
        name: 任务的全局注册名（``TaskName`` 成员值）。

    Returns:
        对应的 :class:`TaskSpec`。

    Raises:
        KeyError: 任务名不在 :data:`TASK_CATALOG` 中。
    """
    try:
        return TASK_CATALOG[name]
    except KeyError as exc:
        raise KeyError(
            f"未知任务名 {name!r}；可用任务: {', '.join(sorted(TASK_CATALOG))}"
        ) from exc


def build_payload(name: str, **params: Any) -> TaskPayload | None:
    """按任务名构造并校验入参模型实例。

    Args:
        name: 任务的全局注册名（``TaskName`` 成员值）。
        **params: 传给对应 ``*Payload`` 模型的字段。

    Returns:
        校验通过的入参模型实例；该任务无入参模型时返回 ``None``。

    Raises:
        KeyError: 任务名不在 :data:`TASK_CATALOG` 中。
        pydantic.ValidationError: 入参不满足模型约束时抛出。
    """
    spec = get_task_spec(name)
    if spec.payload is None:
        return None
    return spec.payload(**params)
