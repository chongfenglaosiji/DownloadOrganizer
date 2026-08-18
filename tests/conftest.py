# -*- coding: utf-8 -*-
"""pytest 公共配置：确保能导入项目包，并显式把依赖 watchdog 加入路径。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# 运行时若已在本机的 watchdog 安装处，可正常导入；
# 无则跳过依赖 watchdog 的用例（见 test_organizer 中的 skip 条件）。
try:
    import watchdog  # noqa: F401
except ImportError:
    os.environ.setdefault("PYTEST_MISSING_WATCHDOG", "1")
