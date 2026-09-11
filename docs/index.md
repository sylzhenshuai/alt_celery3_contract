# alt-celery3-contract

`alt_celery3` 的**纯声明式强类型 Celery 任务契约包**。

本包由静态扫描源项目中的 `@app.task` / `@celery.task` / `@shared_task` 装饰函数生成，
只保留**任务名、入参签名、类型注解与文档**，函数体统一为 `raise NotImplementedError`，
不复制任何业务实现逻辑。

## 为什么需要契约包

跨服务调用 Celery 任务时，最常见的问题是：

- 任务名散落在各处硬编码字符串，重命名后调用方静默失败；
- 参数名或类型写错，直到运行期才暴露；
- 没有 IDE 补全与静态检查，只能翻源码核对签名。

契约包把这三件事一次性解决：**任务名常量化、入参模型化、签名可校验化**。

## 安装

```bash
pip install -e ".[dev,docs]"
```

## 核心概念

| 模块 | 作用 |
| --- | --- |
| `alt_celery3_contract.constants` | `TaskName` 任务名枚举、`TaskGroup` 分组 |
| `alt_celery3_contract.schemas` | `*Payload` Pydantic 入参模型 |
| `alt_celery3_contract.definitions` | 契约函数与 `TASK_CATALOG` 全局目录 |
| `alt_celery3_contract.verify` | 契约一致性校验器 |

## 最短用法

```python
from alt_celery3_contract import TaskName, build_payload

payload = build_payload(TaskName.SIMU_NCEE.value, year=2026, threads=8)
celery_app.send_task(TaskName.SIMU_NCEE.value, kwargs=payload.model_dump())
```

消费端在注册任务时同样引用同一常量，保证两端永不漂移：

```python
from alt_celery3_contract import TaskName

@celery_app.task(name=TaskName.ADD.value)
def add(x: float, y: float) -> float:
    return float(x) + float(y)
```

## 下一步

- [API 参考](api.md)：逐模块的自动生成文档
- [校验指南](verification.md)：如何验证契约与源任务保持一致
