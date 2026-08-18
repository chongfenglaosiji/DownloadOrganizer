# -*- coding: utf-8 -*-
"""配置图形界面（tkinter 标准库）。

编辑监控目录、规则并保存回 TOML。供 ``download-organizer --gui`` 调用；
无显示环境（CI/服务）下导入失败时由调用方降级。
"""
from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .config import load_config, default_rules

log = logging.getLogger("download_organizer")

# 允许的冲突策略
_POLICIES = ("rename", "overwrite", "skip", "recycle")


def _toml_str(s: str) -> str:
    """把字符串转成合法的 TOML 基本字符串（转义反斜杠/引号等）。"""
    import json
    return json.dumps(str(s), ensure_ascii=False)


class ConfigEditor:
    """配置编辑器主窗口。"""

    def __init__(self, config_path: str | None = None):
        self.config_path = config_path
        # 配置以可变模型保存：list[dict]（目录）+ 每个目录的 rules list[dict]
        self.downloads: list[dict] = []
        self._load_or_default()

        self.root = tk.Tk()
        self.root.title("DownloadOrganizer 配置")
        self.root.geometry("760x520")
        self.root.minsize(640, 420)

        self._build_ui()

    # ------------------------------------------------------------------
    # 数据模型
    # ------------------------------------------------------------------
    def _load_or_default(self) -> None:
        cfg = load_config(self.config_path)
        self.downloads = []
        for d in cfg.downloads:
            self.downloads.append({
                "path": d.path,
                "recursive": d.recursive,
                "conflict_policy": d.conflict_policy,
                "check_interval": d.check_interval,
                "stable_checks": d.stable_checks,
                "max_checks": d.max_checks,
                "ignored_endings": list(d.ignored_endings),
                "poll_interval": getattr(d, "poll_interval", 5.0),
                "rules": [
                    {"category": r.category,
                     "extensions": list(r.extensions),
                     "target_dir": r.target_dir or "",
                     "name_pattern": r.name_pattern or ""}
                    for r in d.rules
                ],
            })
        if not self.downloads:
            self.downloads = [{
                "path": str(Path.home() / "Downloads"),
                "recursive": False,
                "conflict_policy": "rename",
                "check_interval": 1.0,
                "stable_checks": 3,
                "max_checks": 30,
                "ignored_endings": [".crdownload", ".part", ".tmp", ".temp", "~", ".aria2"],
                "poll_interval": 5.0,
                "rules": [{"category": r.category,
                           "extensions": list(r.extensions),
                           "target_dir": "",
                           "name_pattern": ""} for r in default_rules()],
            }]

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=6)
        top.pack(fill=tk.BOTH, expand=True)

        # 左：目录列表
        left = ttk.Frame(top)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        ttk.Label(left, text="监控目录").pack(anchor=tk.W)
        self.dir_list = tk.Listbox(left, width=30, exportselection=False)
        self.dir_list.pack(fill=tk.BOTH, expand=True)
        self.dir_list.bind("<<ListboxSelect>>", self._on_select_dir)
        btn_row = ttk.Frame(left)
        btn_row.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(btn_row, text="添加", command=self._add_dir).pack(side=tk.LEFT)
        ttk.Button(btn_row, text="删除", command=self._del_dir).pack(side=tk.LEFT, padx=4)

        # 右：目录详情 + 规则
        right = ttk.Frame(top)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._build_detail(right)

        # 底部按钮
        bottom = ttk.Frame(self.root, padding=6)
        bottom.pack(fill=tk.X)
        ttk.Button(bottom, text="保存", command=self._save).pack(side=tk.RIGHT)
        ttk.Button(bottom, text="退出", command=self.root.destroy).pack(side=tk.RIGHT, padx=4)

        self._refresh_list()
        if self.downloads:
            self.dir_list.selection_set(0)
            self._show_detail(0)

    def _build_detail(self, parent) -> None:
        self.detail = ttk.Frame(parent)
        self.detail.pack(fill=tk.BOTH, expand=True)

        frm = ttk.LabelFrame(self.detail, text="目录设置", padding=6)
        frm.pack(fill=tk.X)
        row1 = ttk.Frame(frm)
        row1.pack(fill=tk.X)
        ttk.Label(row1, text="路径").pack(side=tk.LEFT)
        self.var_path = tk.StringVar()
        ttk.Entry(row1, textvariable=self.var_path).pack(side=tk.LEFT, fill=tk.X,
                                                         expand=True, padx=6)
        self.var_recursive = tk.BooleanVar()
        ttk.Checkbutton(frm, text="递归子目录", variable=self.var_recursive).pack(
            anchor=tk.W, pady=(4, 0))

        row2 = ttk.Frame(frm)
        row2.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(row2, text="冲突策略").pack(side=tk.LEFT)
        self.var_policy = tk.StringVar()
        ttk.Combobox(row2, textvariable=self.var_policy, values=_POLICIES,
                     state="readonly", width=10).pack(side=tk.LEFT, padx=6)
        ttk.Label(row2, text="检查间隔(s)").pack(side=tk.LEFT, padx=(12, 0))
        self.var_interval = tk.StringVar()
        ttk.Entry(row2, textvariable=self.var_interval, width=6).pack(side=tk.LEFT, padx=4)
        ttk.Label(row2, text="稳定次数").pack(side=tk.LEFT, padx=(12, 0))
        self.var_stable = tk.StringVar()
        ttk.Entry(row2, textvariable=self.var_stable, width=4).pack(side=tk.LEFT, padx=4)

        # 规则表
        rframe = ttk.LabelFrame(self.detail, text="分类规则", padding=6)
        rframe.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        cols = ("category", "extensions", "target_dir", "name_pattern")
        self.tree = ttk.Treeview(rframe, columns=cols, show="headings", height=6)
        headers = {"category": "分类", "extensions": "扩展名(逗号分隔)",
                   "target_dir": "目标目录(可空)", "name_pattern": "文件名正则(可空)"}
        widths = {"category": 90, "extensions": 200, "target_dir": 180, "name_pattern": 160}
        for c in cols:
            self.tree.heading(c, text=headers[c])
            self.tree.column(c, width=widths[c])
        self.tree.pack(fill=tk.BOTH, expand=True)
        rbtns = ttk.Frame(rframe)
        rbtns.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(rbtns, text="添加规则", command=self._add_rule).pack(side=tk.LEFT)
        ttk.Button(rbtns, text="删除规则", command=self._del_rule).pack(side=tk.LEFT, padx=4)
        ttk.Button(rbtns, text="上移", command=lambda: self._move_rule(-1)).pack(side=tk.LEFT)
        ttk.Button(rbtns, text="下移", command=lambda: self._move_rule(1)).pack(side=tk.LEFT, padx=4)

    # ------------------------------------------------------------------
    # 目录操作
    # ------------------------------------------------------------------
    def _current_index(self) -> int | None:
        sel = self.dir_list.curselection()
        return int(sel[0]) if sel else None

    def _refresh_list(self) -> None:
        self.dir_list.delete(0, tk.END)
        for d in self.downloads:
            self.dir_list.insert(tk.END, d["path"])

    def _on_select_dir(self, _event) -> None:
        idx = self._current_index()
        if idx is not None:
            self._show_detail(idx)

    def _show_detail(self, idx: int) -> None:
        d = self.downloads[idx]
        self.var_path.set(d["path"])
        self.var_recursive.set(d["recursive"])
        self.var_policy.set(d["conflict_policy"])
        self.var_interval.set(str(d["check_interval"]))
        self.var_stable.set(str(d["stable_checks"]))
        self._refresh_rules(d["rules"])

    def _commit_detail(self) -> None:
        """把表单写回当前目录模型（保存时调用）。"""
        idx = self._current_index()
        if idx is None:
            return
        d = self.downloads[idx]
        d["path"] = self.var_path.get().strip()
        d["recursive"] = self.var_recursive.get()
        d["conflict_policy"] = self.var_policy.get() or "rename"
        try:
            d["check_interval"] = float(self.var_interval.get() or 1.0)
            d["stable_checks"] = int(self.var_stable.get() or 3)
        except ValueError:
            pass

    def _add_dir(self) -> None:
        self._commit_detail()
        self.downloads.append({
            "path": str(Path.home() / "Downloads"),
            "recursive": False, "conflict_policy": "rename",
            "check_interval": 1.0, "stable_checks": 3, "max_checks": 30,
            "ignored_endings": [".crdownload", ".part", ".tmp", ".temp", "~", ".aria2"],
            "poll_interval": 5.0,
            "rules": [{"category": r.category, "extensions": list(r.extensions),
                       "target_dir": "", "name_pattern": ""} for r in default_rules()],
        })
        self._refresh_list()
        self.dir_list.selection_clear(0, tk.END)
        self.dir_list.selection_set(tk.END)
        self.dir_list.see(tk.END)

    def _del_dir(self) -> None:
        idx = self._current_index()
        if idx is None:
            return
        del self.downloads[idx]
        self._refresh_list()
        if self.downloads:
            self.dir_list.selection_set(0)
            self._show_detail(0)

    # ------------------------------------------------------------------
    # 规则操作
    # ------------------------------------------------------------------
    def _refresh_rules(self, rules: list[dict]) -> None:
        self.tree.delete(*self.tree.get_children())
        for r in rules:
            self.tree.insert("", tk.END, values=(
                r["category"], ", ".join(r["extensions"]),
                r.get("target_dir") or "", r.get("name_pattern") or ""))

    def _selected_rule_idx(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.index(sel[0])

    def _add_rule(self) -> None:
        idx = self._current_index()
        if idx is None:
            return
        self._commit_detail()
        d = self.downloads[idx]
        d["rules"].append({"category": "新分类", "extensions": [],
                           "target_dir": "", "name_pattern": ""})
        self._refresh_rules(d["rules"])

    def _del_rule(self) -> None:
        idx = self._current_index()
        ridx = self._selected_rule_idx()
        if idx is None or ridx is None:
            return
        del self.downloads[idx]["rules"][ridx]
        self._refresh_rules(self.downloads[idx]["rules"])

    def _move_rule(self, delta: int) -> None:
        idx = self._current_index()
        ridx = self._selected_rule_idx()
        if idx is None or ridx is None:
            return
        rules = self.downloads[idx]["rules"]
        target = ridx + delta
        if target < 0 or target >= len(rules):
            return
        rules[ridx], rules[target] = rules[target], rules[ridx]
        self._refresh_rules(rules)
        self.tree.selection_set(self.tree.get_children()[target])

    # ------------------------------------------------------------------
    # 保存
    # ------------------------------------------------------------------
    def _save(self) -> None:
        self._commit_detail()
        target = self.config_path or str(Path.cwd() / "config.toml")
        try:
            self._write_toml(Path(target))
        except OSError as exc:
            messagebox.showerror("保存失败", str(exc))
            return
        messagebox.showinfo("已保存", f"已写入 {target}\n重启后生效。")

    def _write_toml(self, p: Path) -> None:
        """把模型序列化为 TOML 文本并写入。"""
        ts = _toml_str
        lines = [
            "# DownloadOrganizer 配置（由 GUI 生成）",
            "# 可继续手工编辑；保存后重启生效。",
            "",
            "[organizer]",
            'log_level = "INFO"',
            "",
        ]
        for d in self.downloads:
            lines.append("[[downloads]]")
            lines.append(f"path = {ts(d['path'])}")
            lines.append(f'recursive = {"true" if d["recursive"] else "false"}')
            lines.append(f"conflict_policy = {ts(d['conflict_policy'])}")
            lines.append(f"check_interval = {d['check_interval']}")
            lines.append(f"stable_checks = {d['stable_checks']}")
            lines.append(f"max_checks = {d['max_checks']}")
            lines.append("ignored_endings = "
                         + "[" + ", ".join(ts(x) for x in d["ignored_endings"]) + "]")
            lines.append("")
            for r in d["rules"]:
                lines.append("  [[downloads.rules]]")
                lines.append(f"  category = {ts(r['category'])}")
                if r["extensions"]:
                    lines.append("  extensions = ["
                                 + ", ".join(ts(x) for x in r["extensions"]) + "]")
                if r.get("target_dir"):
                    lines.append(f"  target_dir = {ts(r['target_dir'])}")
                if r.get("name_pattern"):
                    lines.append(f"  name_pattern = {ts(r['name_pattern'])}")
                lines.append("")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(lines), encoding="utf-8")

    def run(self) -> None:
        self.root.mainloop()


def open_gui(config_path: str | None = None) -> int:
    """打开配置编辑器（阻塞）。无 tkinter/无显示环境时返回非零。"""
    try:
        app = ConfigEditor(config_path)
    except Exception as exc:  # noqa: BLE001
        log.warning("无法打开配置界面: %s", exc)
        print(f"无法打开配置界面: {exc}", file=__import__("sys").stderr)
        return 1
    app.run()
    return 0
