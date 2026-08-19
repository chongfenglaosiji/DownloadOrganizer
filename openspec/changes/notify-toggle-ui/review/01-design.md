# 设计审查：notify-toggle-ui（托盘/GUI 通知开关）

## 轮次 1 — 评审方报告

**审查范围**：proposal.md / specs/notifications/spec.md / design.md / tasks.md
**审查依据**：Issue #1 验收条件（.dsh/issue-notify-toggle.md，`gh issue view 1` 对照）、当前代码状态（download_organizer/config.py、cli.py、tray.py、gui.py、organizer.py）、tests/ 现状、pyproject.toml（pytest+coverage、ruff E4/E7/E9/F/I、line-length 100）、openspec/config.yaml
**审查结论**：**不通过，修改后提交复审**（存在 1 个 Major；按流程门禁 Critical/Major=0，处置后须复审）

### 总体评价

方案整体质量高：D1 运行时开关（模块级标志 + 发通知前检查）准确覆盖 Issue 期望 3 的备选方案之一，D2 无条件注册回调解决了"启动时配置已关 → 托盘无法重新开启"的需求死角，D4 修复 GUI 保存丢失 `notify_on_move` 的根因，D5 取舍显式记录且与 Issue 语义一致；tasks 与 design 逐项映射、顺序合理、可验证。主要问题集中在 delta spec 的行为契约准确性：Requirement 1 未限定"常驻模式"，与 `--once` 保持不通知的设计决策及现状实现直接矛盾（Major）；另有 5 个 Minor 涉及契约语义补全、测试全局状态隔离与边界说明。

### [Major] #1 spec Requirement 1 未限定常驻模式，与 --once 不通知的行为矛盾

- **位置**：`specs/notifications/spec.md` Requirement 1 主句及 Scenario 1/2（L3-13）
- **问题描述**：Requirement 1 主句声称"系统 SHALL 在每次成功移动文件后显示桌面通知"，Scenario 1/2 同样未限定运行模式；但 design.md Non-Goals 明确"--once 单次整理模式保持不通知（现状不变）"，且 cli.py L119-120 的 `--once` 分支提前返回、从不注册通知回调。`--once` 模式下移动成功不会显示通知，直接违反该 Requirement。同一 Requirement 内部 Scenario 3 却限定"以常驻模式启动"，口径自相矛盾。
- **依据**：spec.md L3-13（Requirement 1 主句"每次成功移动文件后显示桌面通知"、Scenario 1/2 无模式限定）；design.md L28（"--once 单次整理模式保持不通知（现状不变）"）；cli.py L119-120（`--once` 提前返回）、L132-140（仅常驻路径注册回调）
- **影响**：行为契约（spec）与已批准设计及现状实现不一致。本项目首个 spec，错误契约会误导后续开发与验收判定——按 spec 验收 `--once` 场景必然失败。
- **建议**：Requirement 1 主句与 Scenario 1/2 增加"常驻模式"限定（如"系统 SHALL 在常驻模式下每次成功移动文件后显示桌面通知"），与 design Non-Goals 对齐；修订后重新 `openspec validate`。

### [Minor] #2 spec 未定义托盘开关"重启后回到配置值"的用户可见语义

- **位置**：`specs/notifications/spec.md` Requirement 2（L19-33）；design.md D5（L56-59）
- **问题描述**：D5 明确托盘开关为运行时状态、不写回配置，重启后回到配置值；但 Requirement 2 仅描述"切换即时生效、无需重启/改配置文件"，未定义重启后的开关状态——用户可观察行为（托盘关闭后重启通知恢复）在契约层缺失。
- **依据**：design.md D5 L56-59（"托盘关闭后重启程序会回到配置值"）；spec.md Requirement 2 L19-21
- **影响**：契约不完整；用户可能预期托盘关闭状态持久化而实际重启后恢复，产生困惑；后续维护无契约依据。
- **建议**：Requirement 2 增补一句运行时状态语义（如"该开关为运行时状态，程序重启后以配置项 notify_on_move 重置"）。

### [Minor] #3 tasks 4.2/4.3 全局状态清理不完整（tray 标志未含）

- **位置**：`tasks.md` 4.2（L23）、4.3（L24）
- **问题描述**：4.3 仅要求"用例间清理 MOVE_CALLBACKS 全局状态"；4.2 未提及任何清理。D1 新增的 tray 模块级 `_NOTIFICATIONS_ENABLED` 同样是跨用例全局状态：4.2 的切换用例与 4.3 的初始化用例都会改写它，未重置会导致用例间污染（后续用例依赖前序用例留下的开关状态而误通过/误失败）。
- **依据**：tasks.md L23-24；design.md D1 L34-36（模块级标志 + 访问器）
- **影响**：测试隔离性不足，可能出现顺序依赖的 flaky 或误判，削弱"行为契约可单测"的 Goal。
- **建议**：tasks 4.2/4.3 明确在 setup/teardown 中将 `tray._NOTIFICATIONS_ENABLED` 重置为默认值 True，并清空 `MOVE_CALLBACKS`。

