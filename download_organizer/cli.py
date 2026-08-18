# -*- coding: utf-8 -*-
"""命令行入口。

用法：
    python -m download_organizer [--config config.toml] [--once]

选项：
    --config PATH   指定 TOML 配置文件（默认自动查找 config.toml）
    --once          只整理一次已存在的文件，然后退出（不做常驻监控）
"""
from __future__ import annotations

import argparse
import logging
import sys

from .config import load_config
from .organizer import DownloadOrganizer, ProcessedState, run_monitor


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _find_config(explicit: str | None) -> str | None:
    if explicit:
        import os
        return explicit if os.path.exists(explicit) else None
    import os
    for name in ("config.toml", "download_organizer.toml"):
        if os.path.exists(name):
            return name
    return None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="DownloadOrganizer",
                                description="自动整理下载文件夹的文件")
    p.add_argument("--config", help="TOML 配置文件路径")
    p.add_argument("--once", action="store_true",
                   help="只整理一次既有文件后退出（不做常驻监控）")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    cfg_path = _find_config(args.config)
    cfg = load_config(cfg_path)
    _setup_logging(cfg.log_level)
    logging.getLogger("download_organizer").info(
        "配置: %s (%d 个监控目录)", cfg_path or "默认", len(cfg.downloads))

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
