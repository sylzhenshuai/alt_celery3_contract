# alt-celery3-contract — Celery 任务契约包

`alt_celery3` 的**纯声明式强类型任务契约包**：由静态扫描源项目的 Celery 任务生成，
只承载「任务名 / 入参类型 / 文档 / 目录」四类契约信息，**不含任何业务实现**。

它让「生产端」与「消费端」在跨服务调用时共享同一份类型定义与任务名常量，
从而获得 IDE 补全、静态类型检查与结构化入参校验，并在协议漂移时第一时间失败。

## 设计原则

| 原则 | 说明 |
| --- | --- |
| 纯声明 | 所有契约函数体统一为 `raise NotImplementedError`，不读写数据库、不调用外部 API |
| 零业务依赖 | 运行时只依赖 `pydantic`；不引入 `celery` / `redis` / `mysqlclient` / LLM SDK |
| 单一事实源 | 任务名字符串只在 `constants.TaskName` 中定义一次，源项目反向引用 |
| 可校验 | 内置基于 `inspect` 的校验器，可随时比对契约与源任务签名是否仍然一致 |
| 现代打包 | 遵循 PEP 517/518/621/639，`src` 布局 + `py.typed`（PEP 561） |

## 目录结构

```text
alt_celery3_contract/
├── src/alt_celery3_contract/
│   ├── __init__.py        # 公共 API 统一出口
│   ├── constants.py       # TaskName / TaskGroup —— 任务名唯一权威来源
│   ├── schemas.py         # Pydantic 入参模型（*Payload）
│   ├── definitions.py     # 契约函数（仅签名）+ TASK_CATALOG 全局目录
│   ├── verify.py          # 基于 inspect 的契约一致性校验器（含 CLI）
│   └── py.typed           # PEP 561 类型标记
├── scripts/verify_contract.py   # 免安装校验入口
├── tests/                 # pytest 用例（含真实源项目一致性测试）
├── docs/                  # MkDocs 文档
├── pyproject.toml         # PEP 621 项目元数据
├── requirements.txt       # 传统依赖清单
├── environment.yml        # Conda 环境定义
└── .readthedocs.yaml      # Read the Docs 托管配置
```

## 安装

> 本包**未发布到 PyPI**，`pip install alt-celery3-contract` 会失败；请从
> GitHub 或本地源码安装。

```bash
# 1) 从 GitHub 安装（默认 main 分支）
pip install "alt-celery3-contract @ git+https://github.com/sylzhenshuai/alt_celery3_contract.git"

# 2) 本地源码开发模式（推荐，含开发与文档依赖）
pip install -e ".[dev,docs]"

# 3) 传统依赖清单
pip install -r requirements.txt

# 4) Conda
conda env create -f environment.yml

# 5) 构建 wheel / sdist（产物在 dist/）
python -m build
```

仓库地址：<https://github.com/sylzhenshuai/alt_celery3_contract>

## 快速开始

### 生产端（投递任务）

```python
from alt_celery3_contract import TASK_CATALOG, TaskName, build_payload

# 方式一：直接使用任务名常量
from celery import Celery

app = Celery(broker="redis://localhost:6379/0")

payload = build_payload(TaskName.GENERATE_MANY_STUDENTS.value, numbers=10_000, threads=8)
assert payload is not None
app.send_task(TaskName.GENERATE_MANY_STUDENTS.value, kwargs=payload.model_dump())

# 方式二：从全局目录取契约函数签名与 Schema
spec = TASK_CATALOG[TaskName.SIMU_NCEE.value]
print(spec.signature)          # (year: 'int', threads: 'int | None' = None, limit: 'int | None' = None) -> 'dict[str, Any]'
print(spec.payload.__name__)   # SimuNceePayload
print(spec.source_module)      # app.tasks.simu_tasks
```

### 消费端（注册任务）

```python
from alt_celery3_contract import TaskName

@celery_app.task(name=TaskName.ADD.value)
def add(x: float, y: float) -> float:
    return float(x) + float(y)
```

> 完整任务清单见 [API 参考 · TASK_CATALOG](docs/api.md)，或运行
> `python scripts/verify_contract.py --list` 输出。

## 任务清单

