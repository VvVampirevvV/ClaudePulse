import tkinter as tk
import customtkinter as ctk
import datetime
from typing import Dict, Any, Optional

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

class ConsoleLog(ctk.CTkTextbox):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(state="disabled", font=("Consolas", 12))
        
        self._textbox.tag_config("timestamp", foreground="#38bdf8") # Sky blue
        self._textbox.tag_config("command", foreground="#facc15")   # Yellow
        self._textbox.tag_config("success", foreground="#10b981")   # Emerald
        self._textbox.tag_config("error", foreground="#ef4444")     # Red
        self._textbox.tag_config("warning", foreground="#f97316")   # Orange
        self._textbox.tag_config("normal", foreground="#a1a1aa")    # Muted
        
    def write_log(self, message: str, tag: str = "normal"):
        self.configure(state="normal")
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
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


class QuotaWidget(ctk.CTkFrame):
    """
    Виджет визуального отслеживания реальных лимитов Claude:
    - 5-часовое сессионное окно (таймер обратного отсчета, % использования, точное время сброса)
    - Недельная квота для всех моделей и Fable (шкала прогресса, % использования и остатка, дата сброса)
    - Кнопка ручной синхронизации квот
    """
    def __init__(self, master, on_refresh=None, **kwargs):
        super().__init__(master, **kwargs)
        self.on_refresh = on_refresh
        
        # 1. Top Badges & Control Row
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.pack(fill="x", padx=16, pady=(12, 8))
        
        # Left side: Plan badge & Account info
        left_header = ctk.CTkFrame(self.top_frame, fg_color="transparent")
        left_header.pack(side="left", fill="y")
        
        self.plan_badge = ctk.CTkLabel(
            left_header,
            text="★ CLAUDE MAX",
            font=("Inter", 11, "bold"),
            fg_color="#064e3b",
            text_color="#34d399",
            corner_radius=6,
            padx=8,
            pady=2
        )
        self.plan_badge.pack(side="left", padx=(0, 8))
        
        self.account_label = ctk.CTkLabel(
            left_header,
            text="",
            font=("Inter", 11),
            text_color="#a1a1aa"
        )
        self.account_label.pack(side="left")
        
        # Right side: Source indicator & Refresh button
        right_header = ctk.CTkFrame(self.top_frame, fg_color="transparent")
        right_header.pack(side="right", fill="y")
        
        self.source_label = ctk.CTkLabel(
            right_header,
            text="✓ Claude CLI",
            font=("Inter", 10),
            text_color="#71717a"
        )
        self.source_label.pack(side="left", padx=(0, 8))
        
        self.refresh_btn = ctk.CTkButton(
            right_header,
            text="🔄 Обновить",
            font=("Inter", 11, "bold"),
            width=88,
            height=26,
            fg_color="#27272a",
            hover_color="#3f3f46",
            text_color="#e4e4e7",
            corner_radius=6,
            border_width=1,
            border_color="#3f3f46",
            command=self._handle_refresh
        )
        self.refresh_btn.pack(side="left")
        
        # ----------------------------------------------------
        # 2. Block 1: 5-Hour Session Quota Window
        # ----------------------------------------------------
        self.session_card = ctk.CTkFrame(self, fg_color="#141417", corner_radius=8, border_width=1, border_color="#27272a")
        self.session_card.pack(fill="x", padx=16, pady=(0, 8), ipady=4)
        
        session_header = ctk.CTkFrame(self.session_card, fg_color="transparent")
        session_header.pack(fill="x", padx=12, pady=(8, 4))
        
        self.session_title = ctk.CTkLabel(
            session_header,
            text="⏳ СЕССИОННОЕ ОКНО (5 ЧАСОВ)",
            font=("Inter", 12, "bold"),
            text_color="#f4f4f5"
        )
        self.session_title.pack(side="left")
        
        self.session_usage_label = ctk.CTkLabel(
            session_header,
            text="0% использовано · 100% свободно",
            font=("Inter", 12, "bold"),
            text_color="#34d399"
        )
        self.session_usage_label.pack(side="right")
        
        self.session_progress_bar = ctk.CTkProgressBar(
            self.session_card,
            height=6,
            corner_radius=3,
            progress_color="#10b981",
            fg_color="#27272a"
        )
        self.session_progress_bar.pack(fill="x", padx=12, pady=(2, 6))
        self.session_progress_bar.set(0.0)
        
        session_footer = ctk.CTkFrame(self.session_card, fg_color="transparent")
        session_footer.pack(fill="x", padx=12, pady=(0, 6))
        
        self.session_reset_label = ctk.CTkLabel(
            session_footer,
            text="Ожидание первого запроса",
            font=("Inter", 11),
            text_color="#a1a1aa"
        )
        self.session_reset_label.pack(side="left")
        
        self.session_status_label = ctk.CTkLabel(
            session_footer,
            text="--:--:--",
            font=("Consolas", 12, "bold"),
            text_color="#10b981"
        )
        self.session_status_label.pack(side="right")
        
        # ----------------------------------------------------
        # 3. Block 2: Weekly Quota (All Models & Fable)
        # ----------------------------------------------------
        self.weekly_card = ctk.CTkFrame(self, fg_color="#141417", corner_radius=8, border_width=1, border_color="#27272a")
        self.weekly_card.pack(fill="x", padx=16, pady=(0, 12), ipady=4)
        
        weekly_header = ctk.CTkFrame(self.weekly_card, fg_color="transparent")
        weekly_header.pack(fill="x", padx=12, pady=(8, 4))
        
        self.weekly_title = ctk.CTkLabel(
            weekly_header,
            text="📅 НЕДЕЛЬНЫЙ ЛИМИТ (ВСЕ МОДЕЛИ)",
            font=("Inter", 12, "bold"),
            text_color="#f4f4f5"
        )
        self.weekly_title.pack(side="left")
        
        self.weekly_usage_label = ctk.CTkLabel(
            weekly_header,
            text="Синхронизация...",
            font=("Inter", 12, "bold"),
            text_color="#fbbf24"
        )
        self.weekly_usage_label.pack(side="right")
        
        self.weekly_progress_bar = ctk.CTkProgressBar(
            self.weekly_card,
            height=6,
            corner_radius=3,
            progress_color="#f59e0b",
            fg_color="#27272a"
        )
        self.weekly_progress_bar.pack(fill="x", padx=12, pady=(2, 6))
        self.weekly_progress_bar.set(0.0)
        
        weekly_footer = ctk.CTkFrame(self.weekly_card, fg_color="transparent")
        weekly_footer.pack(fill="x", padx=12, pady=(0, 6))
        
        self.weekly_reset_label = ctk.CTkLabel(
            weekly_footer,
            text="Сброс квоты: синхронизация...",
            font=("Inter", 11),
            text_color="#a1a1aa"
        )
        self.weekly_reset_label.pack(side="left")
        
        self.weekly_fable_label = ctk.CTkLabel(
            weekly_footer,
            text="",
            font=("Inter", 11),
            text_color="#a1a1aa"
        )
        self.weekly_fable_label.pack(side="right")

        # Tooltips для квот и бейджей
        ToolTip(self.plan_badge, "Тарифный план: Claude Max\nРасширенный лимит сообщений и приоритетный доступ к моделям Anthropic.")
        ToolTip(self.account_label, "Аккаунт Claude Code:\nАвторизованный рабочий e-mail и текущая модель.")
        ToolTip(self.source_label, "Источник синхронизации: Claude CLI\nДанные получены напрямую из официального CLI без расхода токенов.")
        ToolTip(self.refresh_btn, "Обновить квоты:\nПринудительно запросить актуальные проценты расхода сессии и недели через claude /usage.")
        ToolTip(self.session_title, "5-часовое сессионное окно Claude:\nПосле первого запроса лимиты фиксируются на 5 часов. Когда таймер доходит до нуля, окно сбрасывается обратно в 100% доступности.")
        ToolTip(self.session_usage_label, "Расход сессионного окна:\nПроцент использованных запросов и оставшийся запас в текущем 5-часовом окне.")
        ToolTip(self.weekly_title, "Недельный лимит Claude (All models + Fable):\nОфициальный недельный пул токенов подписки. Сбрасывается раз в неделю в указанный день и время.")
        ToolTip(self.weekly_usage_label, "Расход недельной квоты:\nСуммарный процент израсходованных сообщений за текущую неделю.")

    def _handle_refresh(self):
        if not self.on_refresh:
            return
        self.refresh_btn.configure(text="⏳ Обновление...", state="disabled")
        def _done():
            if self.winfo_exists():
                self.after(0, lambda: self.refresh_btn.configure(text="🔄 Обновить", state="normal"))
        self.on_refresh(callback=_done)

    def update_status(self, q: Dict[str, Any]):
        # 1. Обновляем план и аккаунт
        sub = q.get("subscription", "Max").upper()
        self.plan_badge.configure(text=f"★ CLAUDE {sub}")
        
        email = q.get("email", "")
        model = q.get("model", "")
        account_text = f"{email} • {model}" if email and model else (email or model)
        self.account_label.configure(text=account_text)
        
        # 2. Источник синхронизации
        source = q.get("source", "")
        if source:
            self.source_label.configure(text=f"✓ {source}")
            
        # 3. Сессионное 5-часовое окно
        session_used = q.get("session_used_pct", 0)
        session_free = max(0, 100 - session_used)
        session_live_reset = q.get("session_resets_str", "")
        
        if q["active"]:
            self.session_usage_label.configure(
                text=f"{session_used}% использовано · {session_free}% свободно",
                text_color="#34d399" if session_used < 60 else ("#fbbf24" if session_used < 85 else "#f87171")
            )
            
            time_progress = q.get("progress", 0.0)
            bar_val = max(session_used / 100.0, time_progress)
            self.session_progress_bar.set(bar_val)
            
            bar_color = "#10b981" if bar_val < 0.6 else ("#f59e0b" if bar_val < 0.85 else "#ef4444")
            self.session_progress_bar.configure(progress_color=bar_color)
            
            reset_display = session_live_reset or f"в {q.get('reset_time_str', '--:--')}"
            self.session_reset_label.configure(text=f"Сброс окна: {reset_display}")
            self.session_status_label.configure(
                text=f"Осталось: {q.get('remaining_str', '--:--')}",
                text_color="#10b981"
            )
        else:
            if session_live_reset:
                self.session_usage_label.configure(
                    text=f"{session_used}% использовано · {session_free}% свободно",
                    text_color="#34d399"
                )
                self.session_progress_bar.set(session_used / 100.0)
                self.session_progress_bar.configure(progress_color="#10b981")
                self.session_reset_label.configure(text=f"Сброс окна: {session_live_reset}")
                self.session_status_label.configure(text="Сессия активна", text_color="#10b981")
            else:
                self.session_usage_label.configure(text="100% свободно", text_color="#34d399")
                self.session_progress_bar.set(0.0)
                self.session_progress_bar.configure(progress_color="#27272a")
                self.session_reset_label.configure(text="5-часовое окно откроется при следующем запросе")
                self.session_status_label.configure(text="Сброшено", text_color="#71717a")
                
        # 4. Недельный лимит (Все модели + Fable)
        w_has_data = q.get("weekly_has_data", False)
        w_used = q.get("weekly_used_pct", 0)
        w_free = q.get("weekly_remaining_pct", 100)
        w_resets = q.get("weekly_resets_str", "")
        f_used = q.get("fable_used_pct", 0)
        
        if w_has_data or w_resets:
            self.weekly_usage_label.configure(
                text=f"{w_used}% использовано · {w_free}% доступно",
                text_color="#34d399" if w_used < 60 else ("#fbbf24" if w_used < 85 else "#f87171")
            )
            w_prog = min(1.0, max(0.0, w_used / 100.0))
            self.weekly_progress_bar.set(w_prog)
            w_color = "#10b981" if w_prog < 0.6 else ("#f59e0b" if w_prog < 0.85 else "#ef4444")
            self.weekly_progress_bar.configure(progress_color=w_color)
            
            if w_resets:
                self.weekly_reset_label.configure(text=f"Сброс квоты: {w_resets} (Europe/Moscow)")
            else:
                self.weekly_reset_label.configure(text="Недельный лимит синхронизирован")
                
            if f_used > 0:
                self.weekly_fable_label.configure(text=f"Fable: {f_used}% использовано")
            else:
                self.weekly_fable_label.configure(text="")
        else:
            self.weekly_usage_label.configure(text="Загрузка...", text_color="#71717a")
            self.weekly_progress_bar.set(0.0)
            self.weekly_progress_bar.configure(progress_color="#27272a")
            self.weekly_reset_label.configure(text="Синхронизация официальной квоты Claude...")
            self.weekly_fable_label.configure(text="")


