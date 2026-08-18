# -*- coding: utf-8 -*-
"""配置 GUI 的模型↔TOML 往返测试（不依赖真实显示环境）。"""
import os
import tempfile

from download_organizer.config import load_config
from download_organizer.gui import ConfigEditor, _toml_str


def _make_editor(tmpdir: str):
    """跳过窗口初始化，构造一个纯数据编辑器实例。"""
    editor = object.__new__(ConfigEditor)
    editor.config_path = os.path.join(tmpdir, "config.toml")
    editor.downloads = [{
        "path": "D:/下载", "recursive": True, "conflict_policy": "rename",
        "check_interval": 1.0, "stable_checks": 3, "max_checks": 30,
        "ignored_endings": [".crdownload", ".part", ".tmp", ".temp", "~", ".aria2"],
        "poll_interval": 5.0,
        "rules": [
            {"category": "图片", "extensions": [".jpg", ".png"],
             "target_dir": "", "name_pattern": ""},
            {"category": "文档", "extensions": [],
             "target_dir": "归档/文档", "name_pattern": r"report_\d+"},
        ],
    }]
    return editor


def test_toml_str_escapes_backslash_and_quote():
    assert _toml_str(r"a\b") == '"a\\\\b"'
    assert _toml_str('say "hi"') == '"say \\"hi\\""'


def test_roundtrip_preserves_fields(tmp_path):
    editor = _make_editor(str(tmp_path))
    editor._write_toml(tmp_path / "config.toml")
    cfg = load_config(str(tmp_path / "config.toml"))
    d = cfg.downloads[0]
    assert d.path == "D:/下载"
    assert d.recursive is True
    assert d.conflict_policy == "rename"
    assert d.stable_checks == 3
    assert ".aria2" in d.ignored_endings
    assert len(d.rules) == 2
    assert d.rules[0].category == "图片"
    assert d.rules[0].extensions == (".jpg", ".png")
    assert d.rules[1].target_dir == "归档/文档"
    assert d.rules[1].name_pattern == r"report_\d+"


def test_roundtrip_multi_dirs(tmp_path):
    editor = _make_editor(str(tmp_path))
    editor.downloads.append({
        "path": "E:/其他", "recursive": False, "conflict_policy": "skip",
        "check_interval": 2.0, "stable_checks": 5, "max_checks": 20,
        "ignored_endings": [".part"], "poll_interval": 10.0,
        "rules": [{"category": "其他文件", "extensions": [],
                   "target_dir": "", "name_pattern": ""}],
    })
    editor._write_toml(tmp_path / "config.toml")
    cfg = load_config(str(tmp_path / "config.toml"))
    assert len(cfg.downloads) == 2
    assert cfg.downloads[1].path == "E:/其他"
    assert cfg.downloads[1].conflict_policy == "skip"
    assert cfg.downloads[1].check_interval == 2.0
