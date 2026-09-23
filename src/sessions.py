"""
Список чатов Claude Code из ~/.claude/projects/<папка>/<id>.jsonl — для выбора, куда отправить отложенный промпт.

Файлы бывают по десяткам мегабайт, поэтому читаем только хвост (там название и последний промпт)
и при необходимости начало (там рабочая папка и первое сообщение). Результат кэшируется по времени изменения.
"""
import os
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

PROJECTS_DIR = Path.home() / ".claude" / "projects"
TAIL_BYTES = 256 * 1024
HEAD_BYTES = 64 * 1024

# Сессии, которые создаёт сама программа (пинги и опрос лимитов) — в списке не нужны
SERVICE_PROMPTS = {"/usage", "ok", "ок", "ping", "пинг"}

_cache: Dict[str, Tuple[float, Optional[Dict[str, Any]]]] = {}


def _lines(path: Path, tail: bool) -> List[dict]:
    size = path.stat().st_size
    with open(path, "rb") as fh:
        if tail and size > TAIL_BYTES:
            fh.seek(size - TAIL_BYTES)
            raw = fh.read()
            raw = raw[raw.find(b"\n") + 1:]      # первая строка обрезана посередине
        else:
            raw = fh.read(HEAD_BYTES if not tail else size)
    out = []
    for line in raw.decode("utf-8", errors="replace").splitlines():
        if line.startswith("{"):
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def _user_text(entry: dict) -> str:
    """Текст, который набрал человек (без служебных вставок, результатов инструментов и команд)."""
    if entry.get("type") != "user" or entry.get("isMeta") or entry.get("isSidechain"):
        return ""
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, list):
        parts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
        content = " ".join(parts)
    if not isinstance(content, str):
        return ""
    text = content.strip()
    if text.startswith("<") or text.startswith("Caveat:"):
        return ""  # <command-name>, <local-command-stdout>, <system-reminder> и т.п.
    return text


def _scan(path: Path) -> Optional[Dict[str, Any]]:
    info: Dict[str, Any] = {"id": path.stem, "cwd": "", "title": "", "last_prompt": "", "first_prompt": "",
                            "entrypoint": ""}
    custom = ai = ""

    def absorb(entries: List[dict], from_tail: bool):
        nonlocal custom, ai
        for e in entries:
            ty = e.get("type")
            if ty == "custom-title" and e.get("customTitle"):
                custom = e["customTitle"]          # последняя запись — актуальное название
            elif ty == "ai-title" and e.get("aiTitle"):
                ai = e["aiTitle"]
            elif ty == "last-prompt" and e.get("lastPrompt"):
                info["last_prompt"] = e["lastPrompt"]
            if not info["cwd"] and e.get("cwd"):
                info["cwd"] = e["cwd"]
            if not info["entrypoint"] and e.get("entrypoint"):
                info["entrypoint"] = e["entrypoint"]
            text = _user_text(e)
            if text:
                if not info["first_prompt"] and (not from_tail or small):
                    info["first_prompt"] = text
                if from_tail:
                    info["last_prompt"] = text

    small = path.stat().st_size <= TAIL_BYTES
    absorb(_lines(path, tail=True), from_tail=True)
    if not small and (not info["cwd"] or not (custom or ai)):
        absorb(_lines(path, tail=False), from_tail=False)

    info["title"] = custom or ai or info["first_prompt"] or info["last_prompt"]
    prompts = {p.strip().lower() for p in (info["first_prompt"], info["last_prompt"]) if p}
    if not info["cwd"] or not info["title"] or (prompts and prompts <= SERVICE_PROMPTS):
        return None
    return info


def list_sessions(limit: int = 80, projects_dir: Path = PROJECTS_DIR) -> List[Dict[str, Any]]:
    """Последние чаты: id, cwd, project, title, last_prompt, mtime. Новые сверху."""
    if not projects_dir.exists():
        return []
    files = []
    for folder in projects_dir.iterdir():
        if folder.is_dir():
            for f in folder.glob("*.jsonl"):
                try:
                    files.append((f.stat().st_mtime, f))
                except OSError:
                    pass
    files.sort(key=lambda x: x[0], reverse=True)

    result = []
    for mtime, path in files:
        if len(result) >= limit:
            break
        key = str(path)
        cached = _cache.get(key)
        if cached and cached[0] == mtime:
            info = cached[1]
        else:
            try:
                info = _scan(path)
            except OSError:
                info = None
            _cache[key] = (mtime, info)
        if info:
            item = dict(info, mtime=mtime, project=os.path.basename(info["cwd"].rstrip("\\/")) or info["cwd"])
            result.append(item)
    return result


def find_session(session_id: str, projects_dir: Path = PROJECTS_DIR) -> Optional[Path]:
    for path in projects_dir.glob(f"*/{session_id}.jsonl"):
        return path
    return None


def ago(mtime: float, now: Optional[float] = None) -> Tuple[str, int]:
    """(единица, число) для «N минут назад»: ('min'|'hour'|'day', n)."""
    delta = max(0, int((now or time.time()) - mtime))
    if delta < 3600:
        return "min", max(1, delta // 60)
    if delta < 86400:
        return "hour", delta // 3600
    return "day", delta // 86400
