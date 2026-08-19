# 实施审查：notify-toggle-ui（托盘/GUI 通知开关）

## 轮次 1 — 评审方报告

**审查范围**：实现代码（download_organizer/tray.py、cli.py、gui.py）与已批准设计（design.md D1-D5，含设计审查处置后最终版）、specs/notifications/spec.md、tasks.md；新增测试（tests/test_tray.py、test_cli.py、test_gui.py）作为实现正确性验证手段
**审查依据**：对照 design.md D1-D5 逐项核对实现逻辑、边界条件、错误路径、状态转换与并发风险；运行 Developer 已交付的单元测试验证实现（不编写测试、不评估测试覆盖）；git log 核对 4 个实施 commit（45caba9 / e9f5db6 / bc0308d / 8aff3ad）；spec.md 最终版含轮次 2 #7 处置后"托盘/通知后端可用"限定
**审查结论**：**通过，可进入下一环节**（无 Critical/Major/Minor 阻塞项）

### 总体评价

实现与已批准设计高度一致：D1 模块级标志 + notify 门控、D2 无条件注册 + 开关初始化、D3 菜单勾选项复用既有模式、D4 GUI 加载/复选框/写回、D5 不写回配置文件，均按设计落实且边界处理完整（`--once`/`--gui` 不注册、getattr 防御、try/except 降级、托盘无图标静默降级、开关检查先于图标检查）。运行验证：test_tray.py（8 个）与 test_cli.py（3 个）全部通过，覆盖 D1/D2/D3 核心逻辑；test_gui.py 与 test_aria2.py 共 13 个用例因本沙箱禁止 python 进程创建 pytest tmp_path 目录（PermissionError WinError 5，环境限制）未能在此环境运行，但静态读码核对实现与测试逻辑一致（见"发现/备注"）。未发现实质问题。

### Design 决策逐项核对

| 决策 | 设计要求 | 实现位置 | 核对 |
|------|----------|----------|------|
| **D1** | tray.py 模块级 `_NOTIFICATIONS_ENABLED`（默认 True）+ `notifications_enabled()`/`set_notifications_enabled()` 访问器；`notify()` 发通知前检查开关，关闭直接返回；保留无活动图标静默降级 | tray.py L39、L42-50、L158-168 | ✅ `_NOTIFICATIONS_ENABLED = True`（L39）；两个访问器（L42-50，bool 强转 + global）；`notify()` 首行 `if not _NOTIFICATIONS_ENABLED: return`（L160），`_ACTIVE_ICON is None` 静默降级保留（L162-164） |
| **D2** | cli 常驻路径无条件注册回调 + `set_notifications_enabled(cfg.notify_on_move)` 初始化开关；抽出 `_register_move_notification(cfg)`；保留 try/except 降级 | cli.py L107-121、L151 | ✅ `_register_move_notification` 无条件 append 回调（L118-119）且初始化开关（L117，用 `getattr(cfg, "notify_on_move", True)` 保留防御）；`main()` L151 替换原条件注册块；`--gui`（L132-134）/`--once`（L136-137）提前返回不注册；try/except 包裹（L115-121） |
| **D3** | `_menu()` 在"暂停/继续"后插入"通知"勾选项（`checked` 读当前开关）；`_toggle_notifications` 翻转标志 + `update_menu()` | tray.py L107-111、L125-128 | ✅ `pystray.MenuItem("通知", self._toggle_notifications, checked=lambda item: notifications_enabled())` 位于暂停项后；`_toggle_notifications` 翻转 + `self._icon.update_menu()`，与 `_toggle_pause`（L119-123）模式一致 |
| **D4** | `_load_or_default` 加载 `notify_on_move`；底部按钮栏左侧新增复选框（BooleanVar 初始值取配置）；`_save` 提交值；`_write_toml` 在 `[organizer]` 段写回 | gui.py L49、L112-114、L290、L308 | ✅ `self.notify_on_move = bool(cfg.notify_on_move)`（L49）；`tk.BooleanVar(value=self.notify_on_move)` + `ttk.Checkbutton` 文案"移动后显示桌面通知"（L112-114）；`_save` 中 `self.notify_on_move = self.var_notify.get()`（L290）；`_write_toml` 写 `notify_on_move = true\|false`（L308），位于 `[organizer]` 段，与 config.py L204 读取位置一致 |
| **D5** | 托盘开关为运行时状态，不写回配置文件 | tray.py L47-50 | ✅ `set_notifications_enabled` 仅改模块级标志，无任何 TOML 写入；spec Requirement 2 已声明"托盘切换不写回配置文件" |

