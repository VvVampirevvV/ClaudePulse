import re
import tkinter as tk
import customtkinter as ctk
import datetime
from typing import Dict, Any, Optional, Tuple

from src.i18n import t

class ToolTip:
    """
    Универсальная интерактивная всплывающая подсказка в стиле ExitLag Dark.
    - Строгий синглтон: в любой момент времени существует максимум 1 подсказка на экране.
    - Мгновенное исчезновение при уходе курсора мыши или клике.
    - Нулевая нагрузка на процессор (без фонового Motion-поллинга, без задержек и лагов).
    - Крупный четкий шрифт под High-DPI экраны.
    - Защита от перехвата мыши (окно подсказки не блокирует курсор).
    """
    _active_window: Optional[tk.Toplevel] = None
    _active_owner: Optional["ToolTip"] = None
    _active_timer = None

    @classmethod
    def hide_all(cls):
        """Полностью закрывает любую активную подсказку и отменяет таймеры."""
        if cls._active_timer is not None:
            try:
                cls._active_timer[0].after_cancel(cls._active_timer[1])
            except Exception:
                pass
            cls._active_timer = None
        if cls._active_window is not None:
            try:
                cls._active_window.destroy()
            except Exception:
                pass
            cls._active_window = None
        cls._active_owner = None

    def __init__(self, widget, text: str, delay: int = 300):
        self.widget = widget
        self.text = text.strip()
        self.delay = delay
        self.pos = (0, 0)

        targets = [self.widget]
        for attr in ("_canvas", "_text_label", "_label"):
            val = getattr(self.widget, attr, None)
            if val and val not in targets:
                targets.append(val)

        try:
            for ch in self.widget.winfo_children():
                if ch.__class__.__name__ in ("CTkCanvas", "Label"):
                    targets.append(ch)
        except Exception:
            pass

        for t in set(targets):
            try:
                t.bind("<Enter>", self._on_enter, add="+")
                t.bind("<Leave>", self._on_leave, add="+")
                t.bind("<ButtonPress>", self._on_click, add="+")
            except Exception:
                pass

    def _on_enter(self, event):
        ToolTip.hide_all()
        ToolTip._active_owner = self
        self.pos = (event.x_root, event.y_root)
        try:
            timer = self.widget.after(self.delay, self._show)
            ToolTip._active_timer = (self.widget, timer)
        except Exception:
            pass

    def _on_leave(self, event=None):
        if ToolTip._active_owner is self:
            ToolTip.hide_all()

    def _on_click(self, event=None):
        ToolTip.hide_all()

    def _show(self):
        ToolTip._active_timer = None
        if ToolTip._active_owner is not self or not self.widget.winfo_exists():
            return

        ToolTip.hide_all()
        ToolTip._active_owner = self

        try:
            scale = ctk.ScalingTracker.get_window_scaling(self.widget)
        except Exception:
            scale = 1.0
        if scale <= 0:
            scale = 1.0

        try:
            tw = tk.Toplevel(self.widget)
            ToolTip._active_window = tw
            tw.wm_overrideredirect(True)
            tw.wm_attributes("-topmost", True)

            # Если мышь касается подсказки, она мгновенно исчезает
            tw.bind("<Enter>", lambda e: ToolTip.hide_all())
            tw.bind("<ButtonPress>", lambda e: ToolTip.hide_all())

            outer = tk.Frame(
                tw,
                background="#141620",
                highlightbackground="#3b3f54",
                highlightcolor="#3b3f54",
                highlightthickness=1
            )
            outer.pack(fill="both", expand=True)

            accent = tk.Frame(outer, background="#ef4444", height=max(2, round(2 * scale)))
            accent.pack(fill="x", side="top")

            pad_x = max(12, round(12 * scale))
            pad_y = max(8, round(8 * scale))
            wrap_w = max(340, round(380 * scale))

            content = tk.Frame(outer, background="#141620")
            content.pack(fill="both", expand=True, padx=pad_x, pady=pad_y)

            lines = self.text.strip().split("\n", 1)
            title_txt = ""
            body_txt = ""

            if len(lines) > 1:
                title_txt = lines[0].strip()
                body_txt = lines[1].strip()
            elif ":" in self.text and len(self.text.split(":", 1)[0]) < 35:
                parts = self.text.split(":", 1)
                title_txt = parts[0].strip() + ":"
                body_txt = parts[1].strip()
            else:
                body_txt = self.text.strip()

            title_font_size = max(11, round(11.5 * scale))
            body_font_size = max(10, round(10.5 * scale))

            if title_txt and body_txt:
                lbl_title = tk.Label(
                    content,
                    text=title_txt,
                    font=("Segoe UI", title_font_size, "bold"),
                    fg="#ffffff",
                    bg="#141620",
                    anchor="w",
                    justify="left",
                    wraplength=wrap_w
                )
                lbl_title.pack(fill="x", anchor="w", pady=(0, max(2, round(3 * scale))))

                lbl_body = tk.Label(
                    content,
                    text=body_txt,
                    font=("Segoe UI", body_font_size),
                    fg="#d4d4d8",
                    bg="#141620",
                    anchor="w",
                    justify="left",
                    wraplength=wrap_w
                )
                lbl_body.pack(fill="x", anchor="w")
            else:
                lbl_main = tk.Label(
                    content,
                    text=self.text,
                    font=("Segoe UI", title_font_size),
                    fg="#f4f4f5",
                    bg="#141620",
                    anchor="w",
                    justify="left",
                    wraplength=wrap_w
                )
                lbl_main.pack(fill="both", expand=True)

            tw.update_idletasks()
            w = tw.winfo_width()
            h = tw.winfo_height()

            cur_x, cur_y = self.pos
            if cur_x <= 0 or cur_y <= 0:
                cur_x = self.widget.winfo_rootx() + (self.widget.winfo_width() // 2)
                cur_y = self.widget.winfo_rooty() + self.widget.winfo_height()

            screen_w = int(self.widget.winfo_screenwidth() * scale)
            screen_h = int(self.widget.winfo_screenheight() * scale)

            x = cur_x + max(14, round(14 * scale))
            y = cur_y + max(18, round(18 * scale))

            if x + w > screen_w - round(12 * scale):
                x = cur_x - w - max(10, round(10 * scale))
            if x < round(10 * scale):
                x = round(10 * scale)

            if y + h > screen_h - round(35 * scale):
                y = cur_y - h - max(10, round(10 * scale))
            if y < round(10 * scale):
                y = round(10 * scale)

            tw.wm_geometry(f"+{x}+{y}")
        except Exception:
            ToolTip.hide_all()


# ----------------------------------------------------
# Общие цвета и хелперы
# ----------------------------------------------------
GREEN, GREEN_TEXT = "#10b981", "#34d399"
AMBER, AMBER_TEXT = "#f59e0b", "#fbbf24"
RED, RED_TEXT = "#ef4444", "#f87171"
GREY, GREY_TEXT = "#27272a", "#71717a"


def pct_colors(pct: Optional[int], levels) -> tuple:
    """(цвет полосы, цвет текста) по порогам предупреждений."""
    if pct is None:
        return GREY, GREY_TEXT
    levels = sorted(levels) or [80, 95]
    if pct >= levels[-1]:
        return RED, RED_TEXT
    if pct >= levels[0]:
        return AMBER, AMBER_TEXT
    return GREEN, GREEN_TEXT


# (шаблон строки из /usage, ключ перевода, ключ совета, имена групп)
_TIP_PATTERNS = [
    (re.compile(r'(\d+)% of your usage was at >(\S+) context', re.I), "tip.long_context", "tip.long_context.advice", ("pct", "size")),
    (re.compile(r'(\d+)% of your usage came from subagent-heavy sessions', re.I), "tip.subagents", "tip.subagents.advice", ("pct",)),
    (re.compile(r'(\d+)% of your usage was while (\d+)\+ sessions ran in parallel', re.I), "tip.parallel", "tip.parallel.advice", ("pct", "n")),
    (re.compile(r'Top skills:\s*(.+)', re.I), "tip.top_skills", None, ("list",)),
    (re.compile(r'Top subagents:\s*(.+)', re.I), "tip.top_subagents", None, ("list",)),
    (re.compile(r'Top MCP servers:\s*(.+)', re.I), "tip.top_mcp", None, ("list",)),
]
ADVICE_MIN_PCT = 30


def translate_tip(item: str) -> Tuple[str, Optional[str]]:
    """Строка из блока /usage -> (понятный текст, совет или None). Незнакомые строки — как есть."""
    for rx, key, advice_key, names in _TIP_PATTERNS:
        m = rx.search(item)
        if not m:
            continue
        values = dict(zip(names, m.groups()))
        pct = values.get("pct")
        advice = t(advice_key) if advice_key and pct and int(pct) >= ADVICE_MIN_PCT else None
        return t(key, **values), advice
    return item, None


class ConsoleLog(ctk.CTkTextbox):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(state="disabled", font=("Consolas", 12))

        self._textbox.tag_config("timestamp", foreground="#38bdf8")
        self._textbox.tag_config("command", foreground="#facc15")
        self._textbox.tag_config("success", foreground="#10b981")
        self._textbox.tag_config("error", foreground="#ef4444")
        self._textbox.tag_config("warning", foreground="#f97316")
        self._textbox.tag_config("normal", foreground="#a1a1aa")

    def write_log(self, message: str, tag: str = "normal", timestamp: Optional[str] = None):
        self.configure(state="normal")
        timestamp = timestamp or datetime.datetime.now().strftime("%H:%M:%S")
        self._textbox.insert("end", f"[{timestamp}] ", "timestamp")
        self._textbox.insert("end", f"{message}\n", tag)
        self.see("end")
        self.configure(state="disabled")

    def clear_log(self):
        self.configure(state="normal")
        self.delete("1.0", "end")
        self.configure(state="disabled")

    def get_log_text(self) -> str:
        return self.get("1.0", "end").strip()


class _QuotaBlock(ctk.CTkFrame):
    """Один блок квоты: заголовок, процент, полоса, строка сброса и правая подпись."""
    def __init__(self, master, title: str, tip: str):
        super().__init__(master, fg_color="#141417", corner_radius=8, border_width=1, border_color="#27272a")
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(8, 4))
        self.title = ctk.CTkLabel(header, text=title, font=("Inter", 12, "bold"), text_color="#f4f4f5")
        self.title.pack(side="left")
        self.usage = ctk.CTkLabel(header, text=t("quota.loading"), font=("Inter", 12, "bold"), text_color=GREY_TEXT)
        self.usage.pack(side="right")
        self.bar = ctk.CTkProgressBar(self, height=6, corner_radius=3, progress_color=GREY, fg_color="#27272a")
        self.bar.pack(fill="x", padx=12, pady=(2, 6))
        self.bar.set(0.0)
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=12, pady=(0, 6))
        self.reset = ctk.CTkLabel(footer, text="", font=("Inter", 11), text_color="#a1a1aa")
        self.reset.pack(side="left")
        self.right = ctk.CTkLabel(footer, text="", font=("Consolas", 12, "bold"), text_color=GREEN)
        self.right.pack(side="right")
        ToolTip(self.title, tip)

    def show(self, pct: Optional[int], levels, reset_text: str, right_text: str = "", right_color: str = GREEN):
        bar_color, text_color = pct_colors(pct, levels)
        if pct is None:
            self.usage.configure(text=t("quota.loading"), text_color=GREY_TEXT)
            self.bar.set(0.0)
        else:
            self.usage.configure(text=t("quota.used_free", used=pct, free=max(0, 100 - pct)), text_color=text_color)
            self.bar.set(min(1.0, max(0.0, pct / 100.0)))
        self.bar.configure(progress_color=bar_color)
        self.reset.configure(text=reset_text)
        self.right.configure(text=right_text, text_color=right_color)


