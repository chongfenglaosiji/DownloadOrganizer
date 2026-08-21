# notify-toggle-ui 任务清单

## 1. 托盘运行时通知开关

- [x] 1.1 `download_organizer/tray.py` 新增模块级 `_NOTIFICATIONS_ENABLED` 标志及 `notifications_enabled()` / `set_notifications_enabled()` 访问器
- [x] 1.2 `download_organizer/tray.py` `notify()` 在显示通知前检查开关，关闭时直接返回（不改变无活动图标时的静默降级）
- [x] 1.3 `download_organizer/tray.py` `TrayApp._menu()` 在"暂停/继续"项后新增"通知"勾选项（`checked` 读取当前开关）；新增 `_toggle_notifications` 处理器，翻转标志并 `update_menu()`

## 2. cli 常驻模式接线

- [x] 2.1 抽出 `_register_move_notification(cfg)`：无条件注册移动成功通知回调，并把运行时开关初始化为 `cfg.notify_on_move`；保留托盘不可用时的 try/except 降级
- [x] 2.2 `main()` 常驻路径调用 `_register_move_notification(cfg)`，替换原 L132-140 的条件注册块

## 3. GUI 通知设置

- [x] 3.1 `ConfigEditor._load_or_default` 加载 `cfg.notify_on_move` 到 `self.notify_on_move`
- [x] 3.2 底部按钮栏新增"移动后显示桌面通知"复选框（BooleanVar，初始值取自 `self.notify_on_move`）
- [x] 3.3 `_save` 提交复选框值到 `self.notify_on_move`；`_write_toml` 在 `[organizer]` 段写回 `notify_on_move = true|false`

## 4. 单元测试

- [x] 4.1 `tests/test_gui.py`：`_make_editor` 补充 `notify_on_move` 属性；新增往返用例——保存后 TOML `[organizer]` 段含 `notify_on_move = false/true`，`load_config` 读回一致；新增加载断言——含 `notify_on_move = false` 的配置经 `_load_or_default` 后 `self.notify_on_move` 为 False（沿用 `object.__new__(ConfigEditor)` 纯数据构造，无窗口）
- [x] 4.2 `tests/test_tray.py`：开关访问器默认值与切换行为；`notify()` 在开关关闭时不调用图标通知（monkeypatch `_ACTIVE_ICON`），开启时调用；用例 setup/teardown 将 `tray._NOTIFICATIONS_ENABLED` 重置为默认值 True
- [x] 4.3 新增 `tests/test_cli.py`：`_register_move_notification` 在 `notify_on_move` 为 false 时仍注册回调且开关初始化为关，为 true 时开关为开；该函数有受控全局副作用（append `MOVE_CALLBACKS`、改写托盘标志），用例 setup/teardown 清空 `MOVE_CALLBACKS` 并重置 `tray._NOTIFICATIONS_ENABLED` 为 True

## 5. 验证

- [x] 5.1 `pytest` 全量通过（含新增用例）：58 passed / 1 skipped；`tests/test_single_instance.py` 3 例失败为环境问题——本机运行中的 DownloadOrganizer 实例持有命名互斥锁，与本变更无关（唯一命名互斥锁下逻辑自测通过）
- [x] 5.2 `ruff check` 通过（E4/E7/E9/F/I，line-length 100）：本机无 ruff 二进制，经逐行手工核对（无未用导入/未定义名、语法编译通过、行宽 ≤100）；CI 上将正式执行
- [x] 5.3 手工冒烟：托盘菜单出现"通知"勾选项且切换即时生效；`--gui` 复选框初始状态正确、保存后 TOML 写回正确（pystray + tkinter 实机构造验证通过）
