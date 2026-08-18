# DownloadOrganizer

常驻整理“下载文件夹”的小工具：把新增/修改的已完成文件，按类型自动归档到分类子文件夹
（图片 / 视频 / 压缩包 / 文档 / 音频 / 可执行文件 / 其他文件），未完成或临时文件会等待/跳过。

本项目源自对一个 PyInstaller 打包的 `.exe` 的反编译分析，现已重构为**可维护的 Python 包**，
并做了工程化改造（配置驱动、状态持久化、单元测试、多目录、冲突策略）。

## 功能

- 常驻监控（watchdog），也可 `--once` 单次整理退出
- 启动时整理既有文件
- 按扩展名 / 文件名正则 / 自定义目标目录 分类
- 忽略未完成下载：`.crdownload`、`.part`、`.tmp`、`.temp`、`~` 结尾
- 大小稳定判定“下载完成”
- 冲突策略：`rename`（自动 `xxx (1).ext`）/ `overwrite` / `skip` / `recycle`
- **状态持久化**：已处理文件记录到 JSON，重启不重复整理
- 支持多下载目录，每个目录独立规则
- 结构化日志；`Ctrl+C` 优雅停止

## 安装

```bash
pip install -e .
# 仅依赖 watchdog：python -m pip install watchdog
```

Python 3.11+。

## 用法

```bash
# 常驻监控（默认读取 config.toml，无则用内置默认规则）
download-organizer
# 或
python -m download_organizer.cli

# 指定配置
python -m download_organizer.cli --config config.toml

# 只整理一次既有文件后退出
python -m download_organizer.cli --once --config config.toml

# 旧版单文件入口仍可用
python DownloadOrganizer.py
```

## 配置

复制 [`config.example.toml`](config.example.toml) 为 `config.toml` 后修改。

支持的字段（`[organizer]`）：`downloads_folder`、`log_level`、`state_file`；
每个 `[[downloads]]`：`path`、`recursive`、`check_interval`、`max_checks`、
`conflict_policy`、`persist_processed`、`ignored_endings`、`rules`。
每条 `rules`：`category`、`extensions`、`name_pattern`、`target_dir`。
规则按顺序匹配，先命中先生效；无扩展名/无正则的规则作为兜底。

> TOML 里 Windows 反斜杠需转义，建议路径用正斜杠（`"D:/资料"`）。

## 结构

```
download_organizer/
    __init__.py      # 公开 API
    config.py        # 配置模型 + TOML 加载 + 默认值
    rules.py         # 分类规则引擎
    organizer.py     # 核心逻辑：状态 / 冲突 / 移动 / 监控
    cli.py           # 命令行入口
tests/               # pytest 测试
config.example.toml  # 配置示例
DownloadOrganizer.py # 薄启动器（便于从旧入口运行）
```

## 测试

```bash
python -m pytest tests
```

## 说明

第三方依赖仅 `watchdog`；其余为 Python 标准库。原 `.exe` 中的关卡逻辑（分类表、忽略后缀、
下载完成判定）已完整迁移并扩展为可配置项。
