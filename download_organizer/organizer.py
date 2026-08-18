# -*- coding: utf-8 -*-
"""核心整理引擎。

包含：
  * 状态持久化（已处理文件列表，避免重启后重复整理）
  * 冲突处理（rename / overwrite / skip / recycle）
  * “下载完成”判定
  * watchdog 事件处理器与常驻监控
"""
from __future__ import annotations

import json
import logging
import os
import shutil
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
class ProcessedState:
    """记录已成功处理（移动）的文件路径，跨进程/重启保留。"""

    def __init__(self, file: str | Path | None):
        self.file = str(Path(file).expanduser()) if file else None
        self._paths: set[str] = set()
        if self.file:
            self._load()

    def _load(self) -> None:
        try:
            p = Path(self.file)
            if p.is_file():
                data = json.loads(p.read_text(encoding="utf-8"))
                self._paths = set(data.get("processed", []))
        except Exception as exc:  # 状态文件损坏时忽略，不阻塞启动
            log.warning("状态文件加载失败（将重置）: %s", exc)
            self._paths = set()

    def save(self) -> None:
        if not self.file:
            return
        try:
            p = Path(self.file)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(
                json.dumps({"processed": sorted(self._paths)}, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            log.warning("状态文件写入失败: %s", exc)

    def contains(self, path: str) -> bool:
        return path in self._paths

    def add(self, path: str) -> None:
        self._paths.add(path)

    def discard(self, path: str) -> None:
        self._paths.discard(path)


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
                              max_checks: int = 30) -> bool:
    """估算文件是否已下载完成：大小在 interval 秒内不再变化。"""
    p = Path(file_path)
    for _ in range(max_checks):
        if not p.exists():
            time.sleep(interval)
            continue
        try:
            initial = p.stat().st_size
            time.sleep(interval)
            if not p.exists():
                continue
            final = p.stat().st_size
            if initial == final:
                return True
        except OSError as exc:
            log.warning("检查文件大小出错: %s", exc)
            return False
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

    # -- 判断 ------------------------------------------------
    def should_ignore(self, filename: str) -> bool:
        return any(filename.endswith(s) for s in self._ignored)

    def target_for(self, filename: str) -> Path | None:
        m = self.matcher.match(filename)
        if m is None or not m.should_move():
            return None
        return self.resolver.resolve(m.target_dir / filename)

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
    def organize_existing(self) -> None:
        if not self.root.is_dir():
            log.warning("监控目录不存在: %s", self.root)
            return
        for entry in self.root.iterdir():
            if not entry.is_file():
                continue
            sp = str(entry)
            if self.should_ignore(entry.name):
                continue
            if self.state.contains(sp):
                continue
            if not self._completion(entry, interval=self.cfg.check_interval,
                                    max_checks=self.cfg.max_checks):
                continue
            if self.move_file(entry) is not None:
                self.state.add(sp)
        self.state.save()


# ---------------------------------------------------------------------------
# watchdog 事件处理
# ---------------------------------------------------------------------------
class DownloadHandler:
    """处理 watchdog 事件，把完成文件交给 DownloadOrganizer 移动。

    不直接继承 FileSystemEventHandler（保持本模块不强制依赖 watchdog）：
    watchdog 的 Observer.schedule 只要求 handler 提供 on_created/on_modified
    等方法，并对事件对象进行鸭子类型访问（is_directory / src_path）。
    """

    def __init__(self, organizer: DownloadOrganizer):
        self.organizer = organizer
        self.pending: dict[str, bool] = {}

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
        self.pending[file_path] = True
        try:
            if org._completion(file_path, interval=org.cfg.check_interval,
                               max_checks=org.cfg.max_checks):
                log.info("文件下载完成: %s", filename)
                if org.move_file(file_path) is not None:
                    org.state.add(file_path)
                del self.pending[file_path]
            else:
                log.info("文件未完成下载，稍后重试: %s", filename)
                del self.pending[file_path]
        except Exception as exc:
            log.warning("处理文件 %s 出错: %s", filename, exc)
            self.pending.pop(file_path, None)
        org.state.save()


# ---------------------------------------------------------------------------
# 常驻监控
# ---------------------------------------------------------------------------
def run_monitor(cfg, state_file: str | None = None, block: bool = True):
    """组装并启动对所有配置目录的监控。返回 Observer 以便外部控制。"""
    Observer = _import_watchdog()
    state = ProcessedState(state_file)
    organizers = [DownloadOrganizer(d, state) for d in cfg.downloads]

    observer = Observer()
    registry = []
    for org in organizers:
        org.create_folders()
        org.organize_existing()
        handler = DownloadHandler(org)
        observer.schedule(handler, str(org.root), recursive=org.cfg.recursive)
        registry.append((org, handler))

    observer.start()
    log.info("开始监控: %s", ", ".join(str(o.root) for o in organizers))
    if block:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
            log.info("停止监控…")
        finally:
            observer.join()
    return observer
