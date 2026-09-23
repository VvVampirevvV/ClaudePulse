"""
Отложенные задачи: «отправь этот промпт в этот чат Claude Code, когда сбросится лимит (или в HH:MM)».

Задачи хранятся в %APPDATA%\\ClaudePulse\\tasks.json и переживают перезапуск. Выполняются по одной,
в фоне, без окна. Если лимит снова кончился посреди задачи — один раз переносим на следующий сброс.
"""
import re
import json
import time
import uuid
import threading
import subprocess
from datetime import datetime, timedelta
from typing import Callable, Optional, Dict, Any, List

from src.config import APPDATA_DIR
from src.claude_cli import run_resume
from src.claude_parser import parse_reset
from src.i18n import t

TASKS_FILE = APPDATA_DIR / "tasks.json"
AFTER_RESET = 60                  # отправлять через минуту после сброса
DEFAULT_TIMEOUT_MIN = 60
MAX_LIMIT_RETRIES = 1
RESULT_MAX_CHARS = 20000

# Права без присмотра: ключ в UI -> режим Claude Code
PERMISSIONS = {"auto": "auto", "edits": "acceptEdits", "read": "plan"}
SESSION_ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def next_time_of_day(hhmm: str, now: Optional[datetime] = None) -> Optional[datetime]:
    try:
        hh, mm = (int(x) for x in hhmm.strip().split(":"))
        now = now or datetime.now()
        at = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        return at if at > now else at + timedelta(days=1)
    except (ValueError, AttributeError):
        return None


