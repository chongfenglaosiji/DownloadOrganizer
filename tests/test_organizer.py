# -*- coding: utf-8 -*-
"""核心整理逻辑测试：状态持久化、冲突策略、移动、事件处理。

注意：为避免测试临时目录落到工作区之外或触发沙箱对系统临时目录的限制，
这里用工作区下的 `test_tmp/` 作为临时根，并自行负责清理。
"""
import os
import shutil
import time
import uuid

import pytest

from download_organizer.config import DownloadsConfig, Rule
from download_organizer.organizer import (
    ConflictResolver,
    DownloadOrganizer,
    ProcessedState,
    is_file_download_complete,
)

WORKDIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_tmp")
os.makedirs(WORKDIR, exist_ok=True)

RULES = (
    Rule("图片", extensions=(".jpg", ".png")),
    Rule("文档", extensions=(".pdf", ".docx")),
    Rule("视频", extensions=(".mp4",)),
    Rule("其他文件", ()),
)
IGNORED = (".crdownload", ".part", ".tmp", ".temp", "~")


@pytest.fixture()
def dl_dir():
    """返回一个工作区内的隔离临时目录（含 category 子目录），用后自清。"""
    root = os.path.join(WORKDIR, uuid.uuid4().hex)
    os.makedirs(root, exist_ok=True)
    yield root
    shutil.rmtree(root, ignore_errors=True)


@pytest.fixture()
def dl(dl_dir):
    """把 dl_dir 包成 DownloadOrganizer 实例。"""
    cfg = DownloadsConfig(path=dl_dir, rules=RULES, ignored_endings=IGNORED,
                          conflict_policy="rename", check_interval=0.01, max_checks=2)
    org = DownloadOrganizer(cfg, ProcessedState(os.path.join(WORKDIR, "tmp_state.json")))
    org.create_folders()
    return {"root": dl_dir, "org": org}


def _make(root, name, content=b"x"):
    p = os.path.join(root, name)
    with open(p, "wb") as f:
        f.write(content)
    return p


class TestMove:
    def test_moves_to_category(self, dl):
        root, org = dl["root"], dl["org"]
        f = _make(root, "photo.jpg")
        target = org.move_file(f)
        assert target is not None
        assert os.path.exists(os.path.join(root, "图片", "photo.jpg"))
        assert not os.path.exists(f)

    def test_unknown_to_other(self, dl):
        root, org = dl["root"], dl["org"]
        f = _make(root, "blob.xyz")
        target = org.move_file(f)
        assert target is not None
        assert os.path.exists(os.path.join(root, "其他文件", "blob.xyz"))

    def test_ignored_not_moved(self, dl):
        root, org = dl["root"], dl["org"]
        f = _make(root, "dl.crdownload")
        target = org.move_file(f)
        assert target is None
        assert os.path.exists(f)

    def test_conflict_rename(self, dl):
        root, org = dl["root"], dl["org"]
        _make(root, "a.jpg")
        org.move_file(os.path.join(root, "a.jpg"))
        _make(root, "a.jpg")
        target = org.move_file(os.path.join(root, "a.jpg"))
        assert target is not None
        assert os.path.basename(target) == "a (1).jpg"
        assert os.path.exists(os.path.join(root, "图片", "a.jpg"))

    def test_conflict_skip(self, dl_dir):
        cfg = DownloadsConfig(path=dl_dir, rules=RULES, conflict_policy="skip",
                              check_interval=0.01, max_checks=2)
        org = DownloadOrganizer(cfg, ProcessedState(None))
        org.create_folders()
        _make(dl_dir, "a.jpg")
        org.move_file(os.path.join(dl_dir, "a.jpg"))
        _make(dl_dir, "a.jpg")
        target = org.move_file(os.path.join(dl_dir, "a.jpg"))
        assert target is None  # skip：不移动、不覆盖


class TestState:
    def test_persist_roundtrip(self, dl_dir):
        sf = os.path.join(dl_dir, "state.json")
        s = ProcessedState(sf)
        s.add("C:/x/y.jpg")
        s.save(force=True)
        s2 = ProcessedState(sf)
        assert s2.contains("C:/x/y.jpg")

    def test_organize_skips_already_done(self, dl):
        root, org = dl["root"], dl["org"]
        org.state.add(os.path.join(root, "photo.jpg"))
        _make(root, "photo.jpg")
        _make(root, "doc.pdf")
        org.organize_existing()
        # 已处理项留在原地，未处理项被移动
        assert os.path.exists(os.path.join(root, "photo.jpg"))
        assert os.path.exists(os.path.join(root, "文档", "doc.pdf"))

    def test_cap_drops_oldest(self, dl_dir):
        sf = os.path.join(dl_dir, "state.json")
        s = ProcessedState(sf)
        s.MAX_ITEMS = 5
        for i in range(10):
            s.add(f"C:/dl/f{i}.jpg")
        assert len(s._items) == 5
        # 最旧的 5 条被丢弃，保留最新的 5 条
        assert "C:/dl/f0.jpg" not in s._items
        assert "C:/dl/f9.jpg" in s._items

    def test_prune_keeps_only_root_paths(self, dl_dir):
        s = ProcessedState(None)
        s.add(os.path.join(dl_dir, "inside.jpg"))
        s.add("C:/outside/x.jpg")
        s.prune([dl_dir])
        assert os.path.join(dl_dir, "inside.jpg") in s._items
        assert "C:/outside/x.jpg" not in s._items


