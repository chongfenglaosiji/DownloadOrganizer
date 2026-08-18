# -*- coding: utf-8 -*-
"""核心整理引擎。

包含：
  * 状态持久化（已处理文件列表，避免重启后重复整理）
  * 冲突处理（rename / overwrite / skip / recycle）
  * “下载完成”判定
  * watchdog 事件处理器与常驻监控
"""
from __future__ import annotations

import inspect
import json
import logging
import os
import queue
import shutil
import threading
import time
from pathlib import Path

from .config import DownloadsConfig
from .rules import RuleMatcher

log = logging.getLogger("download_organizer")

# watchdog 仅用于“常驻监控”，为保持纯整理/单次整理不依赖第三方库，
# 这里延迟导入，并在真正使用监控时给出清晰错误。
def _import_watchdog():
    """导入 watchdog；未安装时抛出带说明的 ImportError。"""
    try:
        from watchdog.events import FileSystemEventHandler  # noqa: F401
        from watchdog.observers import Observer
        return Observer
    except ImportError as exc:
        raise ImportError(
            "常驻监控需要 `watchdog`，请先安装：python -m pip install watchdog"
        ) from exc


# ---------------------------------------------------------------------------
# 状态持久化
# ---------------------------------------------------------------------------
def _fingerprint(path: str) -> tuple[int, int] | None:
    """返回文件指纹 (size, mtime_ns)；取不到则返回 None。"""
    try:
        st = Path(path).stat()
        return (st.st_size, st.st_mtime_ns)
    except OSError:
        return None