class QuotaWidget(ctk.CTkFrame):
    """Реальные лимиты Claude из `claude /usage`: 5-часовое окно и недельная квота."""
    def __init__(self, master, on_refresh=None, **kwargs):
        super().__init__(master, **kwargs)
        self.on_refresh = on_refresh

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(12, 8))

        left = ctk.CTkFrame(top, fg_color="transparent")
        left.pack(side="left", fill="y")
        self.plan_badge = ctk.CTkLabel(left, text="", font=("Inter", 11, "bold"), fg_color="#064e3b",
                                       text_color=GREEN_TEXT, corner_radius=6, padx=8, pady=2)
        self.account_label = ctk.CTkLabel(left, text="", font=("Inter", 11), text_color="#a1a1aa")
        self.account_label.pack(side="left")

        right = ctk.CTkFrame(top, fg_color="transparent")
        right.pack(side="right", fill="y")
        self.source_label = ctk.CTkLabel(right, text="", font=("Inter", 10), text_color=GREY_TEXT)
        self.source_label.pack(side="left", padx=(0, 8))
        self.refresh_btn = ctk.CTkButton(
            right, text=t("btn.refresh"), font=("Inter", 11, "bold"), width=88, height=26,
            fg_color="#27272a", hover_color="#3f3f46", text_color="#e4e4e7", corner_radius=6,
            border_width=1, border_color="#3f3f46", command=self._handle_refresh
        )
        self.refresh_btn.pack(side="left")

        self.session = _QuotaBlock(self, t("quota.session.title"), t("quota.session.tip"))
        self.session.pack(fill="x", padx=16, pady=(0, 8), ipady=4)
        self.weekly = _QuotaBlock(self, t("quota.weekly.title"), t("quota.weekly.tip"))
        self.weekly.pack(fill="x", padx=16, pady=(0, 8), ipady=4)

        self.hint = ctk.CTkLabel(self, text="", font=("Inter", 11), text_color=AMBER_TEXT, justify="left", wraplength=520)

        ToolTip(self.source_label, t("quota.source.tip"))
        ToolTip(self.refresh_btn, t("quota.refresh.tip"))

    def _handle_refresh(self):
        if not self.on_refresh:
            return
        self.refresh_btn.configure(text=t("btn.refreshing"), state="disabled")

        def _done():
            try:
                self.after(0, lambda: self.refresh_btn.configure(text=t("btn.refresh"), state="normal"))
            except Exception:
                pass
        self.on_refresh(callback=_done)

    def update_status(self, q: Dict[str, Any]):
        from src.usage_monitor import format_reset, format_duration
        levels = q.get("levels", [80, 95])

        # Аккаунт: показываем только то, что реально пришло из CLI
        acc = q.get("account") or {}
        sub = (acc.get("subscription") or "").strip()
        if sub:
            self.plan_badge.configure(text=f"★ CLAUDE {sub.upper()}")
            if not self.plan_badge.winfo_ismapped():
                self.plan_badge.pack(side="left", padx=(0, 8), before=self.account_label)
        elif self.plan_badge.winfo_ismapped():
            self.plan_badge.pack_forget()
        if acc.get("logged_in") is False:
            self.account_label.configure(text=t("quota.not_logged_in"), text_color=RED_TEXT)
        else:
            self.account_label.configure(text=acc.get("email", ""), text_color="#a1a1aa")

        # Когда обновлялось
        if q.get("fetching"):
            self.source_label.configure(text=t("quota.updating"))
        elif q.get("fetched_at"):
            mins = int((datetime.datetime.now().timestamp() - q["fetched_at"]) // 60)
            self.source_label.configure(text=t("quota.updated_now") if mins < 1 else t("quota.updated_ago", m=mins))

        # 5-часовое окно
        s = q.get("session", {})
        if q.get("forced_reset"):
            self.session.show(100, levels, t("quota.limit_hit", when=q["forced_reset"]), t("quota.exhausted"), RED)
        elif not s.get("known"):
            self.session.show(None, levels, t("quota.waiting"))
        elif s.get("active"):
            self.session.show(s["pct"], levels, t("quota.session.reset", when=format_reset(s["reset"])),
                              t("quota.left", time=format_duration(s["remaining"])))
        else:
            self.session.show(s["pct"], levels, t("quota.session.fresh"), t("quota.session.closed"), GREY_TEXT)

        # Неделя
        w = q.get("weekly", {})
        if not w.get("known"):
            self.weekly.show(None, levels, t("quota.waiting"))
        else:
            fable = w.get("fable_pct")
            right = t("quota.fable", pct=fable) if fable else ""
            reset = t("quota.weekly.reset", when=format_reset(w["reset"])) if w.get("reset") else ""
            self.weekly.show(w["pct"], levels, reset, right, "#a1a1aa")

        # Подсказка, если данных нет
        err = q.get("error")
        if err and not s.get("known"):
            self.hint.configure(text=t("quota.no_data_hint") if err == "no_data" else t("quota.error", err=err))
            if not self.hint.winfo_ismapped():
                self.hint.pack(anchor="w", padx=16, pady=(0, 10))
        elif self.hint.winfo_ismapped():
            self.hint.pack_forget()


class TipsCard(ctk.CTkFrame):
    """«На что уходят лимиты» — блок из /usage с переводом и советами."""
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="#14151d", border_width=1, border_color="#212330", corner_radius=10, **kwargs)
        self._period = "24h"
        self._last_key = None

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 4))
        title = ctk.CTkLabel(header, text=t("tips.title"), font=("Inter", 13, "bold"), text_color="#f4f4f5")
        title.pack(side="left")
        ToolTip(title, t("tips.tip"))
        self.switch = ctk.CTkSegmentedButton(
            header, values=[t("tips.24h"), t("tips.7d")], command=self._on_period,
            font=("Inter", 11, "bold"), height=24, selected_color="#ef4444", selected_hover_color="#dc2626",
            unselected_color="#181924", unselected_hover_color="#272938", fg_color="#181924"
        )
        self.switch.set(t("tips.24h"))
        self.switch.pack(side="right")

        self.summary = ctk.CTkLabel(self, text="", font=("Inter", 11), text_color=GREY_TEXT, anchor="w")
        self.summary.pack(fill="x", padx=14)
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="x", padx=14, pady=(4, 12))
        self._tips = []

    def _on_period(self, value):
        self._period = "7d" if value == t("tips.7d") else "24h"
        self._last_key = None
        self.update_tips(self._tips)

    def update_tips(self, tips):
        self._tips = tips or []
        block = next((b for b in self._tips if b["period"] == self._period), None)
        key = (self._period, repr(block))
        if key == self._last_key:
            return
        self._last_key = key
        for w in self.body.winfo_children():
            w.destroy()
        if not block:
            self.summary.configure(text=t("tips.empty"))
            return
        self.summary.configure(text=t("tips.summary", req=block["requests"], ses=block["sessions"]))
        for item in block["items"]:
            text, advice = translate_tip(item)
            row = ctk.CTkFrame(self.body, fg_color="#0f1016", corner_radius=6)
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"• {text}", font=("Inter", 12), text_color="#e4e4e7",
                         anchor="w", justify="left", wraplength=900).pack(fill="x", padx=10, pady=(6, 0 if advice else 6))
            if advice:
                ctk.CTkLabel(row, text=f"💡 {advice}", font=("Inter", 11), text_color=AMBER_TEXT,
                             anchor="w", justify="left", wraplength=900).pack(fill="x", padx=10, pady=(0, 6))


