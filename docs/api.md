# API 参考

以下内容由 [mkdocstrings](https://mkdocstrings.github.io/) 从源码的 Google 风格
docstring 自动生成。

## 任务名常量

::: alt_celery3_contract.constants
    options:
      members:
        - TaskName
        - TaskGroup
        - TASK_NAMES
        - TASK_NAME_SET
        - TASK_NAME_PREFIX
        - TASK_GROUP_BY_NAME

## 入参模型

::: alt_celery3_contract.schemas
    options:
      members:
        - TaskPayload
        - AddPayload
        - GetUnGroupsPayload
        - GenerateManyStudentsPayload
        - SimulationPayload
        - SimuNceePayload
        - SimuAdmissionPayload
        - SimuExamPayload
        - SimuGraduatePayload

## 契约函数与任务目录

::: alt_celery3_contract.definitions
    options:
      members:
        - TaskSpec
        - TASK_CATALOG
        - add
        - heartbeat
        - try_mysql
        - get_one_student
        - generate_many_students
        - init_web_db
        - get_un_groups
        - simu_ncee
        - simu_admission
        - simu_exam
        - simu_graduate
        - get_task_spec
        - build_payload

## 契约校验器

::: alt_celery3_contract.verify
    options:
      members:
        - SourceParam
        - SourceTask
        - CheckResult
        - VerificationReport
        - discover_source_tasks
        - load_contract_tasks
        - compare
        - verify
        - resolve_source_root
        - main
