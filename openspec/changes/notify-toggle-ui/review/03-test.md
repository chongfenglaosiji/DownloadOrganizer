# 测试审查：notify-toggle-ui（托盘/GUI 通知开关）

## 轮次 1 — 评审方报告

**审查范围**：Developer 交付的单元测试（tests/test_tray.py、test_cli.py、test_gui.py）与生产实现（tray.py / cli.py / gui.py）；对照 spec `specs/notifications/spec.md`（R1-R3 共 10 个 Scenario）与 design.md D1-D5、tasks.md 4.x
**审查依据**：Issue #1 验收条件（.dsh/issue-notify-toggle.md）；实际运行 `py -3.14 -m pytest` 输出（本沙箱受 tmp_path 拦截，采用临时插件 + 工作区 basetemp 验证，见"已知约束"）
**审查结论**：**通过，可进入下一环节**（测试就绪，未发现生产/测试缺陷；仅环境性失败与本变更无关，见"已知约束"）

### 测试结果报告

#### 汇总

- **总计**: 73 | **通过**: 69 | **失败**: 3 | **跳过**: 1
- 受影响测试（本变更范围）: **29 通过**（test_tray 10 / test_cli 5 / test_gui 9 / test_integration_notify 5）
- 单元/模块测试: 24 通过（tray / cli / gui 数据层）
- 集成测试: 5 通过（`tests/test_integration_notify.py`，跨模块移动→通知链路）
- 质量门禁: ruff ✗（本机无二进制且沙箱禁止安装，待 CI 正式执行）；compileall ✓；行宽 ≤100 ✓；未用导入/未定义名手工核对 ✓

#### 单元测试审查（Developer 交付）

##### 覆盖缺口

| 缺口 | 等级 | 说明 | 处置 |
|------|------|------|------|
| spec R1 S1/S2 无全链路测试（move_file → MOVE_CALLBACKS → notify 门控 → 图标通知） | Major | Developer 单测只覆盖 notify 单点门控与回调注册，未验证"一个文件被成功移动后"的完整通知链及通知内容含文件名——spec 核心场景缺行为级证明 | 已补 `tests/test_integration_notify.py`（5 用例，假图标记录可观察调用） |
| cli 降级路径（托盘/后端不可用时静默不注册） | Minor | 只测正常注册，未测 `_register_move_notification` try/except 吞异常分支 | 已补 `test_register_notification_degrades_silently_when_tray_fails` |
| spec R1 主句 `--once` 单次模式不显示移动通知 | Minor | 无自动测试 | 已补 `test_once_mode_registers_no_move_notification` |
| spec R3 S1/S2 "保存"契约只测到 `_write_toml` 直写，绕过 `_save` 的 var_notify 提交桥 | Minor | 若 `_save` 忘记提交复选框值，现有测试无法发现 | 已补 `test_save_commits_checkbox_value_to_toml`（参数化关/开两方向，模型初值故意与复选框相反以验证桥生效） |
| notify 图标异常吞掉 / toggle 无图标不崩 / 双向切换 | Minor | 错误路径与边界未覆盖 | 已补 `test_notify_icon_exception_swallowed`、`test_toggle_notifications_both_directions_without_icon` |

##### 弱断言 / 假通过

| 测试 | 问题 | 处置 |
|------|------|------|
| test_cli.py 三个注册用例（`len(MOVE_CALLBACKS) == 1`） | 仅断言"注册发生"，不证明回调实际触发 notify——单独看有弱化嫌疑 | 非假通过：注册行为本身绑定 D2 契约；回调行为已由集成测试补证（`test_move_with_notifications_on_notifies_filename` 等） |
| test_tray.py `test_notify_enabled_calls_icon`（断言 `icon.notify` 收到 `("消息", "标题")`） | 绑定 pystray `notify(message, title)` 实参顺序 | 属可观察交付（通知携带标题与消息），保留；arg 顺序为 pystray API 既定签名，不构成镜像实现风险 |
| 未发现弱化断言 / 假通过 / 测试自证实现的用例 | — | — |

##### 优化/重写

- 无重写需求；Developer 测试整体绑定可观察行为（图标调用、TOML 内容、`load_config` 读回、开关标志），autouse fixture 对 `_NOTIFICATIONS_ENABLED`/`MOVE_CALLBACKS` 的全局状态清理正确（对应设计审查 #3 处置）。
- 按 testing 方法论对新增断言做了变异自检：删 notify 门控 → 集成测试 S2 失败；删 `_save` 提交行 → GUI 参数化用例失败；回调改条件注册 → `test_config_off_start_then_tray_enable` 失败；均能抓住。

#### 新增/变更测试清单

| 测试文件 | 新增测试 | 覆盖场景 |
|----------|----------|----------|
| tests/test_tray.py | test_toggle_notifications_both_directions_without_icon | R2 S1/S2 双向切换、无图标不崩（边界） |
| tests/test_tray.py | test_notify_icon_exception_swallowed | 通知后端异常静默降级（错误路径） |
| tests/test_cli.py | test_register_notification_degrades_silently_when_tray_fails | D2 托盘不可用静默不注册（错误路径） |
| tests/test_cli.py | test_once_mode_registers_no_move_notification | R1 主句 `--once` 不通知 |
| tests/test_gui.py | test_save_commits_checkbox_value_to_toml（×2 参数化） | R3 S1/S2 保存路径（复选框→模型→TOML） |
| tests/test_integration_notify.py（新文件） | test_move_with_notifications_on_notifies_filename | R1 S1 移动成功显示含文件名通知 |
| tests/test_integration_notify.py | test_move_with_notifications_off_no_notification | R1 S2 开关关不通知（移动不受影响） |
| tests/test_integration_notify.py | test_config_off_start_then_tray_enable | R1 S3 + R2 S3 配置关启动不通知、托盘开启即时生效 |
| tests/test_integration_notify.py | test_tray_toggle_off_then_on_immediate_effect | R2 S1/S2 托盘切换即时生效（双向） |
| tests/test_integration_notify.py | test_restart_resets_switch_to_config_value | R2 S4 重启后开关恢复配置值 |

