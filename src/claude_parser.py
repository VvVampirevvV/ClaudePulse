import os
import json
import re
import time
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

CLAUDE_MAX_TOKEN_BUDGET = 15_000_000

def _format_date_ru(raw_date: str) -> str:
    """Форматирует дату из вывода Claude (напр. 'Sep 23, 8am') в читаемый русский вид."""
    if not raw_date:
        return ""
    text = raw_date.strip()
    
    # Перестановка 'Sep 23' -> '23 Sep'
    text = re.sub(r'([A-Za-z]+)\s+(\d{1,2})', r'\2 \1', text)

    # Замена месяцев
    months = {
        "Jan": "янв.", "Feb": "фев.", "Mar": "марта", "Apr": "апр.",
        "May": "мая", "Jun": "июня", "Jul": "июля", "Aug": "авг.",
        "Sep": "сент.", "Oct": "окт.", "Nov": "нояб.", "Dec": "дек."
    }
    for en, ru in months.items():
        text = re.sub(r'\b' + en + r'\b', ru, text, flags=re.IGNORECASE)
        
    # Форматирование времени 8am -> 08:00, 2pm -> 14:00, 6:30am -> 06:30
    def time_repl(m):
        hh = int(m.group(1))
        mm = int(m.group(2)) if m.group(2) else 0
        ampm = m.group(3).lower()
        if ampm == "pm" and hh < 12:
            hh += 12
        elif ampm == "am" and hh == 12:
            hh = 0
        return f"{hh:02}:{mm:02}"
        
    text = re.sub(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', time_repl, text, flags=re.IGNORECASE)
    return text

class ClaudeParser:
    """
    Модуль парсинга реального состояния Claude Code:
    - Сессионные (5 часов) и Недельные квоты (claude -p /usage)
    - Чтение информации об аккаунте и подписке (claude auth status)
    - Чтение локальных сессий из ~/.claude/projects для фоновой синхронизации
    """
    def __init__(self):
        self.claude_dir = Path.home() / ".claude"
        self.projects_dir = self.claude_dir / "projects"
        self._cached_auth_info: Dict[str, Any] = {}
        self._last_auth_check: float = 0.0
        self._cached_usage: Dict[str, Any] = {}
        self._last_usage_check: float = 0.0
        self._is_fetching_usage = False

    def get_auth_info(self, force_refresh: bool = False) -> Dict[str, Any]:
        now = time.time()
        if not force_refresh and self._cached_auth_info and (now - self._last_auth_check < 600):
            return self._cached_auth_info

        default_info = {
            "loggedIn": True,
            "subscriptionType": "Max",
            "email": "",
            "orgName": "",
            "model": "Opus 5"
        }

        try:
            creationflags = 0
            if os.name == 'nt':
                creationflags = subprocess.CREATE_NO_WINDOW

            result = subprocess.run(
                ["claude", "auth", "status"],
                capture_output=True,
                shell=True,
                creationflags=creationflags,
                timeout=6
            )
            
            raw_output = result.stdout or b""
            try:
                text_output = raw_output.decode('utf-8')
            except UnicodeDecodeError:
                text_output = raw_output.decode('cp866', errors='replace')

            if text_output.strip():
                match = re.search(r'\{.*\}', text_output, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                    sub = data.get("subscriptionType", "Max").capitalize()
                    default_info["loggedIn"] = data.get("loggedIn", True)
                    default_info["subscriptionType"] = sub
                    default_info["email"] = data.get("email", "")
                    default_info["orgName"] = data.get("orgName", "")
                    self._cached_auth_info = default_info
                    self._last_auth_check = now
                    return default_info
        except Exception:
            pass

        return self._cached_auth_info if self._cached_auth_info else default_info

    def get_live_usage(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Запрашивает официальные живые данные по сессионным и недельным квотам через /usage.
        Кэшируется на 10 минут, если не запрошено принудительное обновление.
        """
        now = time.time()
        if not force_refresh and self._cached_usage and (now - self._last_usage_check < 600):
            return self._cached_usage

        if self._is_fetching_usage and self._cached_usage:
            return self._cached_usage

        self._is_fetching_usage = True
        try:
            creationflags = 0
            if os.name == 'nt':
                creationflags = subprocess.CREATE_NO_WINDOW

            process = subprocess.Popen(
                'claude -p "/usage"',
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creationflags
            )
            stdout_bytes, _ = process.communicate(timeout=12)
            text = stdout_bytes.decode('utf-8', errors='replace')

            # Парсинг вывода
            usage_data = {
                "has_data": False,
                "session_used_pct": 0,
                "session_resets_str": "",
                "weekly_used_pct": 0,
                "weekly_remaining_pct": 100,
                "weekly_resets_str": "",
                "fable_used_pct": 0,
                "raw_summary": ""
            }

            s_match = re.search(r'Current session:\s*(\d+)%\s*used(?:\s*·\s*resets\s*([^(\n\r]+))?', text)
            if s_match:
                usage_data["has_data"] = True
                usage_data["session_used_pct"] = int(s_match.group(1))
                if s_match.group(2):
                    usage_data["session_resets_str"] = _format_date_ru(s_match.group(2))

            w_match = re.search(r'Current week \(all models\):\s*(\d+)%\s*used(?:\s*·\s*resets\s*([^(\n\r]+))?', text)
            if w_match:
                usage_data["has_data"] = True
                w_used = int(w_match.group(1))
                usage_data["weekly_used_pct"] = w_used
                usage_data["weekly_remaining_pct"] = max(0, 100 - w_used)
                if w_match.group(2):
                    usage_data["weekly_resets_str"] = _format_date_ru(w_match.group(2))

            f_match = re.search(r'Current week \(Fable\):\s*(\d+)%\s*used', text)
            if f_match:
                usage_data["fable_used_pct"] = int(f_match.group(1))

            if usage_data["has_data"]:
                self._cached_usage = usage_data
                self._last_usage_check = now
                return usage_data

        except Exception:
            pass
        finally:
            self._is_fetching_usage = False

        return self._cached_usage if self._cached_usage else {
            "has_data": False,
            "session_used_pct": 0,
            "session_resets_str": "",
            "weekly_used_pct": 0,
            "weekly_remaining_pct": 100,
            "weekly_resets_str": "",
            "fable_used_pct": 0
        }

    def get_latest_session_details(self) -> Dict[str, Any]:
        result = {
            "has_activity": False,
            "last_interaction_time": 0.0,
            "tokens_left": "100%",
            "tokens_percent": 100.0,
            "model_name": "Opus 5",
            "is_active_window": False,
            "window_elapsed_seconds": 0.0
        }

        if not self.projects_dir.exists():
            return result

        jsonl_files = []
        try:
            for root, _, files in os.walk(self.projects_dir):
                for f in files:
                    if f.endswith(".jsonl"):
                        p = Path(root) / f
                        try:
                            jsonl_files.append((p.stat().st_mtime, p))
                        except Exception:
                            pass
        except Exception:
            return result

        if not jsonl_files:
            return result

        jsonl_files.sort(key=lambda x: x[0], reverse=True)
        now = time.time()

        earliest_active_window = 0.0
        tokens_found_pct = None
        model_found = ""

        for _, file_path in jsonl_files[:5]:
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()

                for line in reversed(lines):
                    line_str = line.strip()
                    if not line_str or not line_str.startswith("{"):
                        continue

                    if tokens_found_pct is None:
                        tok_match = re.search(r'<total_tokens>([\d\s]+)\s*tokens\s*left</total_tokens>', line_str)
                        if tok_match:
                            try:
                                num_tokens = int(tok_match.group(1).replace(" ", ""))
                                pct = round((num_tokens / CLAUDE_MAX_TOKEN_BUDGET) * 100, 1)
                                pct = max(0.0, min(100.0, pct))
                                tokens_found_pct = pct
                            except Exception:
                                pass

                    if not model_found:
                        mod_match = re.search(r'"marketingName":"([^"]+)"', line_str)
                        if mod_match:
                            model_found = mod_match.group(1).strip()

                    if '"type":"queue-operation"' in line_str or '"type":"user"' in line_str:
                        ts_match = re.search(r'"timestamp":"([^"]+)"', line_str)
                        if ts_match:
                            try:
                                dt = datetime.fromisoformat(ts_match.group(1).replace("Z", "+00:00"))
                                epoch = dt.timestamp()
                                if now - epoch < 5 * 3600:
                                    if earliest_active_window == 0.0 or epoch < earliest_active_window:
                                        earliest_active_window = epoch
                            except Exception:
                                pass
            except Exception:
                pass

        if earliest_active_window > 0.0:
            elapsed = now - earliest_active_window
            result["has_activity"] = True
            result["last_interaction_time"] = earliest_active_window
            result["is_active_window"] = True
            result["window_elapsed_seconds"] = elapsed

        if tokens_found_pct is not None:
            result["tokens_percent"] = tokens_found_pct
            result["tokens_left"] = f"{int(tokens_found_pct)}%" if tokens_found_pct.is_integer() else f"{tokens_found_pct:.1f}%"
        else:
            result["tokens_left"] = "100%"
            result["tokens_percent"] = 100.0

        if model_found:
            result["model_name"] = model_found

        return result

    @staticmethod
    def parse_rate_limit_reset_time(output_text: str) -> Optional[str]:
        patterns = [
            r'(?:until|at|after|до)\s+(\d{1,2}:\d{2}(?:\s*[AP]M)?)',
            r'resets?\s+(?:at|in)?\s*(\d{1,2}:\d{2}(?:\s*[AP]M)?)',
            r'лимит(?:\s+\w+)*\s+до\s+(\d{1,2}:\d{2})'
        ]
        for p in patterns:
            match = re.search(p, output_text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None