class FeatureCard(ctk.CTkFrame):
    """Карточка системной настройки с тумблером."""
    def __init__(self, master, icon: str, title: str, description: str, variable: ctk.BooleanVar,
                 badge_text: str = "", footer_note: str = "", command=None, **kwargs):
        super().__init__(master, fg_color="#14151d", border_width=1, border_color="#212330", corner_radius=10, **kwargs)
        self.variable = variable
        self.command = command

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 6))
        left_box = ctk.CTkFrame(header, fg_color="transparent")
        left_box.pack(side="left", fill="y")
        ctk.CTkLabel(left_box, text=icon, font=("Segoe UI Emoji", 16)).pack(side="left", padx=(0, 8))
        self.title_label = ctk.CTkLabel(left_box, text=title, font=("Inter", 13, "bold"), text_color="#f4f4f5")
        self.title_label.pack(side="left")
        if badge_text:
            ctk.CTkLabel(left_box, text=badge_text, font=("Inter", 9, "bold"), fg_color="#064e3b",
                         text_color=GREEN_TEXT, corner_radius=4, padx=6, pady=1).pack(side="left", padx=(8, 0))

        self.switch = ctk.CTkSwitch(
            header, text="", width=46, height=24, switch_width=44, switch_height=22, corner_radius=11,
            variable=variable, progress_color=GREEN, button_color="#ffffff", button_hover_color="#e4e4e7",
            fg_color="#27272a", command=self._on_toggle
        )
        self.switch.pack(side="right")

        self.desc_label = ctk.CTkLabel(self, text=description, font=("Inter", 11), text_color="#9ca3af",
                                       justify="left", wraplength=340)
        self.desc_label.pack(anchor="w", padx=14, pady=(0, 6))
        if footer_note:
            ctk.CTkLabel(self, text=footer_note, font=("Inter", 10), text_color="#52525b",
                         justify="left", wraplength=340).pack(anchor="w", padx=14, pady=(0, 10))

        tip_text = f"{title}:\n{description}" + (f"\n\n{footer_note}" if footer_note else "")
        ToolTip(self.title_label, tip_text)
        ToolTip(self.desc_label, tip_text)

    def _on_toggle(self):
        if self.command:
            self.command()


