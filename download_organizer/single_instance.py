# -*- coding: utf-8 -*-
"""单实例锁：防止程序被重复启动。

Windows 用命名 Mutex（进程退出时内核自动释放）；其他平台回退到
文件锁（fcntl 不可用时降级为“可获取”，不拦截）。
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

# 锁名（含版本常量，避免与其它应用冲突）
_MUTEX_NAME = "DownloadOrganizer-SingleInstance-0-3"
_LOCK_FILENAME = "download_organizer.lock"


class SingleInstance:
    """获取/释放单实例锁。

    用法::

        si = SingleInstance()
        if not si.acquire():
            # 已有实例在运行
            ...
        ...
        si.release()
    """

    def __init__(self, name: str = _MUTEX_NAME):
        self._name = name
        self._handle = None      # Windows Mutex handle
        self._lock_fd = None     # 文件锁 fd
        self._lock_path: Path | None = None  # 惰性初始化（仅非 Windows 需要）
        self._acquired = False

    def _get_lock_path(self) -> Path:
        """惰性取得文件锁路径（仅非 Windows 调用，避免无 temp 时初始化失败）。"""
        if self._lock_path is None:
            self._lock_path = Path(tempfile.gettempdir()) / _LOCK_FILENAME
        return self._lock_path

    def acquire(self) -> bool:
        """尝试获取单实例锁；返回 True 表示本实例持有，False 表示已有实例。"""
        if self._acquired:
            return True
        if os.name == "nt":
            return self._acquire_mutex()
        return self._acquire_file()

    def _acquire_mutex(self) -> bool:
        import ctypes

        ERROR_ALREADY_EXISTS = 183
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateMutexW.restype = ctypes.c_void_p
        handle = k32.CreateMutexW(None, True, self._name)
        err = ctypes.get_last_error()
        if not handle or err == ERROR_ALREADY_EXISTS:
            if handle:
                k32.CloseHandle(handle)
            return False
        self._handle = handle
        self._acquired = True
        return True

    def _acquire_file(self) -> bool:
        try:
            import fcntl
        except ImportError:
            # 无 fcntl（如 Windows 的非 NT 路径）：降级为可获取
            self._acquired = True
            return True
        try:
            fd = os.open(str(self._get_lock_path()), os.O_CREAT | os.O_RDWR)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False
        self._lock_fd = fd
        self._acquired = True
        return True

    def release(self) -> None:
        """释放锁（进程退出时也会自动释放，可安全重复调用）。"""
        if not self._acquired:
            return
        if self._handle is not None:
            import ctypes
            ctypes.WinDLL("kernel32").CloseHandle(self._handle)
            self._handle = None
        if self._lock_fd is not None:
            try:
                import fcntl
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            except (ImportError, OSError):
                pass
            os.close(self._lock_fd)
            self._lock_fd = None
        self._acquired = False

    def __enter__(self) -> "SingleInstance":
        self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self.release()
