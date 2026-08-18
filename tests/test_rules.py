# -*- coding: utf-8 -*-
"""规则引擎测试。"""
import os

from download_organizer.config import default_rules, Rule
from download_organizer.rules import RuleMatcher


def norm(p) -> str:
    return str(p).replace("\\", "/").replace("//", "/")


def _matcher(root="/tmp/dl", rules=None):
    return RuleMatcher(root, rules or default_rules())


def test_extension_match_case_insensitive():
    m = _matcher()
    assert m.match("photo.JPG").category == "图片"
    assert m.match("photo.Png").category == "图片"
    assert m.match("movie.mkv").category == "视频"


def test_no_extension_falls_to_other():
    m = _matcher()
    assert m.categorize("noext") == "其他文件"
    # 未匹配任何具体扩展名/正则时，命中“其他文件”兜底规则
    res = m.match("noext")
    assert res is not None and res.category == "其他文件"


def test_custom_target_dir_precedence():
    rules = (
        Rule("课程", extensions=(".mp4",), target_dir="D:/资料/课程"),
        Rule("其他文件", ()),
    )
    m = _matcher("/tmp/dl", rules)
    res = m.match("lecture.mp4")
    assert res is not None
    assert norm(res.target_dir.parent) == "D:/资料" and res.target_dir.name == "课程"


def test_relative_target_dir():
    rules = (
        Rule("图片", extensions=(".jpg",), target_dir="归档/图片"),
        Rule("其他文件", ()),
    )
    m = _matcher("/tmp/dl", rules)
    res = m.match("a.jpg")
    assert norm(res.target_dir) == norm(os.path.join("/tmp/dl", "归档", "图片"))
    assert str(res.target_dir).endswith(os.path.join("归档", "图片"))


def test_name_pattern():
    rules = (
        Rule("报表", name_pattern=r"report_\d{4}"),
        Rule("其他文件", ()),
    )
    m = _matcher("/tmp/dl", rules)
    assert m.match("report_2024.pdf").category == "报表"
    assert m.categorize("something.pdf") == "其他文件"
