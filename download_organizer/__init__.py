# -*- coding: utf-8 -*-
"""DownloadOrganizer —— 下载文件夹自动整理工具（工程化重构）。"""
from __future__ import annotations

from .config import (
    Config,
    DownloadsConfig,
    Rule,
    default_config,
    load_config,
)
from .organizer import (
    ConflictResolver,
    DownloadHandler,
    DownloadOrganizer,
    ProcessedState,
    is_file_download_complete,
    run_monitor,
)
from .rules import RuleMatcher

__all__ = [
    "Config",
    "DownloadsConfig",
    "Rule",
    "default_config",
    "load_config",
    "RuleMatcher",
    "DownloadOrganizer",
    "DownloadHandler",
    "ProcessedState",
    "ConflictResolver",
    "is_file_download_complete",
    "run_monitor",
]

__version__ = "0.1.1"

# 版本号单一来源：优先从已安装包元数据读取（与 pyproject.toml 保持一致），
# 未安装（如直接跑源码）时回退到上面的固定串。
try:
    from importlib.metadata import version as _pkg_version

    _v = _pkg_version("download-organizer")
    if _v:
        __version__ = _v
except Exception:  # noqa: BLE001 —— 元数据不可用（未安装）时保持固定串
    pass
