import os
import re
import json
import time
import tempfile
import subprocess
from datetime import datetime, timedelta, tzinfo
from typing import Dict, Any, Optional, List

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}

_RESET_FULL = re.compile(
    r'([A-Za-z]{3})[a-z]*\s+(\d{1,2}),?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)', re.IGNORECASE)
_RESET_TIME = re.compile(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', re.IGNORECASE)
_RESET_TZ = re.compile(r'\(([A-Za-z_]+/[A-Za-z_/+-]+|UTC)\)')

_SESSION = re.compile(r'Current session:\s*(\d+)%\s*used(?:\s*·\s*resets\s*([^\r\n]+))?')
_WEEKLY = re.compile(r'Current week \(all models\):\s*(\d+)%\s*used(?:\s*·\s*resets\s*([^\r\n]+))?')
_WEEKLY_FABLE = re.compile(r'Current week \(Fable\):\s*(\d+)%\s*used')
_TIPS_HEADER = re.compile(r'^Last\s+(\S+)\s*·\s*(\d+)\s+requests?\s*·\s*(\d+)\s+sessions?', re.IGNORECASE)


def _to_24h(hh: int, ampm: str) -> int:
    ampm = ampm.lower()
    if ampm == "pm" and hh < 12:
        return hh + 12
    if ampm == "am" and hh == 12:
        return 0
    return hh


def _zone(name: Optional[str]) -> Optional[tzinfo]:
    if not name or ZoneInfo is None:
        return None
    try:
        return ZoneInfo(name)
    except Exception:
        return None


def parse_reset(raw: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """'Sep 23, 4am (Europe/Moscow)' -> aware datetime. Без даты ('4am') — ближайшее будущее."""
    if not raw:
        return None
    tz_match = _RESET_TZ.search(raw)
    tz = _zone(tz_match.group(1)) if tz_match else None
    if now is None:
        now = datetime.now().astimezone()
    elif now.tzinfo is None:
        now = now.astimezone()
    tz = tz or now.tzinfo

    m = _RESET_FULL.search(raw)
    if m:
        month = MONTHS.get(m.group(1).lower()[:3])
        if not month:
            return None
        day, hh, mm = int(m.group(2)), _to_24h(int(m.group(3)), m.group(5)), int(m.group(4) or 0)
        now_local = now.astimezone(tz)
        try:
            dt = datetime(now_local.year, month, day, hh, mm, tzinfo=tz)
        except ValueError:
            return None
        # На стыке годов 'Jan 2' в декабре — это следующий год
        if dt < now_local - timedelta(days=180):
            dt = dt.replace(year=dt.year + 1)
        return dt

    m = _RESET_TIME.search(raw)
    if m:
        hh, mm = _to_24h(int(m.group(1)), m.group(3)), int(m.group(2) or 0)
        now_local = now.astimezone(tz)
        dt = now_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if dt <= now_local:
            dt += timedelta(days=1)
        return dt
    return None


def parse_tips(text: str) -> List[Dict[str, Any]]:
    """Блок «What's contributing to your limits usage?» -> [{period, requests, sessions, items}]."""
    idx = text.find("What's contributing")
    if idx < 0:
        return []
    blocks: List[Dict[str, Any]] = []
    current = None
    for line in text[idx:].splitlines()[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        header = _TIPS_HEADER.match(stripped)
        if header:
            current = {
                "period": header.group(1),
                "requests": int(header.group(2)),
                "sessions": int(header.group(3)),
                "items": [],
            }
            blocks.append(current)
        elif current is not None and line[:1].isspace():
            current["items"].append(stripped)
    return blocks


def parse_usage(text: str, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Разбирает вывод `claude -p "/usage"`. Ничего не выдумывает: нет строки — нет данных."""
    data: Dict[str, Any] = {
        "has_data": False,
        "session_pct": None,
        "session_reset": None,
        "weekly_pct": None,
        "weekly_reset": None,
        "fable_pct": None,
        "tips": [],
    }
    m = _SESSION.search(text)
    if m:
        data["has_data"] = True
        data["session_pct"] = int(m.group(1))
        data["session_reset"] = parse_reset(m.group(2) or "", now)
    m = _WEEKLY.search(text)
    if m:
        data["has_data"] = True
        data["weekly_pct"] = int(m.group(1))
        data["weekly_reset"] = parse_reset(m.group(2) or "", now)
    m = _WEEKLY_FABLE.search(text)
    if m:
        data["fable_pct"] = int(m.group(1))
    data["tips"] = parse_tips(text)
    return data


def parse_rate_limit_reset_time(output_text: str) -> Optional[str]:
    """Время сброса из текста ошибки лимита ('limit reached ... resets 4am')."""
    patterns = [
        r'(?:until|at|after|до)\s+(\d{1,2}:\d{2}(?:\s*[AP]M)?)',
        r'resets?\s+(?:at|in)?\s*(\d{1,2}(?::\d{2})?\s*(?:[AP]M)?)',
        r'лимит(?:\s+\w+)*\s+до\s+(\d{1,2}:\d{2})'
    ]
    for p in patterns:
        match = re.search(p, output_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def run_cli(command: str, timeout: float) -> str:
    """Запуск команды Claude CLI без окна консоли. Рабочая папка — временная, чтобы не плодить проекты."""
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    proc = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        cwd=tempfile.gettempdir(),
        creationflags=creationflags,
        timeout=timeout,
    )
    raw = proc.stdout or b""
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return raw.decode('cp866', errors='replace')


class ClaudeAccount:
    """Информация об аккаунте из `claude auth status` (кэш на час). Неизвестно — пустые строки, без заглушек."""
    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._checked_at = 0.0

    def get(self, force: bool = False) -> Dict[str, Any]:
        if not force and self._cache and time.time() - self._checked_at < 3600:
            return self._cache
        info = {"logged_in": None, "subscription": "", "email": ""}
        try:
            text = run_cli("claude auth status", timeout=15)
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                info["logged_in"] = bool(data.get("loggedIn", False))
                info["subscription"] = str(data.get("subscriptionType") or "")
                info["email"] = str(data.get("email") or "")
        except Exception:
            pass
        if info["logged_in"] is not None:
            self._cache = info
            self._checked_at = time.time()
        return info if info["logged_in"] is not None else (self._cache or info)
