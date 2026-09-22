import os
import datetime
import webbrowser
from tkinter import filedialog
from typing import List

import customtkinter as ctk

from src.config import CLI_PRESETS, APP_VERSION, DAY_CODES
from src.autostart import set_autostart, check_autostart
from src.scheduler import parse_hhmm, ping_time_for_target
from src.i18n import t, set_lang, get_lang, LANGUAGES
from src import applog, ipc
from src.ui.components import (ConsoleLog, QuotaWidget, FeatureCard, ConnectionTile,
                               NextPingCard, TipsCard, ToolTip)

# ExitLag-inspired Dark Theme Palette
BG_COLOR = "#0c0d12"
SIDEBAR_BG = "#08090d"
HEADER_BG = "#0e0f15"
CARD_COLOR = "#14151d"
BORDER_COLOR = "#212330"
TEXT_COLOR = "#f4f4f5"
MUTED_COLOR = "#71717a"
MUTED_LIGHT = "#a1a1aa"
ACCENT_COLOR = "#10b981"
ACCENT_HOVER = "#059669"
CORAL_COLOR = "#ef4444"
CORAL_DARK = "#2b1115"
DANGER_HOVER = "#dc2626"
FIELD_BG = "#0c0d12"
CHIP_BG = "#181924"

LOG_BUFFER_MAX = 500
HOME_TILES = [
    ("Claude Code", "⚡"),
    ("Claude Opus Ping", "🧠"),
    ("Claude Sonnet", "🚀"),
    ("Claude Haiku", "🔔"),
]

ctk.set_appearance_mode("Dark")


def _small_button(master, text, command, width=None, **kw):
    opts = dict(font=("Inter", 11, "bold"), height=28, fg_color=CHIP_BG, hover_color=BORDER_COLOR,
                border_width=1, border_color=BORDER_COLOR, text_color=MUTED_LIGHT, command=command)
    if width:
        opts["width"] = width
    opts.update(kw)
    return ctk.CTkButton(master, text=text, **opts)


