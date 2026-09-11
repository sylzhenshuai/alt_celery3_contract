"""任务入参的 Pydantic 强类型模型。

每一个「业务参数多于一个」或「入参校验逻辑较复杂」的任务，都在此声明一个
``*Payload`` 模型。模型只描述 *接口*，不含任何业务实现：

* 字段名与契约函数（:mod:`alt_celery3_contract.definitions`）的参数名逐一对应；
* 字段默认值与源任务签名保持一致；
* 数值边界与格式约束对齐源任务内的参数校验规则（越界即抛
  :class:`pydantic.ValidationError`，它是 :class:`ValueError` 的子类）。

模型一律不可变（``frozen=True``）且拒绝未知字段（``extra="forbid"``），
从而在跨服务边界上尽早暴露拼写错误与协议漂移。
"""

from __future__ import annotations

from datetime import date
from typing import Final, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

__all__ = [
    "DEFAULT_BIRTHDAY_MAX",
    "DEFAULT_BIRTHDAY_MIN",
    "AddPayload",
    "GenerateManyStudentsPayload",
    "GetUnGroupsPayload",
    "SimuAdmissionPayload",
    "SimuExamPayload",
    "SimuGraduatePayload",
    "SimuNceePayload",
    "SimulationPayload",
    "TaskPayload",
]

#: ``generate_many_students`` 未显式指定出生日期下限时的默认值
DEFAULT_BIRTHDAY_MIN: Final[str] = "2000-01-01"
#: ``generate_many_students`` 未显式指定出生日期上限时的默认值
DEFAULT_BIRTHDAY_MAX: Final[str] = "2015-12-31"