class TaskManager:
    def __init__(self, get_config: Callable[[], Dict[str, Any]], usage):
        self._get_config = get_config
        self.usage = usage
        self.log: Callable[[str, str], None] = lambda m, tag="normal": None
        self.notify: Callable[..., None] = lambda *a, **k: None
        self._lock = threading.Lock()
        self.version = 0                  # растёт при любом изменении — сигнал интерфейсу перерисоваться
        self.tasks: List[Dict[str, Any]] = self._load()

    # ---------- хранение ----------
    def _load(self) -> List[Dict[str, Any]]:
        try:
            tasks = json.loads(TASKS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        for task in tasks:
            if task.get("status") == "running":   # программа закрылась посреди задачи
                task["status"] = "failed"
                task["result"] = t("task.interrupted")
        return tasks

    def _save(self):
        self.version += 1
        try:
            APPDATA_DIR.mkdir(parents=True, exist_ok=True)
            tmp = TASKS_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.tasks, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(TASKS_FILE)
        except OSError:
            pass

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        return next((x for x in self.tasks if x["id"] == task_id), None)

    # ---------- когда отправлять ----------
    def resolve_due(self, when: str, at: str = "") -> Optional[float]:
        """Время отправки. «После сброса»: неделя исчерпана — её сброс, окно открыто — его сброс, иначе сразу."""
        if when == "time":
            dt = next_time_of_day(at)
            return dt.timestamp() if dt else None
        now = time.time()
        weekly, session = self.usage.weekly_state(), self.usage.session_state()
        if weekly.get("known") and weekly["pct"] >= 100 and weekly.get("reset"):
            return weekly["reset"].timestamp() + AFTER_RESET
        if session.get("active") and session.get("reset"):
            return session["reset"].timestamp() + AFTER_RESET
        return now + 5

    # ---------- действия ----------
    def create(self, session: Dict[str, Any], prompt: str, when: str, at: str, permission: str) -> Dict[str, Any]:
        if not SESSION_ID_RE.match(session.get("id", "")):
            raise ValueError(t("task.err.session"))
        if not prompt.strip():
            raise ValueError(t("task.err.prompt"))
        due = self.resolve_due(when, at)
        if due is None:
            raise ValueError(t("task.err.time"))
        task = {
            "id": uuid.uuid4().hex[:8],
            "session_id": session["id"],
            "cwd": session.get("cwd", ""),
            "title": session.get("title", "")[:120],
            "project": session.get("project", ""),
            "prompt": prompt.strip(),
            "when": when,
            "at": at,
            "permission": permission if permission in PERMISSIONS else "auto",
            "due_at": due,
            "status": "scheduled",
            "created_at": time.time(),
            "retries": 0,
            "result": "",
        }
        with self._lock:
            self.tasks.insert(0, task)
            self._save()
        self.log(t("log.task_created", project=task["project"], when=datetime.fromtimestamp(due).strftime("%d.%m %H:%M")),
                 "success")
        return task

    def cancel(self, task_id: str):
        with self._lock:
            task = self.get(task_id)
            if task and task["status"] == "scheduled":
                task["status"] = "cancelled"
                self._save()
                self.log(t("log.task_cancelled", project=task["project"]), "warning")

    def remove(self, task_id: str):
        with self._lock:
            self.tasks = [x for x in self.tasks if not (x["id"] == task_id and x["status"] != "running")]
            self._save()

    def run_now(self, task_id: str):
        with self._lock:
            task = self.get(task_id)
            if task and task["status"] in ("scheduled", "failed", "cancelled"):
                task["status"] = "scheduled"
                task["due_at"] = time.time()
                self._save()

    def next_due(self) -> Optional[float]:
        due = [x["due_at"] for x in self.tasks if x["status"] == "scheduled"]
        return min(due) if due else None

    def running(self) -> Optional[Dict[str, Any]]:
        return next((x for x in self.tasks if x["status"] == "running"), None)

    # ---------- выполнение ----------
    def tick(self):
        """Раз в секунду из цикла планировщика: запустить созревшую задачу, если сейчас ничего не выполняется."""
        with self._lock:
            if self.running():
                return
            now = time.time()
            ready = [x for x in self.tasks if x["status"] == "scheduled" and x["due_at"] <= now]
            if not ready:
                return
            task = min(ready, key=lambda x: x["due_at"])
            task["status"] = "running"
            task["started_at"] = now
            self._save()
        threading.Thread(target=self._run, args=(task,), daemon=True).start()

    def _run(self, task: Dict[str, Any]):
        self.log(t("log.task_started", project=task["project"], prompt=task["prompt"][:80]), "command")
        timeout = float(self._get_config().get("task_timeout_minutes", DEFAULT_TIMEOUT_MIN)) * 60
        try:
            result = run_resume(task["session_id"], task["prompt"], task["cwd"],
                                PERMISSIONS[task["permission"]], timeout)
        except subprocess.TimeoutExpired:
            result = {"ok": False, "text": t("task.timeout", min=int(timeout // 60)), "limit_hit": False}
        except Exception as e:
            result = {"ok": False, "text": str(e) or e.__class__.__name__, "limit_hit": False}

        with self._lock:
            task["finished_at"] = time.time()
            task["result"] = (result.get("text") or "")[:RESULT_MAX_CHARS]
            if result.get("limit_hit") and task["retries"] < MAX_LIMIT_RETRIES:
                task["retries"] += 1
                task["status"] = "scheduled"
                task["due_at"] = self._after_limit(result.get("reset_hint"))
                when = datetime.fromtimestamp(task["due_at"]).strftime("%H:%M")
                self._save()
                self.log(t("log.task_limit", project=task["project"], when=when), "warning")
                self.notify(t("toast.task_limit.title"), t("toast.task_limit.body", project=task["project"], when=when))
                return
            task["status"] = "done" if result.get("ok") else "failed"
            self._save()

        link = f"claudepulse:chat/{task['id']}"
        if task["status"] == "done":
            self.log(t("log.task_done", project=task["project"], result=task["result"][:500]), "success")
            self.notify(t("toast.task_done.title", project=task["project"]), _short(task["result"]),
                        launch=link, actions=[(t("toast.btn.open_chat"), link)])
        else:
            self.log(t("log.task_failed", project=task["project"], err=task["result"][:500]), "error")
            self.notify(t("toast.task_failed.title", project=task["project"]), _short(task["result"]),
                        launch=link, actions=[(t("toast.btn.open_chat"), link)])

    def _after_limit(self, reset_hint: Optional[str]) -> float:
        """Когда повторить после «лимит исчерпан»: время из текста ошибки, иначе из /usage, иначе через час."""
        if reset_hint:
            dt = parse_reset(reset_hint)
            if dt and dt.timestamp() > time.time():
                return dt.timestamp() + AFTER_RESET
        due = self.resolve_due("reset")
        return due if due and due > time.time() + 120 else time.time() + 3600


def _short(text: str, limit: int = 180) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[:limit - 1] + "…"
