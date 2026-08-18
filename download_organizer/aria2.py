# -*- coding: utf-8 -*-
"""aria2 控制文件（``*.aria2``）解析：获取下载总长度，用于精确完成判定。

控制文件是二进制格式（见 aria2 官方 technical-notes.rst）：:

    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    +---+-------+-------+-------------------------------------------+
    |VER|  EXT  |INFO   |INFO HASH ...                              |
    |(2)|  (4)  |HASH   | (INFO HASH LENGTH)                        |
    |   |       |LENGTH |                                           |
    |   |       |  (4)  |                                           |
    +---+---+---+-------+---+---------------+-------+---------------+
    |PIECE  |TOTAL LENGTH   |UPLOAD LENGTH  |BIT-   |BITFIELD ...   |
    |LENGTH |     (8)       |     (8)       |FIELD  | (BITFIELD     |
    |  (4)  |               |               |LENGTH |  LENGTH)      |
    |       |               |               |  (4)  |               |
    +-------+-------+-------+-------+-------+-------+---------------+

* ``VER`` 2 字节：0 或 1；版本 1 的多字节整数为网络字节序（大端）。
* ``INFO HASH LENGTH`` 4 字节：BitTorrent 为 20，HTTP/FTP 下载为 0。
* ``TOTAL LENGTH`` 8 字节：下载总长度，位于偏移 ``14 + info_hash_length``。

解析失败（文件不存在/太短/损坏）一律返回 None，调用方回退到常规判定。
"""
from __future__ import annotations

import struct
from pathlib import Path

# 头部固定字段长度（VER + EXT + INFO HASH LENGTH + PIECE LENGTH）
_FIXED_HEADER = 2 + 4 + 4 + 4
_HEADER_UNPACK = 2 + 4 + 4  # VER(2) + EXT(4) + INFO HASH LENGTH(4)


def control_file_for(file_path: str | Path) -> Path:
    """返回与主文件对应的 ``*.aria2`` 控制文件路径（如 ``a.bin.aria2``）。"""
    return Path(file_path).with_name(Path(file_path).name + ".aria2")


def total_length_from_control(file_path: str | Path) -> int | None:
    """从 ``*.aria2`` 控制文件读取下载总长度；无法解析时返回 None。

    注意：版本 0 的控制文件使用主机字节序，无法可靠跨平台解析；
    这里仅处理版本 1（大端），版本 0/损坏文件返回 None（回退常规判定）。
    """
    ctrl = control_file_for(file_path)
    try:
        with open(ctrl, "rb") as f:
            head = f.read(_HEADER_UNPACK)
            if len(head) < _HEADER_UNPACK:
                return None
            # VER(2) + EXT(4) + INFO HASH LENGTH(4) = 10 字节（>HII）
            ver, _ext, info_hash_len = struct.unpack(">HII", head)
            if ver not in (0, 1):
                return None
            if ver == 0:
                # 版本 0 为宿主字节序，无法安全解析；放弃精确判定
                return None
            # 继续读 INFO HASH + PIECE LENGTH + TOTAL LENGTH
            tail = f.read(info_hash_len + 4 + 8)
    except OSError:
        return None
    if len(tail) < info_hash_len + 4 + 8:
        return None
    # 跳过 INFO HASH 与 PIECE LENGTH，读 TOTAL LENGTH（大端 8 字节）
    (total,) = struct.unpack(">Q", tail[info_hash_len + 4: info_hash_len + 4 + 8])
    return total


def aria2_download_complete(file_path: str | Path) -> bool | None:
    """aria2 精确完成判定。

    返回：
        True  —— 主文件大小 >= 控制文件记录的总长度（下载完成）
        False —— 控制文件存在且未达到总长度（仍在下载）
        None  —— 无控制文件 / 无法解析（由调用方回退常规判定）

    额外信号：aria2 下载完成时默认会删除 ``*.aria2`` 控制文件；
    “控制文件曾经存在、现在消失”由调用方结合快照处理。
    """
    total = total_length_from_control(file_path)
    if total is None:
        return None
    try:
        size = Path(file_path).stat().st_size
    except OSError:
        return False
    return size >= total
