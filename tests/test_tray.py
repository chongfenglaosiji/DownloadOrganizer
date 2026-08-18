# -*- coding: utf-8 -*-
"""托盘模块结构级测试（不启动真实托盘，验证降级与暂停开关）。"""
import pytest

from download_organizer.organizer import PAUSED, set_paused


def test_pause_toggle():
    set_paused(True)
    assert PAUSED.is_set()
    set_paused(False)
    assert not PAUSED.is_set()


def test_tray_import_and_icon():
    from download_organizer import tray
    img = tray._make_icon_image()
    assert img is not None
    assert img.size == (64, 64)