#### 缺陷清单

**生产代码缺陷**：无

**测试缺陷**：无（Developer 交付测试经审查无需重写，缺口已由上述 10 个新用例关闭）

**已知约束**：
- 托盘菜单勾选渲染（pystray MenuItem checked）与 GUI 复选框 UI 绑定（`BooleanVar(value=...)`）需真实显示环境，无法无头自动验证 → 以开关访问器/数据层测试 + 代码审查兜底（gui.py/tray.py 本就在 coverage omit 内）
- 本沙箱拦截 pytest tmp_path（`mkdir(mode=0o700)` → WinError 5，且生成的 0o700 目录后续不可枚举/删除）；验证使用临时插件 `test_tmp/pytest_nomode_plugin.py`（剥离 Path.mkdir 的 mode）+ `--basetemp` 工作区路径——沙箱专用验证手段，**不入库**；CI/正常环境直接 `pytest` 即可
- 全量 3 失败 = `tests/test_single_instance.py`（本机 2 个运行中的 DownloadOrganizer 实例持有命名互斥锁 CreateMutexW err=183），环境占用，与本变更无关；CI 无运行实例时预期全绿
- ruff 无二进制且沙箱禁止安装 → 门禁待 CI；本机以 compileall（语法）+ 行宽 ≤100 + 手工核对 F401/F821 替代
- watchdog 未安装 → `tests/test_organizer.py::TestHandler` 1 跳过（既有 skip 条件，与本变更无关）

#### 全量运行命令

```bash
# CI/正常环境
pytest

# 本沙箱（tmp_path 受限）：临时插件 + 工作区 basetemp
$env:PYTHONPATH = "E:\Github\DownloadOrganizer\test_tmp"
py -3.14 -m pytest tests/ -p no:cacheprovider -p pytest_nomode_plugin --basetemp=E:\Github\DownloadOrganizer\test_tmp\bt-<fresh>
```

实际运行输出（受影响 29 用例）：`29 passed in 0.22s`；重复 3 次均 `29 passed`（无 flaky）。
全量输出：`69 passed, 3 failed, 1 skipped`（3 failed 全部为 test_single_instance 环境占用）。

#### Spec 覆盖矩阵

| Requirement | Scenario | 覆盖状态 | 测试 |
|-------------|----------|----------|------|
| R1 移动完成时显示桌面通知 | S1 常驻模式通知开启时移动成功显示通知 | ✅ | test_move_with_notifications_on_notifies_filename；test_notify_enabled_calls_icon |
| R1 | S2 常驻模式通知关闭时移动成功不显示通知 | ✅ | test_move_with_notifications_off_no_notification；test_notify_disabled_skips_icon |
| R1 | S3 配置关闭时启动默认不通知 | ✅ | test_config_off_start_then_tray_enable；test_register_notification_false_still_registers_callback |
| R1 | `--once` 单次整理模式不显示移动通知（主句） | ✅ | test_once_mode_registers_no_move_notification |
| R2 托盘通知开关 | S1 通过托盘关闭通知 | ✅ | test_tray_toggle_off_then_on_immediate_effect；test_toggle_notifications_both_directions_without_icon |
| R2 | S2 通过托盘重新开启通知 | ✅ | test_tray_toggle_off_then_on_immediate_effect |
| R2 | S3 配置关闭时托盘开关初始为未勾选，勾选后可即时开启 | ✅ | test_config_off_start_then_tray_enable；test_register_notification_false_still_registers_callback |
| R2 | S4 重启后开关恢复为配置值 | ✅ | test_restart_resets_switch_to_config_value；test_register_notification_true_initializes_switch_on |
| R3 图形界面通知设置 | S1 关闭通知并保存 | ✅ | test_save_commits_checkbox_value_to_toml[False]；test_roundtrip_writes_notify_on_move_false |
| R3 | S2 开启通知并保存 | ✅ | test_save_commits_checkbox_value_to_toml[True]；test_roundtrip_writes_notify_on_move_true |
| R3 | S3 配置中已关闭时界面初始为未勾选 | ✅（数据层）/ ⚠️ UI 绑定 | test_load_or_default_reads_notify_on_move_false；`BooleanVar(value=self.notify_on_move)` 一行绑定需显示环境，代码审查兜底 |

#### 总体结论

- **通过，可进入下一环节**（测试就绪，未发现新缺陷）
- spec 全部 10 个 Scenario 均有自动测试覆盖（R3 S3 的 UI 绑定层由代码审查兜底，数据层已覆盖）；生产实现与契约一致，无缺陷转 Developer
- 环境性注意项（不阻塞）：本沙箱全量 3 失败为 test_single_instance 实例锁占用；ruff 门禁待 CI 执行；两处均为环境限制，已在"已知约束"说明，请 Main 在 CI / 无实例环境独立重跑确认
