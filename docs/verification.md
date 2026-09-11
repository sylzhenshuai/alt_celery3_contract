# 契约校验指南

契约包的价值建立在「与源任务始终一致」之上。本页说明校验器的工作方式与用法。

## 校验项

校验器逐项比对源任务与契约声明：

| 检查项 | 说明 |
| --- | --- |
| 任务名集合 | 源项目任务与 `TASK_CATALOG` 键集合必须完全相同（双向） |
| 参数名与顺序 | 位置参数、仅关键字参数的名称与顺序必须一致 |
| 类型注解 | 归一化后比较（展开 `Optional` / `Union`、排序联合成员、统一 `typing.` 前缀） |
| 默认值 | 参数默认值必须一致 |
| `bind` 处理 | `bind=True` 任务的 `self` / `task` 首参必须已剥离 |
| 入参 Schema | `*Payload` 的字段名与顺序必须与契约函数参数一致；参数多于 1 个时必须有 Schema |
| 元数据 | `bind` 标记、`source_module`、契约函数名一致 |

## 两种签名后端

| 后端 | 行为 | 适用场景 |
| --- | --- | --- |
| `ast`（默认） | 纯静态解析源文件，不导入源项目 | CI、无源项目依赖的环境 |
| `inspect` | 真实导入源模块，用 `inspect.signature` 读取运行时签名，并核对实际注册的任务名 | 本地联调、发版前深度校验 |

`inspect` 后端在依赖缺失或导入失败时会**自动回退**到 `ast`，因此可安全地在
`--mode inspect` 下运行。

## 命令行用法

```bash
# 默认静态校验
python scripts/verify_contract.py --source ../alt_celery3

# 深度校验（运行时签名）
python scripts/verify_contract.py --source ../alt_celery3 --mode inspect

# 列出源项目任务清单
python scripts/verify_contract.py --source ../alt_celery3 --list

# JSON 报告（便于接入 CI 断言）
python -m alt_celery3_contract.verify --source ../alt_celery3 --json
```

源项目路径解析顺序：`--source` → 环境变量 `ALT_CELERY3_SOURCE` →
当前目录的兄弟目录 `../alt_celery3` → 本包所在项目的兄弟目录。

## 退出码

| 退出码 | 含义 |
| --- | --- |
| `0` | 全部通过（或 `--list` 模式正常输出） |
| `1` | 存在不一致，或无法定位源项目 |

## 在 CI 中接入

```yaml
- name: 校验任务契约
  run: |
    pip install -e .
    alt-celery3-contract-verify --source ../alt_celery3
```

## python -m 入口与脚本入口

| 入口 | 是否需要安装 |
| --- | --- |
| `python -m alt_celery3_contract.verify` | 需要（包在 `sys.path` 上） |
| `python scripts/verify_contract.py` | 不需要（自动注入 `src/`） |
| `alt-celery3-contract-verify` | 需要（控制台命令，随 `pip install` 安装） |