class FeatureCard(ctk.CTkFrame):
    """Карточка системной настройки/твика в стиле ExitLag с тумблером."""
    def __init__(
        self,
        master,
        icon: str,
        title: str,
        description: str,
        variable: ctk.BooleanVar,
        badge_text: str = "",
        footer_note: str = "",
        command = None,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color="#14151d",
            border_width=1,
            border_color="#212330",
            corner_radius=10,
            **kwargs
        )
        self.variable = variable
        self.command = command
        
        # 1. Header (Icon + Title + Badge on left, CTkSwitch on right)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 6))
        
        left_box = ctk.CTkFrame(header, fg_color="transparent")
        left_box.pack(side="left", fill="y")
        
        self.icon_label = ctk.CTkLabel(
            left_box,
            text=icon,
            font=("Segoe UI Emoji", 16)
        )
        self.icon_label.pack(side="left", padx=(0, 8))
        
        self.title_label = ctk.CTkLabel(
            left_box,
            text=title,
            font=("Inter", 13, "bold"),
            text_color="#f4f4f5"
        )
        self.title_label.pack(side="left")
        
        if badge_text:
            b_fg = "#1e293b" if "Бета" in badge_text else "#064e3b"
            b_tc = "#38bdf8" if "Бета" in badge_text else "#34d399"
            badge = ctk.CTkLabel(
                left_box,
                text=badge_text,
                font=("Inter", 9, "bold"),
                fg_color=b_fg,
                text_color=b_tc,
                corner_radius=4,
                padx=6,
                pady=1
            )
            badge.pack(side="left", padx=(8, 0))
            
        self.switch = ctk.CTkSwitch(
            header,
            text="",
            width=46,
            height=24,
            switch_width=44,
            switch_height=22,
            corner_radius=11,
            variable=variable,
            progress_color="#10b981",
            button_color="#ffffff",
            button_hover_color="#e4e4e7",
            fg_color="#27272a",
            command=self._on_toggle
        )
        self.switch.pack(side="right")
        
        # 2. Description
        self.desc_label = ctk.CTkLabel(
            self,
            text=description,
            font=("Inter", 11),
            text_color="#9ca3af",
            justify="left",
            wraplength=340
        )
        self.desc_label.pack(anchor="w", padx=14, pady=(0, 6))
        
        # 3. Footer note
        if footer_note:
            self.footer_label = ctk.CTkLabel(
                self,
                text=footer_note,
                font=("Inter", 10),
                text_color="#52525b",
                justify="left"
            )
            self.footer_label.pack(anchor="w", padx=14, pady=(0, 10))

        # Tooltip
        tip_text = f"{title}:\n{description}"
        if footer_note:
            tip_text += f"\n\nПодсказка: {footer_note}"
        ToolTip(self.switch, f"Переключатель опции:\nВключить или выключить '{title}'")
        ToolTip(self.title_label, tip_text)
        ToolTip(self.desc_label, tip_text)

    def _on_toggle(self):
        if self.command:
            self.command()


