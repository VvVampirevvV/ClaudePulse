import json
import os
from pathlib import Path

APP_NAME = "ClaudePulse"
APP_VERSION = "3.0 VER WORK"
APPDATA_DIR = Path(os.getenv('APPDATA', '')) / APP_NAME
CONFIG_FILE = APPDATA_DIR / "config.json"

CLI_PRESETS = {
    "Claude Code": 'claude -p "ок"',
    "Claude Code (ping)": 'claude -p "ping"',
    "Claude Opus Ping": 'claude -p "ок" --model opus',
    "Claude Sonnet": 'claude -p "ок" --model sonnet',
    "Cursor CLI": 'cursor --version',
    "Aider": 'aider --message "ping"',
    "Пользовательская": ''
}

DEFAULT_CONFIG = {
    "master_enabled": True,
    "mode": "fixed", # "fixed" or "interval"
    "times": ["05:00"],
    "interval_hours": 1.0,
    "days": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
    "command": 'claude -p "ок"',
    "selected_preset": "Claude Code",
    "working_dir": str(Path.home()),
    "hidden_console": True,
    "wake_pc": False,
    "autostart": False,
    "notify": True,
    "catch_up_missed": True,
    "timeout_seconds": 45,
    "quota_window_started_at": 0.0
}

def load_config():
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            config = DEFAULT_CONFIG.copy()
            config.update(data)
            
            # Migration from older format
            if "time" in data and "times" not in data:
                config["times"] = [data["time"]]
                
            return config
    except Exception:
        return DEFAULT_CONFIG.copy()

def save_config(config_data):
    APPDATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=4, ensure_ascii=False)