class ConnectionTile(ctk.CTkFrame):
    """Карточка пресета команды. Активной всегда остаётся ровно одна."""
    def __init__(self, master, icon: str, name: str, subtitle: str, is_active: bool, on_toggle=None, **kwargs):
        super().__init__(master, fg_color="#14151d", border_width=1,
                         border_color="#ef4444" if is_active else "#212330", corner_radius=10, **kwargs)
        self.on_toggle = on_toggle
        self.is_active_var = ctk.BooleanVar(value=is_active)

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=12, pady=10)
        icon_box = ctk.CTkFrame(inner, width=38, height=38, corner_radius=8, fg_color="#1e202b")
        icon_box.pack(side="left", padx=(0, 10))
        icon_box.pack_propagate(False)
        ctk.CTkLabel(icon_box, text=icon, font=("Segoe UI Emoji", 18)).place(relx=0.5, rely=0.5, anchor="center")

        self.switch = ctk.CTkSwitch(
            inner, text="", width=42, height=22, switch_width=40, switch_height=20, corner_radius=10,
            variable=self.is_active_var, progress_color=GREEN, button_color="#ffffff", fg_color="#27272a",
            command=self._handle_click
        )
        self.switch.pack(side="right")

        text_box = ctk.CTkFrame(inner, fg_color="transparent")
        text_box.pack(side="left", fill="both", expand=True)
        self.title_lbl = ctk.CTkLabel(text_box, text=name, font=("Inter", 12, "bold"), text_color="#f4f4f5", anchor="w")
        self.title_lbl.pack(anchor="w")
        # Флаги модели — главное отличие пресетов; сама команда целиком — в подсказке
        short = subtitle.split("--model", 1)[1].strip() if "--model" in subtitle else subtitle
        self.sub_lbl = ctk.CTkLabel(text_box, text=short, font=("Consolas", 10), text_color=GREY_TEXT, anchor="w")
        self.sub_lbl.pack(anchor="w")

        tip = t("tile.tip", name=name, cmd=subtitle)
        for w in (self.switch, self.title_lbl, self.sub_lbl, icon_box):
            ToolTip(w, tip)

    def _handle_click(self):
        # Выключить активный пресет нельзя — только выбрать другой
        if not self.is_active_var.get():
            self.is_active_var.set(True)
            return
        if self.on_toggle:
            self.on_toggle(True)

    def set_active(self, active: bool):
        self.is_active_var.set(active)
        self.configure(border_color="#ef4444" if active else "#212330")