### 边界条件核对

| 边界 | 设计/规范要求 | 实现 | 核对 |
|------|-------------|------|------|
| `--once` / `--gui` 模式 | 不注册通知回调（spec Requirement 1：`--once` 不显示移动通知） | cli.py L132-137 提前返回 | ✅ 两分支均不触达 `_register_move_notification` |
| `notify_on_move=false` 启动 | 开关初始为关，托盘项未勾选，用户仍可运行时开启（开关双向即时生效） | cli.py L117 初始化开关；tray.py L160 notify 门控；菜单 checked 读实时标志 | ✅ 开关为关时 notify 直接返回；托盘勾选可翻转（D3） |
| 配置缺失/无配置路径 | 走默认值 True（spec：`notify_on_move` 默认 true） | gui.py L49 `bool(cfg.notify_on_move)`，config.py L204 默认 True | ✅ 缺失时 cfg.notify_on_move=True → 复选框初始勾选、开关初始开 |
| 非法类型配置值（字符串 "false"） | 沿用既有 config.py bool() 强转语义，不在本变更范围（design Risks 记录） | 未触碰 config.py；gui.py L49 二次 bool() 无害 | ✅ 与设计一致 |
| 托盘不可用/无显示环境 | 静默降级（spec Requirement 1：托盘/通知后端不可用时静默降级） | tray.py notify 无图标静默返回；cli.py try/except | ✅ 行为与 spec 最终版一致 |
| GUI 保存时序（无选中目录） | 复选框值仍须提交（`_commit_detail` 提前 return 不影响） | gui.py L288-290：`_commit_detail()` 后独立执行 `self.notify_on_move = self.var_notify.get()` | ✅ 顺序正确，`_current_index() is None` 不影响复选框提交 |
| 并发：托盘线程切换 vs worker 线程发通知 | 无数据竞争（GIL 布尔原子）；不运行时增删回调 | 开关仅布尔读写；`_register_move_notification` 在 `main()` 中、`_run_resident`/worker 启动前注册（cli.py L151 → L154） | ✅ 注册先于监控启动，规避回调列表运行时增删竞态 |
| 单实例获取失败 | 不注册回调、直接退出 | cli.py L140-147 return 1 在 L151 之前 | ✅ 时序正确 |
| 通知开关关闭且无图标 | 关闭时直接返回（开关检查先于图标检查） | tray.py L160 先查开关，L162 再查图标 | ✅ 与 D1"发通知前检查开关"一致 |

### 发现/备注

- **测试运行结果**：`pytest tests/test_tray.py tests/test_cli.py tests/test_gui.py tests/test_config.py tests/test_rules.py tests/test_aria2.py` → **21 passed / 13 errors**。errors 全部为 pytest tmp_path fixture 目录创建/扫描被本沙箱拦截（PermissionError WinError 5：系统 Temp 的 `pytest-of-Administrator` 与工作区内 basetemp 均被拒），属环境限制、与实现无关：test_gui.py（6 个）与 test_aria2.py（7 个）均依赖 tmp_path。**test_tray.py（8 个）与 test_cli.py（3 个）全部通过**，实证了 D1 开关访问器/notify 门控/`_toggle_notifications` 与 D2 `_register_move_notification`（false 仍注册且开关关、true 开关开、缺属性默认开）及全局状态清理（autouse fixture 重置 `_NOTIFICATIONS_ENABLED`、清空 `MOVE_CALLBACKS`）。
- **test_gui.py 未能在此环境运行**：静态读码核对实现与测试一致——`_make_editor` 已补 `notify_on_move` 属性（test_gui.py L9-13）；`_write_toml` 写回断言（L68-84）与实现 L308 匹配；`_load_or_default` 加载断言（L87-104）与实现 L49 匹配。D4 的运行时实证留待阶段 5 Tester / CI（本机 test_single_instance 3 用例失败亦为环境事实，与本变更无关）。
- **实施 commit 核对**：45caba9（tray 运行时开关）/ e9f5db6（cli 接线）/ bc0308d（gui 写回）/ 8aff3ad（tasks 勾选）均在分支上，tasks.md 1-5 全部勾选，与 Developer 报告一致。
- **docstring 与注释一致性**：tray.py L4 菜单说明已更新为含"通知"；tray.py L38/L158 注释正确描述运行时开关语义；cli.py L107-114 docstring 准确说明副作用受控与降级语义；未发现实现与注释矛盾。
- **无过度实现**：未引入新依赖、新抽象或设计外功能；`getattr` 防御（cli.py L117）为轮次 1 补充说明建议，合理保留。