### [Minor] #4 design D2"纯函数式"表述与实现不符

- **位置**：`design.md` D2（L41）
- **问题描述**：D2 称 `_register_move_notification(cfg)` 为"纯函数式、可单测"；但该函数会向模块级 `MOVE_CALLBACKS` append 回调并调用 `tray.set_notifications_enabled()` 改写全局标志，产生副作用，并非纯函数。
- **依据**：design.md L41（"纯函数式、可单测"）；cli.py L134-140 现状（append 到 MOVE_CALLBACKS）；design.md D1 L34（`set_notifications_enabled` 改模块级标志）
- **影响**：表述误导实现与测试预期——测试必须处理其全局副作用（见 #3），按"纯函数"假设编写的测试会踩污染坑。
- **建议**：改为"无外部 IO、副作用受控、可单测的辅助函数"，并在 tasks 4.3 说明其全局副作用需清理。

### [Minor] #5 tasks 4.1 未覆盖 `_load_or_default` 对 notify_on_move=false 的加载断言

- **位置**：`tasks.md` 4.1（L22）
- **问题描述**：spec Requirement 3 Scenario 3 要求"配置中已关闭时界面初始为未勾选"，对应实现是 `_load_or_default` 读 false → `self.notify_on_move = False`。tasks 4.1 仅覆盖保存写回往返（TOML 含 `notify_on_move` + `load_config` 读回一致），未包含加载初始状态断言；该 Scenario 只剩手工冒烟（5.3）兜底。
- **依据**：spec.md L47-49（Scenario 3）；design.md D4 L51（`self.notify_on_move = bool(cfg.notify_on_move)`）；tasks.md L22
- **影响**：契约场景缺自动测试覆盖；GUI 层已被 coverage omit（pyproject.toml L29），若无数据层断言该行为完全依赖手工验证。
- **建议**：tasks 4.1 补充"含 notify_on_move=false 的配置经 `_load_or_default` 后 `self.notify_on_move` 为 False"断言（无窗口可测，沿用 `object.__new__(ConfigEditor)` 模式）。

### [Minor] #6 配置文件非法值边界未说明（既有 bool() 强转陷阱）

- **位置**：`design.md` Context（L7）与 Risks / Trade-offs（L61-67）
- **问题描述**：config.py L204 用 `bool(top.get("notify_on_move", True))` 读取；若用户手工编辑写入字符串 `notify_on_move = "false"`，`bool("false")` 为 True，启动时开关为开，与"配置 false → 初始关"的预期相反。本变更不触碰 config.py（GUI 写回布尔字面量不会触发），但设计未说明该既有语义，边界场景（非法类型配置值）无文档覆盖。
- **依据**：config.py L204；spec.md Requirement 1 L5（"配置项 notify_on_move（默认 true）决定……初始状态"）
- **影响**：手工配置非法类型时行为与直觉相反；契约未定义非法值行为，验收时可能产生争议。
- **建议**：在 design.md Risks 注明"非法类型沿用既有 config.py bool() 强转语义，不属本变更范围"，或显式列为 Non-Goal。

### 补充说明

