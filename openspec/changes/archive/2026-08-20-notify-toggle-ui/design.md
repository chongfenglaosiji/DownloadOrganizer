# notify-toggle-ui 设计

## Context

背景与现状（依据为当前分支代码）：

- `config.py` L75 定义 `Config.notify_on_move: bool = True`；L204 从 TOML `[organizer]` 段读取（`top.get("notify_on_move", True)`）。
- `cli.py` L132-140：常驻模式下**仅当** `cfg.notify_on_move` 为 True 时向 `MOVE_CALLBACKS` 追加通知回调（`lambda src, dst: tray.notify(...)`）；`--gui`（L115-117）与 `--once`（L119-120）分支提前返回，不注册回调。
- `organizer.py` L31：`MOVE_CALLBACKS` 为模块级列表；L425-429：`move_file` 成功后遍历调用回调，回调异常不阻塞移动。
- `tray.py` L85-97：托盘菜单无通知项（现有：暂停/继续、立即整理一次、打开配置、打开日志目录、退出）；L99-104 `_toggle_pause` 是既有"勾选式切换 + `icon.update_menu()`"模式；L133-141 `notify()` 在 `_ACTIVE_ICON is None` 时静默降级。
- `gui.py` L47-82 `_load_or_default` 不加载顶层 `notify_on_move`；L294-328 `_write_toml` 的 `[organizer]` 段仅写 `log_level`——这是"GUI 保存后 `notify_on_move` 行被删、通知悄悄复活"的根因（Issue「现状」第 2 点）。
- `config.example.toml` L11 已文档化 `notify_on_move`；`openspec/specs/` 为空，本变更首次建立行为契约 spec。
- 约束：Python>=3.11；GUI 用 tkinter 标准库；依赖 watchdog/pystray/Pillow；coverage 排除 `gui.py`/`tray.py`（pyproject.toml L29）；ruff select E4/E7/E9/F/I、line-length 100。

## Goals / Non-Goals

**Goals:**
- 托盘菜单提供"通知"勾选开关，运行时即时生效（开/关双向），无需重启、无需编辑配置文件；
- GUI 提供"移动后显示桌面通知"复选框并写回 `notify_on_move`，修复保存丢失；
- 通知开关状态语义单一：启动时以 `notify_on_move` 初始化运行时开关，通知显示统一由该开关门控（开关在通知链路上只有一处判定）；
- 行为契约可单测（不依赖真实托盘/显示环境）。

**Non-Goals:**
- 托盘开关不持久化到 config.toml（持久化路径为 GUI 复选框 / 手工编辑）；重启后回到配置值；
- 不改变 `notify_on_move` 的配置格式、默认值，不改 `config.example.toml` 已有文档；
- 不新增通知策略（如通知队列、去重、跨会话记忆开关状态）；
- 不修 GUI 其它既有保存行为（如 `log_level` 硬编码 `"INFO"`、整文件重写丢弃手工注释）；
- `--once` 单次整理模式保持不通知（现状不变）。

## Decisions

### D1 运行时开关：模块级标志 + 发通知前检查（而非动态增删回调）

- `tray.py` 新增模块级 `_NOTIFICATIONS_ENABLED`（默认 `True`）及访问器 `notifications_enabled()` / `set_notifications_enabled()`；`notify()` 在弹通知前检查该标志，关闭时直接返回（保留无活动图标时静默降级的既有行为）。
- 备选：托盘切换时动态 `MOVE_CALLBACKS.remove/append`。否决理由：回调是 cli.py 内联创建的 lambda，移除需持有稳定引用；`organizer.move_file`（L425-429）在 worker 线程中迭代回调列表，运行时增删有竞态；且"启动时配置已关 → 回调未注册 → 托盘无法重新开启"不满足需求。
- 布尔标志读写为解释器级原子操作（GIL），跨线程无需加锁。

### D2 cli 常驻模式：无条件注册回调，开关从配置初始化

