import customtkinter as ctk
from src.config import save_config, CLI_PRESETS, APP_VERSION
from src.autostart import set_autostart, check_autostart
from src.ui.components import ConsoleLog, QuotaWidget, FeatureCard, ConnectionTile, SessionStatsCard, ToolTip
import threading
import time
from tkinter import filedialog
import os
from typing import Dict, Any

# ExitLag-inspired Dark Theme Palette
BG_COLOR = "#0c0d12"
SIDEBAR_BG = "#08090d"
HEADER_BG = "#0e0f15"
CARD_COLOR = "#14151d"
BORDER_COLOR = "#212330"
BORDER_ACTIVE = "#ef4444"
TEXT_COLOR = "#f4f4f5"
MUTED_COLOR = "#71717a"
MUTED_LIGHT = "#a1a1aa"
ACCENT_COLOR = "#10b981" # Mint/emerald
ACCENT_HOVER = "#059669"
CORAL_COLOR = "#ef4444" # ExitLag coral red
CORAL_DARK = "#2b1115"
DANGER_COLOR = "#ef4444"
DANGER_HOVER = "#dc2626"

ctk.set_appearance_mode("Dark")

class MainWindow(ctk.CTk):
    def __init__(self, scheduler, on_close_callback):
        super().__init__()
        self.scheduler = scheduler
        self.on_close_callback = on_close_callback
        
        self.title(f"Claude Pulse {APP_VERSION}")
        self.geometry("1060x720")
        self.minsize(960, 640)
        self.resizable(True, True)
        self.configure(fg_color=BG_COLOR)
        
        self.protocol("WM_DELETE_WINDOW", self.on_close_callback)
        
        self.times_entries = []
        self.day_buttons = {}
        self.nav_buttons = {}
        self.pages = {}
        self.connection_tiles = {}
        self.current_page = "home"
        
        # State variables
        self.master_var = ctk.BooleanVar(value=self.scheduler.is_master_enabled())
        self.mode_var = ctk.StringVar(value="fixed")
        self.preset_var = ctk.StringVar(value="Claude Code")
        self.wake_var = ctk.BooleanVar(value=False)
        self.auto_var = ctk.BooleanVar(value=False)
        self.notify_var = ctk.BooleanVar(value=True)
        self.hidden_var = ctk.BooleanVar(value=True)
        self.catchup_var = ctk.BooleanVar(value=True)
        self.anthropic_sync_var = ctk.BooleanVar(value=True)
        
        self._build_ui()
        self._load_config()
        self._switch_page("home")
        self._start_timer_updater()
        self.after(500, self.scheduler.refresh_live_quota)
        
    def _build_ui(self):
        # Root container: Left Sidebar + Right Main Area
        self.root_container = ctk.CTkFrame(self, fg_color="transparent")
        self.root_container.pack(fill="both", expand=True)
        
        # ----------------------------------------------------
        # 1. Left Navigation Rail (Sidebar)
        # ----------------------------------------------------
        self.sidebar = ctk.CTkFrame(self.root_container, width=74, fg_color=SIDEBAR_BG, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        
        # Logo / Emblem at top
        logo_box = ctk.CTkFrame(self.sidebar, width=54, height=54, fg_color="transparent")
        logo_box.pack(pady=(14, 18))
        
        logo_icon = ctk.CTkLabel(logo_box, text="⚡", font=("Segoe UI Emoji", 26), text_color=CORAL_COLOR)
        logo_icon.pack()
        logo_sub = ctk.CTkLabel(logo_box, text="PULSE", font=("Inter", 9, "bold"), text_color="#f87171")
        logo_sub.pack()
        ToolTip(logo_box, "Claude Pulse 3.0 VER WORK\nФоновый менеджер сессий и квот Claude для автоматического удержания 5-часового окна")
        
        # Nav Buttons
        nav_defs = [
            ("home", "🏠", "Главная"),
            ("presets", "⚡", "Подключения"),
            ("schedule", "⏰", "Расписание"),
            ("system", "🛠️", "Твики ПК"),
            ("logs", "📜", "Терминал")
        ]
        
        nav_tips = {
            "home": "🏠 Главная страница\nСводка квот, активный пресет и статус последнего проверочного пинга",
            "presets": "⚡ Подключения и CLI\nВыбор AI-модели (Opus 5, Sonnet 3.7) и детальная настройка команды",
            "schedule": "⏰ Расписание запусков\nНастройка точного времени или интервала и выбор дней недели",
            "system": "🛠️ Твики ПК и Оптимизация\nАвтозапуск с Windows, вывод из спящего режима, уведомления",
            "logs": "📜 Терминал логов\nПросмотр живых ответов от Claude, времени выполнения и истории событий"
        }
        
        for page_id, icon, label in nav_defs:
            btn = ctk.CTkButton(
                self.sidebar,
                text=icon,
                font=("Segoe UI Emoji", 19),
                width=52,
                height=46,
                corner_radius=10,
                fg_color="transparent",
                hover_color="#181922",
                text_color=MUTED_COLOR,
                command=lambda pid=page_id: self._switch_page(pid)
            )
            btn.pack(pady=4)
            self.nav_buttons[page_id] = btn
            ToolTip(btn, nav_tips.get(page_id, label))
            
        # Bottom spacer & version info
        bottom_box = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom_box.pack(side="bottom", pady=14)
        
        # Claude badge circle
        avatar = ctk.CTkFrame(bottom_box, width=36, height=36, corner_radius=18, fg_color="#064e3b")
        avatar.pack(pady=(0, 6))
        avatar.pack_propagate(False)
        ctk.CTkLabel(avatar, text="★", font=("Inter", 13, "bold"), text_color="#34d399").place(relx=0.5, rely=0.5, anchor="center")
        ToolTip(avatar, "Тариф: Claude Max\nАккаунт авторизован в Claude Code")
        
        ver_lbl = ctk.CTkLabel(bottom_box, text="v3.0", font=("Inter", 9, "bold"), text_color="#52525b")
        ver_lbl.pack()
        ToolTip(ver_lbl, "Версия сборки: Claude Pulse 3.0 VER WORK")
        
        # ----------------------------------------------------
        # 2. Right Area (Header Bar + Content Container)
        # ----------------------------------------------------
        self.right_area = ctk.CTkFrame(self.root_container, fg_color=BG_COLOR, corner_radius=0)
        self.right_area.pack(side="right", fill="both", expand=True)
        
        # Top Header Bar (ExitLag Style)
        self.header_bar = ctk.CTkFrame(self.right_area, height=56, fg_color=HEADER_BG, corner_radius=0, border_width=1, border_color="#181a24")
        self.header_bar.pack(fill="x")
        self.header_bar.pack_propagate(False)
        
        # Left side: Master Switch Pill (ExitLag ON/OFF)
        self.master_pill = ctk.CTkFrame(self.header_bar, fg_color=CARD_COLOR, corner_radius=18, border_width=1, border_color="#064e3b")
        self.master_pill.pack(side="left", padx=16, pady=10)
        
        self.master_status_lbl = ctk.CTkLabel(
            self.master_pill,
            text="● Claude Pulse ON",
            font=("Inter", 12, "bold"),
            text_color="#34d399"
        )
        self.master_status_lbl.pack(side="left", padx=(12, 8), pady=4)
        
        self.master_switch = ctk.CTkSwitch(
            self.master_pill,
            text="",
            width=44,
            height=22,
            switch_width=42,
            switch_height=20,
            corner_radius=10,
            variable=self.master_var,
            progress_color=ACCENT_COLOR,
            button_color="#ffffff",
            fg_color="#27272a",
            command=self._toggle_master
        )
        self.master_switch.pack(side="left", padx=(0, 6), pady=4)
        
        ToolTip(
            self.master_pill,
            "Главный рубильник фоновой работы:\n"
            "• ВКЛ (зеленый): программа отправляет запросы в Claude точно по вашему расписанию.\n"
            "• ВЫКЛ (серый): расписание полностью на паузе, никакие команды не выполняются."
        )
        ToolTip(
            self.master_switch,
            "Включить или выключить автоматические фоновые пинги Claude Pulse."
        )
        
        # Center: Next run pill
        self.next_run_pill = ctk.CTkLabel(
            self.header_bar,
            text="⏳ След. запуск: ...",
            font=("Inter", 12, "bold"),
            text_color="#e4e4e7",
            fg_color=CARD_COLOR,
            corner_radius=8,
            padx=14,
            pady=6
        )
        self.next_run_pill.pack(side="left", padx=12)
        ToolTip(
            self.next_run_pill,
            "Таймер обратного отсчета:\n"
            "Показывает точное время, когда программа автоматически отправит следующий проверочный запрос в Claude."
        )
        
        # Right: Quick action buttons
        right_btns = ctk.CTkFrame(self.header_bar, fg_color="transparent")
        right_btns.pack(side="right", padx=16)
        
        btn_refresh = ctk.CTkButton(
            right_btns,
            text="🔄 Обновить квоты",
            font=("Inter", 11, "bold"),
            width=120,
            height=30,
            fg_color="#181924",
            hover_color="#272938",
            border_width=1,
            border_color=BORDER_COLOR,
            text_color="#e4e4e7",
            corner_radius=6,
            command=self._refresh_quotas
        )
        btn_refresh.pack(side="left", padx=(0, 8))
        ToolTip(
            btn_refresh,
            "Обновить официальные квоты:\n"
            "Запрашивает у серверов Anthropic свежие проценты расхода 5-часовой сессии и недельного лимита (через claude /usage)."
        )
        
        btn_save = ctk.CTkButton(
            right_btns,
            text="💾 Сохранить",
            font=("Inter", 11, "bold"),
            width=100,
            height=30,
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            text_color="#ffffff",
            corner_radius=6,
            command=self._save_and_apply
        )
        btn_save.pack(side="left")
        ToolTip(
            btn_save,
            "Сохранить настройки:\n"
            "Записывает все изменения расписания, выбранную модель, папку и системные твики в постоянную память."
        )
        
        # Main Body Pages Container
        self.body_container = ctk.CTkFrame(self.right_area, fg_color="transparent")
        self.body_container.pack(fill="both", expand=True)
        
        # Build individual pages
        self._build_page_home()
        self._build_page_presets()
        self._build_page_schedule()
        self._build_page_system()
        self._build_page_logs()
        
    def _switch_page(self, page_id: str):
        self.current_page = page_id
        for pid, btn in self.nav_buttons.items():
            if pid == page_id:
                btn.configure(
                    fg_color=CORAL_DARK,
                    text_color=CORAL_COLOR,
                    border_width=1,
                    border_color=CORAL_COLOR
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=MUTED_COLOR,
                    border_width=0
                )
                
        for pid, page_widget in self.pages.items():
            if pid == page_id:
                page_widget.pack(fill="both", expand=True, padx=20, pady=16)
            else:
                page_widget.pack_forget()

    # ----------------------------------------------------
    # PAGE 1: HOME (Dashboard)
    # ----------------------------------------------------
    def _build_page_home(self):
        page = ctk.CTkScrollableFrame(self.body_container, fg_color="transparent")
        self.pages["home"] = page
        
        # Section 1: Connections Header
        conn_header = ctk.CTkFrame(page, fg_color="transparent")
        conn_header.pack(fill="x", pady=(0, 2))
        
        ctk.CTkLabel(
            conn_header,
            text="Подключения и Пресеты",
            font=("Inter", 16, "bold"),
            text_color=TEXT_COLOR
        ).pack(side="left")
        
        link_btn = ctk.CTkButton(
            conn_header,
            text="Перейти к подключениям ➔",
            font=("Inter", 11, "bold"),
            fg_color="transparent",
            hover_color="#181924",
            text_color=MUTED_LIGHT,
            command=lambda: self._switch_page("presets")
        )
        link_btn.pack(side="right")
        ToolTip(link_btn, "Перейти в расширенный раздел настройки параметров команд, папок и моделей")
        
        ctk.CTkLabel(
            page,
            text="Выберите активный профиль для регулярного поддержания открытого 5-часового окна лимитов",
            font=("Inter", 11),
            text_color=MUTED_COLOR
        ).pack(anchor="w", pady=(0, 10))
        
        # Section 1 Grid: Connection Tiles (ExitLag style)
        tiles_grid = ctk.CTkFrame(page, fg_color="transparent")
        tiles_grid.pack(fill="x", pady=(0, 14))
        tiles_grid.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="tile")
        
        tiles_meta = [
            ("Claude Code", "⚡", "Автоматический", 'claude -p "ок"'),
            ("Claude Opus Ping", "🧠", "Ручной / Авто", 'claude -p "ок" --model opus'),
            ("Claude Sonnet", "🚀", "Ручной / Авто", 'claude -p "ок" --model sonnet'),
            ("Claude (ping)", "🔔", "Легкий пинг", 'claude -p "ping"')
        ]
        
        for idx, (name, icon, sub, cmd) in enumerate(tiles_meta):
            is_active = (name == self.preset_var.get())
            tile = ConnectionTile(
                tiles_grid,
                icon=icon,
                name=name,
                subtitle=sub,
                is_active=is_active,
                on_toggle=lambda act, n=name, c=cmd: self._on_tile_toggled(n, c, act)
            )
            tile.grid(row=0, column=idx, padx=4, pady=4, sticky="nsew")
            self.connection_tiles[name] = tile
            
        # Section 2: Dual Quota Dashboard (Left) & Last Session Stats (Right)
        dash_row = ctk.CTkFrame(page, fg_color="transparent")
        dash_row.pack(fill="x", pady=(0, 14))
        dash_row.grid_columnconfigure(0, weight=3)
        dash_row.grid_columnconfigure(1, weight=2)
        
        # Left: QuotaWidget (Session & Weekly quotas)
        self.quota_widget = QuotaWidget(
            dash_row,
            on_refresh=self.scheduler.refresh_live_quota,
            fg_color=CARD_COLOR,
            corner_radius=12,
            border_width=1,
            border_color=BORDER_COLOR
        )
        self.quota_widget.grid(row=0, column=0, padx=(0, 8), sticky="nsew")
        
        # Right: Last Session Data (ExitLag style)
        self.session_stats_card = SessionStatsCard(
            dash_row,
            on_run_now=self._run_test
        )
        self.session_stats_card.grid(row=0, column=1, padx=(8, 0), sticky="nsew")

    def _on_tile_toggled(self, name: str, cmd: str, is_active: bool):
        if is_active:
            self.preset_var.set(name)
            self.cmd_entry.delete(0, "end")
            self.cmd_entry.insert(0, cmd)
            for t_name, tile in self.connection_tiles.items():
                tile.set_active(t_name == name)
            self.log(f"Выбран активный пресет: {name}", "command")

    # ----------------------------------------------------
    # PAGE 2: PRESETS & CONNECTIONS
    # ----------------------------------------------------
    def _build_page_presets(self):
        page = ctk.CTkScrollableFrame(self.body_container, fg_color="transparent")
        self.pages["presets"] = page
        
        ctk.CTkLabel(page, text="Подключения и Параметры CLI", font=("Inter", 18, "bold"), text_color=TEXT_COLOR).pack(anchor="w", pady=(0, 2))
        ctk.CTkLabel(page, text="Настройка исполняемой команды и рабочей папки для взаимодействия с Claude Code", font=("Inter", 12), text_color=MUTED_COLOR).pack(anchor="w", pady=(0, 12))
        
        # Presets Card
        card = ctk.CTkFrame(page, fg_color=CARD_COLOR, corner_radius=12, border_width=1, border_color=BORDER_COLOR)
        card.pack(fill="x", pady=(0, 14), ipady=12)
        
        ctk.CTkLabel(card, text="Выберите профиль CLI:", font=("Inter", 13, "bold"), text_color=MUTED_LIGHT).pack(anchor="w", padx=18, pady=(12, 2))
        ctk.CTkLabel(card, text="Готовые шаблоны команд для автоматического вызова разных моделей Claude", font=("Inter", 11), text_color=MUTED_COLOR).pack(anchor="w", padx=18, pady=(0, 8))
        
        p_row = ctk.CTkFrame(card, fg_color="transparent")
        p_row.pack(fill="x", padx=18, pady=(0, 12))
        
        preset_tips = {
            "Claude Code": "claude -p 'ок' — Стандартный подогрев сессии через официальный Claude Code CLI (рекомендуется)",
            "Claude Code (ping)": "claude -p 'ping' — Легковесный проверочный запрос без генерации развернутого ответа",
            "Claude Opus Ping": "claude -p 'ок' --model opus — Вызов флагманской модели Opus 5 для открытия её квоты",
            "Claude Sonnet": "claude -p 'ок' --model sonnet — Вызов быстрой модели Sonnet 3.7",
            "Cursor CLI": "cursor --version — Проверка готовности AI-редактора Cursor",
            "Aider": "aider --message 'ping' — Пинг консольного AI-помощника Aider",
            "Пользовательская": "Ввод любой вашей собственной консольной команды Windows"
        }
        
        for pname in CLI_PRESETS.keys():
            p_btn = ctk.CTkButton(
                p_row,
                text=pname,
                font=("Inter", 11, "bold"),
                height=30,
                fg_color="#181924",
                hover_color=BORDER_COLOR,
                border_width=1,
                border_color=BORDER_COLOR,
                text_color=TEXT_COLOR,
                command=lambda p=pname: self._select_preset_pill(p)
            )
            p_btn.pack(side="left", padx=(0, 6), pady=2)
            ToolTip(p_btn, preset_tips.get(pname, pname))
            
        # Command Entry
        ctk.CTkLabel(card, text="Исполняемая команда:", font=("Inter", 13, "bold"), text_color=MUTED_LIGHT).pack(anchor="w", padx=18, pady=(6, 2))
        ctk.CTkLabel(card, text="Команда, которая автоматически вызывается по расписанию в консоли Windows", font=("Inter", 11), text_color=MUTED_COLOR).pack(anchor="w", padx=18, pady=(0, 4))
        self.cmd_entry = ctk.CTkEntry(card, height=36, font=("Consolas", 13), fg_color="#0c0d12", border_color=BORDER_COLOR)
        self.cmd_entry.pack(fill="x", padx=18, pady=(0, 12))
        ToolTip(self.cmd_entry, "Текст консольной команды, которая запускается планировщиком без всплывающих окон")
        
        # Directory Entry
        ctk.CTkLabel(card, text="Рабочая директория:", font=("Inter", 13, "bold"), text_color=MUTED_LIGHT).pack(anchor="w", padx=18, pady=(6, 2))
        ctk.CTkLabel(card, text="Папка на вашем ПК, в контексте которой запускается Claude (например, папка проекта)", font=("Inter", 11), text_color=MUTED_COLOR).pack(anchor="w", padx=18, pady=(0, 4))
        dir_frame = ctk.CTkFrame(card, fg_color="transparent")
        dir_frame.pack(fill="x", padx=18, pady=(0, 12))
        
        self.dir_entry = ctk.CTkEntry(dir_frame, height=36, font=("Inter", 12), fg_color="#0c0d12", border_color=BORDER_COLOR)
        self.dir_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ToolTip(self.dir_entry, "Путь к рабочей папке проекта на диске")
        
        btn_browse = ctk.CTkButton(dir_frame, text="Обзор...", width=90, height=36, font=("Inter", 12), fg_color="#181924", hover_color=BORDER_COLOR, border_width=1, border_color=BORDER_COLOR, command=self._browse_dir)
        btn_browse.pack(side="right")
        ToolTip(btn_browse, "Выбрать рабочую папку на диске через стандартный проводник Windows")
        
        # Test Run Button
        self.test_btn = ctk.CTkButton(
            card,
            text="⚡ Проверить выполнение сейчас",
            font=("Inter", 12, "bold"),
            fg_color=CORAL_COLOR,
            hover_color=DANGER_HOVER,
            text_color="#ffffff",
            height=38,
            corner_radius=8,
            command=self._run_test
        )
        self.test_btn.pack(anchor="w", padx=18, pady=(6, 6))
        ToolTip(self.test_btn, "Запустить команду немедленно в тестовом режиме и проверить результат в логах терминала")

    def _select_preset_pill(self, choice: str):
        self.preset_var.set(choice)
        if choice in CLI_PRESETS and CLI_PRESETS[choice]:
            self.cmd_entry.delete(0, "end")
            self.cmd_entry.insert(0, CLI_PRESETS[choice])
        for t_name, tile in self.connection_tiles.items():
            tile.set_active(t_name == choice)

    # ----------------------------------------------------
    # PAGE 3: SCHEDULE
    # ----------------------------------------------------
    def _build_page_schedule(self):
        page = ctk.CTkScrollableFrame(self.body_container, fg_color="transparent")
        self.pages["schedule"] = page
        
        ctk.CTkLabel(page, text="Расписание запусков", font=("Inter", 18, "bold"), text_color=TEXT_COLOR).pack(anchor="w", pady=(0, 2))
        ctk.CTkLabel(page, text="Укажите, в какие часы и дни недели программа должна отправлять проверочный запрос", font=("Inter", 12), text_color=MUTED_COLOR).pack(anchor="w", pady=(0, 12))
        
        sched_card = ctk.CTkFrame(page, fg_color=CARD_COLOR, corner_radius=12, border_width=1, border_color=BORDER_COLOR)
        sched_card.pack(fill="x", pady=(0, 14), ipady=12)
        
        # Mode Selection
        mode_frame = ctk.CTkFrame(sched_card, fg_color="transparent")
        mode_frame.pack(fill="x", padx=20, pady=(12, 10))
        
        self.radio_fixed = ctk.CTkRadioButton(mode_frame, text="Точное время", font=("Inter", 13, "bold"), variable=self.mode_var, value="fixed", command=self._toggle_mode, fg_color=ACCENT_COLOR, text_color=TEXT_COLOR)
        self.radio_fixed.pack(side="left", padx=(0, 30))
        ToolTip(self.radio_fixed, "Режим точного времени:\nЗапуск в фиксированные часы каждый день (например, в 08:00 и 08:45 каждое утро).")
        
        self.radio_interval = ctk.CTkRadioButton(mode_frame, text="Интервал", font=("Inter", 13, "bold"), variable=self.mode_var, value="interval", command=self._toggle_mode, fg_color=ACCENT_COLOR, text_color=TEXT_COLOR)
        self.radio_interval.pack(side="left")
        ToolTip(self.radio_interval, "Режим интервала:\nПовторять запуск каждые N часов (например, каждые 4.5 часа для непрерывной сессии).")
        
        # Fixed Time Settings
        self.fixed_time_frame = ctk.CTkFrame(sched_card, fg_color="transparent")
        
        # Chips container
        self.times_list_frame = ctk.CTkFrame(self.fixed_time_frame, fg_color="transparent")
        self.times_list_frame.pack(fill="x", pady=(0, 8))
        
        # Quick Pills + Add button row
        actions_row = ctk.CTkFrame(self.fixed_time_frame, fg_color="transparent")
        actions_row.pack(fill="x", pady=(0, 5))
        
        btn_add = ctk.CTkButton(actions_row, text="+ Своё время", font=("Inter", 12, "bold"), width=110, height=28, fg_color="#181924", hover_color=BORDER_COLOR, border_width=1, border_color=BORDER_COLOR, text_color=TEXT_COLOR, command=self._add_time_entry)
        btn_add.pack(side="left", padx=(0, 12))
        ToolTip(btn_add, "Добавить строку для ввода любого другого времени (в формате ЧЧ:ММ)")
        
        ctk.CTkLabel(actions_row, text="Быстро:", font=("Inter", 11), text_color=MUTED_COLOR).pack(side="left", padx=(0, 6))
        for pill_t in ["08:00", "08:45", "09:00", "14:00", "20:00"]:
            pill_btn = ctk.CTkButton(
                actions_row,
                text=f"+{pill_t}",
                font=("Inter", 11),
                width=58,
                height=26,
                fg_color="#181924",
                hover_color=BORDER_COLOR,
                border_width=1,
                border_color=BORDER_COLOR,
                text_color=MUTED_LIGHT,
                command=lambda t=pill_t: self._add_time_entry(t)
            )
            pill_btn.pack(side="left", padx=(0, 6))
            ToolTip(pill_btn, f"Добавить время {pill_t} в список ежедневных запусков")
            
        # Days
        self.days_frame = ctk.CTkFrame(sched_card, fg_color="transparent")
        ctk.CTkLabel(self.days_frame, text="Дни недели:", font=("Inter", 12, "bold"), text_color=MUTED_COLOR).pack(anchor="w", pady=(10, 5))
        
        days_inner = ctk.CTkFrame(self.days_frame, fg_color="transparent")
        days_inner.pack(fill="x")
        
        self.day_vars = {}
        for day in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]:
            var = ctk.BooleanVar(value=True)
            self.day_vars[day] = var
            btn = ctk.CTkButton(days_inner, text=day, width=44, height=30, font=("Inter", 12, "bold"), corner_radius=15)
            btn.pack(side="left", padx=(0, 6))
            btn.configure(command=lambda b=btn, v=var: self._toggle_day_btn(b, v))
            self.day_buttons[day] = btn
            self._update_day_btn_style(btn, var.get())
            ToolTip(btn, f"Включить или выключить автоматические запуски в {day}")
            
        # Interval Settings
        self.interval_frame = ctk.CTkFrame(sched_card, fg_color="transparent")
        ctk.CTkLabel(self.interval_frame, text="Интервал повторений (часов):", font=("Inter", 12, "bold"), text_color=MUTED_COLOR).pack(anchor="w", pady=(10, 5))
        self.interval_entry = ctk.CTkEntry(self.interval_frame, width=110, height=34, font=("Inter", 13), fg_color="#0c0d12", border_color=BORDER_COLOR)
        self.interval_entry.pack(anchor="w")
        ToolTip(self.interval_entry, "Количество часов между повторными автоматическими запусками")

    # ----------------------------------------------------
    # PAGE 4: SYSTEM TWEAKS & OPTIMIZATION (ExitLag 2nd screenshot!)
    # ----------------------------------------------------
    def _build_page_system(self):
        page = ctk.CTkScrollableFrame(self.body_container, fg_color="transparent")
        self.pages["system"] = page
        
        # Header banner
        ctk.CTkLabel(page, text="Ускорение и Оптимизация ПК", font=("Inter", 18, "bold"), text_color=TEXT_COLOR).pack(anchor="w", pady=(0, 2))
        ctk.CTkLabel(page, text="Настройки производительности фонового демона и интеграции с Windows", font=("Inter", 12), text_color=MUTED_COLOR).pack(anchor="w", pady=(0, 14))
        
        # Grid of ExitLag FeatureCards (2 columns)
        grid_frame = ctk.CTkFrame(page, fg_color="transparent")
        grid_frame.pack(fill="x", pady=(0, 14))
        grid_frame.grid_columnconfigure((0, 1), weight=1, uniform="feat")
        
        features_meta = [
            (
                "🖥️",
                "Автозапуск с Windows",
                "Запускает Claude Pulse в системном трее при включении ПК без отвлечения внимания.",
                self.auto_var,
                "Рекомендуется",
                "Обеспечивает подогрев квот 24/7.",
                self._toggle_autostart
            ),
            (
                "⚡",
                "Пробуждение ПК (Wake PC)",
                "Автоматически выводит компьютер из спящего режима перед назначенным пингом.",
                self.wake_var,
                "Таймер ОС",
                "Использует системный Win32 Waitable Timer.",
                None
            ),
            (
                "🔔",
                "Windows Notifications",
                "Всплывающие уведомления о сбросе квот, открытии 5-часового окна и статусе пингов.",
                self.notify_var,
                "Toasts",
                "Интеграция с Центром действий Windows.",
                None
            ),
            (
                "🛡️",
                "Скрытый режим консоли",
                "Полное подавление черных окон cmd/powershell при фоновом запуске команд Claude.",
                self.hidden_var,
                "Stealth",
                "Бесшумная фоновая работа без прерывания игр.",
                None
            ),
            (
                "⏱️",
                "Наверстывание пропущенных",
                "Немедленный запуск пинга при включении, если запланированное время было пропущено.",
                self.catchup_var,
                "Смарт",
                "Гарантирует своевременное открытие квоты.",
                None
            ),
            (
                "📊",
                "Синхронизация Anthropic",
                "Автоматический перехват заголовков Rate Limit Exceeded и парсинг точного времени.",
                self.anthropic_sync_var,
                "Live API",
                "Точность сброса до секунды от серверов Claude.",
                None
            )
        ]
        
        for idx, (icon, title, desc, var, badge, footer, cmd) in enumerate(features_meta):
            r = idx // 2
            c = idx % 2
            card = FeatureCard(
                grid_frame,
                icon=icon,
                title=title,
                description=desc,
                variable=var,
                badge_text=badge,
                footer_note=footer,
                command=cmd
            )
            card.grid(row=r, column=c, padx=6, pady=6, sticky="nsew")

    # ----------------------------------------------------
    # PAGE 5: TERMINAL / LOGS
    # ----------------------------------------------------
    def _build_page_logs(self):
        page = ctk.CTkFrame(self.body_container, fg_color="transparent")
        self.pages["logs"] = page
        
        # Header row
        header = ctk.CTkFrame(page, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(header, text="Терминал событий и логов", font=("Inter", 18, "bold"), text_color=TEXT_COLOR).pack(side="left")
        ctk.CTkLabel(header, text="(Журнал ответов и диагностика)", font=("Inter", 12), text_color=MUTED_COLOR).pack(side="left", padx=12)
        
        btn_copy = ctk.CTkButton(
            header,
            text="📋 Копировать",
            font=("Inter", 11, "bold"),
            width=90,
            height=28,
            fg_color="#181924",
            hover_color=BORDER_COLOR,
            border_width=1,
            border_color=BORDER_COLOR,
            text_color=MUTED_LIGHT,
            command=self._copy_log
        )
        btn_copy.pack(side="right", padx=(6, 0))
        ToolTip(btn_copy, "Скопировать весь текст логов в буфер обмена Windows")
        
        btn_clear = ctk.CTkButton(
            header,
            text="🗑 Очистить",
            font=("Inter", 11, "bold"),
            width=80,
            height=28,
            fg_color="#181924",
            hover_color=BORDER_COLOR,
            border_width=1,
            border_color=BORDER_COLOR,
            text_color=MUTED_LIGHT,
            command=self._clear_log
        )
        btn_clear.pack(side="right")
        ToolTip(btn_clear, "Очистить экран терминала от старых записей")
        
        # Console
        self.console = ConsoleLog(page, fg_color=CARD_COLOR, border_width=1, border_color=BORDER_COLOR)
        self.console.pack(fill="both", expand=True)
        
        self.scheduler.set_log_callback(self.log)

    # ----------------------------------------------------
    # LOGIC & HANDLERS
    # ----------------------------------------------------
    def _toggle_master(self):
        val = self.master_var.get()
        self.scheduler.set_master_enabled(val)
        self._update_master_ui(val)

    def _update_master_ui(self, is_enabled: bool):
        if is_enabled:
            self.master_status_lbl.configure(text="● Claude Pulse ON", text_color="#34d399")
            self.master_pill.configure(border_color="#064e3b")
        else:
            self.master_status_lbl.configure(text="○ Claude Pulse OFF", text_color="#71717a")
            self.master_pill.configure(border_color="#27272a")

    def _refresh_quotas(self):
        self.scheduler.refresh_live_quota()
        self.log("Запрос обновления квот через Claude CLI...", "command")

    def _copy_log(self):
        text = self.console.get_log_text()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.log("Логи скопированы в буфер обмена.", "normal")

    def _clear_log(self):
        self.console.clear_log()

    def _toggle_day_btn(self, btn, var):
        var.set(not var.get())
        self._update_day_btn_style(btn, var.get())
        
    def _update_day_btn_style(self, btn, is_active):
        if is_active:
            btn.configure(fg_color=ACCENT_COLOR, hover_color=ACCENT_HOVER, text_color="#ffffff")
        else:
            btn.configure(fg_color="#181924", hover_color=BORDER_COLOR, text_color=MUTED_COLOR)

    def _add_time_entry(self, val="05:00"):
        chip = ctk.CTkFrame(self.times_list_frame, fg_color="#181924", corner_radius=14, border_width=1, border_color=BORDER_COLOR)
        chip.pack(side="left", padx=(0, 6), pady=2)
        
        entry = ctk.CTkEntry(chip, width=58, height=26, font=("Inter", 12, "bold"), justify="center", fg_color="transparent", border_width=0, text_color=TEXT_COLOR)
        entry.pack(side="left", padx=(4, 0), pady=2)
        entry.insert(0, val)
        
        def remove_row():
            chip.destroy()
            if entry in self.times_entries:
                self.times_entries.remove(entry)
            
        btn_del = ctk.CTkButton(chip, text="✕", width=20, height=20, corner_radius=10, fg_color="transparent", hover_color=DANGER_HOVER, text_color=MUTED_COLOR, font=("Inter", 9), command=remove_row)
        btn_del.pack(side="left", padx=(1, 4), pady=2)
        ToolTip(btn_del, "Удалить это время из расписания")
        
        self.times_entries.append(entry)

    def _toggle_mode(self):
        if self.mode_var.get() == "fixed":
            self.interval_frame.pack_forget()
            self.fixed_time_frame.pack(fill="x", padx=20, pady=0)
            self.days_frame.pack(fill="x", padx=20, pady=0)
        else:
            self.fixed_time_frame.pack_forget()
            self.days_frame.pack_forget()
            self.interval_frame.pack(fill="x", padx=20, pady=0)

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
            
        is_master = config.get("master_enabled", True)
        self.master_var.set(is_master)
        self._update_master_ui(is_master)
        
        self.mode_var.set(config.get("mode", "fixed"))
        
        for w in self.times_list_frame.winfo_children():
            w.destroy()
        self.times_entries.clear()
        
        times = config.get("times", ["05:00"])
        for t in times:
            self._add_time_entry(t)
            
        if not times:
            self._add_time_entry("05:00")
        
        self.interval_entry.delete(0, "end")
        self.interval_entry.insert(0, str(config.get("interval_hours", 1)))
        
        saved_days = config.get("days", [])
        for day, var in self.day_vars.items():
            var.set(day in saved_days)
            self._update_day_btn_style(self.day_buttons[day], var.get())
            
        preset = config.get("selected_preset", "Claude Code")
        if preset in CLI_PRESETS:
            self.preset_var.set(preset)
            for t_name, tile in self.connection_tiles.items():
                tile.set_active(t_name == preset)
            
        self.cmd_entry.delete(0, "end")
        self.cmd_entry.insert(0, config.get("command", 'claude -p "ок"'))
        
        self.dir_entry.delete(0, "end")
        self.dir_entry.insert(0, config.get("working_dir", str(os.path.expanduser("~"))))
        
        self.wake_var.set(config.get("wake_pc", False))
        self.auto_var.set(check_autostart())
        self.notify_var.set(config.get("notify", True))
        self.hidden_var.set(config.get("hidden_console", True))
        self.catchup_var.set(config.get("catch_up_missed", True))
        
        self._toggle_mode()
        
    def _save_and_apply(self):
        times = []
        for entry in self.times_entries:
            val = entry.get().strip()
            if val:
                times.append(val)
                
        if not times:
            times = ["05:00"]
            
        config = {
            "master_enabled": self.master_var.get(),
            "mode": self.mode_var.get(),
            "times": times,
            "interval_hours": float(self.interval_entry.get() or 1),
            "days": [day for day, var in self.day_vars.items() if var.get()],
            "selected_preset": self.preset_var.get(),
            "command": self.cmd_entry.get(),
            "working_dir": self.dir_entry.get(),
            "hidden_console": self.hidden_var.get(),
            "wake_pc": self.wake_var.get(),
            "autostart": self.auto_var.get(),
            "notify": self.notify_var.get(),
            "catch_up_missed": self.catchup_var.get(),
            "timeout_seconds": 45,
            "quota_window_started_at": self.scheduler.config.get("quota_window_started_at", 0.0)
        }
        save_config(config)
        self.scheduler.set_config(config)
        self.log("Настройки успешно сохранены и применены.", "success")
        
    def _run_test(self):
        self.scheduler.run_now()
        
    def log(self, message: str, tag: str = "normal"):
        self.after(0, lambda: self.console.write_log(message, tag))
        
    def _start_timer_updater(self):
        def update():
            # 1. Update Next Run Pill
            next_run = self.scheduler.get_next_run()
            self.next_run_pill.configure(text=f"⏳ След. запуск: {next_run}")
            
            # 2. Update Quota Widget
            q_status = self.scheduler.get_quota_status()
            self.quota_widget.update_status(q_status)
            
            # 3. Update Session Stats Card
            last_stats = self.scheduler.get_last_run_stats()
            self.session_stats_card.update_stats(last_stats, q_status)
            
            if self.winfo_exists():
                self.after(1000, update)
                
        self.after(1000, update)
