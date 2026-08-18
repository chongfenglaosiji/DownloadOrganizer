# -*- coding: utf-8 -*-
"""分类规则引擎。

把“文件名/扩展名 -> 目标路径”的判断从文件操作中解耦出来，
便于测试与复用。目标目录支持绝对路径，也支持相对“下载根目录”的路径。
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from .config import Rule


def _normalize_ext(ext: str) -> str:
    ext = ext.strip().lower()
    return ext if ext.startswith(".") else ("." + ext if ext else ext)


@dataclass(frozen=True)
class MatchResult:
    """一个文件命中规则后的归类结果。"""

    category: str
    target_dir: Path | None   # None 表示不移动（如归到“忽略”/未知但无可移动目标）

    def should_move(self) -> bool:
        return self.target_dir is not None


class RuleMatcher:
    """按规则表匹配文件，得到目标目录。

    Parameters
    ----------
    root : Path
        下载根目录（用于解析相对 target_dir）。
    rules : tuple[Rule, ...]
        按顺序匹配，先命中先生效。
    """

    def __init__(self, root: Path, rules: tuple[Rule, ...]):
        self.root = Path(root)
        self.rules = rules
        self._patterns = {
            i: (re.compile(r.name_pattern) if r.name_pattern else None)
            for i, r in enumerate(rules)
        }

    def _rule_target(self, rule: Rule) -> Path | None:
        if rule.target_dir:
            t = Path(rule.target_dir).expanduser()
            if not t.is_absolute():
                t = self.root / t
            return t
        # 无目标目录：使用 category 作为子目录名
        return self.root / rule.category

    def match(self, filename: str) -> MatchResult | None:
        """返回命中规则的 MatchResult；无规则命中时返回 None。"""
        ext = _normalize_ext(os.path.splitext(filename)[1])
        for idx, rule in enumerate(self.rules):
            pat = self._patterns[idx]
            if rule.extensions and ext in rule.extensions:
                return MatchResult(rule.category, self._rule_target(rule))
            if pat is not None and pat.search(filename):
                return MatchResult(rule.category, self._rule_target(rule))
            # 既无扩展名也无正则的规则视为兜底：匹配任何文件
            if not rule.extensions and pat is None:
                return MatchResult(rule.category, self._rule_target(rule))
        return None

    def categorize(self, filename: str) -> str:
        """返回分类名（未命中返回 '其他文件'）。"""
        res = self.match(filename)
        if res is None:
            return "其他文件"
        return res.category
