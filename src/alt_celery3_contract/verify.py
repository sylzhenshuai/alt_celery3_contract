"""契约一致性校验器：比对契约声明与 ``alt_celery3`` 源任务签名。

校验流程：

1. **定位源任务**：静态扫描源项目的 ``.py`` 文件，识别
   ``@app.task`` / ``@celery.task`` / ``@shared_task`` 装饰的函数，
   取出任务名、``bind`` 标记与函数定义所在模块；
2. **读取契约**：用 :func:`inspect.signature` 读取契约函数与
   ``TASK_CATALOG`` 中登记的入参 ``Schema``；
3. **逐项比对**：任务名集合、参数名与顺序、类型注解、默认值、
   ``bind`` 首参剥离、Payload 字段，全部一致才算通过。

参数签名有两种来源后端：

* ``ast``（默认）：纯静态解析，不导入源项目、无任何副作用，
  因此在未安装 Celery / MySQL 驱动的环境中同样可用；
* ``inspect``：真实导入源模块并用 :func:`inspect.signature` 读取
  运行时签名（还会核对实际注册的任务名），需要源项目依赖齐备。

命令示例::

    python -m alt_celery3_contract.verify --source ../alt_celery3
    python -m alt_celery3_contract.verify --source ../alt_celery3 --json
    python -m alt_celery3_contract.verify --list            # 仅打印任务清单
"""

from __future__ import annotations

import argparse
import ast
import importlib
import inspect
import json
import os
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from alt_celery3_contract.constants import TASK_NAMES, TaskName
from alt_celery3_contract.definitions import TASK_CATALOG, TaskSpec

__all__ = [
    "CheckResult",
    "SourceParam",
    "SourceTask",
    "VerificationReport",
    "compare",
    "discover_source_tasks",
    "load_contract_tasks",
    "main",
    "resolve_source_root",
    "verify",
]

#: 扫描源项目时跳过的目录名
_SKIP_DIRS: Final[frozenset[str]] = frozenset(
    {
        ".git",
        ".hg",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "logs",
        "node_modules",
        "venv",
        "wheels",
    }
)

#: 视作 Celery 任务装饰器的函数名（属性名 ``.task`` 或独立 ``shared_task``）
_TASK_DECORATOR_NAMES: Final[frozenset[str]] = frozenset({"task", "shared_task"})

#: 类型注解归一化时的别名映射
_TYPE_ALIASES: Final[Mapping[str, str]] = {
    "Dict": "dict",
    "FrozenSet": "frozenset",
    "List": "list",
    "NoneType": "None",
    "Set": "set",
    "Tuple": "tuple",
}


@dataclass(frozen=True)
class SourceParam:
    """源 / 契约函数的一个参数声明。

    Attributes:
        name: 参数名。
        annotation: 类型注解的规范化文本；未注解时为 ``None``。
        default: 默认值的规范化文本；无默认值时（必填参数）为 ``None``。
    """

    name: str
    annotation: str | None
    default: str | None


@dataclass(frozen=True)
class SourceTask:
    """从源项目提取（或由 ``inspect`` 读取）的单个任务声明。

    Attributes:
        name: 任务全局注册名。
        module: 定义任务的模块路径。
        func_name: 模块内承载任务的函数名。
        bind: 是否启用 ``bind=True``（``True`` 表示首参已剥离）。
        params: 剥离 ``bind`` 首参后的业务参数列表。
        returns: 返回值注解的规范化文本；未注解时为 ``None``。
        description: docstring 首行。
        file: 源文件路径（``inspect`` 后端为模块文件或空串）。
        lineno: 函数定义的起始行号（``inspect`` 后端为 0）。
        backend: 签名来源，``"ast"`` 或 ``"inspect"``。
    """

    name: str
    module: str
    func_name: str
    bind: bool
    params: tuple[SourceParam, ...]
    returns: str | None
    description: str
    file: str
    lineno: int
    backend: str


@dataclass(frozen=True)
class CheckResult:
    """单个任务的校验结果。

    Attributes:
        task: 任务名。
        ok: 是否全部检查通过。
        problems: 未通过项的说明列表。
    """

    task: str
    ok: bool
    problems: tuple[str, ...]


