# notify-toggle-ui 任务清单

## 1. 托盘运行时通知开关

- [ ] 1.1 `download_organizer/tray.py` 新增模块级 `_NOTIFICATIONS_ENABLED` 标志及 `notifications_enabled()` / `set_notifications_enabled()` 访问器
- [ ] 1.2 `download_organizer/tray.py` `notify()` 在显示通知前检查开关，关闭时直接返回（不改变无活动图标时的静默降级）
- [ ] 1.3 `download_organizer/tray.py` `TrayApp._menu()` 在"暂停/继续"项后新增"通知"勾选项（`checked` 读取当前开关）；新增 `_toggle_notifications` 处理器，翻转标志并 `update_menu()`

## 2. cli 常驻模式接线

- [ ] 2.1 抽出 `_register_move_notification(cfg)`：无条件注册移动成功通知回调，并把运行时开关初始化为 `cfg.notify_on_move`；保留托盘不可用时的 try/except 降级
- [ ] 2.2 `main()` 常驻路径调用 `_register_move_notification(cfg)`，替换原 L132-140 的条件注册块

## 3. GUI 通知设置

- [ ] 3.1 `ConfigEditor._load_or_default` 加载 `cfg.notify_on_move` 到 `self.notify_on_move`
- [ ] 3.2 底部按钮栏新增"移动后显示桌面通知"复选框（BooleanVar，初始值取自 `self.notify_on_move`）
- [ ] 3.3 `_save` 提交复选框值到 `self.notify_on_move`；`_write_toml` 在 `[organizer]` 段写回 `notify_on_move = true|false`

## 4. 单元测试

- [ ] 4.1 `tests/test_gui.py`：`_make_editor` 补充 `notify_on_move` 属性；新增往返用例——保存后 TOML `[organizer]` 段含 `notify_on_move = false/true`，`load_config` 读回一致
- [ ] 4.2 `tests/test_tray.py`：开关访问器默认值与切换行为；`notify()` 在开关关闭时不调用图标通知（monkeypatch `_ACTIVE_ICON`），开启时调用
- [ ] 4.3 新增 `tests/test_cli.py`：`_register_move_notification` 在 `notify_on_move` 为 false 时仍注册回调且开关初始化为关，为 true 时开关为开（用例间清理 `MOVE_CALLBACKS` 全局状态）

## 5. 验证

- [ ] 5.1 `pytest` 全量通过（含新增用例）
- [ ] 5.2 `ruff check` 通过（E4/E7/E9/F/I，line-length 100）
- [ ] 5.3 手工冒烟：托盘菜单出现"通知"勾选项且切换即时生效；`--gui` 复选框初始状态正确、保存后 TOML 写回正确
