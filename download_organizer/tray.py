# -*- coding: utf-8 -*-
"""系统托盘（pystray）与桌面通知。

托盘菜单：暂停/继续、立即整理一次、打开配置、打开日志目录、退出。
pystray 不可用（未安装 / 无显示环境）时相关函数自动降级为 no-op，
不影响核心监控逻辑。
"""
from __future__ import annotations

import logging
import subprocess
import sys
import threading
from pathlib import Path

from .organizer import PAUSED

log = logging.getLogger("download_organizer")

try:
    import pystray
    from PIL import Image, ImageDraw

    _HAVE_TRAY = True
except Exception:  # noqa: BLE001 —— 缺依赖/无显示时降级
    _HAVE_TRAY = False


def is_paused() -> bool:
    return PAUSED.is_set()


def set_paused(paused: bool) -> None:
    from .organizer import set_paused as _set_paused
    _set_paused(paused)


# 当前运行中的托盘图标（供 notify 复用；无托盘时为 None）
_ACTIVE_ICON = None


def icon_path() -> Path:
    """定位程序图标 assets/icon.ico（打包后经 sys._MEIPASS 解压，源码运行取项目根）。"""
    if getattr(sys, "frozen", False):  # PyInstaller 打包
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "assets" / "icon.ico"


def _make_icon_image() -> "Image.Image":
    """托盘图标：优先加载 assets/icon.ico，失败回退手绘文件夹图标。"""
    ico = icon_path()
    if ico.is_file():
        try:
            img = Image.open(ico)
            img = img.convert("RGBA")
            if img.size[0] > 64:   # 托盘显示用 64 足矣
                img = img.resize((64, 64), Image.LANCZOS)
            return img
        except Exception as exc:  # noqa: BLE001 —— 加载失败回退手绘
            log.warning("加载图标失败，使用内置图标: %s", exc)
    # 回退：手绘简单文件夹图标（64x64）
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([6, 14, 58, 54], fill=(255, 200, 40, 255))
    d.rectangle([6, 14, 30, 24], fill=(255, 220, 80, 255))
    d.rectangle([12, 22, 52, 48], fill=(70, 130, 220, 255))
    d.rectangle([22, 30, 44, 44], fill=(255, 255, 255, 255))
    return img


class TrayApp:
    """托盘应用：管理图标、菜单与生命周期回调。"""

    def __init__(self, on_run_once=None, on_open_config=None, on_quit=None,
                 on_toggle_pause=None):
        self._on_run_once = on_run_once or (lambda: None)
        self._on_open_config = on_open_config or (lambda: None)
        self._on_quit = on_quit or (lambda: None)
        self._on_toggle_pause = on_toggle_pause or (lambda: None)
        self._icon = None
        self._paused_label = "暂停整理"

    def _menu(self):
        return pystray.Menu(
            pystray.MenuItem(
                lambda item: self._paused_label,
                self._toggle_pause,
                checked=lambda item: PAUSED.is_set(),
            ),
            pystray.MenuItem("立即整理一次", lambda icon, item: self._on_run_once()),
            pystray.MenuItem("打开配置…", lambda icon, item: self._on_open_config()),
            pystray.MenuItem("打开日志目录", lambda icon, item: open_log_dir()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", lambda icon, item: self._quit(icon)),
        )

    def _toggle_pause(self, icon, item) -> None:
        self._on_toggle_pause()
        self._paused_label = "恢复整理" if PAUSED.is_set() else "暂停整理"
        if self._icon is not None:
            self._icon.update_menu()

    def _quit(self, icon) -> None:
        icon.stop()
        self._on_quit()

    def run(self) -> None:
        """在调用线程运行托盘（阻塞）。"""
        if not _HAVE_TRAY:
            log.warning("pystray 不可用，跳过托盘")
            return
        global _ACTIVE_ICON
        try:
            self._icon = pystray.Icon(
                "DownloadOrganizer", _make_icon_image(), "DownloadOrganizer",
                self._menu())
            _ACTIVE_ICON = self._icon
            self._icon.run()
        except Exception as exc:  # noqa: BLE001
            log.warning("托盘启动失败（降级为无托盘运行）: %s", exc)
        finally:
            _ACTIVE_ICON = None

    def run_detached(self) -> threading.Thread:
        """在后台线程运行托盘，返回线程（可 join）。"""
        t = threading.Thread(target=self.run, daemon=True, name="tray")
        t.start()
        return t


def notify(title: str, message: str) -> None:
    """桌面通知；无运行中的托盘图标时静默降级（不新建独立图标）。"""
    icon = _ACTIVE_ICON
    if icon is None:
        return
    try:
        icon.notify(message, title)
    except Exception as exc:  # noqa: BLE001
        log.warning("通知失败: %s", exc)


def open_log_dir() -> None:
    """打开日志目录（跨平台）。"""
    log_dir = Path.home() / ".download_organizer"
    log_dir.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(log_dir)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(log_dir)])
        else:
            subprocess.Popen(["xdg-open", str(log_dir)])
    except OSError as exc:
        log.warning("打开日志目录失败: %s", exc)
