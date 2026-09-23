"""Страница «Отложенные задачи»: выбрать чат Claude Code, написать промпт, отправить после сброса лимита."""
import threading
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

import customtkinter as ctk

from src.i18n import t
from src.sessions import list_sessions, ago
from src.tasks import next_time_of_day
from src.claude_cli import open_chat_in_terminal
from src.usage_monitor import format_duration
from src.ui.components import ToolTip, GREEN, GREEN_TEXT, AMBER_TEXT, RED_TEXT, GREY_TEXT

CARD = "#14151d"
BORDER = "#212330"
ROW = "#101117"
ROW_SELECTED = "#2b1115"
CORAL = "#ef4444"
TEXT = "#f4f4f5"
MUTED = "#a1a1aa"
SESSIONS_SHOWN = 40

STATUS_STYLE = {
    "scheduled": ("#064e3b", GREEN_TEXT),
    "running": ("#1e3a8a", "#93c5fd"),
    "done": ("#1f2937", "#d4d4d8"),
    "failed": ("#450a0a", RED_TEXT),
    "cancelled": ("#27272a", GREY_TEXT),
}


def _clip(text: str, n: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[:n - 1] + "…"


def _ago_text(mtime: float) -> str:
    unit, n = ago(mtime)
    return t(f"ago.{unit}", n=n)


class TasksPage(ctk.CTkScrollableFrame):
    def __init__(self, master, scheduler, log):
        super().__init__(master, fg_color="transparent")
        self.scheduler = scheduler
        self.tasks = scheduler.tasks
        self.log = log
        self.sessions: List[Dict[str, Any]] = []
        self.selected: Optional[Dict[str, Any]] = None
        self._session_rows: Dict[str, ctk.CTkFrame] = {}
        self._shown_version = -1
        self._countdowns: Dict[str, ctk.CTkLabel] = {}

        ctk.CTkLabel(self, text=t("tasks.title"), font=("Inter", 18, "bold"), text_color=TEXT).pack(anchor="w", pady=(0, 2))
        ctk.CTkLabel(self, text=t("tasks.subtitle"), font=("Inter", 12), text_color="#71717a",
                     justify="left", wraplength=880).pack(anchor="w", pady=(0, 12))
        self._build_form()
        self._build_list()
        self.reload_sessions()

    # ---------- форма ----------
    def _step(self, card, key: str, sub_key: str = ""):
        ctk.CTkLabel(card, text=t(key), font=("Inter", 13, "bold"), text_color=MUTED).pack(anchor="w", padx=18, pady=(12, 2))
        if sub_key:
            ctk.CTkLabel(card, text=t(sub_key), font=("Inter", 11), text_color="#71717a",
                         justify="left", wraplength=860).pack(anchor="w", padx=18, pady=(0, 6))

    def _build_form(self):
        card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12, border_width=1, border_color=BORDER)
        card.pack(fill="x", pady=(0, 14), ipady=8)

        # 1. Чат
        self._step(card, "tasks.step.chat", "tasks.step.chat.sub")
        search_row = ctk.CTkFrame(card, fg_color="transparent")
        search_row.pack(fill="x", padx=18, pady=(0, 6))
        self.search = ctk.CTkEntry(search_row, height=32, placeholder_text=t("tasks.search"),
                                   fg_color="#0c0d12", border_color=BORDER)
        self.search.pack(side="left", fill="x", expand=True)
        self.search.bind("<KeyRelease>", lambda e: self._fill_sessions())
        refresh = ctk.CTkButton(search_row, text="🔄", width=36, height=32, fg_color="#181924", hover_color=BORDER,
                                border_width=1, border_color=BORDER, command=self.reload_sessions)
        refresh.pack(side="left", padx=(8, 0))
        ToolTip(refresh, t("tasks.reload"))
        self.session_list = ctk.CTkScrollableFrame(card, height=230, fg_color="#0c0d12", corner_radius=8)
        self.session_list.pack(fill="x", padx=18, pady=(0, 4))
        self.selected_lbl = ctk.CTkLabel(card, text=t("tasks.none_selected"), font=("Inter", 11, "bold"),
                                         text_color=GREY_TEXT, anchor="w")
        self.selected_lbl.pack(fill="x", padx=18)

        # 2. Промпт
        self._step(card, "tasks.step.prompt", "tasks.step.prompt.sub")
        self.prompt = ctk.CTkTextbox(card, height=110, font=("Inter", 13), fg_color="#0c0d12",
                                     border_width=1, border_color=BORDER, wrap="word")
        self.prompt.pack(fill="x", padx=18)

        # 3. Когда
        self._step(card, "tasks.step.when")
        when_row = ctk.CTkFrame(card, fg_color="transparent")
        when_row.pack(fill="x", padx=18)
        self.when_values = {t("tasks.when.reset"): "reset", t("tasks.when.time"): "time"}
        self.when = ctk.CTkSegmentedButton(when_row, values=list(self.when_values), command=lambda _v: self._when_changed(),
                                           font=("Inter", 12, "bold"), selected_color=CORAL, selected_hover_color="#dc2626",
                                           unselected_color="#181924", unselected_hover_color="#272938", fg_color="#181924")
        self.when.set(t("tasks.when.reset"))
        self.when.pack(side="left")
        self.time_entry = ctk.CTkEntry(when_row, width=80, height=30, justify="center", fg_color="#0c0d12",
                                       border_color=BORDER, font=("Inter", 13, "bold"))
        self.time_entry.insert(0, "09:00")
        self.when_preview = ctk.CTkLabel(card, text="", font=("Consolas", 12, "bold"), text_color=GREEN_TEXT,
                                         anchor="w", justify="left")
        self.when_preview.pack(fill="x", padx=18, pady=(6, 0))

        # 4. Права
        self._step(card, "tasks.step.perm")
        self.perm_values = {t("perm.auto"): "auto", t("perm.edits"): "edits", t("perm.read"): "read"}
        self.perm = ctk.CTkSegmentedButton(card, values=list(self.perm_values), command=lambda _v: self._perm_changed(),
                                           font=("Inter", 12, "bold"), selected_color=CORAL, selected_hover_color="#dc2626",
                                           unselected_color="#181924", unselected_hover_color="#272938", fg_color="#181924")
        self.perm.set(t("perm.auto"))
        self.perm.pack(anchor="w", padx=18)
        self.perm_hint = ctk.CTkLabel(card, text="", font=("Inter", 11), text_color=MUTED, justify="left",
                                      wraplength=860, anchor="w")
        self.perm_hint.pack(fill="x", padx=18, pady=(4, 0))
        self._perm_changed()

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=18, pady=(14, 4))
        ctk.CTkButton(btn_row, text=t("tasks.schedule"), font=("Inter", 13, "bold"), height=38, corner_radius=8,
                      fg_color=GREEN, hover_color="#059669", command=self._create).pack(side="left")
        ctk.CTkLabel(card, text=t("tasks.warning"), font=("Inter", 11), text_color=AMBER_TEXT, justify="left",
                     wraplength=860, anchor="w").pack(fill="x", padx=18, pady=(8, 4))

    def reload_sessions(self):
        self.selected_lbl.configure(text=t("tasks.loading"), text_color=GREY_TEXT)

        def work():
            sessions = list_sessions(limit=150)
            self.after(0, lambda: self._set_sessions(sessions))
        threading.Thread(target=work, daemon=True).start()

    def _set_sessions(self, sessions):
        self.sessions = sessions
        self._fill_sessions()
        self._update_selected_label()

    def _fill_sessions(self):
        for w in self.session_list.winfo_children():
            w.destroy()
        self._session_rows.clear()
        query = self.search.get().strip().lower()
        shown = [s for s in self.sessions
                 if not query or query in (s["title"] + " " + s["project"] + " " + s["last_prompt"] + " " + s["cwd"]).lower()]
        if not shown:
            ctk.CTkLabel(self.session_list, text=t("tasks.no_sessions"), text_color=GREY_TEXT).pack(pady=12)
            return
        for s in shown[:SESSIONS_SHOWN]:
            self._session_row(s)

    def _session_row(self, s: Dict[str, Any]):
        is_sel = self.selected is not None and self.selected["id"] == s["id"]
        row = ctk.CTkFrame(self.session_list, fg_color=ROW_SELECTED if is_sel else ROW, corner_radius=6,
                           border_width=1, border_color=CORAL if is_sel else "#1c1d26")
        row.pack(fill="x", pady=2, padx=2)
        top = ctk.CTkFrame(row, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(6, 0))
        title = ctk.CTkLabel(top, text=_clip(s["title"], 70), font=("Inter", 12, "bold"), text_color=TEXT, anchor="w")
        title.pack(side="left")
        meta = ctk.CTkLabel(top, text=f"📁 {s['project']} · {_ago_text(s['mtime'])}", font=("Inter", 11),
                            text_color=GREY_TEXT)
        meta.pack(side="right")
        last = ctk.CTkLabel(row, text=t("tasks.last_msg", text=_clip(s["last_prompt"], 110)), font=("Inter", 11),
                            text_color=MUTED, anchor="w", justify="left")
        last.pack(fill="x", padx=10, pady=(0, 6))
        for w in (row, top, title, meta, last):
            w.bind("<Button-1>", lambda e, sess=s: self._select(sess))
        ToolTip(title, f"{s['title']}\n\n{s['cwd']}\nID: {s['id']}")
        self._session_rows[s["id"]] = row

    def _select(self, session):
        self.selected = session
        for sid, row in self._session_rows.items():
            sel = sid == session["id"]
            row.configure(fg_color=ROW_SELECTED if sel else ROW, border_color=CORAL if sel else "#1c1d26")
        self._update_selected_label()

    def _update_selected_label(self):
        if self.selected:
            self.selected_lbl.configure(text=t("tasks.selected", title=_clip(self.selected["title"], 60),
                                               project=self.selected["project"]), text_color=GREEN_TEXT)
        else:
            self.selected_lbl.configure(text=t("tasks.none_selected") if self.sessions else t("tasks.no_sessions"),
                                        text_color=GREY_TEXT)

    def _when_changed(self):
        if self.when_values[self.when.get()] == "time":
            self.time_entry.pack(side="left", padx=(10, 0))
        else:
            self.time_entry.pack_forget()
        self._update_preview()

    def _perm_changed(self):
        self.perm_hint.configure(text=t(f"perm.{self.perm_values[self.perm.get()]}.hint"))

    def _update_preview(self):
        mode = self.when_values[self.when.get()]
        if mode == "time":
            dt = next_time_of_day(self.time_entry.get())
            text = t("tasks.preview.time", when=dt.strftime("%d.%m %H:%M"),
                     left=format_duration(dt.timestamp() - time.time())) if dt else t("tasks.preview.bad_time")
        else:
            due = self.tasks.resolve_due("reset")
            if due and due - time.time() > 30:
                text = t("tasks.preview.reset", when=datetime.fromtimestamp(due).strftime("%H:%M"),
                         left=format_duration(due - time.time()))
            else:
                text = t("tasks.preview.now")
        if self.when_preview.cget("text") != text:
            self.when_preview.configure(text=text)

    def _create(self):
        if not self.selected:
            self.log(t("task.err.session"), "error")
            self.selected_lbl.configure(text=t("task.err.session"), text_color=RED_TEXT)
            return
        try:
            self.tasks.create(self.selected, self.prompt.get("1.0", "end"), self.when_values[self.when.get()],
                              self.time_entry.get(), self.perm_values[self.perm.get()])
        except ValueError as e:
            self.log(str(e), "error")
            self.selected_lbl.configure(text=str(e), text_color=RED_TEXT)
            return
        self.prompt.delete("1.0", "end")
        self.refresh_list()

    # ---------- список задач ----------
    def _build_list(self):
        self.list_card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12, border_width=1, border_color=BORDER)
        self.list_card.pack(fill="x", pady=(0, 14), ipady=6)
        ctk.CTkLabel(self.list_card, text=t("tasks.list"), font=("Inter", 14, "bold"), text_color=TEXT).pack(
            anchor="w", padx=18, pady=(12, 6))
        self.list_body = ctk.CTkFrame(self.list_card, fg_color="transparent")
        self.list_body.pack(fill="x", padx=18, pady=(0, 8))

    def refresh_list(self):
        self._shown_version = self.tasks.version
        for w in self.list_body.winfo_children():
            w.destroy()
        self._countdowns.clear()
        if not self.tasks.tasks:
            ctk.CTkLabel(self.list_body, text=t("tasks.empty"), text_color=GREY_TEXT).pack(anchor="w", pady=6)
            return
        for task in self.tasks.tasks[:30]:
            self._task_row(task)

    def _task_row(self, task: Dict[str, Any]):
        row = ctk.CTkFrame(self.list_body, fg_color=ROW, corner_radius=8, border_width=1, border_color="#1c1d26")
        row.pack(fill="x", pady=3)
        top = ctk.CTkFrame(row, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(8, 2))
        bg, fg = STATUS_STYLE.get(task["status"], STATUS_STYLE["cancelled"])
        ctk.CTkLabel(top, text=t(f"task.status.{task['status']}"), font=("Inter", 10, "bold"), fg_color=bg,
                     text_color=fg, corner_radius=6, padx=8, pady=1).pack(side="left")
        ctk.CTkLabel(top, text=f"📁 {task['project']} · {_clip(task['title'], 50)}", font=("Inter", 12, "bold"),
                     text_color=TEXT).pack(side="left", padx=(8, 0))
        when = ctk.CTkLabel(top, text="", font=("Consolas", 11, "bold"), text_color=AMBER_TEXT)
        when.pack(side="right")
        if task["status"] == "scheduled":
            self._countdowns[task["id"]] = when
        else:
            stamp = task.get("finished_at") or task.get("started_at") or task.get("created_at")
            when.configure(text=datetime.fromtimestamp(stamp).strftime("%d.%m %H:%M") if stamp else "",
                           text_color=GREY_TEXT)

        ctk.CTkLabel(row, text=f"✉ {_clip(task['prompt'], 140)}", font=("Inter", 11), text_color=MUTED,
                     anchor="w", justify="left").pack(fill="x", padx=12)
        if task.get("result") and task["status"] in ("done", "failed"):
            color = "#d4d4d8" if task["status"] == "done" else RED_TEXT
            ctk.CTkLabel(row, text=f"↳ {_clip(task['result'], 160)}", font=("Inter", 11), text_color=color,
                         anchor="w", justify="left").pack(fill="x", padx=12, pady=(2, 0))

        btns = ctk.CTkFrame(row, fg_color="transparent")
        btns.pack(fill="x", padx=12, pady=(6, 8))

        def button(text, cmd, primary=False):
            ctk.CTkButton(btns, text=text, height=26, font=("Inter", 11, "bold"), corner_radius=6,
                          fg_color=CORAL if primary else "#181924", hover_color="#dc2626" if primary else BORDER,
                          border_width=0 if primary else 1, border_color=BORDER, command=cmd).pack(side="left", padx=(0, 6))

        tid = task["id"]
        if task["status"] == "scheduled":
            button(t("tasks.btn.run_now"), lambda: self.tasks.run_now(tid), primary=True)
            button(t("tasks.btn.cancel"), lambda: self.tasks.cancel(tid))
        if task["status"] in ("done", "failed"):
            button(t("tasks.btn.open_chat"), lambda: self.open_chat(tid), primary=True)
            button(t("tasks.btn.answer"), lambda: self.show_answer(tid))
        if task["status"] in ("failed", "cancelled"):
            button(t("tasks.btn.retry"), lambda: self.tasks.run_now(tid))
        if task["status"] in ("done", "failed", "cancelled"):
            button(t("tasks.btn.remove"), lambda: self.tasks.remove(tid))

    def open_chat(self, task_id: str):
        task = self.tasks.get(task_id)
        if task:
            try:
                open_chat_in_terminal(task["session_id"], task["cwd"])
            except OSError as e:
                self.log(str(e), "error")

    def show_answer(self, task_id: str):
        task = self.tasks.get(task_id)
        if not task:
            return
        win = ctk.CTkToplevel(self)
        win.title(f"{task['project']} — {_clip(task['title'], 40)}")
        win.geometry("760x520")
        win.configure(fg_color="#0c0d12")
        win.attributes("-topmost", True)
        box = ctk.CTkTextbox(win, font=("Inter", 13), fg_color=CARD, wrap="word")
        box.pack(fill="both", expand=True, padx=12, pady=(12, 6))
        box.insert("end", f"{t('tasks.answer.prompt')}\n{task['prompt']}\n\n{t('tasks.answer.result')}\n{task['result']}")
        box.configure(state="disabled")
        ctk.CTkButton(win, text=t("tasks.btn.open_chat"), fg_color=CORAL, hover_color="#dc2626",
                      command=lambda: self.open_chat(task_id)).pack(pady=(0, 12))

    # ---------- раз в секунду ----------
    def tick(self):
        if self._shown_version != self.tasks.version:
            self.refresh_list()
        now = time.time()
        for tid, lbl in self._countdowns.items():
            task = self.tasks.get(tid)
            if task:
                left = task["due_at"] - now
                text = t("tasks.due", when=datetime.fromtimestamp(task["due_at"]).strftime("%d.%m %H:%M"),
                         left=format_duration(left)) if left > 0 else t("tasks.due_now")
                if lbl.cget("text") != text:
                    lbl.configure(text=text)
        self._update_preview()
