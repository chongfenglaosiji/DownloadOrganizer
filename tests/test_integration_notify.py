# -*- coding: utf-8 -*-
"""移动成功 → 通知回调 → 运行时通知开关 的跨模块集成测试。

链路：``cli._register_move_notification`` 注册回调 → ``organizer.move_file``
触发 ``MOVE_CALLBACKS`` → ``tray.notify`` 按运行时开关门控 → 假托盘图标记录调用。
验证 spec Requirement 1/2 的可观察行为（通知含文件名、开关关不通知、托盘切换
即时生效、配置关启动后仍可开启、重启回到配置值），不启动真实托盘/监控。
"""
import pytest

from download_organizer import cli, tray
from download_organizer.config import DownloadsConfig, Rule
from download_organizer.organizer import DownloadOrganizer, MOVE_CALLBACKS, ProcessedState

RULES = (Rule("图片", extensions=(".jpg",)),)
IGNORED = (".crdownload",)


class _Cfg:
    """携带 notify_on_move 的最小配置替身（与 cli 接线目标一致）。"""

    def __init__(self, notify_on_move: bool):
        self.notify_on_move = notify_on_move


class _RecordingIcon:
    """记录 notify 调用的假托盘图标。"""

    def __init__(self):
        self.calls = []

    def notify(self, message, title=None):
        self.calls.append((title, message))


@pytest.fixture(autouse=True)
def _reset_global_state():
    """通知开关与回调列表为跨用例全局状态，用例前后重置。"""
    MOVE_CALLBACKS.clear()
    tray.set_notifications_enabled(True)
    yield
    MOVE_CALLBACKS.clear()
    tray.set_notifications_enabled(True)


@pytest.fixture()
def icon(monkeypatch):
    icon = _RecordingIcon()
    monkeypatch.setattr(tray, "_ACTIVE_ICON", icon)
    return icon


@pytest.fixture()
def org(tmp_path):
    return DownloadOrganizer(
        DownloadsConfig(path=str(tmp_path), rules=RULES, ignored_endings=IGNORED),
        ProcessedState(None),
    )


def _make_file(root, name, content=b"x"):
    p = root / name
    p.write_bytes(content)
    return str(p)


def test_move_with_notifications_on_notifies_filename(icon, org, tmp_path):
    cli._register_move_notification(_Cfg(True))
    target = org.move_file(_make_file(tmp_path, "photo.jpg"))
    assert target is not None
    assert len(icon.calls) == 1
    title, message = icon.calls[0]
    assert title == "已整理"
    assert "photo.jpg" in message


def test_move_with_notifications_off_no_notification(icon, org, tmp_path):
    cli._register_move_notification(_Cfg(True))
    tray.set_notifications_enabled(False)  # 模拟托盘菜单关闭开关
    target = org.move_file(_make_file(tmp_path, "photo.jpg"))
    assert target is not None  # 移动本身不受开关影响
    assert icon.calls == []


def test_config_off_start_then_tray_enable(icon, org, tmp_path):
    # spec R1 S3 / R2 S3：配置 notify_on_move=false 启动 → 初始不通知
    cli._register_move_notification(_Cfg(False))
    assert tray.notifications_enabled() is False
    assert org.move_file(_make_file(tmp_path, "a.jpg")) is not None
    assert icon.calls == []
    # 用户经托盘勾选开启 → 即时生效（回调始终注册，门控在 notify）
    tray.set_notifications_enabled(True)
    assert org.move_file(_make_file(tmp_path, "b.jpg")) is not None
    assert len(icon.calls) == 1
    assert "b.jpg" in icon.calls[0][1]


def test_tray_toggle_off_then_on_immediate_effect(icon, org, tmp_path):
    # spec R2 S1/S2：托盘关闭后移动不通知，重开后立即恢复
    cli._register_move_notification(_Cfg(True))
    assert org.move_file(_make_file(tmp_path, "a.jpg")) is not None
    assert len(icon.calls) == 1
    tray.set_notifications_enabled(False)
    assert org.move_file(_make_file(tmp_path, "b.jpg")) is not None
    assert len(icon.calls) == 1
    tray.set_notifications_enabled(True)
    assert org.move_file(_make_file(tmp_path, "c.jpg")) is not None
    assert len(icon.calls) == 2
    assert "c.jpg" in icon.calls[1][1]


def test_restart_resets_switch_to_config_value(icon, org, tmp_path):
    # spec R2 S4：托盘关闭后"重启"（清空回调、以配置值重新初始化）→ 开关回到配置值
    cli._register_move_notification(_Cfg(True))
    tray.set_notifications_enabled(False)  # 用户经托盘关闭
    assert org.move_file(_make_file(tmp_path, "a.jpg")) is not None
    assert icon.calls == []
    MOVE_CALLBACKS.clear()  # 新进程：回调列表重建
    cli._register_move_notification(_Cfg(True))
    assert tray.notifications_enabled() is True
    assert org.move_file(_make_file(tmp_path, "b.jpg")) is not None
    assert len(icon.calls) == 1
    assert "b.jpg" in icon.calls[0][1]
