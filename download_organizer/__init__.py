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

__version__ = "0.1.0"
