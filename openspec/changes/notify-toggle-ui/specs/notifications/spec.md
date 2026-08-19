## ADDED Requirements

### Requirement: 移动完成时显示桌面通知

系统 SHALL 在每次成功移动文件后显示桌面通知（托盘气泡）；通知显示与否受通知开关控制，配置项 `notify_on_move`（默认 `true`）决定程序启动时通知开关的初始状态。

#### Scenario: 通知开启时移动成功显示通知
- **WHEN** 通知开关为开，且一个文件被成功移动
- **THEN** 系统显示包含文件名的桌面通知

#### Scenario: 通知关闭时移动成功不显示通知
- **WHEN** 通知开关为关，且一个文件被成功移动
- **THEN** 系统不显示桌面通知

#### Scenario: 配置关闭时启动默认不通知
- **WHEN** 配置中 `notify_on_move = false` 且程序以常驻模式启动
- **THEN** 通知开关初始为关，移动成功时不显示桌面通知

### Requirement: 托盘通知开关

系统 SHALL 在系统托盘菜单提供"通知"勾选开关，用户可随时切换通知开关状态；切换 SHALL 即时生效，无需重启程序、无需编辑配置文件。托盘菜单中该勾选项的状态 SHALL 反映当前运行时开关状态，并 SHALL 在启动时以配置项 `notify_on_move` 初始化。

#### Scenario: 通过托盘关闭通知
- **WHEN** 通知开关为开，用户点击托盘菜单中的"通知"项使其变为未勾选
- **THEN** 通知开关立即变为关，此后移动成功不再显示桌面通知

#### Scenario: 通过托盘重新开启通知
- **WHEN** 通知开关为关，用户点击托盘菜单中的"通知"项使其变为勾选
- **THEN** 通知开关立即变为开，此后移动成功恢复显示桌面通知

#### Scenario: 配置关闭时托盘开关初始为未勾选
- **WHEN** 配置中 `notify_on_move = false` 且程序以常驻模式启动
- **THEN** 托盘菜单"通知"项初始为未勾选状态，用户勾选后可即时开启通知

### Requirement: 图形界面通知设置

图形配置界面（`--gui`）SHALL 提供"移动后显示桌面通知"复选框，其初始状态 SHALL 取自当前配置的 `notify_on_move`；保存配置时 SHALL 把 `notify_on_move` 写回 TOML 文件的 `[organizer]` 段，保存后该设置不得丢失。

#### Scenario: 关闭通知并保存
- **WHEN** 用户在图形配置界面取消勾选"移动后显示桌面通知"并保存
- **THEN** 配置文件 `[organizer]` 段写入 `notify_on_move = false`，重新加载配置后通知开关为关

#### Scenario: 开启通知并保存
- **WHEN** 用户在图形配置界面勾选"移动后显示桌面通知"并保存
- **THEN** 配置文件 `[organizer]` 段写入 `notify_on_move = true`，重新加载配置后通知开关为开

#### Scenario: 配置中已关闭时界面初始为未勾选
- **WHEN** 配置文件中 `notify_on_move = false` 且用户打开图形配置界面
- **THEN** "移动后显示桌面通知"复选框初始为未勾选状态
