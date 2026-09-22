"""
Команды от второго запуска программы к уже работающей копии.

Клик по уведомлению запускает `ClaudePulse.exe claudepulse:pause2h`. Вторая копия сразу
закрывается, а команду оставляет в файле — работающая копия забирает его раз в секунду.
"""
import os
from typing import List, Optional

from src.config import APPDATA_DIR

COMMAND_FILE = APPDATA_DIR / "commands.txt"
COMMANDS = ("open", "pause2h", "pause_today", "resume", "ping", "update")


def parse_argv(argv: List[str]) -> Optional[str]:
    """'claudepulse:pause2h' или 'claudepulse://pause2h/' -> 'pause2h'. Незнакомое — None."""
    for arg in argv[1:]:
        if arg.lower().startswith("claudepulse:"):
            cmd = arg.split(":", 1)[1].strip("/ ").lower()
            return cmd if cmd in COMMANDS else "open"
    return None


def send(command: str):
    try:
        APPDATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(COMMAND_FILE, "a", encoding="utf-8") as f:
            f.write(command + "\n")
    except OSError:
        pass


def take() -> List[str]:
    """Забрать накопившиеся команды (файл удаляется)."""
    if not COMMAND_FILE.exists():
        return []
    try:
        tmp = COMMAND_FILE.with_suffix(".taking")
        os.replace(COMMAND_FILE, tmp)
        lines = tmp.read_text(encoding="utf-8").split()
        tmp.unlink()
        return [c for c in lines if c in COMMANDS]
    except OSError:
        return []
