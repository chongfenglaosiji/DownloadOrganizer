# -*- coding: utf-8 -*-
"""cli 常驻模式通知接线测试（不启动真实监控/托盘）。

``_register_move_notification`` 有受控全局副作用（向 MOVE_CALLBACKS 追加回调、
改写 tray 通知开关标志），用例 setup/teardown 清空回调并重置开关为默认值 True。
"""
import pytest

from download_organizer import cli, tray
from download_organizer.organizer import MOVE_CALLBACKS


@pytest.fixture(autouse=True)
def _reset_global_state():
    MOVE_CALLBACKS.clear()
    tray.set_notifications_enabled(True)
    yield
    MOVE_CALLBACKS.clear()
    tray.set_notifications_enabled(True)


class _FakeCfg:
    def __init__(self, notify_on_move: bool):
        self.notify_on_move = notify_on_move


def test_register_notification_false_still_registers_callback():
    cli._register_move_notification(_FakeCfg(False))
    assert len(MOVE_CALLBACKS) == 1
    assert tray.notifications_enabled() is False


def test_register_notification_true_initializes_switch_on():
    cli._register_move_notification(_FakeCfg(True))
    assert len(MOVE_CALLBACKS) == 1
    assert tray.notifications_enabled() is True


def test_register_notification_missing_attr_defaults_on():
    # getattr 防御：旧/测试 cfg 对象缺 notify_on_move 属性时按默认 True 处理
    cli._register_move_notification(object())
    assert len(MOVE_CALLBACKS) == 1
    assert tray.notifications_enabled() is True


def test_register_notification_degrades_silently_when_tray_fails(monkeypatch):
    # 托盘/通知后端不可用（以 tray 访问器抛异常模拟）：静默降级，不注册回调
    def _boom(enabled):
        raise RuntimeError("tray unavailable")

    monkeypatch.setattr(tray, "set_notifications_enabled", _boom)
    cli._register_move_notification(_FakeCfg(True))
    assert MOVE_CALLBACKS == []
    assert tray.notifications_enabled() is True


def test_once_mode_registers_no_move_notification(monkeypatch):
    # spec R1：--once 单次整理模式不显示移动通知 → 常驻注册逻辑不触达
    monkeypatch.setattr(cli, "_find_config", lambda explicit: None)
    monkeypatch.setattr(cli, "_run_once", lambda cfg: 0)
    rc = cli.main(["--once"])
    assert rc == 0
    assert MOVE_CALLBACKS == []
    assert tray.notifications_enabled() is True  # 开关未被改写
