# DownloadOrganizer

常驻整理“下载文件夹”的小工具：把新增/修改的**已完成**文件，按类型自动归档到分类子文件夹
（图片 / 视频 / 压缩包 / 文档 / 音频 / 可执行文件 / 其他文件）。未完成、正在下载（含 aria2）、
临时文件会等待或跳过，绝不移动不完整的文件。

- 免安装：直接下载 exe，**扔进 `shell:startup` 即开机自启、无黑框**
- 项目源自对一个 PyInstaller 打包 `.exe` 的反编译分析，现已重构为可维护的 Python 包
- 配置驱动、状态持久化、单元测试、多目录、冲突策略

## 快速开始（普通用户，推荐）

不需要装 Python，三步搞定：

1. **下载 exe**：到 [Releases](https://github.com/chongfenglaosiji/DownloadOrganizer/releases)
   下载最新的 `DownloadOrganizer.exe`（Windows 单文件、已内置 Python 运行时）。
2. **放到固定位置**：把 exe 放到一个不会删的目录（如 `C:\Tools\DownloadOrganizer.exe`），
   双击运行一次验证能正常整理（日志写入 `%USERPROFILE%\.download_organizer\run.log`）。
3. **开机自启（无黑框）**：
   - 在 exe 上右键 → **发送到 → 桌面快捷方式**；
   - 按 `Win + R`，输入 `shell:startup` 回车，打开“启动”文件夹；
   - 把刚才的快捷方式**剪切/复制**进这个文件夹。

   之后每次开机都会**静默后台运行**：无控制台窗口（`--noconsole` 打包），
   日志自动写到 `%USERPROFILE%\.download_organizer\run.log`，不会弹黑框、不会报错。

> 想用自定义配置？在快捷方式“目标”里追加参数，例如：
> `"C:\Tools\DownloadOrganizer.exe" --config "D:\config.toml"`
> 不指定则使用内置默认规则（监控系统“下载”文件夹）。

## 开发者 / 源码运行

```bash
pip install -e .
# 仅需常驻监控依赖 watchdog：python -m pip install watchdog
```

```bash
# 常驻监控（默认读取 config.toml，无则用内置默认规则）
download-organizer
# 或
python -m download_organizer

# 指定配置
python -m download_organizer --config config.toml

# 只整理一次既有文件后退出
python -m download_organizer --once --config config.toml

# 无控制台日志到文件（适合开机自启/无窗口）
python -m download_organizer --hidden

# 旧版单文件入口仍可用
python DownloadOrganizer.py
```

Python 3.11+。

## 功能

- 常驻监控（watchdog），也可 `--once` 单次整理退出
- 启动时整理既有文件（`recursive` 时含子目录，且不会重复移动已归档文件）
- 按扩展名 / 文件名正则 / 自定义目标目录 分类
- **下载中保护**：忽略未完成/临时文件 `.crdownload`、`.part`、`.tmp`、`.temp`、`~`、
  **`.aria2`（aria2 控制文件）**；正在写入的文件不会被移动
- **完成判定**：大小**连续多次采样稳定**才算“下载完成”，显著降低对 aria2 等
  分段/慢速下载的误判
- 冲突策略：`rename`（自动 `xxx (1).ext`）/ `overwrite` / `skip`
- **状态持久化**：已处理文件记录到 JSON，重启不重复整理；**同名文件重新下载后会再次整理**
- 支持多下载目录，每个目录独立规则
- 结构化日志；`Ctrl+C` 优雅停止

## 配置

复制 [`config.example.toml`](config.example.toml) 为 `config.toml` 后修改。

支持的字段（`[organizer]`）：`downloads_folder`、`log_level`、`state_file`；
每个 `[[downloads]]`：`path`、`recursive`、`check_interval`、`max_checks`、`stable_checks`、
`conflict_policy`、`persist_processed`、`ignored_endings`、`rules`。
每条 `rules`：`category`、`extensions`、`name_pattern`、`target_dir`。
规则按顺序匹配，先命中先生效；无扩展名/无正则的规则作为兜底。

最小示例：

```toml
[organizer]
log_level = "INFO"

[[downloads]]
path = "D:/下载"
recursive = false
conflict_policy = "rename"   # rename | overwrite | skip

  [[downloads.rules]]
  category = "图片"
  extensions = [".jpg", ".jpeg", ".png", ".gif", ".webp"]

  [[downloads.rules]]
  category = "视频"
  extensions = [".mp4", ".mkv", ".avi"]

  [[downloads.rules]]
  category = "其他文件"
  extensions = []
```

> TOML 里 Windows 反斜杠需转义，建议路径用正斜杠（`"D:/资料"`）。

## 结构

```
download_organizer/
    __init__.py      # 公开 API + 版本
    __main__.py      # python -m download_organizer 入口
    config.py        # 配置模型 + TOML 加载 + 默认值
    rules.py         # 分类规则引擎
    organizer.py     # 核心逻辑：状态 / 冲突 / 完成判定 / 移动 / 监控
    cli.py           # 命令行入口
tests/               # pytest 测试
config.example.toml  # 配置示例
DownloadOrganizer.py # 薄启动器（便于从旧入口运行）
```

## 测试

```bash
python -m pytest tests
```

## 打包 / 发布（GitHub Actions 自动化）

推送到带版本号的标签（如 `v0.1.1`）会自动触发工作流 `.github/workflows/build.yml`：
用 PyInstaller 在 Windows 上打包成**单文件、无控制台窗口**的 `DownloadOrganizer.exe`，
随后自动发布为 GitHub Release。

```bash
git tag v0.1.1
git push origin v0.1.1
# Release 发布后可到仓库 Releases 页下载 DownloadOrganizer.exe
```

> 可视化查看构建：仓库页面 → Actions

## 说明

- 第三方依赖仅 `watchdog`；其余为 Python 标准库。
- 原 `.exe` 中的分类表、忽略后缀、下载完成判定已完整迁移并扩展为可配置项。
- 常驻监控默认把“等待下载完成”放到独立线程处理，不会因等待而阻塞事件监听。
