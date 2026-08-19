# notify-toggle-ui

## Why

程序在整理完成后会弹出桌面通知（托盘气泡，对应配置项 `notify_on_move`），但目前没有任何界面开关：系统托盘菜单与图形配置界面（`--gui`）都没有该选项，用户只能手工编辑 `config.toml`；更糟的是 GUI 保存配置时 `_write_toml` 不写回 `notify_on_move`，会静默删掉该行，导致通知在下次启动时"悄悄复活"。普通用户无法便捷地控制这个打扰性功能。

## What Changes

- 系统托盘菜单新增"通知"勾选开关：随时切换，即时生效，无需重启、无需改配置文件；
- 常驻模式下通知回调改为无条件注册，运行时开关（初始取自 `notify_on_move`）在每次发通知前检查，使开关"开/关"两个方向都可即时生效；
- `--gui` 配置界面新增"移动后显示桌面通知"复选框，并在保存时把 `notify_on_move` 写回 TOML（修复 GUI 保存丢失该设置的问题）。

## Capabilities

### New Capabilities
- `notifications`: 桌面通知的显示与开关控制——移动完成通知、托盘运行时开关、GUI 配置项持久化

### Modified Capabilities
<!-- 无：openspec/specs/ 目前为空目录，项目尚无既有行为契约 spec -->

## Impact

- `download_organizer/tray.py`：新增运行时通知开关（模块级标志 + 访问器），`notify()` 按开关门控；托盘菜单新增"通知"勾选项
- `download_organizer/cli.py`：常驻模式通知回调注册改为无条件注册 + 从配置初始化开关（抽出 `_register_move_notification` 辅助函数）
- `download_organizer/gui.py`：`_load_or_default` 加载 `notify_on_move`；UI 新增复选框；`_write_toml` 写回 `notify_on_move`
- 测试：`tests/test_tray.py`、`tests/test_gui.py` 扩展，新增 `tests/test_cli.py`
- 无新增依赖；配置格式不变（`notify_on_move` 字段已存在，`config.example.toml` L11 已文档化）
