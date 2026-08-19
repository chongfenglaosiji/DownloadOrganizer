# -*- coding: utf-8 -*-
"""托盘模块结构级测试（不启动真实托盘，验证降级、暂停与通知开关）。"""
import pytest

from download_organizer.organizer import PAUSED, set_paused


@pytest.fixture(autouse=True)
def _reset_notifications_flag():
    """通知开关为跨用例全局状态，用例前后重置为默认值 True。"""
    from download_organizer import tray
    tray.set_notifications_enabled(True)
    yield
    tray.set_notifications_enabled(True)


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


def test_notifications_default_enabled():
    from download_organizer import tray
    assert tray.notifications_enabled() is True


def test_notifications_toggle():
    from download_organizer import tray
    tray.set_notifications_enabled(False)
    assert tray.notifications_enabled() is False
    tray.set_notifications_enabled(True)
    assert tray.notifications_enabled() is True


def test_notify_disabled_skips_icon(monkeypatch):
    from download_organizer import tray
    calls = []

    class _FakeIcon:
        def notify(self, message, title):
            calls.append((message, title))

    monkeypatch.setattr(tray, "_ACTIVE_ICON", _FakeIcon())
    tray.set_notifications_enabled(False)
    tray.notify("标题", "消息")
    assert calls == []


def test_notify_enabled_calls_icon(monkeypatch):
    from download_organizer import tray
    calls = []

    class _FakeIcon:
        def notify(self, message, title):
            calls.append((message, title))

    monkeypatch.setattr(tray, "_ACTIVE_ICON", _FakeIcon())
    tray.set_notifications_enabled(True)
    tray.notify("标题", "消息")
    assert calls == [("消息", "标题")]


def test_notify_without_icon_silent(monkeypatch):
    from download_organizer import tray
    monkeypatch.setattr(tray, "_ACTIVE_ICON", None)
    tray.set_notifications_enabled(True)
    tray.notify("标题", "消息")  # 无活动图标：静默降级，不应抛异常


def test_toggle_notifications_flips_flag_and_updates_menu():
    from download_organizer import tray
    updated = []

    class _FakeIcon:
        def update_menu(self):
            updated.append(1)

    app = tray.TrayApp()
    app._icon = _FakeIcon()
    tray.set_notifications_enabled(False)
    app._toggle_notifications(None, None)
    assert tray.notifications_enabled() is True
    assert updated == [1]
