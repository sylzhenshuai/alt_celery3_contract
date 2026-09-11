#!/usr/bin/env python3
"""契约校验脚本（无需安装即可运行）。

将本包的 ``src`` 目录临时加入 ``sys.path`` 后，把命令行参数原样转交给
:func:`alt_celery3_contract.verify.main`，适合在未 ``pip install`` 的
开发环境中直接使用::

    python scripts/verify_contract.py --source ../alt_celery3
    python scripts/verify_contract.py --list
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from alt_celery3_contract.verify import main  # noqa: E402 - 需先注入 src 路径

if __name__ == "__main__":
    raise SystemExit(main())
