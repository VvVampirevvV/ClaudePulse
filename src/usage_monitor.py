import time
import threading
from datetime import datetime
from typing import Callable, Optional, Dict, Any, List

from src.claude_parser import parse_usage, run_cli, ClaudeAccount
from src.i18n import t

DEFAULT_POLL_MINUTES = 5
USAGE_TIMEOUT = 30


class UsageMonitor:
    """
    Фоновый опрос `claude -p "/usage"` раз в N минут.
    Интерфейс и трей читают готовый снимок из памяти — никаких обращений к диску раз в секунду.
    """
    def __init__(self, get_config: Callable[[], Dict[str, Any]]):
        self._get_config = get_config
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._running = False
        self._callbacks: List[Callable[[], None]] = []
        self._pending_done: List[Callable[[], None]] = []
        self.account = ClaudeAccount()
        self.notify: Optional[Callable[[str, str], None]] = None
        self.log: Optional[Callable[[str, str], None]] = None

        self.snapshot: Dict[str, Any] = parse_usage("")
        self.account_info: Dict[str, Any] = {"logged_in": None, "subscription": "", "email": ""}
        self.fetched_at = 0.0
        self.last_error = ""
        self.fetching = False
        self._alerts_sent: Dict[str, int] = {}

    # ---------- жизненный цикл ----------
    def start(self):
        if self._running:
            return
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._running = False
        self._wake.set()

    def on_update(self, callback: Callable[[], None]):
        self._callbacks.append(callback)

    def request_refresh(self, callback: Optional[Callable[[], None]] = None):
        if callback:
            with self._lock:
                self._pending_done.append(callback)
        self._wake.set()

    def _loop(self):
        while self._running:
            self._fetch()
            minutes = float(self._get_config().get("usage_poll_minutes", DEFAULT_POLL_MINUTES) or DEFAULT_POLL_MINUTES)
            self._wake.wait(timeout=max(1.0, minutes) * 60)
            self._wake.clear()

    # ---------- опрос ----------
    def _fetch(self):
        self.fetching = True
        try:
            self.account_info = self.account.get()
            text = run_cli('claude -p "/usage"', timeout=USAGE_TIMEOUT)
            data = parse_usage(text)
            with self._lock:
                self.fetched_at = time.time()
                if data["has_data"]:
                    self.snapshot = data
                    self.last_error = ""
                else:
                    self.last_error = "no_data"
        except Exception as e:
            self.last_error = str(e) or e.__class__.__name__
        finally:
            self.fetching = False

        if self.last_error and self.log:
            self.log(t("log.usage_failed", err=self._error_text()), "warning")
        self._check_alerts()

        with self._lock:
            done, self._pending_done = self._pending_done, []
        for cb in self._callbacks + done:
            try:
                cb()
            except Exception:
                pass

    def _error_text(self) -> str:
        return t("quota.no_data_hint") if self.last_error == "no_data" else self.last_error

    # ---------- производные значения ----------
    def session_state(self) -> Dict[str, Any]:
        """Состояние 5-часового окна по реальному времени сброса из /usage."""
        s = self.snapshot
        reset: Optional[datetime] = s.get("session_reset")
        pct = s.get("session_pct")
        if pct is None:
            return {"known": False}
        now = datetime.now().astimezone()
        if reset and reset > now:
            return {"known": True, "active": True, "pct": pct, "reset": reset,
                    "remaining": (reset - now).total_seconds()}
        # Сброс уже прошёл: окно закрыто, свежий лимит. Снимок устарел — просим новый.
        if reset and self.fetched_at < reset.timestamp() and not self.fetching:
            self._wake.set()
        return {"known": True, "active": False, "pct": 0 if reset else pct, "reset": None, "remaining": 0}

    def weekly_state(self) -> Dict[str, Any]:
        s = self.snapshot
        pct = s.get("weekly_pct")
        if pct is None:
            return {"known": False}
        reset = s.get("weekly_reset")
        if reset and reset <= datetime.now().astimezone():
            return {"known": True, "pct": 0, "reset": None, "fable_pct": 0}
        return {"known": True, "pct": pct, "reset": reset, "fable_pct": s.get("fable_pct")}

    def worst_pct(self) -> Optional[int]:
        values = []
        ss, ws = self.session_state(), self.weekly_state()
        if ss.get("known"):
            values.append(ss["pct"])
        if ws.get("known"):
            values.append(ws["pct"])
        return max(values) if values else None

    def alert_levels(self) -> List[int]:
        levels = self._get_config().get("alert_levels", [80, 95])
        try:
            return sorted(int(x) for x in levels)
        except Exception:
            return [80, 95]

    # ---------- предупреждения ----------
    def _check_alerts(self):
        cfg = self._get_config()
        if not cfg.get("alerts_enabled", True) or not self.notify:
            return
        levels = self.alert_levels()
        for kind, state in (("session", self.session_state()), ("weekly", self.weekly_state())):
            if not state.get("known"):
                continue
            pct = state["pct"]
            reached = [lvl for lvl in levels if pct >= lvl]
            if not reached:
                continue
            level = reached[-1]
            reset = state.get("reset")
            key = f"{kind}|{reset.isoformat() if reset else ''}"
            if self._alerts_sent.get(key, 0) >= level:
                continue
            self._alerts_sent[key] = level
            when = format_reset(reset) if reset else t("quota.unknown_reset")
            self.notify(
                t(f"alert.{kind}.title", pct=pct),
                t("alert.body", when=when),
            )
            if self.log:
                self.log(t(f"alert.{kind}.title", pct=pct), "warning")


def format_reset(dt: Optional[datetime]) -> str:
    """'сегодня в 04:00' / 'завтра в 08:00' / '25 сент. в 08:00' — в локальном времени ПК."""
    if not dt:
        return "—"
    local = dt.astimezone()
    today = datetime.now().astimezone().date()
    hhmm = local.strftime("%H:%M")
    delta = (local.date() - today).days
    if delta == 0:
        return t("time.today_at", time=hhmm)
    if delta == 1:
        return t("time.tomorrow_at", time=hhmm)
    return t("time.date_at", date=f"{local.day} {t(f'month.{local.month}')}", time=hhmm)


def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02}:{m:02}:{s:02}"
