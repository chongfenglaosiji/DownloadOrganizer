# -*- coding: utf-8 -*-
"""核心整理逻辑测试：状态持久化、冲突策略、移动、事件处理。

注意：为避免测试临时目录落到工作区之外或触发沙箱对系统临时目录的限制，
这里用工作区下的 `test_tmp/` 作为临时根，并自行负责清理。
"""
import os
import shutil
import sys
import uuid

import pytest

from download_organizer.config import DownloadsConfig, Rule
from download_organizer.organizer import (
    ConflictResolver,
    DownloadOrganizer,
    ProcessedState,
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
        s.save()
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
