import json
import os
from pathlib import Path

APP_NAME = "ClaudePulse"
APP_VERSION = "3.1"
APPDATA_DIR = Path(os.getenv('CLAUDEPULSE_HOME') or (Path(os.getenv('APPDATA', '')) / APP_NAME))
CONFIG_FILE = APPDATA_DIR / "config.json"

QUOTA_WINDOW_HOURS = 5

CLI_PRESETS = {
    "Claude Code": 'claude -p "ok"',
    "Claude Code (ping)": 'claude -p "ping"',
    "Claude Opus Ping": 'claude -p "ok" --model opus',
    "Claude Sonnet": 'claude -p "ok" --model sonnet',
    "Claude Haiku": 'claude -p "ok" --model haiku',
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
    "command": 'claude -p "ok"',
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
    "last_job_at": 0.0,
}

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
