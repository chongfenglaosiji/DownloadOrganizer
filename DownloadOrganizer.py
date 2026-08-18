#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DownloadOrganizer —— 下载文件夹自动整理工具（启动入口）。

此文件只是薄启动器，真正的实现位于 download_organizer 包。
功能：常驻监控下载目录，把已完成文件按类型归档到分类子文件夹。

用法：
    python DownloadOrganizer.py                 # 使用默认/本地 config.toml
    python DownloadOrganizer.py --config x.toml # 指定配置文件
    python DownloadOrganizer.py --once          # 只整理一次后退出
"""
import sys

from download_organizer.cli import main

if __name__ == "__main__":
    sys.exit(main())
