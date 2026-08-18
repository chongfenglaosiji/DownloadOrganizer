# -*- coding: utf-8 -*-
"""配置加载测试。"""
import os

from download_organizer.config import (
    Config,
    DownloadsConfig,
    Rule,
    default_config,
    load_config,
)

EXAMPLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "config.example.toml")


def test_default_config_has_downloads():
    c = default_config()
    assert c.downloads, "默认应至少有一个监控目录"
    assert c.downloads[0].rules, "默认应有分类规则"


def test_load_example_config():
    c = load_config(EXAMPLE)
    assert c.downloads
    d = c.downloads[0]
    assert d.path.endswith("Downloads")
    assert len(d.rules) >= 7
    categories = [r.category for r in d.rules]
    assert "图片" in categories and "其他文件" in categories
    assert d.conflict_policy == "rename"
    assert d.check_interval == 1.0


def test_missing_file_returns_default():
    c = load_config("/nonexistent/no/such.toml")
    assert isinstance(c, Config)


def test_rule_parser_target_dir():
    # 手工构造 DownloadsConfig 验证 target_dir 传入
    rule = Rule(category="课程", extensions=(".mp4",), target_dir="D:/资料/课程")
    d = DownloadsConfig(path="/tmp/dl", rules=(rule,))
    assert d.rules[0].target_dir == "D:/资料/课程"