class TaskPayload(BaseModel):
    """全部任务入参模型的公共基类。

    统一的模型策略：

    * ``extra="forbid"``：拒绝契约之外的字段，防止调用方静默传错参数名；
    * ``frozen=True``：模型实例不可变，可安全跨线程 / 跨任务复用。
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


class AddPayload(TaskPayload):
    """``tasks.add`` 的入参模型。

    Attributes:
        x: 第一个加数，允许可被 ``float()`` 解析的字符串。
        y: 第二个加数，允许可被 ``float()`` 解析的字符串。
    """

    x: float
    """第一个加数。"""

    y: float
    """第二个加数。"""


class GetUnGroupsPayload(TaskPayload):
    """``tasks.get_un_groups`` 的入参模型。

    Attributes:
        count: 要获取的高校数量，必须为正整数。
    """

    count: int = Field(default=3, ge=1, strict=True)
    """要获取的高校数量（默认 3，正整数）。"""


class GenerateManyStudentsPayload(TaskPayload):
    """``tasks.generate_many_students`` 的入参模型。

    Attributes:
        numbers: 要生成的人数，必须为正整数。
        birthday_min: 出生年月日下限（含），``"YYYY-MM-DD"`` 格式；
            为 ``None`` 时服务端按 :data:`DEFAULT_BIRTHDAY_MIN` 处理。
        birthday_max: 出生年月日上限（含），``"YYYY-MM-DD"`` 格式；
            为 ``None`` 时服务端按 :data:`DEFAULT_BIRTHDAY_MAX` 处理。
        threads: 并发线程数（1~64）；为 ``None`` 时服务端使用默认值 8。
    """

    numbers: int = Field(ge=1, strict=True)
    """要生成的人数（正整数）。"""

    birthday_min: str | None = None
    """出生年月日下限（含），``"YYYY-MM-DD"``；``None`` 表示使用服务端默认值。"""

    birthday_max: str | None = None
    """出生年月日上限（含），``"YYYY-MM-DD"``；``None`` 表示使用服务端默认值。"""

    threads: int | None = Field(default=None, ge=1, le=64, strict=True)
    """并发线程数（1~64）；``None`` 表示使用服务端默认值 8。"""

    @field_validator("birthday_min", "birthday_max", mode="after")
    @classmethod
    def _check_iso_date(cls, value: str | None) -> str | None:
        """校验出生日期字符串可被解析为 ``YYYY-MM-DD`` 日期。

        Args:
            value: 待校验的日期字符串或 ``None``。

        Returns:
            原样返回的日期字符串（``None`` 直接透传）。

        Raises:
            ValueError: 字符串无法按 ``YYYY-MM-DD`` 解析时抛出。
        """
        if value is None:
            return value
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"出生日期格式非法（应为 YYYY-MM-DD）: {value!r}") from exc
        return value

    @model_validator(mode="after")
    def _check_birthday_range(self) -> Self:
        """校验出生日期区间的起止顺序。

        ``None`` 字段按服务端默认值（:data:`DEFAULT_BIRTHDAY_MIN` /
        :data:`DEFAULT_BIRTHDAY_MAX`）参与比较。

        Returns:
            校验通过的模型实例自身。

        Raises:
            ValueError: 下限晚于上限时抛出。
        """
        start = date.fromisoformat(self.birthday_min or DEFAULT_BIRTHDAY_MIN)
        end = date.fromisoformat(self.birthday_max or DEFAULT_BIRTHDAY_MAX)
        if start > end:
            raise ValueError(f"birthday_min ({start}) 不能晚于 birthday_max ({end})")
        return self


class SimulationPayload(TaskPayload):
    """升学模拟任务链（``tasks.simu_*``）的公共入参模型。

    高考评测、高校录取、本科毕业三个任务的入参完全一致，故共用该基类；
    ``tasks.simu_exam`` 在此基础上额外追加考试次数区间字段。

    Attributes:
        year: 任务年份（2000~2100）。
        threads: 并发线程数（1~64）；为 ``None`` 时服务端使用默认值 8。
        limit: 处理行数上限（调试用）；为 ``None`` 表示处理全部候选行。
    """

    year: int = Field(ge=2000, le=2100, strict=True)
    """任务年份（高考年份 / 学年 / 毕业届年份），取值 2000~2100。"""

    threads: int | None = Field(default=None, ge=1, le=64, strict=True)
    """并发线程数（1~64）；``None`` 表示使用服务端默认值 8。"""

    limit: int | None = Field(default=None, ge=1, strict=True)
    """处理行数上限（调试用）；``None`` 表示处理全部候选行。"""


class SimuNceePayload(SimulationPayload):
    """``tasks.simu_ncee``（高考评测）的入参模型，字段语义见 :class:`SimulationPayload`。"""


class SimuAdmissionPayload(SimulationPayload):
    """``tasks.simu_admission``（高校录取）的入参模型，字段语义见 :class:`SimulationPayload`。"""


class SimuGraduatePayload(SimulationPayload):
    """``tasks.simu_graduate``（本科毕业）的入参模型，字段语义见 :class:`SimulationPayload`。"""


class SimuExamPayload(SimulationPayload):
    """``tasks.simu_exam``（高校日常考试）的入参模型。

    Attributes:
        min_exams: 每名学生最少考试次数。
        max_exams: 每名学生最多考试次数，需满足 ``1 <= min_exams <= max_exams <= 20``。
    """

    min_exams: int = Field(default=5, ge=1, strict=True)
    """每名学生最少考试次数（默认 5）。"""

    max_exams: int = Field(default=10, ge=1, strict=True)
    """每名学生最多考试次数（默认 10，且不超过 20）。"""

    @model_validator(mode="after")
    def _check_exam_range(self) -> Self:
        """校验考试次数区间满足 ``1 <= min_exams <= max_exams <= 20``。

        Returns:
            校验通过的模型实例自身。

        Raises:
            ValueError: 区间非法时抛出。
        """
        if not 1 <= self.min_exams <= self.max_exams <= 20:
            raise ValueError(
                f"考试次数区间非法: min_exams={self.min_exams}, max_exams={self.max_exams}"
            )
        return self