| 任务名 | 契约函数 | 入参 Schema | bind | 服务端模块 |
| --- | --- | --- | :---: | --- |
| `tasks.add` | `add(x, y)` | `AddPayload` | | `app.tasks.math_tasks` |
| `tasks.heartbeat` | `heartbeat()` | — | | `app.tasks.periodic_tasks` |
| `tasks.try_mysql` | `try_mysql()` | — | | `app.tasks.db_tasks` |
| `tasks.get_one_student` | `get_one_student()` | — | | `app.tasks.student_tasks` |
| `tasks.generate_many_students` | `generate_many_students(numbers, birthday_min, birthday_max, threads)` | `GenerateManyStudentsPayload` | ✓ | `app.tasks.bulk_student_tasks` |
| `tasks.init_web_db` | `init_web_db()` | — | ✓ | `app.tasks.init_db_tasks` |
| `tasks.get_un_groups` | `get_un_groups(count=3)` | `GetUnGroupsPayload` | | `app.tasks.un_tasks` |
| `tasks.simu_ncee` | `simu_ncee(year, threads, limit)` | `SimuNceePayload` | ✓ | `app.tasks.simu_tasks` |
| `tasks.simu_admission` | `simu_admission(year, threads, limit)` | `SimuAdmissionPayload` | ✓ | `app.tasks.simu_tasks` |
| `tasks.simu_exam` | `simu_exam(year, threads, limit, min_exams=5, max_exams=10)` | `SimuExamPayload` | ✓ | `app.tasks.simu_tasks` |
| `tasks.simu_graduate` | `simu_graduate(year, threads, limit)` | `SimuGraduatePayload` | ✓ | `app.tasks.simu_tasks` |

> `bind=True` 的任务在契约中已剥离首参（`self` / `task`），因此只保留业务参数。

## 契约校验

校验器会逐项比对**任务名集合、参数名与顺序、类型注解、默认值、`bind` 首参剥离、
Payload 字段**，任一不一致即退出码 `1`。

```bash
# 纯静态解析（默认，不导入源项目、无副作用）
python scripts/verify_contract.py --source ../alt_celery3

# 运行时 inspect 后端（需源项目依赖齐备，会额外核对真实注册名）
python scripts/verify_contract.py --source ../alt_celery3 --mode inspect

# 仅输出源项目任务清单，便于人工核对
python scripts/verify_contract.py --list

# 机器可读报告
python -m alt_celery3_contract.verify --json > contract-report.json
```

安装本包后也可直接使用控制台命令：

```bash
alt-celery3-contract-verify --source ../alt_celery3
```

输出示例：

```text
源项目        : /path/to/alt_celery3
签名后端      : ast
源任务数      : 11
任务名常量数  : 11
契约任务数    : 11
------------------------------------------------------------------------
[PASS] tasks.add
[PASS] tasks.generate_many_students
...
------------------------------------------------------------------------
结果: 全部通过
```

## 源项目新增任务后的同步流程

1. 在 `alt_celery3` 中新增任务，装饰器建议直接引用契约常量：
   `@celery_app.task(name=TaskName.NEW_TASK.value)`；
2. 在 `src/alt_celery3_contract/constants.py` 的 `TaskName` 与 `TASK_GROUP_BY_NAME` 中登记；
3. 若业务参数多于 1 个，在 `schemas.py` 中补充 `NewTaskPayload`；
4. 在 `definitions.py` 中补充同名契约函数，并在 `TASK_CATALOG` 中登记条目；
5. 运行 `python scripts/verify_contract.py --source ../alt_celery3` 确认全部通过；
6. 若原任务被删除，同步移除契约条目（校验器会报「契约多余」）。

## 开发

```bash
ruff check .          # 静态检查（含 Google 风格 docstring）
python -m mypy        # 严格类型检查
python -m pytest -q   # 单元测试 + 源项目一致性测试
```

## 文档

文档由 [MkDocs Material](https://squidfunk.github.io/mkdocs-material/) +
[mkdocstrings](https://mkdocstrings.github.io/) 从 Google 风格 docstring 自动生成：

```bash
mkdocs serve    # 本地预览 http://127.0.0.1:8000
```

`.readthedocs.yaml` 已按 RTD v2 规范配置，推送到 GitHub 并在 Read the Docs
导入项目即可自动构建。

## 相关项目

- **本仓库**：<https://github.com/sylzhenshuai/alt_celery3_contract>
- `alt_celery3`：任务的服务端实现（Docker + Celery + Redis + Flower）。
  契约包未发布 PyPI，该项目按既有的「离线 wheels」约定，从本项目构建 wheel
  后放入其 `wheels/` 目录离线安装。

## 许可证

[MIT](LICENSE)