class ProcessedState:
    """记录已成功处理（移动）的文件路径指纹，跨进程/重启保留。

    记录的是“源路径 + 移走时的文件指纹”。判断是否已处理时，
    若当前文件指纹与记录一致才算已处理；否则视为重新下载的同名新文件，
    允许再次整理（修复“同名再下载后被永久跳过”的缺陷）。
    """

    # 磁盘写入冷却（秒）：事件频繁时合并落盘，减少整写
    SAVE_COOLDOWN = 5.0

    def __init__(self, file: str | Path | None):
        self.file = str(Path(file).expanduser()) if file else None
        # path -> 指纹；旧格式（纯字符串）记为 None，视为“已处理”
        self._items: dict[str, tuple[int, int] | None] = {}
        self._last_save: float = 0.0
        self._dirty = False
        if self.file:
            self._load()

    def _load(self) -> None:
        try:
            p = Path(self.file)
            if p.is_file():
                data = json.loads(p.read_text(encoding="utf-8"))
                self._items = {}
                for it in data.get("processed", []):
                    if isinstance(it, str):            # 旧格式
                        self._items[it] = None
                    elif isinstance(it, dict) and it.get("p"):
                        self._items[it["p"]] = (it.get("s"), it.get("m"))
        except Exception as exc:  # 状态文件损坏时忽略，不阻塞启动
            log.warning("状态文件加载失败（将重置）: %s", exc)
            self._items = {}

    def _dump(self) -> list:
        payload: list = []
        for p, fp in self._items.items():
            if fp is None:
                payload.append(p)
            else:
                payload.append({"p": p, "s": fp[0], "m": fp[1]})
        return payload

    def save(self, force: bool = False) -> None:
        if not self.file:
            return
        now = time.monotonic()
        if not force and (now - self._last_save) < self.SAVE_COOLDOWN:
            self._dirty = True   # 合并：稍后统一写盘
            return
        self._write()
        self._last_save = now
        self._dirty = False

    def _write(self) -> None:
        try:
            p = Path(self.file)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(
                json.dumps({"processed": self._dump()}, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            log.warning("状态文件写入失败: %s", exc)

    def flush(self) -> None:
        """强制把尚未落盘的改动写入（进程退出前调用）。"""
        if self._dirty or (self._items and time.monotonic() - self._last_save >= self.SAVE_COOLDOWN):
            self._write()
            self._last_save = time.monotonic()
            self._dirty = False

    def contains(self, path: str) -> bool:
        """是否“已处理”：仅当记录在案且当前文件指纹与记录一致。"""
        if path not in self._items:
            return False
        rec = self._items[path]
        if rec is None:             # 旧格式记录：视为已处理
            return True
        fp = _fingerprint(path)
        if fp is None:              # 取不到指纹（文件不存在/不可读）→ 保守跳过
            return True
        return fp == rec

    def add(self, path: str) -> None:
        """以当前文件指纹记录（供测试/旧调用：此时文件通常仍存在）。"""
        self._items[path] = _fingerprint(path)

    def record(self, path: str, fingerprint: tuple[int, int] | None) -> None:
        """记录移走时的源路径与指纹（用于在移动后正确判定同名重下载）。"""
        self._items[path] = fingerprint

    def discard(self, path: str) -> None:
        self._items.pop(path, None)


# ---------------------------------------------------------------------------
# 冲突处理
# ---------------------------------------------------------------------------
def _unique_target(target: Path) -> Path:
    """目标已存在时生成不冲突路径：name (1).ext、name (2).ext …"""
    target = Path(target)
    if not target.exists():
        return target
    stem, suffix = os.path.splitext(target.name)
    counter = 1
    while True:
        candidate = target.with_name(f"{stem} ({counter}){suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


class ConflictResolver:
    """根据 conflict_policy 决定最终目标路径。"""

    def __init__(self, policy: str):
        self.policy = policy

    def resolve(self, proposed: Path | str) -> Path | None:
        """返回实际应移动到的路径；None 表示应跳过（不移动）。"""
        proposed = Path(proposed)
        if not proposed.exists():
            return proposed
        if self.policy == "rename":
            return _unique_target(proposed)
        if self.policy == "overwrite":
            return proposed
        if self.policy == "skip":
            return None
        if self.policy == "recycle":
            # 简化：重命名避冲突，避免直接使用未安装的 send2trash
            return _unique_target(proposed)
        # 默认降级为 rename
        return _unique_target(proposed)


# ---------------------------------------------------------------------------
# 下载完成判定
# ---------------------------------------------------------------------------
def is_file_download_complete(file_path: str | Path, interval: float = 1.0,
                              max_checks: int = 30,
                              stable_checks: int = 3) -> bool:
    """估算文件是否已下载完成：大小连续 ``stable_checks`` 次采样都不变。

    比“单次大小不变”更保守：aria2 等分段/慢速下载在两次采样之间可能
    恰好暂停增长，连续多次稳定可显著降低“误判完成、移走不完整文件”的概率。
    """
    p = Path(file_path)
    # 不能要求比“可观察到的重复次数”还多的连续稳定采样：
    # 第 1 次采样只建立基线，最多只能确认 (max_checks - 1) 次稳定。
    stable_checks = max(1, min(int(stable_checks), int(max_checks) - 1))
    last_size: int | None = None
    stable = 0
    for _ in range(max_checks):
        if not p.exists():
            time.sleep(interval)
            continue
        try:
            size = p.stat().st_size
        except OSError as exc:
            log.warning("检查文件大小出错: %s", exc)
            return False
        if size == last_size:
            stable += 1
            if stable >= stable_checks:
                return True
        else:
            stable = 0
        last_size = size
        time.sleep(interval)
    return False


# ---------------------------------------------------------------------------
# 整理目录（单次整理 + 事件处理）
# ---------------------------------------------------------------------------
class DownloadOrganizer:
    """对一个监控目录执行整理逻辑。"""

    def __init__(
        self,
        downloads: DownloadsConfig,
        state: ProcessedState,
        completion_checker=is_file_download_complete,
    ):
        self.root = Path(downloads.path).expanduser()
        self.cfg = downloads
        self.state = state
        self.matcher = RuleMatcher(self.root, downloads.rules)
        self.resolver = ConflictResolver(downloads.conflict_policy)
        self._completion = completion_checker
        self._ignored = tuple(downloads.ignored_endings)
        self._stable_checks = max(1, int(getattr(downloads, "stable_checks", 3)))

    # -- 判断 ------------------------------------------------
    def should_ignore(self, filename: str) -> bool:
        return any(filename.endswith(s) for s in self._ignored)

    def target_for(self, filename: str) -> Path | None:
        m = self.matcher.match(filename)
        if m is None or not m.should_move():
            return None
        return self.resolver.resolve(m.target_dir / filename)

    def _is_complete(self, path: str | Path) -> bool:
        """带连续稳定次数的完成判定（供单次整理与事件处理共用）。

        兼容旧的自定义 completion_checker（不含 stable_checks 参数）。
        """
        kwargs = {"interval": self.cfg.check_interval,
                  "max_checks": self.cfg.max_checks}
        try:
            if "stable_checks" in inspect.signature(self._completion).parameters:
                kwargs["stable_checks"] = self._stable_checks
        except (TypeError, ValueError):
            pass
        return self._completion(path, **kwargs)

    def create_folders(self, rules=None) -> None:
        """创建各规则的目标目录（幂等）。"""
        dirs: set[Path] = set()
        for rule in (rules or self.cfg.rules):
            if rule.target_dir:
                t = Path(rule.target_dir).expanduser()
                if not t.is_absolute():
                    t = self.root / t
                dirs.add(t)
            else:
                dirs.add(self.root / rule.category)
        for d in dirs:
            try:
                d.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                log.warning("创建目录 %s 失败: %s", d, exc)

    # -- 移动 ------------------------------------------------
    def move_file(self, file_path: str | Path) -> Path | None:
        """把文件移动到规则命中的目标目录；返回最终路径，失败/skip 返回 None。"""
        p = Path(file_path)
        filename = os.path.basename(str(p))
        if self.should_ignore(filename):
            return None
        target = self.target_for(filename)
        if target is None:
            return None
        # 确认目标目录存在
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            log.warning("创建目标目录失败: %s (%s)", target.parent, exc)
        try:
            shutil.move(str(p), str(target))
            log.info("已移动: %s -> %s", filename, target)
            return target
        except Exception as exc:
            log.warning("移动文件 %s 失败: %s", filename, exc)
            return None

    # -- 整理既有文件 ----------------------------------------
    def _target_dirs(self) -> set[Path]:
        """规则目标目录集合（用于在遍历时排除，避免把已归档文件再次移动）。"""
        dirs: set[Path] = set()
        for rule in self.cfg.rules:
            if rule.target_dir:
                t = Path(rule.target_dir).expanduser()
                if not t.is_absolute():
                    t = self.root / t
            else:
                t = self.root / rule.category
            dirs.add(t)
        return dirs

    def _iter_files(self):
        """遍历监控目录下的文件；recursive=True 时含子目录（仅文件）。

        排除规则目标目录：recursive 遍历会把已归档到“图片/”等分类目录的
        文件再次扫到并重复移动，这里直接跳过这些目标目录内的文件。
        """
        targets = self._target_dirs()

        def under_target(p: Path) -> bool:
            return any(p.is_relative_to(t) for t in targets)

        if self.cfg.recursive:
            for p in self.root.rglob("*"):
                if p.is_file() and not under_target(p):
                    yield p
        else:
            for p in self.root.iterdir():
                if p.is_file() and not under_target(p):
                    yield p

    def organize_existing(self) -> None:
        if not self.root.is_dir():
            log.warning("监控目录不存在: %s", self.root)
            return
        for entry in self._iter_files():
            sp = str(entry)
            if self.should_ignore(entry.name):
                continue
            if self.state.contains(sp):
                continue
            if not self._is_complete(entry):
                continue
            fp = _fingerprint(sp)          # 移动前取指纹，用于同名重下载判定
            if self.move_file(entry) is not None:
                self.state.record(sp, fp)
        self.state.save()


# ---------------------------------------------------------------------------
# watchdog 事件处理
# ---------------------------------------------------------------------------
class DownloadHandler:
    """处理 watchdog 事件，把完成文件交给 DownloadOrganizer 移动。

    不直接继承 FileSystemEventHandler（保持本模块不强制依赖 watchdog）：
    watchdog 的 Observer.schedule 只要求 handler 提供 on_created/on_modified
    等方法，并对事件对象进行鸭子类型访问（is_directory / src_path）。

    常驻监控下由 ``_Worker`` 异步处理（观察者线程只入队，避免被等待
    下载完成的 sleep 阻塞）；无 worker（如单测直接调用）时同步处理。
    """

    def __init__(self, organizer: DownloadOrganizer, worker: "_Worker | None" = None):
        self.organizer = organizer
        self.worker = worker
        self.pending: set[str] = set()

    def on_created(self, event) -> None:
        self.process_event(event)

    def on_modified(self, event) -> None:
        self.process_event(event)

    def process_event(self, event) -> None:
        org = self.organizer
        if event.is_directory:
            return
        file_path = str(event.src_path)
        filename = os.path.basename(file_path)

        if org.should_ignore(filename):
            return
        if org.state.contains(file_path):
            return
        if file_path in self.pending:
            return

        log.info("检测到文件: %s", filename)
        self.pending.add(file_path)
        if self.worker is not None:
            self.worker.submit(self, file_path, filename)
        else:
            self._process(org, file_path, filename)

    def _process(self, org, file_path: str, filename: str) -> None:
        try:
            if org._is_complete(file_path):
                log.info("文件下载完成: %s", filename)
                fp = _fingerprint(file_path)
                if org.move_file(file_path) is not None:
                    org.state.record(file_path, fp)
            else:
                log.info("文件未完成下载，稍后重试: %s", filename)
        except Exception as exc:
            log.warning("处理文件 %s 出错: %s", filename, exc)
        finally:
            self.pending.discard(file_path)
            org.state.save()


class _Worker:
    """独立线程消费事件队列：把“等待下载完成 + 移动”移出观察者线程。"""

    def __init__(self, handlers: list[DownloadHandler]):
        self.handlers = handlers
        self._q: "queue.Queue" = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name="organizer-worker")

    def start(self) -> None:
        self._thread.start()

    def submit(self, handler, file_path: str, filename: str) -> None:
        self._q.put((handler, file_path, filename))

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        self._q.put(None)   # 唤醒可能阻塞的 get
        self._thread.join(timeout=timeout)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                item = self._q.get(timeout=1.0)
            except queue.Empty:
                continue
            if item is None:
                break
            handler, file_path, filename = item
            org = handler.organizer
            # 处理前再次核对（可能已被其它路径处理/移动）
            if org.state.contains(file_path) or file_path not in handler.pending:
                continue
            handler._process(org, file_path, filename)


# ---------------------------------------------------------------------------
# 常驻监控
# ---------------------------------------------------------------------------
def run_monitor(cfg, state_file: str | None = None, block: bool = True):
    """组装并启动对所有配置目录的监控。返回 Observer 以便外部控制。"""
    Observer = _import_watchdog()
    state = ProcessedState(state_file)
    organizers = [DownloadOrganizer(d, state) for d in cfg.downloads]

    observer = Observer()
    handlers: list[DownloadHandler] = []
    for org in organizers:
        org.create_folders()
        org.organize_existing()
        handler = DownloadHandler(org)
        observer.schedule(handler, str(org.root), recursive=org.cfg.recursive)
        handlers.append(handler)

    # 事件处理放入独立线程，避免等待下载完成的 sleep 阻塞观察者线程
    worker = _Worker(handlers)
    for h in handlers:
        h.worker = worker

    observer.start()
    worker.start()
    log.info("开始监控: %s", ", ".join(str(o.root) for o in organizers))
    if block:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            log.info("停止监控…")
        finally:
            observer.stop()
            observer.join()
            worker.stop()
            state.flush()
    return observer