class ConnectionTile(ctk.CTkFrame):
    """Карточка подключения/пресета в стиле ExitLag."""
    def __init__(
        self,
        master,
        icon: str,
        name: str,
        subtitle: str,
        is_active: bool,
        on_toggle = None,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color="#14151d",
            border_width=1,
            border_color="#2e3244" if is_active else "#212330",
            corner_radius=10,
            **kwargs
        )
        self.on_toggle = on_toggle
        self.is_active_var = ctk.BooleanVar(value=is_active)
        
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=12, pady=10)
        
        # Icon badge on left
        icon_box = ctk.CTkFrame(inner, width=38, height=38, corner_radius=8, fg_color="#1e202b")
        icon_box.pack(side="left", padx=(0, 10))
        icon_box.pack_propagate(False)
        ctk.CTkLabel(icon_box, text=icon, font=("Segoe UI Emoji", 18)).place(relx=0.5, rely=0.5, anchor="center")
        
        # Title + Subtitle
        text_box = ctk.CTkFrame(inner, fg_color="transparent")
        text_box.pack(side="left", fill="y", expand=True)
        
        self.title_lbl = ctk.CTkLabel(text_box, text=name, font=("Inter", 12, "bold"), text_color="#f4f4f5", anchor="w")
        self.title_lbl.pack(anchor="w")
        
        self.sub_lbl = ctk.CTkLabel(text_box, text=subtitle, font=("Inter", 10), text_color="#71717a", anchor="w")
        self.sub_lbl.pack(anchor="w")
        
        # Switch on right
        self.switch = ctk.CTkSwitch(
            inner,
            text="",
            width=42,
            height=22,
            switch_width=40,
            switch_height=20,
            corner_radius=10,
            variable=self.is_active_var,
            progress_color="#10b981",
            button_color="#ffffff",
            fg_color="#27272a",
            command=self._handle_click
        )
        self.switch.pack(side="right")

        # Tooltip
        tile_tip = f"Профиль: {name} ({subtitle})\nНажмите на переключатель справа, чтобы сделать этот профиль активным для фоновых пингов."
        ToolTip(self.switch, f"Переключатель профиля:\nСделать '{name}' активным для автоматических запусков")
        ToolTip(self.title_lbl, tile_tip)
        ToolTip(self.sub_lbl, tile_tip)
        ToolTip(icon_box, tile_tip)

    def _handle_click(self):
        if self.on_toggle:
            self.on_toggle(self.is_active_var.get())

    def set_active(self, active: bool):
        self.is_active_var.set(active)
        self.configure(border_color="#ef4444" if active else "#212330")


