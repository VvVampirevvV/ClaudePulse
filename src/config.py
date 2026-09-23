import json
import os
import re
from pathlib import Path

APP_NAME = "ClaudePulse"
APP_VERSION = "3.3"
APPDATA_DIR = Path(os.getenv('CLAUDEPULSE_HOME') or (Path(os.getenv('APPDATA', '')) / APP_NAME))
CONFIG_FILE = APPDATA_DIR / "config.json"

QUOTA_WINDOW_HOURS = 5

# --no-session-persistence: пинг не оставляет пустых «чатов» в ~/.claude/projects
CLI_PRESETS = {
    "Claude Code": 'claude -p "ok" --no-session-persistence',
    "Claude Code (ping)": 'claude -p "ping" --no-session-persistence',
    "Claude Opus Ping": 'claude -p "ok" --model opus --no-session-persistence',
    "Claude Sonnet": 'claude -p "ok" --model sonnet --no-session-persistence',
    "Claude Haiku": 'claude -p "ok" --model haiku --no-session-persistence',
    "Aider": 'aider --message "ping"',
    "custom": ''
}

# Внутренние коды дней недели (исторически русские — так они лежат в старых конфигах)
DAY_CODES = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

DEFAULT_CONFIG = {
    "master_enabled": True,
    "mode": "fixed",  # "fixed" | "interval" | "target"
    "times": ["05:00"],
    "target_times": ["14:00"],
    "interval_hours": 1.0,
    "days": list(DAY_CODES),
    "command": 'claude -p "ok" --no-session-persistence',
    "selected_preset": "Claude Code",
    "working_dir": str(Path.home()),
    "hidden_console": True,
    "wake_pc": False,
    "autostart": False,
    "notify": True,
    "catch_up_missed": True,
    "alerts_enabled": True,
    "alert_levels": [80, 95],
    "usage_poll_minutes": 5,
    "timeout_seconds": 45,
    "language": "",  # "" = как в Windows
    "skip_if_open": True,
    "check_updates": True,
    "last_job_at": 0.0,
    "paused_until": 0.0,
    "deferred_at": 0.0,
    "task_timeout_minutes": 60,
}

# Старые пресеты без --no-session-persistence (до 3.3) — дописываем флаг при загрузке
_OLD_PRESET_RE = re.compile(r'^claude -p "(ok|ок|ping)"( --model \w+)?$')

# Ключи, которые больше не используются (удаляются при загрузке)
_OBSOLETE_KEYS = ("quota_window_started_at", "anthropic_sync")


def load_config():
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        config = DEFAULT_CONFIG.copy()
        config.update(data)

        # Миграция со старых форматов
        if "time" in data and "times" not in data:
            config["times"] = [data["time"]]
        if _OLD_PRESET_RE.match(config.get("command", "").strip()):
            config["command"] = config["command"].strip() + " --no-session-persistence"
        if config.get("selected_preset") == "Пользовательская":
            config["selected_preset"] = "custom"
        for key in _OBSOLETE_KEYS:
            config.pop(key, None)
        return config
    except Exception:
        return DEFAULT_CONFIG.copy()


def save_config(config_data):
    APPDATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_FILE.with_suffix(".tmp")
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=4, ensure_ascii=False)
    os.replace(tmp, CONFIG_FILE)