class MainWindow(ctk.CTk):
    def __init__(self, scheduler, on_close_callback):
        super().__init__()
        self.scheduler = scheduler
        self.on_close_callback = on_close_callback
        self._log_buffer: List[tuple] = []

        self.title(f"Claude Pulse {APP_VERSION}")
        self.geometry("1100x760")
        self.minsize(980, 660)
        self.configure(fg_color=BG_COLOR)
        self.protocol("WM_DELETE_WINDOW", self.on_close_callback)

        self.scheduler.set_log_callback(self._display_log)
        self._build_all()
        self._switch_page("home")
        self._start_timer_updater()

    # ----------------------------------------------------
    # Построение (повторяется при смене языка)
    # ----------------------------------------------------
    def _build_all(self):
        self.times_entries = []
        self.target_entries = []
        self.day_buttons = {}
        self.nav_buttons = {}
        self.pages = {}
        self.connection_tiles = {}

        self.master_var = ctk.BooleanVar(value=self.scheduler.is_master_enabled())
        self.mode_var = ctk.StringVar(value="fixed")
        self.preset_var = ctk.StringVar(value="Claude Code")
        self.wake_var = ctk.BooleanVar(value=False)
        self.auto_var = ctk.BooleanVar(value=False)
        self.notify_var = ctk.BooleanVar(value=True)
        self.hidden_var = ctk.BooleanVar(value=True)
        self.catchup_var = ctk.BooleanVar(value=True)
        self.alerts_var = ctk.BooleanVar(value=True)
        self.skip_open_var = ctk.BooleanVar(value=True)
        self.updates_var = ctk.BooleanVar(value=True)

        self.root_container = ctk.CTkFrame(self, fg_color="transparent")
        self.root_container.pack(fill="both", expand=True)
        self._build_sidebar()
        self._build_header()
        self.body_container = ctk.CTkFrame(self.right_area, fg_color="transparent")
        self.body_container.pack(fill="both", expand=True)
        self._build_page_home()
        self._build_page_presets()
        self._build_page_schedule()
        self._build_page_system()
        self._build_page_logs()
        self._load_config()

    def _rebuild(self):
        page = getattr(self, "current_page", "home")
        ToolTip.hide_all()
        self.root_container.destroy()
        self._build_all()
        self._switch_page(page)

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self.root_container, width=74, fg_color=SIDEBAR_BG, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        logo_box = ctk.CTkFrame(self.sidebar, width=54, height=54, fg_color="transparent")
        logo_box.pack(pady=(14, 18))
        ctk.CTkLabel(logo_box, text="⚡", font=("Segoe UI Emoji", 26), text_color=CORAL_COLOR).pack()
        ctk.CTkLabel(logo_box, text="PULSE", font=("Inter", 9, "bold"), text_color="#f87171").pack()
        ToolTip(logo_box, t("app.tagline"))

        for page_id, icon in (("home", "🏠"), ("presets", "⚡"), ("schedule", "⏰"), ("system", "🛠️"), ("logs", "📜")):
            btn = ctk.CTkButton(
                self.sidebar, text=icon, font=("Segoe UI Emoji", 19), width=52, height=46, corner_radius=10,
                fg_color="transparent", hover_color="#181922", text_color=MUTED_COLOR,
                command=lambda pid=page_id: self._switch_page(pid)
            )
            btn.pack(pady=4)
            self.nav_buttons[page_id] = btn
            ToolTip(btn, t(f"nav.{page_id}"))

        bottom_box = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom_box.pack(side="bottom", pady=14)
        ver_lbl = ctk.CTkLabel(bottom_box, text=f"v{APP_VERSION}", font=("Inter", 9, "bold"), text_color="#52525b")
        ver_lbl.pack()

    def _build_header(self):
        self.right_area = ctk.CTkFrame(self.root_container, fg_color=BG_COLOR, corner_radius=0)
        self.right_area.pack(side="right", fill="both", expand=True)

        self.header_bar = ctk.CTkFrame(self.right_area, height=56, fg_color=HEADER_BG, corner_radius=0,
                                       border_width=1, border_color="#181a24")
        self.header_bar.pack(fill="x")
        self.header_bar.pack_propagate(False)

        self.master_pill = ctk.CTkFrame(self.header_bar, fg_color=CARD_COLOR, corner_radius=18,
                                        border_width=1, border_color="#064e3b")
        self.master_pill.pack(side="left", padx=16, pady=10)
        self.master_status_lbl = ctk.CTkLabel(self.master_pill, text="", font=("Inter", 12, "bold"), text_color="#34d399")
        self.master_status_lbl.pack(side="left", padx=(12, 8), pady=4)
        self.master_switch = ctk.CTkSwitch(
            self.master_pill, text="", width=44, height=22, switch_width=42, switch_height=20, corner_radius=10,
            variable=self.master_var, progress_color=ACCENT_COLOR, button_color="#ffffff", fg_color="#27272a",
            command=self._toggle_master
        )
        self.master_switch.pack(side="left", padx=(0, 6), pady=4)
        ToolTip(self.master_pill, t("master.tip"))

        self.next_run_pill = ctk.CTkLabel(self.header_bar, text="", font=("Inter", 12, "bold"), text_color="#e4e4e7",
                                          fg_color=CARD_COLOR, corner_radius=8, padx=14, pady=6)
        self.next_run_pill.pack(side="left", padx=12)
        ToolTip(self.next_run_pill, t("next.tip"))

        right_btns = ctk.CTkFrame(self.header_bar, fg_color="transparent")
        right_btns.pack(side="right", padx=16)
        self.update_btn = ctk.CTkButton(right_btns, text="", font=("Inter", 11, "bold"), height=30,
                                        fg_color=CORAL_COLOR, hover_color=DANGER_HOVER, text_color="#ffffff",
                                        corner_radius=6, command=self._open_update)
        ToolTip(self.update_btn, t("update.tip"))
        self._update_anchor = right_btns
        btn_refresh = _small_button(right_btns, t("btn.refresh_quotas"), self._refresh_quotas, height=30,
                                    text_color="#e4e4e7", corner_radius=6)
        btn_refresh.pack(side="left", padx=(0, 8))
        ToolTip(btn_refresh, t("quota.refresh.tip"))
        btn_save = ctk.CTkButton(right_btns, text=t("btn.save"), font=("Inter", 11, "bold"), height=30,
                                 fg_color=ACCENT_COLOR, hover_color=ACCENT_HOVER, text_color="#ffffff",
                                 corner_radius=6, command=self._save_and_apply)
        btn_save.pack(side="left")
        ToolTip(btn_save, t("btn.save.tip"))

    def _switch_page(self, page_id: str):
        self.current_page = page_id
        for pid, btn in self.nav_buttons.items():
            if pid == page_id:
                btn.configure(fg_color=CORAL_DARK, text_color=CORAL_COLOR, border_width=1, border_color=CORAL_COLOR)
            else:
                btn.configure(fg_color="transparent", text_color=MUTED_COLOR, border_width=0)
        for pid, page_widget in self.pages.items():
            if pid == page_id:
                page_widget.pack(fill="both", expand=True, padx=20, pady=16)
            else:
                page_widget.pack_forget()

    def _page(self, page_id: str, scrollable: bool = True):
        cls = ctk.CTkScrollableFrame if scrollable else ctk.CTkFrame
        page = cls(self.body_container, fg_color="transparent")
        self.pages[page_id] = page
        return page

    def _page_title(self, page, title_key: str, sub_key: str):
        ctk.CTkLabel(page, text=t(title_key), font=("Inter", 18, "bold"), text_color=TEXT_COLOR).pack(anchor="w", pady=(0, 2))
        ctk.CTkLabel(page, text=t(sub_key), font=("Inter", 12), text_color=MUTED_COLOR,
                     justify="left", wraplength=880).pack(anchor="w", pady=(0, 12))

    def _card(self, master):
        card = ctk.CTkFrame(master, fg_color=CARD_COLOR, corner_radius=12, border_width=1, border_color=BORDER_COLOR)
        card.pack(fill="x", pady=(0, 14), ipady=10)
        return card

    def _field_label(self, card, title_key: str, sub_key: str = ""):
        ctk.CTkLabel(card, text=t(title_key), font=("Inter", 13, "bold"), text_color=MUTED_LIGHT).pack(anchor="w", padx=18, pady=(10, 2))
        if sub_key:
            ctk.CTkLabel(card, text=t(sub_key), font=("Inter", 11), text_color=MUTED_COLOR,
                         justify="left", wraplength=860).pack(anchor="w", padx=18, pady=(0, 6))

    # ----------------------------------------------------
    # PAGE 1: HOME
    # ----------------------------------------------------
    def _build_page_home(self):
        page = self._page("home")

        conn_header = ctk.CTkFrame(page, fg_color="transparent")
        conn_header.pack(fill="x", pady=(0, 2))
        ctk.CTkLabel(conn_header, text=t("home.title"), font=("Inter", 16, "bold"), text_color=TEXT_COLOR).pack(side="left")
        ctk.CTkButton(conn_header, text=t("home.to_presets"), font=("Inter", 11, "bold"), fg_color="transparent",
                      hover_color=CHIP_BG, text_color=MUTED_LIGHT,
                      command=lambda: self._switch_page("presets")).pack(side="right")
        ctk.CTkLabel(page, text=t("home.subtitle"), font=("Inter", 11), text_color=MUTED_COLOR).pack(anchor="w", pady=(0, 10))

        tiles_grid = ctk.CTkFrame(page, fg_color="transparent")
        tiles_grid.pack(fill="x", pady=(0, 14))
        tiles_grid.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="tile")
        for idx, (name, icon) in enumerate(HOME_TILES):
            tile = ConnectionTile(tiles_grid, icon=icon, name=name, subtitle=CLI_PRESETS[name],
                                  is_active=False, on_toggle=lambda _a, n=name: self._select_preset(n))
            tile.grid(row=0, column=idx, padx=4, pady=4, sticky="nsew")
            self.connection_tiles[name] = tile

        dash_row = ctk.CTkFrame(page, fg_color="transparent")
        dash_row.pack(fill="x", pady=(0, 14))
        dash_row.grid_columnconfigure(0, weight=3)
        dash_row.grid_columnconfigure(1, weight=2)
        self.quota_widget = QuotaWidget(dash_row, on_refresh=self.scheduler.refresh_live_quota, fg_color=CARD_COLOR,
                                        corner_radius=12, border_width=1, border_color=BORDER_COLOR)
        self.quota_widget.grid(row=0, column=0, padx=(0, 8), sticky="nsew")
        self.next_ping_card = NextPingCard(dash_row, on_run_now=self._run_test,
                                           on_skip_today=self.scheduler.pause_today, on_resume=self.scheduler.resume)
        self.next_ping_card.grid(row=0, column=1, padx=(8, 0), sticky="nsew")

        self.tips_card = TipsCard(page)
        self.tips_card.pack(fill="x", pady=(0, 14))

    def _select_preset(self, name: str):
        self.preset_var.set(name)
        if CLI_PRESETS.get(name):
            self.cmd_entry.delete(0, "end")
            self.cmd_entry.insert(0, CLI_PRESETS[name])
        for t_name, tile in self.connection_tiles.items():
            tile.set_active(t_name == name)
        self.log(t("log.preset_selected", name=self._preset_label(name)), "command")

    @staticmethod
    def _preset_label(name: str) -> str:
        return t("preset.custom") if name == "custom" else name

    # ----------------------------------------------------
    # PAGE 2: PRESETS
    # ----------------------------------------------------
    def _build_page_presets(self):
        page = self._page("presets")
        self._page_title(page, "presets.title", "presets.subtitle")
        card = self._card(page)

        self._field_label(card, "presets.profile", "presets.profile.sub")
        p_row = ctk.CTkFrame(card, fg_color="transparent")
        p_row.pack(fill="x", padx=18, pady=(0, 8))
        for pname, cmd in CLI_PRESETS.items():
            p_btn = _small_button(p_row, self._preset_label(pname), lambda p=pname: self._select_preset(p),
                                  height=30, text_color=TEXT_COLOR)
            p_btn.pack(side="left", padx=(0, 6), pady=2)
            ToolTip(p_btn, cmd or t("preset.custom.tip"))

        self._field_label(card, "presets.command", "presets.command.sub")
        self.cmd_entry = ctk.CTkEntry(card, height=36, font=("Consolas", 13), fg_color=FIELD_BG, border_color=BORDER_COLOR)
        self.cmd_entry.pack(fill="x", padx=18, pady=(0, 8))

        self._field_label(card, "presets.dir", "presets.dir.sub")
        dir_frame = ctk.CTkFrame(card, fg_color="transparent")
        dir_frame.pack(fill="x", padx=18, pady=(0, 8))
        self.dir_entry = ctk.CTkEntry(dir_frame, height=36, font=("Inter", 12), fg_color=FIELD_BG, border_color=BORDER_COLOR)
        self.dir_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        _small_button(dir_frame, t("btn.browse"), self._browse_dir, width=90, height=36).pack(side="right")

        self.test_btn = ctk.CTkButton(card, text=t("btn.test_now"), font=("Inter", 12, "bold"), fg_color=CORAL_COLOR,
                                      hover_color=DANGER_HOVER, text_color="#ffffff", height=38, corner_radius=8,
                                      command=self._run_test)
        self.test_btn.pack(anchor="w", padx=18, pady=(8, 4))
        ctk.CTkLabel(card, text=t("presets.cost_note"), font=("Inter", 11), text_color=MUTED_COLOR,
                     justify="left", wraplength=860).pack(anchor="w", padx=18, pady=(2, 4))

    # ----------------------------------------------------
    # PAGE 3: SCHEDULE
    # ----------------------------------------------------
    def _build_page_schedule(self):
        page = self._page("schedule")
        self._page_title(page, "schedule.title", "schedule.subtitle")
        card = self._card(page)
        self.sched_card = card

        mode_frame = ctk.CTkFrame(card, fg_color="transparent")
        mode_frame.pack(fill="x", padx=20, pady=(12, 10))
        for value in ("target", "fixed", "interval"):
            rb = ctk.CTkRadioButton(mode_frame, text=t(f"mode.{value}"), font=("Inter", 13, "bold"),
                                    variable=self.mode_var, value=value, command=self._toggle_mode,
                                    fg_color=ACCENT_COLOR, text_color=TEXT_COLOR)
            rb.pack(side="left", padx=(0, 28))
            ToolTip(rb, t(f"mode.{value}.tip"))

        # Режим «Свежий лимит к…»
        self.target_frame = ctk.CTkFrame(card, fg_color="transparent")
        ctk.CTkLabel(self.target_frame, text=t("target.explain"), font=("Inter", 12), text_color=MUTED_LIGHT,
                     justify="left", wraplength=860).pack(anchor="w", pady=(0, 8))
        self.target_list_frame = ctk.CTkFrame(self.target_frame, fg_color="transparent")
        self.target_list_frame.pack(fill="x", pady=(0, 6))
        t_row = ctk.CTkFrame(self.target_frame, fg_color="transparent")
        t_row.pack(fill="x")
        _small_button(t_row, t("btn.add_time"), lambda: self._add_chip(self.target_list_frame, self.target_entries, "14:00"),
                      width=110, text_color=TEXT_COLOR).pack(side="left", padx=(0, 12))
        self.target_preview = ctk.CTkLabel(self.target_frame, text="", font=("Consolas", 12, "bold"),
                                           text_color="#34d399", justify="left")
        self.target_preview.pack(anchor="w", pady=(8, 0))
        ctk.CTkLabel(self.target_frame, text=t("target.caveat"), font=("Inter", 11), text_color=MUTED_COLOR,
                     justify="left", wraplength=860).pack(anchor="w", pady=(4, 0))

        # Режим «Точное время»
        self.fixed_time_frame = ctk.CTkFrame(card, fg_color="transparent")
        self.times_list_frame = ctk.CTkFrame(self.fixed_time_frame, fg_color="transparent")
        self.times_list_frame.pack(fill="x", pady=(0, 8))
        actions_row = ctk.CTkFrame(self.fixed_time_frame, fg_color="transparent")
        actions_row.pack(fill="x", pady=(0, 5))
        _small_button(actions_row, t("btn.add_time"), lambda: self._add_chip(self.times_list_frame, self.times_entries),
                      width=110, text_color=TEXT_COLOR).pack(side="left", padx=(0, 12))
        ctk.CTkLabel(actions_row, text=t("schedule.quick"), font=("Inter", 11), text_color=MUTED_COLOR).pack(side="left", padx=(0, 6))
        for pill_t in ["05:00", "08:00", "09:00", "14:00", "20:00"]:
            _small_button(actions_row, f"+{pill_t}",
                          lambda v=pill_t: self._add_chip(self.times_list_frame, self.times_entries, v),
                          width=58, height=26, font=("Inter", 11)).pack(side="left", padx=(0, 6))

        # Дни недели (для «точного времени» и «свежего лимита»)
        self.days_frame = ctk.CTkFrame(card, fg_color="transparent")
        self.days_label = ctk.CTkLabel(self.days_frame, text="", font=("Inter", 12, "bold"), text_color=MUTED_COLOR)
        self.days_label.pack(anchor="w", pady=(10, 5))
        days_inner = ctk.CTkFrame(self.days_frame, fg_color="transparent")
        days_inner.pack(fill="x")
        self.day_vars = {}
        for i, day in enumerate(DAY_CODES):
            var = ctk.BooleanVar(value=True)
            self.day_vars[day] = var
            btn = ctk.CTkButton(days_inner, text=t(f"day.{i}"), width=44, height=30, font=("Inter", 12, "bold"), corner_radius=15)
            btn.pack(side="left", padx=(0, 6))
            btn.configure(command=lambda b=btn, v=var: self._toggle_day_btn(b, v))
            self.day_buttons[day] = btn
            self._update_day_btn_style(btn, True)

        # Режим «Интервал»
        self.interval_frame = ctk.CTkFrame(card, fg_color="transparent")
        ctk.CTkLabel(self.interval_frame, text=t("schedule.interval"), font=("Inter", 12, "bold"),
                     text_color=MUTED_COLOR).pack(anchor="w", pady=(10, 5))
        self.interval_entry = ctk.CTkEntry(self.interval_frame, width=110, height=34, font=("Inter", 13),
                                           fg_color=FIELD_BG, border_color=BORDER_COLOR)
        self.interval_entry.pack(anchor="w")

        ctk.CTkLabel(page, text=t("schedule.save_hint"), font=("Inter", 11), text_color=MUTED_COLOR).pack(anchor="w")

    def _add_chip(self, container, entries: list, val: str = "05:00"):
        chip = ctk.CTkFrame(container, fg_color=CHIP_BG, corner_radius=14, border_width=1, border_color=BORDER_COLOR)
        chip.pack(side="left", padx=(0, 6), pady=2)
        entry = ctk.CTkEntry(chip, width=58, height=26, font=("Inter", 12, "bold"), justify="center",
                             fg_color="transparent", border_width=0, text_color=TEXT_COLOR)
        entry.pack(side="left", padx=(4, 0), pady=2)
        entry.insert(0, val)

        def remove_chip():
            chip.destroy()
            if entry in entries:
                entries.remove(entry)

        ctk.CTkButton(chip, text="✕", width=20, height=20, corner_radius=10, fg_color="transparent",
                      hover_color=DANGER_HOVER, text_color=MUTED_COLOR, font=("Inter", 9),
                      command=remove_chip).pack(side="left", padx=(1, 4), pady=2)
        entries.append(entry)

    def _toggle_mode(self):
        mode = self.mode_var.get()
        for frame in (self.target_frame, self.fixed_time_frame, self.days_frame, self.interval_frame):
            frame.pack_forget()
        if mode == "target":
            self.target_frame.pack(fill="x", padx=20)
            self.days_label.configure(text=t("schedule.days_target"))
            self.days_frame.pack(fill="x", padx=20)
        elif mode == "fixed":
            self.fixed_time_frame.pack(fill="x", padx=20)
            self.days_label.configure(text=t("schedule.days"))
            self.days_frame.pack(fill="x", padx=20)
        else:
            self.interval_frame.pack(fill="x", padx=20)

    def _update_target_preview(self):
        lines = []
        for entry in self.target_entries:
            raw = entry.get().strip()
            p = ping_time_for_target(raw)
            if not p:
                lines.append(t("target.bad", time=raw or "—"))
                continue
            ping = f"{p[0]:02}:{p[1]:02}"
            key = "target.preview_prev_day" if p[2] < 0 else "target.preview"
            lines.append(t(key, ping=ping, target=raw))
        text = "\n".join(lines)
        if self.target_preview.cget("text") != text:
            self.target_preview.configure(text=text)

    def _toggle_day_btn(self, btn, var):
        var.set(not var.get())
        self._update_day_btn_style(btn, var.get())

    def _update_day_btn_style(self, btn, is_active):
        if is_active:
            btn.configure(fg_color=ACCENT_COLOR, hover_color=ACCENT_HOVER, text_color="#ffffff")
        else:
            btn.configure(fg_color=CHIP_BG, hover_color=BORDER_COLOR, text_color=MUTED_COLOR)

    # ----------------------------------------------------
    # PAGE 4: SYSTEM & ALERTS
    # ----------------------------------------------------
    def _build_page_system(self):
        page = self._page("system")
        self._page_title(page, "system.title", "system.subtitle")

        grid_frame = ctk.CTkFrame(page, fg_color="transparent")
        grid_frame.pack(fill="x", pady=(0, 14))
        grid_frame.grid_columnconfigure((0, 1), weight=1, uniform="feat")
        features = [
            ("💰", "feat.skip_open", self.skip_open_var, None),
            ("🔔", "feat.alerts", self.alerts_var, None),
            ("💬", "feat.notify", self.notify_var, None),
            ("🖥️", "feat.autostart", self.auto_var, self._toggle_autostart),
            ("⏱️", "feat.catchup", self.catchup_var, None),
            ("⚡", "feat.wake", self.wake_var, None),
            ("🛡️", "feat.hidden", self.hidden_var, None),
            ("⬆️", "feat.updates", self.updates_var, None),
        ]
        for idx, (icon, key, var, cmd) in enumerate(features):
            card = FeatureCard(grid_frame, icon=icon, title=t(key), description=t(f"{key}.desc"), variable=var,
                               badge_text=t(f"{key}.badge"), footer_note=t(f"{key}.note"), command=cmd)
            card.grid(row=idx // 2, column=idx % 2, padx=6, pady=6, sticky="nsew")

        card = self._card(page)
        self._field_label(card, "settings.levels", "settings.levels.sub")
        self.levels_entry = ctk.CTkEntry(card, width=140, height=34, font=("Inter", 13), fg_color=FIELD_BG, border_color=BORDER_COLOR)
        self.levels_entry.pack(anchor="w", padx=18)

        self._field_label(card, "settings.poll", "settings.poll.sub")
        self.poll_entry = ctk.CTkEntry(card, width=140, height=34, font=("Inter", 13), fg_color=FIELD_BG, border_color=BORDER_COLOR)
        self.poll_entry.pack(anchor="w", padx=18)

        self._field_label(card, "settings.language", "settings.language.sub")
        names = [name for _code, name in LANGUAGES]
        self.lang_switch = ctk.CTkSegmentedButton(card, values=names, command=self._on_language,
                                                  font=("Inter", 12, "bold"), selected_color=CORAL_COLOR,
                                                  selected_hover_color=DANGER_HOVER, unselected_color=CHIP_BG,
                                                  unselected_hover_color="#272938", fg_color=CHIP_BG)
        self.lang_switch.set(dict(LANGUAGES)[get_lang()])
        self.lang_switch.pack(anchor="w", padx=18, pady=(0, 6))

    def _on_language(self, name: str):
        code = next(c for c, n in LANGUAGES if n == name)
        if code == get_lang():
            return
        self.scheduler.config["language"] = code
        self.scheduler.save()
        set_lang(code)
        self._rebuild()
        self.log(t("log.language", name=name), "success")

    # ----------------------------------------------------
    # PAGE 5: LOGS
    # ----------------------------------------------------
    def _build_page_logs(self):
        page = self._page("logs", scrollable=False)
        header = ctk.CTkFrame(page, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(header, text=t("logs.title"), font=("Inter", 18, "bold"), text_color=TEXT_COLOR).pack(side="left")
        _small_button(header, t("btn.copy"), self._copy_log, width=90).pack(side="right", padx=(6, 0))
        _small_button(header, t("btn.clear"), self._clear_log, width=80).pack(side="right")
        folder_btn = _small_button(header, t("btn.log_folder"), self._open_log_folder, width=110)
        folder_btn.pack(side="right", padx=(0, 6))
        ToolTip(folder_btn, t("btn.log_folder.tip", path=str(applog.LOG_FILE)))
        self.console = ConsoleLog(page, fg_color=CARD_COLOR, border_width=1, border_color=BORDER_COLOR)
        self.console.pack(fill="both", expand=True)
        for ts, message, tag in self._log_buffer:
            self.console.write_log(message, tag, ts)

    # ----------------------------------------------------
    # LOGIC & HANDLERS
    # ----------------------------------------------------
    def _toggle_master(self):
        val = self.master_var.get()
        self.scheduler.set_master_enabled(val)
        self._update_master_ui(val)

    def _update_master_ui(self, is_enabled: bool):
        if is_enabled:
            self.master_status_lbl.configure(text=t("master.on"), text_color="#34d399")
            self.master_pill.configure(border_color="#064e3b")
        else:
            self.master_status_lbl.configure(text=t("master.off"), text_color=MUTED_COLOR)
            self.master_pill.configure(border_color="#27272a")

    def _refresh_quotas(self):
        self.scheduler.refresh_live_quota()
        self.log(t("log.refresh_requested"), "command")

    def _copy_log(self):
        text = self.console.get_log_text()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.log(t("log.copied"), "normal")

    def _clear_log(self):
        self._log_buffer.clear()
        self.console.clear_log()

    def _browse_dir(self):
        folder = filedialog.askdirectory()
        if folder:
            self.dir_entry.delete(0, "end")
            self.dir_entry.insert(0, folder)

    def _toggle_autostart(self):
        set_autostart(self.auto_var.get())

    def _load_config(self):
        config = self.scheduler.config
        if not config:
            return
        self.master_var.set(config.get("master_enabled", True))
        self._update_master_ui(self.master_var.get())
        self.mode_var.set(config.get("mode", "fixed"))

        for entries, frame, key, default in ((self.times_entries, self.times_list_frame, "times", "05:00"),
                                            (self.target_entries, self.target_list_frame, "target_times", "14:00")):
            for w in frame.winfo_children():
                w.destroy()
            entries.clear()
            for tm in config.get(key) or [default]:
                self._add_chip(frame, entries, tm)

        self.interval_entry.delete(0, "end")
        self.interval_entry.insert(0, str(config.get("interval_hours", 1)))
        saved_days = config.get("days", [])
        for day, var in self.day_vars.items():
            var.set(day in saved_days)
            self._update_day_btn_style(self.day_buttons[day], var.get())

        preset = config.get("selected_preset", "Claude Code")
        self.preset_var.set(preset)
        for t_name, tile in self.connection_tiles.items():
            tile.set_active(t_name == preset)
        self.cmd_entry.delete(0, "end")
        self.cmd_entry.insert(0, config.get("command", CLI_PRESETS["Claude Code"]))
        self.dir_entry.delete(0, "end")
        self.dir_entry.insert(0, config.get("working_dir", os.path.expanduser("~")))

        self.wake_var.set(config.get("wake_pc", False))
        self.auto_var.set(check_autostart())
        self.notify_var.set(config.get("notify", True))
        self.hidden_var.set(config.get("hidden_console", True))
        self.catchup_var.set(config.get("catch_up_missed", True))
        self.alerts_var.set(config.get("alerts_enabled", True))
        self.skip_open_var.set(config.get("skip_if_open", True))
        self.updates_var.set(config.get("check_updates", True))
        self.levels_entry.delete(0, "end")
        self.levels_entry.insert(0, ", ".join(str(x) for x in config.get("alert_levels", [80, 95])))
        self.poll_entry.delete(0, "end")
        self.poll_entry.insert(0, str(config.get("usage_poll_minutes", 5)))
        self._toggle_mode()

    def _collect_times(self, entries) -> list:
        values = [e.get().strip() for e in entries if e.get().strip()]
        bad = [v for v in values if not parse_hhmm(v)]
        if bad:
            raise ValueError(t("err.bad_times", times=", ".join(bad)))
        return [f"{parse_hhmm(v)[0]:02}:{parse_hhmm(v)[1]:02}" for v in values]

    def _save_and_apply(self):
        try:
            times = self._collect_times(self.times_entries) or ["05:00"]
            target_times = self._collect_times(self.target_entries) or ["14:00"]
            try:
                interval = float(self.interval_entry.get().replace(",", "."))
                assert interval > 0
            except Exception:
                raise ValueError(t("err.bad_interval"))
            try:
                levels = sorted({int(x) for x in self.levels_entry.get().replace(";", ",").split(",") if x.strip()})
                assert levels and all(1 <= x <= 100 for x in levels)
            except Exception:
                raise ValueError(t("err.bad_levels"))
            try:
                poll = float(self.poll_entry.get().replace(",", "."))
                assert poll >= 1
            except Exception:
                raise ValueError(t("err.bad_poll"))
        except ValueError as e:
            self.log(str(e), "error")
            self._switch_page("logs")
            return

        config = dict(self.scheduler.config)  # сохраняем ключи, которых нет на форме
        config.update({
            "master_enabled": self.master_var.get(),
            "mode": self.mode_var.get(),
            "times": times,
            "target_times": target_times,
            "interval_hours": interval,
            "days": [day for day, var in self.day_vars.items() if var.get()],
            "selected_preset": self.preset_var.get(),
            "command": self.cmd_entry.get(),
            "working_dir": self.dir_entry.get(),
            "hidden_console": self.hidden_var.get(),
            "wake_pc": self.wake_var.get(),
            "autostart": self.auto_var.get(),
            "notify": self.notify_var.get(),
            "catch_up_missed": self.catchup_var.get(),
            "alerts_enabled": self.alerts_var.get(),
            "skip_if_open": self.skip_open_var.get(),
            "check_updates": self.updates_var.get(),
            "alert_levels": levels,
            "usage_poll_minutes": poll,
        })
        self.scheduler.set_config(config)
        self.scheduler.save()
        self.log(t("log.saved"), "success")

    def _run_test(self):
        self.scheduler.run_now()

    def log(self, message: str, tag: str = "normal"):
        """Сообщения самого окна: в файл журнала и на экран."""
        applog.write(message, tag)
        self._display_log(message, tag)

    def _display_log(self, message: str, tag: str = "normal"):
        ts = datetime.datetime.now().strftime("%H:%M:%S")

        def _write():
            self._log_buffer.append((ts, message, tag))
            del self._log_buffer[:-LOG_BUFFER_MAX]
            try:
                self.console.write_log(message, tag, ts)
            except Exception:
                pass
        self.after(0, _write)

    def _start_timer_updater(self):
        def update():
            try:
                self.next_run_pill.configure(text=t("next.pill", next=self.scheduler.get_next_run()))
                q = self.scheduler.get_quota_status()
                self.quota_widget.update_status(q)
                self.next_ping_card.update_state(self.scheduler.next_ping_info(),
                                                 self.scheduler.get_last_run_stats(),
                                                 self.scheduler.config.get("command", ""))
                self._update_banner()
                for command in ipc.take():
                    self.handle_command(command)
                self.tips_card.update_tips(q.get("tips"))
                if self.mode_var.get() == "target":
                    self._update_target_preview()
            except Exception:
                pass
            self.after(1000, update)
        self.after(300, update)

    # ----------------------------------------------------
    # Обновления, журнал, команды из уведомлений
    # ----------------------------------------------------
    def _update_banner(self):
        latest = self.scheduler.updates.latest
        if latest:
            text = t("update.available", version=latest)
            if self.update_btn.cget("text") != text:
                self.update_btn.configure(text=text)
            if not self.update_btn.winfo_ismapped():
                self.update_btn.pack(side="left", padx=(0, 8), before=self._update_anchor.winfo_children()[1])
        elif self.update_btn.winfo_ismapped():
            self.update_btn.pack_forget()

    def _open_update(self):
        webbrowser.open(self.scheduler.updates.url)

    def _open_log_folder(self):
        try:
            applog.LOG_DIR.mkdir(parents=True, exist_ok=True)
            os.startfile(applog.LOG_DIR)
        except OSError as e:
            self.log(str(e), "error")

    def show(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def handle_command(self, command: str):
        """Команда из клика по уведомлению или из второго запуска программы."""
        if command == "open":
            self.show()
        elif command == "pause2h":
            self.scheduler.pause(2.0)
        elif command == "pause_today":
            self.scheduler.pause_today()
        elif command == "resume":
            self.scheduler.resume()
        elif command == "ping":
            self.scheduler.run_now()
        elif command == "update":
            self._open_update()
