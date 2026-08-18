# -*- coding: utf-8 -*-
"""命令行入口。

用法：
    python -m download_organizer [--config config.toml] [--once] [--hidden]

说明：
    * 常驻监控模式会一直运行，直到 Ctrl+C。
    * --hidden 供“开机自启”（如 Windows 的 shell:startup）或无控制台场景使用：
      即便在窗口模式下 stdout/stderr 为 None，也把日志落到文件，不会抛错。
    * 配置查找顺序：--config 指定 > 当前目录 config.toml > 可执行文件旁 config.toml
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import load_config
from . import __version__
from .organizer import DownloadOrganizer, ProcessedState, run_monitor

LOG_DIR = Path.home() / ".download_organizer"
LOG_FILE = LOG_DIR / "run.log"

# 无控制台（--noconsole / 窗口模式）时 sys.stdout/stderr 为 None
_has_console = sys.stdout is not None and sys.stderr is not None


def _setup_logging(level: str, hidden: bool = False) -> None:
    root = logging.getLogger("download_organizer")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s",
                            datefmt="%H:%M:%S")

    # 无控制台或显式 --hidden：日志写文件
    if hidden or not _has_console:
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            fh = RotatingFileHandler(
                LOG_FILE, maxBytes=1024 * 1024, backupCount=2, encoding="utf-8")
            fh.setFormatter(fmt)
            root.addHandler(fh)
        except OSError:
            pass  # 无法写日志文件时静默（不阻塞启动）
    else:
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        root.addHandler(sh)


def _app_dir() -> Path:
    """可执行文件所在目录（打包后为 exe 目录，开发时为脚本目录）。"""
    if getattr(sys, "frozen", False):  # PyInstaller 打包
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _find_config(explicit: str | None) -> str | None:
    if explicit:
        return explicit if os.path.exists(explicit) else None
    candidates = [
        Path.cwd() / "config.toml",
        _app_dir() / "config.toml",
        Path.cwd() / "download_organizer.toml",
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    return None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="DownloadOrganizer",
                                description="自动整理下载文件夹的文件")
    p.add_argument("--config", help="TOML 配置文件路径")
    p.add_argument("--once", action="store_true",
                   help="只整理一次既有文件后退出（不做常驻监控）")
    p.add_argument("--hidden", action="store_true",
                   help="无控制台日志到文件（适合开机自启/无窗口运行）")
    p.add_argument("--version", action="version", version=f"DownloadOrganizer {__version__}")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    cfg_path = _find_config(args.config)
    cfg = load_config(cfg_path)
    _setup_logging(cfg.log_level, hidden=args.hidden)
    log = logging.getLogger("download_organizer")
    log.info("配置: %s (%d 个监控目录)", cfg_path or "默认", len(cfg.downloads))

    if not _has_console and not args.hidden:
        # 自动化场景（无控制台）默认走 --hidden 语义，避免日志异常
        pass

    if args.once:
        state = ProcessedState(cfg.state_file)
        for d in cfg.downloads:
            org = DownloadOrganizer(d, state)
            org.create_folders()
            org.organize_existing()
        return 0

    run_monitor(cfg, state_file=cfg.state_file, block=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