- `cli.py` 常驻路径改为**无条件**注册通知回调，并调用 `tray.set_notifications_enabled(cfg.notify_on_move)` 把运行时开关初始化为配置值。
- 抽出 `_register_move_notification(cfg)` 辅助函数（cli.py 内，无外部 IO、副作用受控、可单测；副作用为向 `MOVE_CALLBACKS` 追加回调与经 `set_notifications_enabled` 改写托盘全局标志），`main()` 用它替换 L132-140 的条件注册块；保留 try/except 降级（托盘不可用时静默不注册，与现状一致）。
- 效果：`notify_on_move=false` 启动时开关为关、托盘项未勾选，用户仍可在运行时勾选开启——开关双向即时生效。

### D3 托盘菜单项复用既有勾选切换模式

- `TrayApp._menu()` 在"暂停/继续"项后插入 `pystray.MenuItem("通知", self._toggle_notifications, checked=lambda item: notifications_enabled())`；
- `_toggle_notifications` 翻转标志后调用 `self._icon.update_menu()` 刷新勾选态（与 `_toggle_pause` L99-104 完全一致）。

### D4 GUI：加载 → 复选框 → 写回

- `ConfigEditor._load_or_default` 增加 `self.notify_on_move = bool(cfg.notify_on_move)`；
- 底部按钮栏左侧新增 `ttk.Checkbutton`（BooleanVar），文案"移动后显示桌面通知"，初始值取自 `self.notify_on_move`；
- `_save` 时把复选框值提交到 `self.notify_on_move`；`_write_toml` 在 `[organizer]` 段追加 `notify_on_move = true|false`（与 config.py L204 读取位置一致）。
- 注意：现有 `tests/test_gui.py` 用 `object.__new__(ConfigEditor)` 构造纯数据测试对象，需在 `_make_editor` 中补 `notify_on_move` 属性，并新增往返断言。

### D5 托盘开关为运行时状态，不写回配置文件

- 理由：Issue 期望 1 明确"无需重启、无需改配置文件"（即时的运行时控制）；持久化路径由 GUI 复选框承担。托盘线程并发写 TOML 会与 GUI 保存/手工编辑互相覆盖，超出本次范围。
- 取舍：托盘关闭后重启程序会回到配置值（`notify_on_move=true` 时通知恢复）。该取舍显式记录于此，供 Architect 审查。

## Risks / Trade-offs

- [托盘开关不持久化：重启后回到配置值] → 作为显式决策（D5）与非目标记录；若评审认为应持久化，走设计变更补充托盘侧 TOML 写回。
- [pystray 勾选状态刷新依赖 `update_menu()`] → 复用 `_toggle_pause` 既有模式；`checked` 回调每次渲染时读取当前标志，即便漏调 `update_menu()`，下次打开菜单也会显示最新状态。
- [`_write_toml` 整文件重写覆盖手工注释] → 既有行为（gui.py L298 注释即声明"由 GUI 生成"），本次不改变；只保证 `notify_on_move` 不再被静默丢弃。
- [无托盘/无显示环境降级] → 保持既有降级链：托盘不可用则不注册回调（D2 保留 try/except）；GUI 无显示环境返回非零（gui.py L334-343 不变）。
- [布尔标志跨线程可见性] → 解释器级布尔读写原子且即时可见（GIL），无数据竞争。
- [配置文件非法类型值（如 `notify_on_move = "false"` 字符串）] → 沿用既有 config.py L204 `bool()` 强转语义（`bool("false")` 为 True，与直觉相反）；本变更不触碰 config.py、GUI 写回布尔字面量不会触发该分支，属既有行为，不在本变更范围（与 spec 中"配置项 `notify_on_move` 决定初始状态"的契约在合法布尔值范围内成立）。

## Migration Plan

- 无数据迁移：`notify_on_move` 字段、TOML 读取路径均已存在；
- 回滚：撤销 tray.py / cli.py / gui.py 改动与对应测试即可恢复原行为，配置格式无变化；
- 部署：随既有打包流程（PyInstaller）发布，无新增依赖。

## Open Questions

- 无阻塞问题。唯一待裁决项：托盘开关是否应持久化跨重启（按 D5 暂不持久化，理由见上）——请 Architect 在阶段 2 审查中裁决。