@dataclass(frozen=True)
class VerificationReport:
    """整体校验报告。

    Attributes:
        source_root: 源项目根目录。
        backend: 实际使用的签名后端。
        source_tasks: 从源项目提取到的全部任务。
        results: 逐个任务的校验结果。
        missing_in_catalog: 源项目存在但契约目录缺失的任务名。
        extra_in_catalog: 契约目录存在但源项目已移除的任务名。
    """

    source_root: Path
    backend: str
    source_tasks: tuple[SourceTask, ...]
    results: tuple[CheckResult, ...]
    missing_in_catalog: tuple[str, ...]
    extra_in_catalog: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """整体是否通过（含任务集合与逐项签名检查）。

        Returns:
            bool: 全部通过返回 ``True``。
        """
        return (
            not self.missing_in_catalog
            and not self.extra_in_catalog
            and all(result.ok for result in self.results)
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为可 JSON 序列化的字典。

        Returns:
            dict[str, Any]: 报告的结构化表示。
        """
        return {
            "source_root": str(self.source_root),
            "backend": self.backend,
            "ok": self.ok,
            "task_count": len(self.source_tasks),
            "missing_in_catalog": list(self.missing_in_catalog),
            "extra_in_catalog": list(self.extra_in_catalog),
            "tasks": [
                {
                    "name": task.name,
                    "module": task.module,
                    "func_name": task.func_name,
                    "bind": task.bind,
                    "backend": task.backend,
                    "file": task.file,
                    "lineno": task.lineno,
                    "description": task.description,
                    "params": [
                        {
                            "name": param.name,
                            "annotation": param.annotation,
                            "default": param.default,
                        }
                        for param in task.params
                    ],
                    "returns": task.returns,
                }
                for task in self.source_tasks
            ],
            "results": [
                {"task": result.task, "ok": result.ok, "problems": list(result.problems)}
                for result in self.results
            ],
        }


# ============================================================
# 注解 / 默认值归一化
# ============================================================
def _split_top_level(text: str, separator: str) -> list[str]:
    """按 ``separator`` 切分文本，忽略括号内部的分隔符。

    Args:
        text: 待切分文本。
        separator: 顶层分隔符（单字符）。

    Returns:
        list[str]: 切分结果（自动丢弃空片段）。
    """
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for char in text:
        if char in "[(":
            depth += 1
        elif char in ")]":
            depth -= 1
        if char == separator and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    parts.append("".join(current))
    return [part for part in (piece.strip() for piece in parts) if part]


def _split_union(text: str) -> list[str]:
    """把 ``X | Y`` / ``Optional[X]`` / ``Union[X, Y]`` 展开为成员列表。

    Args:
        text: 类型注解文本。

    Returns:
        list[str]: 展开后的联合类型成员。
    """
    members: list[str] = []
    for chunk in _split_top_level(text, "|"):
        for piece in _split_top_level(chunk, ","):
            match = re.fullmatch(r"(Optional|Union)\[(.*)\]", piece)
            if match:
                members.extend(_split_union(match.group(2)))
            else:
                members.append(piece)
    return members


def _normalize_atom(text: str) -> str:
    """归一化单个类型原子（含泛型参数递归）。

    Args:
        text: 类型原子文本，如 ``dict[str, Any]``。

    Returns:
        str: 归一化后的类型文本。
    """
    match = re.fullmatch(r"([\w.]+)\[(.*)\]", text)
    if match is None:
        return _TYPE_ALIASES.get(text, text)
    head, inner = match.group(1), match.group(2)
    head = _TYPE_ALIASES.get(head.rsplit(".", 1)[-1], head)
    parts: list[str] = []
    for piece in _split_top_level(inner, ","):
        normalized = _normalize_annotation(piece)
        if normalized is not None:
            parts.append(normalized)
    return f"{head}[{','.join(parts)}]"


def _normalize_annotation(text: str | None) -> str | None:
    """归一化类型注解，使不同写法可比较。

    统一处理：去除空白、展开 ``Optional`` / ``Union``、排序联合成员、
    归一化 ``typing.`` 前缀与常见旧式别名（``List`` -> ``list``）。

    Args:
        text: 原始注解文本；``None`` 表示未注解。

    Returns:
        str | None: 归一化后的注解文本；入参为 ``None`` 时返回 ``None``。
    """
    if text is None:
        return None
    collapsed = re.sub(r"\s+", "", text).replace("typing.", "")
    members = _split_union(collapsed)
    return "|".join(sorted(_normalize_atom(member) for member in members))


def _normalize_default(value: Any) -> str | None:
    """把默认值对象归一化为可比较文本。

    Args:
        value: 默认值；``inspect.Parameter.empty`` 表示必填。

    Returns:
        str | None: 归一化文本；必填参数返回 ``None``。
    """
    if value is inspect.Parameter.empty:
        return None
    return re.sub(r"\s+", "", repr(value))


def _normalize_default_text(text: str | None) -> str | None:
    """把源码中的默认值表达式归一化为可比较文本。

    Args:
        text: 默认值表达式源码；``None`` 表示必填参数。

    Returns:
        str | None: 去除全部空白后的表达式；``None`` 直接透传。
    """
    if text is None:
        return None
    return re.sub(r"\s+", "", text)


def _annotation_to_text(annotation: Any) -> str | None:
    """把 ``inspect`` 读到的注解对象转换为源文本。

    Args:
        annotation: ``inspect.Parameter.annotation`` 或返回值注解。

    Returns:
        str | None: 注解文本；未注解（``inspect.Signature.empty``）返回 ``None``。
    """
    if annotation is inspect.Signature.empty or annotation is None:
        return None
    if isinstance(annotation, str):
        return annotation
    if isinstance(annotation, type):
        return annotation.__name__
    return str(annotation)


# ============================================================
# AST 扫描：定位任务
# ============================================================
@dataclass(frozen=True)
class _TaskCandidate:
    """AST 扫描命中的任务候选。"""

    name: str | None
    module: str
    func_name: str
    bind: bool
    decorator: str
    params: tuple[SourceParam, ...]
    returns: str | None
    description: str
    file: str
    lineno: int


def _iter_python_files(source_root: Path) -> Iterable[Path]:
    """递归遍历源项目下的 Python 文件（跳过缓存 / 虚拟环境目录）。

    Args:
        source_root: 源项目根目录。

    Yields:
        Path: 候选 Python 文件路径，按路径排序保证结果稳定。
    """
    for path in sorted(source_root.rglob("*.py")):
        if any(part in _SKIP_DIRS for part in path.relative_to(source_root).parts):
            continue
        yield path


def _module_name(source_root: Path, path: Path) -> str:
    """由源文件路径推导模块路径。

    Args:
        source_root: 源项目根目录。
        path: 源文件路径。

    Returns:
        str: 形如 ``app.tasks.math_tasks`` 的模块路径。
    """
    relative = path.relative_to(source_root).with_suffix("")
    parts = list(relative.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _match_task_decorator(decorator: ast.expr) -> tuple[bool, ast.Call | None]:
    """判断装饰器是否为 Celery 任务装饰器。

    Args:
        decorator: 装饰器表达式节点。

    Returns:
        tuple[bool, ast.Call | None]: ``(是否任务装饰器, 带参数的调用节点或 None)``。
    """
    call = decorator if isinstance(decorator, ast.Call) else None
    target = call.func if call is not None else decorator
    if isinstance(target, ast.Attribute) and target.attr in _TASK_DECORATOR_NAMES:
        return True, call
    if isinstance(target, ast.Name) and target.id in _TASK_DECORATOR_NAMES:
        return True, call
    return False, None


def _decorator_kwarg(call: ast.Call | None, keyword: str) -> ast.expr | None:
    """读取装饰器调用的指定关键字实参。

    Args:
        call: 装饰器调用节点；``None`` 表示无参数调用。
        keyword: 关键字名。

    Returns:
        ast.expr | None: 实参节点；未提供时返回 ``None``。
    """
    if call is None:
        return None
    for item in call.keywords:
        if item.arg == keyword:
            return item.value
    return None


def _resolve_task_name(node: ast.expr) -> str | None:
    """把装饰器 ``name=`` 实参解析为任务名字符串。

    支持两种写法：

    * 字面量：``name="tasks.add"``；
    * 契约常量：``name=TaskName.ADD.value``（也接受 ``TaskName.ADD``）。

    Args:
        node: ``name=`` 的实参表达式节点。

    Returns:
        str | None: 解析出的任务名；无法静态解析时返回 ``None``。
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    parts = ast.unparse(node).split(".")
    if len(parts) >= 2 and parts[0] == "TaskName" and parts[1] in TaskName.__members__:
        return TaskName[parts[1]].value
    return None


def _resolve_name_by_catalog(module: str, func_name: str) -> str | None:
    """按「源模块 + 函数名」在契约目录中反查任务名。

    当装饰器 ``name=`` 使用了扫描器无法静态求值的表达式时，用该回退策略
    定位任务名，保证源项目改用契约常量后仍可完成校验。

    Args:
        module: 任务所在模块路径。
        func_name: 承载任务的函数名。

    Returns:
        str | None: 反查到的任务名；未命中时返回 ``None``。
    """
    for name, spec in TASK_CATALOG.items():
        if spec.source_module == module and spec.func.__name__ == func_name:
            return name
    return None


def _extract_params(
    node: ast.FunctionDef | ast.AsyncFunctionDef, bind: bool
) -> tuple[SourceParam, ...]:
    """提取函数位置参数（含注解与默认值），并按 ``bind`` 剥离首参。

    Args:
        node: 函数定义节点。
        bind: 是否启用 ``bind=True``。

    Returns:
        tuple[SourceParam, ...]: 业务参数列表。
    """
    positional = [*node.args.posonlyargs, *node.args.args]
    defaults = list(node.args.defaults)
    offset = len(positional) - len(defaults)

    params: list[SourceParam] = []
    for index, arg in enumerate(positional):
        default_text = ast.unparse(defaults[index - offset]) if index >= offset else None
        params.append(
            SourceParam(
                name=arg.arg,
                annotation=_normalize_annotation(
                    ast.unparse(arg.annotation) if arg.annotation is not None else None
                ),
                default=_normalize_default_text(default_text),
            )
        )
    for arg, default_node in zip(node.args.kwonlyargs, node.args.kw_defaults, strict=True):
        params.append(
            SourceParam(
                name=arg.arg,
                annotation=_normalize_annotation(
                    ast.unparse(arg.annotation) if arg.annotation is not None else None
                ),
                default=_normalize_default_text(
                    None if default_node is None else ast.unparse(default_node)
                ),
            )
        )
    if bind and params:
        params = params[1:]
    return tuple(params)


def _scan_file(source_root: Path, path: Path) -> list[_TaskCandidate]:
    """扫描单个文件，返回命中的任务候选列表。

    Args:
        source_root: 源项目根目录。
        path: 待扫描的 Python 文件。

    Returns:
        list[_TaskCandidate]: 该文件内的任务候选。
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return []

    module = _module_name(source_root, path)
    candidates: list[_TaskCandidate] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for decorator in node.decorator_list:
            matched, call = _match_task_decorator(decorator)
            if not matched:
                continue
            bind_node = _decorator_kwarg(call, "bind")
            bind = isinstance(bind_node, ast.Constant) and bind_node.value is True
            name_node = _decorator_kwarg(call, "name")
            explicit_name = _resolve_task_name(name_node) if name_node is not None else None
            docstring = ast.get_docstring(node) or ""
            candidates.append(
                _TaskCandidate(
                    name=explicit_name,
                    module=module,
                    func_name=node.name,
                    bind=bind,
                    decorator=ast.unparse(decorator),
                    params=_extract_params(node, bind),
                    returns=_normalize_annotation(
                        ast.unparse(node.returns) if node.returns is not None else None
                    ),
                    description=docstring.strip().splitlines()[0] if docstring.strip() else "",
                    file=str(path),
                    lineno=node.lineno,
                )
            )
            break
    return candidates


def _inspect_candidate(candidate: _TaskCandidate, source_root: Path) -> SourceTask | None:
    """尝试用 ``inspect`` 读取候选任务的运行时签名。

    Args:
        candidate: AST 扫描命中的候选任务。
        source_root: 源项目根目录（用于定位模块）。

    Returns:
        SourceTask | None: 读取成功返回运行时任务信息，失败返回 ``None``。
    """
    try:
        if str(source_root) not in sys.path:
            sys.path.insert(0, str(source_root))
        module = importlib.import_module(candidate.module)
    except Exception:  # noqa: BLE001 - 依赖缺失 / 导入副作用失败时回退 AST
        return None

    target = getattr(module, candidate.func_name, None)
    if target is None:
        return None
    func = getattr(target, "run", target)
    registered = getattr(target, "name", None)
    fallback_name = candidate.name or f"{candidate.module}.{candidate.func_name}"

    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return None

    raw_params = list(signature.parameters.values())
    # Celery 在 bind=True 时会把 ``run`` 绑定为方法（首参 self 已被绑定机制移除），
    # 此时不能再剥离；只有拿到未绑定的普通函数时才需要手动剥离任务实例首参。
    if candidate.bind and raw_params and not inspect.ismethod(func):
        raw_params = raw_params[1:]
    params = [
        param
        for param in raw_params
        if param.kind
        not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
    ]
    docstring = inspect.getdoc(func) or candidate.description

    return SourceTask(
        name=registered if isinstance(registered, str) else fallback_name,
        module=candidate.module,
        func_name=candidate.func_name,
        bind=candidate.bind,
        params=tuple(
            SourceParam(
                name=param.name,
                annotation=_normalize_annotation(_annotation_to_text(param.annotation)),
                default=_normalize_default(param.default),
            )
            for param in params
        ),
        returns=_normalize_annotation(_annotation_to_text(signature.return_annotation)),
        description=docstring.strip().splitlines()[0] if docstring.strip() else "",
        file=candidate.file,
        lineno=candidate.lineno,
        backend="inspect",
    )


def discover_source_tasks(source_root: Path, mode: str = "ast") -> tuple[list[SourceTask], str]:
    """从源项目提取全部 Celery 任务声明。

    Args:
        source_root: 源项目根目录。
        mode: 签名后端，``"ast"``（默认，纯静态）或 ``"inspect"``（运行时导入）。

    Returns:
        tuple[list[SourceTask], str]: 任务列表与**实际生效**的后端名。

    Raises:
        FileNotFoundError: 源项目根目录不存在时抛出。
        ValueError: ``mode`` 取值非法时抛出。
    """
    if not source_root.is_dir():
        raise FileNotFoundError(f"源项目目录不存在: {source_root}")
    if mode not in {"ast", "inspect"}:
        raise ValueError(f"mode 必须为 'ast' 或 'inspect'，收到: {mode!r}")

    candidates: list[_TaskCandidate] = []
    for path in _iter_python_files(source_root):
        candidates.extend(_scan_file(source_root, path))

    tasks: list[SourceTask] = []
    resolved_backend = mode
    for candidate in candidates:
        task: SourceTask | None = None
        if mode == "inspect":
            task = _inspect_candidate(candidate, source_root)
            if task is None:
                resolved_backend = "ast"
        if task is None:
            resolved_name = (
                candidate.name
                or _resolve_name_by_catalog(candidate.module, candidate.func_name)
                or f"{candidate.module}.{candidate.func_name}"
            )
            task = SourceTask(
                name=resolved_name,
                module=candidate.module,
                func_name=candidate.func_name,
                bind=candidate.bind,
                params=candidate.params,
                returns=candidate.returns,
                description=candidate.description,
                file=candidate.file,
                lineno=candidate.lineno,
                backend="ast",
            )
        tasks.append(task)

    if mode == "inspect" and any(task.backend == "inspect" for task in tasks):
        resolved_backend = "inspect"
    tasks.sort(key=lambda item: item.name)
    return tasks, resolved_backend


# ============================================================
# 契约侧读取与比对
# ============================================================
def load_contract_tasks() -> dict[str, TaskSpec]:
    """读取契约目录。

    Returns:
        dict[str, TaskSpec]: 任务名 -> 契约条目。
    """
    return dict(TASK_CATALOG)


def _contract_params(spec: TaskSpec) -> tuple[SourceParam, ...]:
    """用 ``inspect`` 读取契约函数的业务参数。

    Args:
        spec: 契约条目。

    Returns:
        tuple[SourceParam, ...]: 归一化后的参数列表。
    """
    signature = inspect.signature(spec.func)
    params: list[SourceParam] = []
    for parameter in signature.parameters.values():
        if parameter.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        params.append(
            SourceParam(
                name=parameter.name,
                annotation=_normalize_annotation(_annotation_to_text(parameter.annotation)),
                default=_normalize_default(parameter.default),
            )
        )
    return tuple(params)


def _contract_returns(spec: TaskSpec) -> str | None:
    """用 ``inspect`` 读取契约函数的返回值注解。

    Args:
        spec: 契约条目。

    Returns:
        str | None: 归一化后的返回值注解。
    """
    annotation = inspect.signature(spec.func).return_annotation
    return _normalize_annotation(_annotation_to_text(annotation))


def _compare_params(source: SourceTask, spec: TaskSpec) -> list[str]:
    """比对契约函数与源任务的参数列表。

    Args:
        source: 源任务声明。
        spec: 契约条目。

    Returns:
        list[str]: 未通过项说明；全部通过时为空列表。
    """
    problems: list[str] = []
    contract_params = _contract_params(spec)

    source_names = [param.name for param in source.params]
    contract_names = [param.name for param in contract_params]
    if source_names != contract_names:
        problems.append(f"参数名/顺序不一致: 源={source_names} 契约={contract_names}")

    for index, source_param in enumerate(source.params):
        if index >= len(contract_params):
            break
        contract_param = contract_params[index]
        if source_param.annotation != contract_param.annotation:
            problems.append(
                f"参数 {source_param.name!r} 类型注解不一致: "
                f"源={source_param.annotation!r} 契约={contract_param.annotation!r}"
            )
        if source_param.default != contract_param.default:
            problems.append(
                f"参数 {source_param.name!r} 默认值不一致: "
                f"源={source_param.default!r} 契约={contract_param.default!r}"
            )

    contract_returns = _contract_returns(spec)
    if source.returns != contract_returns:
        problems.append(f"返回值注解不一致: 源={source.returns!r} 契约={contract_returns!r}")
    return problems


def _compare_payload(source: SourceTask, spec: TaskSpec) -> list[str]:
    """比对入参 ``Schema`` 与源任务参数。

    Args:
        source: 源任务声明。
        spec: 契约条目。

    Returns:
        list[str]: 未通过项说明；全部通过时为空列表。
    """
    problems: list[str] = []
    if spec.payload is None:
        return problems

    payload_fields = list(spec.payload.model_fields)
    source_names = [param.name for param in source.params]
    if payload_fields != source_names:
        problems.append(
            f"{spec.payload.__name__} 字段与源参数不一致: 模型={payload_fields} 源={source_names}"
        )
    return problems


def compare(
    source_tasks: Sequence[SourceTask],
    catalog: Mapping[str, TaskSpec],
    *,
    source_root: Path | None = None,
    backend: str = "ast",
) -> VerificationReport:
    """比对源任务集合与契约目录。

    Args:
        source_tasks: 源任务列表。
        catalog: 契约目录。
        source_root: 源项目根目录（写入报告）。
        backend: 实际使用的签名后端（写入报告）。

    Returns:
        VerificationReport: 校验报告。
    """
    source_names = [task.name for task in source_tasks]
    missing = tuple(sorted(set(source_names) - set(catalog)))
    extra = tuple(sorted(set(catalog) - set(source_names)))

    results: list[CheckResult] = []
    for task in sorted(source_tasks, key=lambda item: item.name):
        problems: list[str] = []
        spec = catalog.get(task.name)
        if spec is None:
            problems.append("契约目录中缺少该任务")
        else:
            if spec.func.__name__ != task.func_name:
                problems.append(f"契约函数名不一致: 源={task.func_name} 契约={spec.func.__name__}")
            if spec.bind != task.bind:
                problems.append(f"bind 标记不一致: 源={task.bind} 契约={spec.bind}")
            if spec.source_module != task.module:
                problems.append(f"source_module 不一致: 源={task.module} 契约={spec.source_module}")
            if len(task.params) > 1 and spec.payload is None:
                problems.append("入参多于 1 个但未声明 Pydantic 入参 Schema")
            problems.extend(_compare_params(task, spec))
            problems.extend(_compare_payload(task, spec))
        results.append(CheckResult(task=task.name, ok=not problems, problems=tuple(problems)))

    return VerificationReport(
        source_root=source_root if source_root is not None else Path("."),
        backend=backend,
        source_tasks=tuple(source_tasks),
        results=tuple(results),
        missing_in_catalog=missing,
        extra_in_catalog=extra,
    )


def resolve_source_root(explicit: str | None = None) -> Path:
    """解析源项目根目录。

    查找顺序：命令行 ``--source`` -> 环境变量 ``ALT_CELERY3_SOURCE`` ->
    当前工作目录的兄弟目录 ``../alt_celery3`` -> 本包所在项目的兄弟目录。

    Args:
        explicit: 命令行显式指定的路径。

    Returns:
        Path: 解析到的源项目根目录（尚未校验存在性）。

    Raises:
        FileNotFoundError: 全部候选路径都不存在时抛出。
    """
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    env_value = os.getenv("ALT_CELERY3_SOURCE")
    if env_value:
        candidates.append(Path(env_value))
    candidates.append(Path.cwd().parent / "alt_celery3")
    candidates.append(Path(__file__).resolve().parents[3] / "alt_celery3")

    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if (resolved / "app" / "tasks").is_dir():
            return resolved
    raise FileNotFoundError(
        "未能定位 alt_celery3 源项目，请用 --source 指定；已尝试: "
        + ", ".join(str(item) for item in candidates)
    )


def verify(source_root: Path, mode: str = "ast") -> VerificationReport:
    """执行完整校验。

    Args:
        source_root: 源项目根目录。
        mode: 源签名后端，``"ast"`` 或 ``"inspect"``。

    Returns:
        VerificationReport: 校验报告。
    """
    source_tasks, backend = discover_source_tasks(source_root, mode)
    return compare(
        source_tasks,
        load_contract_tasks(),
        source_root=source_root,
        backend=backend,
    )


# ============================================================
# CLI
# ============================================================
def _print_inventory(tasks: Sequence[SourceTask]) -> None:
    """打印任务清单。

    Args:
        tasks: 源任务列表。
    """
    print(f"共发现 {len(tasks)} 个任务：")
    for task in tasks:
        params = ", ".join(param.name for param in task.params) or "(无参数)"
        returns = task.returns or "?"
        print(f"  - {task.name}")
        print(f"      bind={task.bind:<5} 模块={task.module} 行号={task.lineno}")
        print(f"      签名: ({params}) -> {returns}")


def _print_report(report: VerificationReport) -> None:
    """打印校验报告。

    Args:
        report: 校验报告。
    """
    print(f"源项目        : {report.source_root}")
    print(f"签名后端      : {report.backend}")
    print(f"源任务数      : {len(report.source_tasks)}")
    print(f"任务名常量数  : {len(TASK_NAMES)}")
    print(f"契约任务数    : {len(TASK_CATALOG)}")
    if report.missing_in_catalog:
        print(f"契约缺失    : {list(report.missing_in_catalog)}")
    if report.extra_in_catalog:
        print(f"契约多余    : {list(report.extra_in_catalog)}")
    print("-" * 72)
    for result in report.results:
        status = "PASS" if result.ok else "FAIL"
        print(f"[{status}] {result.task}")
        for problem in result.problems:
            print(f"        - {problem}")
    print("-" * 72)
    failed = [result.task for result in report.results if not result.ok]
    print(f"结果: {'全部通过' if report.ok else f'存在 {len(failed)} 个不通过任务: {failed}'}")


def _build_parser() -> argparse.ArgumentParser:
    """构造命令行解析器。

    Returns:
        argparse.ArgumentParser: 解析器实例。
    """
    parser = argparse.ArgumentParser(
        prog="alt-celery3-contract-verify",
        description="校验 alt_celery3_contract 契约与 alt_celery3 源任务签名的一致性",
    )
    parser.add_argument("--source", default=None, help="alt_celery3 源项目根目录")
    parser.add_argument(
        "--mode",
        choices=("ast", "inspect"),
        default="ast",
        help="源签名后端：ast=纯静态解析（默认，无副作用）；inspect=运行时导入",
    )
    parser.add_argument("--list", action="store_true", help="仅打印源任务清单（供人工核对）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出校验报告")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """命令行入口。

    Args:
        argv: 命令行参数（不含程序名）；``None`` 表示取 :data:`sys.argv`。

    Returns:
        int: 退出码，``0`` 表示全部通过，``1`` 表示存在不一致。
    """
    args = _build_parser().parse_args(argv)
    try:
        source_root = resolve_source_root(args.source)
        report = verify(source_root, args.mode)
    except FileNotFoundError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    if args.list:
        _print_inventory(report.source_tasks)
        return 0
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        _print_report(report)
    return 0 if report.ok else 1


if __name__ == "__main__":  # pragma: no cover - 手动运行入口
    raise SystemExit(main())