class SessionStatsCard(ctk.CTkFrame):
    """Результат последнего пинга и кнопка «пинг сейчас»."""
    def __init__(self, master, on_run_now=None, **kwargs):
        super().__init__(master, fg_color="#14151d", border_width=1, border_color="#212330", corner_radius=10, **kwargs)
        top_row = ctk.CTkFrame(self, fg_color="transparent")
        top_row.pack(fill="x", padx=14, pady=(12, 6))
        ctk.CTkLabel(top_row, text="⚡", font=("Segoe UI Emoji", 14), text_color="#ef4444").pack(side="left", padx=(0, 6))
        ctk.CTkLabel(top_row, text=t("stats.title"), font=("Inter", 13, "bold"), text_color="#f4f4f5").pack(side="left")

        stats_frame = ctk.CTkFrame(self, fg_color="#0f1016", corner_radius=8)
        stats_frame.pack(fill="x", padx=14, pady=(4, 10))
        self.stat_labels = {}
        for key in ("when", "result", "duration", "next"):
            cell = ctk.CTkFrame(stats_frame, fg_color="transparent")
            cell.pack(side="left", fill="both", expand=True, padx=8, pady=8)
            head = ctk.CTkLabel(cell, text=t(f"stats.{key}"), font=("Inter", 10), text_color=GREY_TEXT)
            head.pack(anchor="w")
            lbl = ctk.CTkLabel(cell, text="—", font=("Consolas", 12, "bold"), text_color="#f4f4f5")
            lbl.pack(anchor="w")
            self.stat_labels[key] = lbl
            ToolTip(head, t(f"stats.{key}.tip"))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=(0, 10))
        self.cmd_lbl = ctk.CTkLabel(btn_row, text="", font=("Consolas", 11), text_color=GREY_TEXT)
        self.cmd_lbl.pack(side="left")
        if on_run_now:
            self.run_btn = ctk.CTkButton(
                btn_row, text=t("btn.ping_now"), font=("Inter", 11, "bold"), fg_color="#ef4444",
                hover_color="#dc2626", text_color="#ffffff", height=28, corner_radius=6, command=on_run_now
            )
            self.run_btn.pack(side="right")
            ToolTip(self.run_btn, t("btn.ping_now.tip"))

    def update_stats(self, stats: Dict[str, Any], next_clock: str, command: str):
        ts = stats.get("timestamp") or 0
        code = stats.get("exit_code")
        if ts:
            self.stat_labels["when"].configure(text=datetime.datetime.fromtimestamp(ts).strftime("%H:%M"))
            self.stat_labels["duration"].configure(text=t("stats.sec", s=f"{stats.get('duration', 0.0):.1f}"))
            ok = code == 0
            self.stat_labels["result"].configure(
                text=t("stats.ok") if ok else t("stats.err", code=code), text_color=GREEN if ok else RED)
        else:
            self.stat_labels["result"].configure(text=t("stats.none"), text_color=GREY_TEXT)
        self.stat_labels["next"].configure(text=next_clock)
        self.cmd_lbl.configure(text=command[:60])