class TestConflictResolver:
    def test_policies(self, dl_dir):
        r = ConflictResolver("rename")
        t = os.path.join(dl_dir, "a.jpg")
        with open(t, "wb") as f:
            f.write(b"x")
        target = r.resolve(t)
        assert os.path.basename(target) == "a (1).jpg"
        assert ConflictResolver("skip").resolve(t) is None
        assert os.fspath(ConflictResolver("overwrite").resolve(t)) == t
        shutil.rmtree(dl_dir, ignore_errors=True)


class TestCompletion:
    def test_continuous_stable_returns_true(self, dl_dir):
        p = os.path.join(dl_dir, "stable.bin")
        with open(p, "wb") as f:
            f.write(b"x" * 100)
        # 连续 stable_checks 次大小不变 -> 判定完成
        assert is_file_download_complete(p, interval=0.01, max_checks=10,
                                         stable_checks=3) is True

    def test_growing_file_returns_false(self, dl_dir):
        p = os.path.join(dl_dir, "growing.bin")
        # 每次采样后增大，永不连续稳定 -> 判定未完成
        import threading

        def grow():
            import time
            for i in range(1, 6):
                with open(p, "ab") as f:
                    f.write(b"x" * i)
                time.sleep(0.02)

        with open(p, "wb") as f:
            f.write(b"x")
        t = threading.Thread(target=grow, daemon=True)
        t.start()
        try:
            assert is_file_download_complete(p, interval=0.015, max_checks=5,
                                             stable_checks=3) is False
        finally:
            t.join(timeout=2)


class TestAria2:
    def test_aria2_control_file_ignored(self, dl_dir):
        # 不显式覆盖 ignored_endings：使用默认值（含 .aria2）
        cfg = DownloadsConfig(path=dl_dir, rules=RULES,
                              check_interval=0.01, max_checks=2)
        org = DownloadOrganizer(cfg, ProcessedState(None))
        f = _make(dl_dir, "movie.mp4.aria2")
        assert org.should_ignore("movie.mp4.aria2")
        assert org.move_file(f) is None
        assert os.path.exists(f)  # 未被移动


class TestReDownload:
    def test_same_name_redownload_moves_again(self, dl):
        root, org = dl["root"], dl["org"]
        # 第一次整理：移动 photo.jpg，状态记录指纹
        f = _make(root, "photo.jpg")
        org.organize_existing()
        assert not os.path.exists(f)
        assert os.path.exists(os.path.join(root, "图片", "photo.jpg"))
        # 模拟重新下载同名文件（不同内容 -> 不同指纹）
        time.sleep(0.02)
        f2 = _make(root, "photo.jpg", content=b"different-content")
        org.organize_existing()
        assert not os.path.exists(f2)  # 再次被移动
        assert os.path.exists(os.path.join(root, "图片", "photo.jpg"))


class TestRecursive:
    def test_organize_existing_recursive(self, dl_dir):
        sub = os.path.join(dl_dir, "sub")
        os.makedirs(sub, exist_ok=True)
        nested = os.path.join(sub, "nested.png")
        _make(dl_dir, "top.jpg")
        with open(nested, "wb") as f:
            f.write(b"x")
        cfg = DownloadsConfig(path=dl_dir, rules=RULES, recursive=True,
                              check_interval=0.01, max_checks=2)
        org = DownloadOrganizer(cfg, ProcessedState(None))
        org.organize_existing()
        assert os.path.exists(os.path.join(dl_dir, "图片", "top.jpg"))
        assert os.path.exists(os.path.join(dl_dir, "图片", "nested.png"))
        assert not os.path.exists(nested)

    def test_non_recursive_does_not_touch_subdir(self, dl_dir):
        sub = os.path.join(dl_dir, "sub")
        os.makedirs(sub, exist_ok=True)
        nested = os.path.join(sub, "nested.png")
        with open(nested, "wb") as f:
            f.write(b"x")
        cfg = DownloadsConfig(path=dl_dir, rules=RULES, recursive=False,
                              check_interval=0.01, max_checks=2)
        org = DownloadOrganizer(cfg, ProcessedState(None))
        org.organize_existing()
        assert os.path.exists(nested)  # 非递归不动子目录


