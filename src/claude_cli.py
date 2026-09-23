"""Запуск Claude Code без окна: поиск настоящего claude.exe и разбор JSON-ответа режима --print."""
import os
import json
import shutil
import subprocess
from typing import List, Optional, Dict, Any

from src.claude_parser import parse_rate_limit_reset_time


def find_claude() -> List[str]:
    """
    Команда запуска Claude Code списком аргументов.
    npm ставит обёртку claude.cmd — за ней лежит настоящий claude.exe, его и запускаем напрямую:
    так аргументы не проходят через cmd.exe и его правила кавычек.
    """
    found = shutil.which("claude")
    if found:
        if found.lower().endswith((".cmd", ".bat", ".ps1")) or not os.path.splitext(found)[1]:
            base = os.path.dirname(found)
            exe = os.path.join(base, "node_modules", "@anthropic-ai", "claude-code", "bin", "claude.exe")
            if os.path.exists(exe):
                return [exe]
            cmd = os.path.join(base, "claude.cmd")
            if os.path.exists(cmd):
                return ["cmd", "/c", cmd]
        return [found]
    native = os.path.join(os.path.expanduser("~"), ".local", "bin", "claude.exe")
    return [native] if os.path.exists(native) else ["claude"]


def run_resume(session_id: str, prompt: str, cwd: str, permission_mode: str, timeout: float) -> Dict[str, Any]:
    """
    Продолжить чат: claude --resume <id> -p (промпт через stdin) --output-format json.
    Промпт идёт через стандартный ввод, поэтому любые кавычки и спецсимволы в нём безопасны.
    """
    args = find_claude() + ["--resume", session_id, "-p", "--output-format", "json",
                            "--permission-mode", permission_mode]
    proc = subprocess.run(
        args,
        input=prompt.encode("utf-8"),
        capture_output=True,
        cwd=cwd if cwd and os.path.isdir(cwd) else None,
        timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    return parse_result(proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace"),
                        proc.returncode)


def parse_result(stdout: str, stderr: str, returncode: int) -> Dict[str, Any]:
    """{ok, text, limit_hit, reset_hint, turns, cost}. Понимает и JSON, и обычный текст ошибки."""
    data: Optional[dict] = None
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                data = json.loads(line)
                break
            except ValueError:
                continue
    if data is not None:
        text = str(data.get("result") or "")
        ok = not data.get("is_error") and data.get("subtype") == "success" and returncode == 0
        turns, cost = data.get("num_turns"), data.get("total_cost_usd")
    else:
        text = (stdout.strip() or stderr.strip())
        ok, turns, cost = returncode == 0 and bool(text), None, None
    combined = f"{text}\n{stderr}"
    limit_hit = (not ok) and is_limit_message(combined)
    return {
        "ok": ok,
        "text": text or stderr.strip(),
        "limit_hit": limit_hit,
        "reset_hint": parse_rate_limit_reset_time(combined) if limit_hit else None,
        "turns": turns,
        "cost": cost,
    }


def is_limit_message(text: str) -> bool:
    low = text.lower()
    return ("limit" in low and any(w in low for w in ("reached", "hit", "exceeded", "resets", "usage limit"))) \
        or "rate_limit" in low


def open_chat_in_terminal(session_id: str, cwd: str):
    """Открыть чат в новом окне терминала: Windows Terminal, если есть, иначе обычная консоль."""
    claude = subprocess.list2cmdline(find_claude())
    folder = cwd if cwd and os.path.isdir(cwd) else os.path.expanduser("~")
    wt = shutil.which("wt")
    if wt:
        subprocess.Popen([wt, "-d", folder, "cmd", "/k", f"{claude} --resume {session_id}"])
    else:
        subprocess.Popen(["cmd", "/k", f"{claude} --resume {session_id}"], cwd=folder,
                         creationflags=subprocess.CREATE_NEW_CONSOLE)
