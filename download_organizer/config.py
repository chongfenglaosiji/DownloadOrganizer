# -*- coding: utf-8 -*-
"""配置模型与加载。

配置采用 TOML（Python 3.11+ 内置 ``tomllib`` 解析）。未指定项回落到默认值。
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_FILENAME = "config.toml"


# ---------------------------------------------------------------------------
# 配置数据结构
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Rule:
    """一条分类规则：命中后文件会被移动（或按目标规则处理）到该分类目录。"""

    category: str
    extensions: tuple[str, ...] = ()
    # 目标目录：绝对路径，或相对“下载根目录”。为空则用 category 作为子目录名。
    target_dir: str | None = None
    # 可选：文件名正则（re.search），命中即归入本类
    name_pattern: str | None = None

    def matcher_brief(self) -> str:
        parts = []
        if self.extensions:
            parts.append("ext=" + ",".join(self.extensions))
        if self.name_pattern:
            parts.append("pattern=" + self.name_pattern)
        if self.target_dir:
            parts.append("target=" + self.target_dir)
        return f"[{self.category} {' '.join(parts)}]"


@dataclass(frozen=True)
class DownloadsConfig:
    """下载目录的监控与整理配置。"""

    path: str
    recursive: bool = False
    rules: tuple[Rule, ...] = ()
    ignored_endings: tuple[str, ...] = (
        ".crdownload", ".part", ".tmp", ".temp", "~", ".aria2",
    )
    conflict_policy: str = "rename"   # rename | overwrite | skip | recycle
    check_interval: float = 1.0
    max_checks: int = 30
    # 连续多少次采样大小都稳定才算“下载完成”，降低对写字中/分段下载文件的误判
    stable_checks: int = 3
    # 如果为 True，在移动后把文件路径记入已处理记录（持久化），避免重启后重复整理
    persist_processed: bool = True


@dataclass(frozen=True)
class Config:
    downloads_folder: str
    log_level: str = "INFO"
    state_file: str = "~/.download_organizer_state.json"
    downloads: tuple[DownloadsConfig, ...] = ()


# ---------------------------------------------------------------------------
# 默认配置与加载
# ---------------------------------------------------------------------------
def default_rules() -> tuple[Rule, ...]:
    """内置默认分类规则（与原程序一致）。"""
    return (
        Rule("图片", (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp")),
        Rule("视频", (".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv")),
        Rule("压缩包", (".zip", ".tar", ".gz", ".rar", ".7z")),
        Rule("文档", (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt")),
        Rule("音频", (".mp3", ".wav", ".flac", ".aac", ".ogg")),
        Rule("可执行文件", (".exe", ".bat", ".msi")),
        Rule("其他文件", ()),
    )


def default_config() -> Config:
    return Config(
        downloads_folder=str((Path.home() / "Downloads")),
        downloads=(DownloadsConfig(
            path=str(Path.home() / "Downloads"),
            rules=default_rules(),
        ),),
    )


def _as_str_list(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [s.strip().lower() for s in v.split(",") if s.strip()]
    if isinstance(v, list):
        return [str(x).strip().lower() for x in v]
    raise TypeError(f"expect list or comma string, got {type(v)}")


def _parse_rule(raw: dict) -> Rule:
    category = str(raw.get("category", "")).strip()
    if not category:
        raise ValueError("rule missing 'category'")
    extensions = tuple(_as_str_list(raw.get("extensions")))
    target_dir = raw.get("target_dir")
    name_pattern = raw.get("name_pattern")
    return Rule(
        category=category,
        extensions=extensions,
        target_dir=str(target_dir) if target_dir else None,
        name_pattern=str(name_pattern) if name_pattern else None,
    )


def _parse_downloads(raw: dict) -> DownloadsConfig:
    try:
        path = str(raw["path"])
    except KeyError:
        raise ValueError("downloads entry missing 'path'") from None
    rules_raw = raw.get("rules")
    if rules_raw is None:
        rules = default_rules()
    else:
        rules = tuple(_parse_rule(r) for r in rules_raw)
    conflict = raw.get("conflict_policy", "rename")
    if conflict not in ("rename", "overwrite", "skip", "recycle"):
        raise ValueError(f"unknown conflict_policy: {conflict}")
    return DownloadsConfig(
        path=path,
        recursive=bool(raw.get("recursive", False)),
        rules=rules,
        ignored_endings=tuple(_as_str_list(raw.get("ignored_endings"))
                              or default_config().downloads[0].ignored_endings),
        conflict_policy=conflict,
        check_interval=float(raw.get("check_interval", 1.0)),
        max_checks=int(raw.get("max_checks", 30)),
        stable_checks=int(raw.get("stable_checks", 3)),
        persist_processed=bool(raw.get("persist_processed", True)),
    )


def load_config(path: str | Path | None = None) -> Config:
    """从 TOML 文件加载配置；未给 path 或文件不存在时返回默认配置。"""
    if path is None:
        return default_config()
    p = Path(path).expanduser()
    if not p.is_file():
        return default_config()
    with open(p, "rb") as f:
        data = tomllib.load(f)
    return _build_config(data, p)


def _build_config(data: dict, src: Path) -> Config:
    top = data.get("organizer", {}) if isinstance(data.get("organizer"), dict) else {}
    downloads_folder = str(
        top.get("downloads_folder")
        or data.get("downloads_folder")
        or default_config().downloads_folder
    ).replace("~", str(Path.home())) if top.get("downloads_folder") or data.get("downloads_folder") \
        else default_config().downloads_folder

    # 兼容两种写法：
    #  1) downloads_paths: ["a", "b"]
    #  2) downloads: [{path, rules, ...}, ...]
    raw_downloads = data.get("downloads")
    downloads_paths = top.get("paths") or data.get("downloads_paths")

    if isinstance(raw_downloads, list) and raw_downloads:
        dls = tuple(_parse_downloads(d) for d in raw_downloads)
    else:
        paths: list[str] = []
        if downloads_paths:
            paths = _as_str_list(downloads_paths)
        if not paths:
            paths = [downloads_folder]
        dls = tuple(DownloadsConfig(path=p, rules=default_rules()) for p in paths)

    return Config(
        downloads_folder=downloads_folder,
        log_level=str(top.get("log_level", "INFO")).upper(),
        state_file=str(top.get("state_file", default_config().state_file)),
        downloads=dls,
    )