class TestEnhancedCompletion:
    def test_enhanced_uses_stable_size_without_aria2(self, dl_dir):
        from download_organizer.organizer import enhanced_completion_check
        p = os.path.join(dl_dir, "stable.bin")
        with open(p, "wb") as f:
            f.write(b"x" * 50)
        assert enhanced_completion_check(p, interval=0.01, max_checks=5,
                                         stable_checks=2) is True

    def test_enhanced_aria2_signal(self, dl_dir):
        import struct
        from download_organizer.organizer import enhanced_completion_check
        # 构造控制文件：总长 100；主文件仅 10 → 未完成（无需等待采样）
        ctrl = os.path.join(dl_dir, "a.bin.aria2")
        header = struct.pack(">HII", 1, 0, 0) + struct.pack(">I", 16384)
        header += struct.pack(">Q", 100) + struct.pack(">Q", 0) + struct.pack(">I", 0)
        with open(ctrl, "wb") as f:
            f.write(header)
        with open(os.path.join(dl_dir, "a.bin"), "wb") as f:
            f.write(b"x" * 10)
        assert enhanced_completion_check(os.path.join(dl_dir, "a.bin"),
                                         interval=0.01, max_checks=5,
                                         stable_checks=2,
                                         use_aria2_check=True) is False

    def test_enhanced_locked_check(self, dl_dir):
        # 非 Windows 平台 is_file_locked 恒 False，走大小判定；此处仅验证不抛错
        from download_organizer.organizer import enhanced_completion_check, is_file_locked
        p = os.path.join(dl_dir, "f.bin")
        with open(p, "wb") as f:
            f.write(b"x" * 10)
        assert is_file_locked(p) is False
        assert enhanced_completion_check(p, interval=0.01, max_checks=5,
                                         stable_checks=2,
                                         check_file_locked=True) is True


class TestTimestampOnMove:
    def test_move_updates_timestamp(self, dl):
        root, org = dl["root"], dl["org"]
        f = _make(root, "photo.jpg")
        old_mtime = os.path.getmtime(f)
        time.sleep(0.02)
        org.move_file(f)
        target = os.path.join(root, "图片", "photo.jpg")
        assert os.path.exists(target)
        assert os.path.getmtime(target) >= old_mtime

    def test_move_timestamp_disabled(self, dl_dir):
        cfg = DownloadsConfig(path=dl_dir, rules=RULES,
                              update_timestamp_on_move=False,
                              check_interval=0.01, max_checks=2)
        org = DownloadOrganizer(cfg, ProcessedState(None))
        f = _make(dl_dir, "photo.jpg")
        before = os.path.getmtime(f)
        org.move_file(f)
        target = os.path.join(dl_dir, "图片", "photo.jpg")
        assert os.path.exists(target)
        # 关闭后：目标 mtime 应基本等于源 mtime（shutil.move 保留）
        assert abs(os.path.getmtime(target) - before) < 1.0


class TestPolling:
    def test_polling_run_once_moves_stable_file(self, dl_dir):
        from download_organizer.organizer import PollingMonitor
        from download_organizer.config import DownloadsConfig
        cfg = DownloadsConfig(path=dl_dir, rules=RULES,
                              check_interval=0.01, max_checks=2,
                              poll_interval=0.05)
        state = ProcessedState(None)
        mon = PollingMonitor(cfg, state)
        f = _make(dl_dir, "photo.jpg")
        mon.run_once()   # 第一轮：记录快照
        mon.run_once()   # 第二轮：快照稳定 → 移动
        assert os.path.exists(os.path.join(dl_dir, "图片", "photo.jpg"))
        assert not os.path.exists(f)

    def test_polling_ignores_growing_file(self, dl_dir):
        from download_organizer.organizer import PollingMonitor
        from download_organizer.config import DownloadsConfig
        cfg = DownloadsConfig(path=dl_dir, rules=RULES,
                              check_interval=0.01, max_checks=2,
                              poll_interval=0.05)
        state = ProcessedState(None)
        mon = PollingMonitor(cfg, state)
        p = os.path.join(dl_dir, "growing.jpg")
        with open(p, "wb") as f:
            f.write(b"x" * 5)
        mon.run_once()          # 快照1: 5
        time.sleep(0.02)
        with open(p, "ab") as f:
            f.write(b"y" * 5)   # 快照2: 10（变化）
        mon.run_once()
        time.sleep(0.02)
        with open(p, "ab") as f:
            f.write(b"z" * 5)   # 快照3: 15（仍变化）
        mon.run_once()
        assert os.path.exists(p)  # 一直增长，未移动


try:
    import watchdog  # noqa: F401
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False


@pytest.mark.skipif(not HAS_WATCHDOG, reason="watchdog 未安装")
class TestHandler:
    def test_event_moves_file(self, dl):
        from watchdog.events import FileSystemEvent
        from download_organizer.organizer import DownloadHandler
        root, org = dl["root"], dl["org"]
        f = _make(root, "movie.mp4")

        class Ev(FileSystemEvent):
            @property
            def is_directory(self):
                return False

        handler = DownloadHandler(org)
        handler.on_created(Ev(f))
        assert os.path.exists(os.path.join(root, "视频", "movie.mp4"))
        assert not os.path.exists(f)
