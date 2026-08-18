# -*- coding: utf-8 -*-
"""aria2 控制文件解析与精确完成判定测试。"""
import os
import struct

from download_organizer import aria2


def _make_control(root, name="movie.mp4", total=1024, version=1,
                  info_hash_len=0) -> str:
    """构造一个最小合法的 *.aria2 控制文件，返回其路径。"""
    ctrl = os.path.join(root, name + ".aria2")
    header = struct.pack(">HII", version, 0, info_hash_len)      # VER EXT INFO HASH LEN
    header += b"\x00" * info_hash_len                            # INFO HASH
    header += struct.pack(">I", 16384)                           # PIECE LENGTH
    header += struct.pack(">Q", total)                           # TOTAL LENGTH (大端)
    header += struct.pack(">Q", 0)                               # UPLOAD LENGTH
    header += struct.pack(">I", 0)                               # BITFIELD LENGTH
    with open(ctrl, "wb") as f:
        f.write(header)
    return ctrl


def test_control_file_for(tmp_path):
    assert str(aria2.control_file_for(tmp_path / "a.bin")) == str(tmp_path / "a.bin.aria2")


def test_total_length_http(tmp_path):
    ctrl = _make_control(str(tmp_path), total=2048, info_hash_len=0)
    # 偏移 = 2+4+4+0+4 = 14，8 字节大端 = 2048
    with open(ctrl, "rb") as f:
        data = f.read()
    assert struct.unpack(">Q", data[14:22])[0] == 2048
    assert aria2.total_length_from_control(str(tmp_path / "movie.mp4")) == 2048


def test_total_length_bittorrent(tmp_path):
    # BitTorrent：INFO HASH LENGTH = 20
    _make_control(str(tmp_path), total=4096, info_hash_len=20)
    assert aria2.total_length_from_control(str(tmp_path / "movie.mp4")) == 4096


def test_missing_control_returns_none(tmp_path):
    assert aria2.total_length_from_control(str(tmp_path / "nope.mp4")) is None


def test_corrupt_control_returns_none(tmp_path):
    p = os.path.join(str(tmp_path), "bad.mp4.aria2")
    with open(p, "wb") as f:
        f.write(b"\x00\x01")   # 太短
    assert aria2.total_length_from_control(str(tmp_path / "bad.mp4")) is None


def test_version0_returns_none(tmp_path):
    # 版本 0（宿主字节序）无法安全解析 → None
    _make_control(str(tmp_path), total=100, version=0)
    assert aria2.total_length_from_control(str(tmp_path / "movie.mp4")) is None


def test_aria2_download_complete(tmp_path):
    root = str(tmp_path)
    # 控制文件记录总长 100，主文件只有 10 → 未完成
    _make_control(root, total=100)
    with open(os.path.join(root, "movie.mp4"), "wb") as f:
        f.write(b"x" * 10)
    assert aria2.aria2_download_complete(os.path.join(root, "movie.mp4")) is False

    # 主文件达到 100 → 完成
    with open(os.path.join(root, "movie.mp4"), "wb") as f:
        f.write(b"x" * 100)
    assert aria2.aria2_download_complete(os.path.join(root, "movie.mp4")) is True

    # 无控制文件 → None
    os.remove(os.path.join(root, "movie.mp4.aria2"))
    assert aria2.aria2_download_complete(os.path.join(root, "movie.mp4")) is None