- **D5 裁决（Architect 结论：接受）**：对照 Issue 期望 1 原文"可随时开关右下角弹窗，**无需重启、无需改配置文件**"——该句描述托盘开关的运行时操作性（即时生效、不触碰配置文件），并不要求状态持久化；持久化路径由 GUI 复选框承担（期望 2），与设计职责划分一致。托盘线程并发写 TOML 会与 GUI 保存/手工编辑互相覆盖，风险真实存在，不持久化是最小且安全的实现。取舍已显式记录于 D5 与 Non-Goals，符合契约语义。唯一遗留为 #2（契约层未写明重启语义），按 Minor 处置即可。
- **新 capability 命名 notifications 合理**：与既有 `notify()`、`notify_on_move` 命名一致；涵盖"移动完成通知显示 + 托盘运行时开关 + GUI 配置项持久化"三个行为面，粒度适合作为该能力域首个契约。`openspec/specs/` 原为空目录，本项目首次建立 spec，命名无历史包袱，予以确认。
- **tasks 4.3 新增 tests/test_cli.py 可行性（确认可行）**：cli.py 顶层仅常量与 import，无副作用，可安全导入；`_register_move_notification` 内延迟导入 tray（tray.py 在 pystray 缺失时仍可导入，`_HAVE_TRAY=False`），可断言"false 时仍注册回调且开关为关 / true 时开关为开"；需注意全局状态清理（见 #3）。coverage omit 含 gui.py/tray.py（pyproject.toml L29），但 cli.py 在覆盖范围内，`_register_move_notification` 计入覆盖率，不影响覆盖率门槛。
- **过度设计检查**：无新增依赖/抽象/基础设施；D1 否决动态增删 `MOVE_CALLBACKS` 的方案理由充分（内联 lambda 需稳定引用、worker 线程迭代回调列表有竞态、"启动时配置已关 → 回调未注册 → 托盘无法重新开启"不满足需求），模块级布尔标志 + 发通知前检查是最小实现，且与 Issue 期望 3 的备选方案之一完全一致。
- **契约一致性**：spec 三个 Requirement ↔ design D1-D4 ↔ tasks 1-3 逐项对应；每个 spec Requirement 均有对应设计决策与 task 落点；唯一不一致为 #1（--once 模式）。
- **依赖合理性**：无新增依赖（proposal Impact 已声明，与 design Context 约束核对一致）。
- **GUI 保存与运行中托盘的同步（记录备查，非缺陷）**：源码模式下 GUI 与托盘同进程不同线程，保存只写 TOML、不更新运行时开关，与既有"重启后生效"提示（gui.py L292）及 spec Scenario"重新加载配置后"措辞一致。
- **getattr 防御（实现细节提示）**：现状 cli.py L134 用 `getattr(cfg, "notify_on_move", True)`；`_register_move_notification(cfg)` 建议保留该防御写法，避免旧/测试 cfg 对象缺属性时抛 AttributeError。

### 处置建议

1. **#1（Major）**：修订 `specs/notifications/spec.md` Requirement 1 主句与 Scenario 1/2，加"常驻模式"限定，与 design.md Non-Goals 对齐；重新 `openspec validate`。
2. **#2（Minor）**：`spec.md` Requirement 2 增补"运行时状态、重启后以 notify_on_move 重置"语义。
3. **#3（Minor）**：`tasks.md` 4.2/4.3 补充 `tray._NOTIFICATIONS_ENABLED` 重置与 `MOVE_CALLBACKS` 清理。
4. **#4（Minor）**：`design.md` D2 措辞修正（非纯函数，改为副作用受控）。
5. **#5（Minor）**：`tasks.md` 4.1 补充 `_load_or_default` 加载断言。
6. **#6（Minor）**：`design.md` Risks 注明非法值既有语义。

---

## 轮次 1 — 实施方处置

- **#1（Major）接受，已修复**：`specs/notifications/spec.md` Requirement 1 主句改为"系统 SHALL 在常驻模式下每次成功移动文件后显示桌面通知"，并显式声明"`--once` 单次整理模式不显示移动通知"；Scenario 1/2 补"常驻模式"限定，与 design.md Non-Goals（"--once 单次整理模式保持不通知（现状不变）"）及 cli.py L119-120 现状对齐。`openspec validate notify-toggle-ui` 通过。
- **#2（Minor）接受，已修复**：Requirement 2 主句增补"该开关为运行时状态，程序重启后 SHALL 以配置项 `notify_on_move` 重置（托盘切换不写回配置文件）"，并新增 Scenario"重启后开关恢复为配置值"，在契约层补全 D5 取舍对应的用户可见行为。
- **#3（Minor）接受，已修复**：tasks 4.2 补"用例 setup/teardown 将 `tray._NOTIFICATIONS_ENABLED` 重置为默认值 True"；tasks 4.3 补"setup/teardown 清空 `MOVE_CALLBACKS` 并重置 `tray._NOTIFICATIONS_ENABLED` 为 True"，消除跨用例全局状态污染。
- **#4（Minor）接受，已修复**：design.md D2 措辞由"纯函数式、可单测"改为"无外部 IO、副作用受控、可单测"，并注明副作用（向 `MOVE_CALLBACKS` 追加回调、经 `set_notifications_enabled` 改写托盘全局标志）；tasks 4.3 相应说明其全局副作用与清理要求。
- **#5（Minor）接受，已修复**：tasks 4.1 补充加载断言——"含 `notify_on_move = false` 的配置经 `_load_or_default` 后 `self.notify_on_move` 为 False（沿用 `object.__new__(ConfigEditor)` 纯数据构造）"，覆盖 spec Requirement 3 Scenario 3。
- **#6（Minor）接受，已修复**：design.md Risks 增补"配置文件非法类型值（如 `notify_on_move = "false"` 字符串）"项，说明沿用既有 config.py L204 `bool()` 强转语义、本变更不触碰 config.py、属既有行为不在本变更范围。

验证：`openspec validate notify-toggle-ui` → valid（4/4 artifacts complete）。