class SessionStatsCard(ctk.CTkFrame):
    """Карточка данных последней сессии в стиле ExitLag."""
    def __init__(self, master, on_run_now=None, **kwargs):
        super().__init__(
            master,
            fg_color="#14151d",
            border_width=1,
            border_color="#212330",
            corner_radius=10,
            **kwargs
        )
        self.on_run_now = on_run_now
        
        top_row = ctk.CTkFrame(self, fg_color="transparent")
        top_row.pack(fill="x", padx=14, pady=(12, 6))
        
        left_h = ctk.CTkFrame(top_row, fg_color="transparent")
        left_h.pack(side="left")
        
        ctk.CTkLabel(left_h, text="⚡", font=("Segoe UI Emoji", 14), text_color="#ef4444").pack(side="left", padx=(0, 6))
        self.model_lbl = ctk.CTkLabel(left_h, text="Claude Code (Opus 5)", font=("Inter", 13, "bold"), text_color="#f4f4f5")
        self.model_lbl.pack(side="left")
        
        self.duration_lbl = ctk.CTkLabel(top_row, text="Длительность: 0.00с", font=("Inter", 11), text_color="#a1a1aa")
        self.duration_lbl.pack(side="right")
        
        stats_frame = ctk.CTkFrame(self, fg_color="#0f1016", corner_radius=8)
        stats_frame.pack(fill="x", padx=14, pady=(4, 10))
        
        col_cfg = [
            ("Задержка CLI", "stat_latency", "~1.1 сек"),
            ("Ответ", "stat_code", "200 OK"),
            ("Расход", "stat_tokens", "0 токенов"),
            ("Статус окна", "stat_status", "Активен")
        ]
        
        self.stat_labels = {}
        for i, (title, key, def_val) in enumerate(col_cfg):
            cell = ctk.CTkFrame(stats_frame, fg_color="transparent")
            cell.pack(side="left", fill="both", expand=True, padx=8, pady=8)
            
            ctk.CTkLabel(cell, text=title, font=("Inter", 10), text_color="#71717a").pack(anchor="w")
            lbl = ctk.CTkLabel(cell, text=def_val, font=("Consolas", 12, "bold"), text_color="#10b981" if "OK" in def_val or "1.1" in def_val else "#f4f4f5")
            lbl.pack(anchor="w")
            self.stat_labels[key] = lbl
            
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=(0, 10))
        
        self.summary_lbl = ctk.CTkLabel(btn_row, text="Готов к отправке проверочного пинга", font=("Inter", 11), text_color="#71717a")
        self.summary_lbl.pack(side="left")
        
        if self.on_run_now:
            self.run_btn = ctk.CTkButton(
                btn_row,
                text="⚡ Быстрый пинг сейчас",
                font=("Inter", 11, "bold"),
                fg_color="#ef4444",
                hover_color="#dc2626",
                text_color="#ffffff",
                height=28,
                corner_radius=6,
                command=self.on_run_now
            )
            self.run_btn.pack(side="right")
            ToolTip(self.run_btn, "Быстрый проверочный пинг:\nОтправляет команду в Claude прямо сейчас, чтобы сразу прогреть и открыть 5-часовое окно лимитов без ожидания по таймеру.")
 
        # Tooltips для ячеек метрик
        ToolTip(self.stat_labels["stat_latency"], "Задержка CLI:\nСколько секунд заняло выполнение проверочной команды в консоли Windows.")
        ToolTip(self.stat_labels["stat_code"], "Код ответа HTTP/CLI:\n200 OK означает успешный ответ от сервера Anthropic без ошибок.")
        ToolTip(self.stat_labels["stat_tokens"], "Расход токенов:\nКоличество токенов контекста, потраченных на проверочный запрос.")
        ToolTip(self.model_lbl, "Модель Claude:\nТекущая активная архитектура модели Claude для отправки проверочных запросов.")

    def update_stats(self, stats: Dict[str, Any], quota_status: Dict[str, Any]):
        dur = stats.get("duration", 0.0)
        self.duration_lbl.configure(text=f"Длительность: {dur:.2f}с")
        
        code = stats.get("exit_code", 0)
        st_text = stats.get("status", "200 OK")
        self.stat_labels["stat_code"].configure(
            text=st_text,
            text_color="#10b981" if code == 0 else "#ef4444"
        )
        self.stat_labels["stat_latency"].configure(text=f"{dur:.2f} сек")
        
        summary = stats.get("summary", "")
        if summary:
            self.summary_lbl.configure(text=summary)
            
        model = quota_status.get("model", "")
        if model:
            self.model_lbl.configure(text=f"Claude ({model})")
            
        is_active = quota_status.get("active", False)
        self.stat_labels["stat_status"].configure(
            text="Окно открыто" if is_active else "Ожидание",
            text_color="#10b981" if is_active else "#71717a"
        )
