import schedule
import time
import threading
import ctypes
from datetime import datetime, timedelta
from typing import Callable, Optional, Dict, Any, List, Tuple

from src.runner import run_command
from src.config import save_config, DAY_CODES, QUOTA_WINDOW_HOURS
from src.claude_parser import parse_rate_limit_reset_time
from src.usage_monitor import UsageMonitor
from src.i18n import t

CATCH_UP_DELAY = 45          # сек после старта: даём /usage прийти, чтобы не пинговать в открытое окно
CATCH_UP_LOOKBACK_HOURS = 24

_WEEKDAY_JOBS = [
    lambda s: s.monday, lambda s: s.tuesday, lambda s: s.wednesday, lambda s: s.thursday,
    lambda s: s.friday, lambda s: s.saturday, lambda s: s.sunday,
]


def _later(delay: float, fn: Callable):
    timer = threading.Timer(delay, fn)
    timer.daemon = True
    timer.start()


def parse_hhmm(value: str) -> Optional[Tuple[int, int]]:
    try:
        hh, mm = value.strip().split(":")
        hh, mm = int(hh), int(mm)
        if 0 <= hh < 24 and 0 <= mm < 60:
            return hh, mm
    except Exception:
        pass
    return None


def ping_time_for_target(target: str) -> Optional[Tuple[int, int, int]]:
    """Свежий лимит к 14:00 -> пинг в 09:00. Возвращает (часы, минуты, сдвиг дня: 0 или -1)."""
    parsed = parse_hhmm(target)
    if not parsed:
        return None
    total = parsed[0] * 60 + parsed[1] - QUOTA_WINDOW_HOURS * 60
    day_shift = -1 if total < 0 else 0
    total %= 24 * 60
    return total // 60, total % 60, day_shift


def planned_slots(config: Dict[str, Any]) -> List[Tuple[int, int, int]]:
    """Все запуски недели: (индекс дня 0=Пн, часы, минуты) для режимов fixed/target."""
    mode = config.get("mode", "fixed")
    days = [DAY_CODES.index(d) for d in config.get("days", []) if d in DAY_CODES]
    slots = []
    if mode == "fixed":
        for d in days:
            for tm in config.get("times", []):
                p = parse_hhmm(tm)
                if p:
                    slots.append((d, p[0], p[1]))
    elif mode == "target":
        # Дни — это дни, к которым нужен свежий лимит; пинг может уйти на вечер накануне
        for d in days:
            for tm in config.get("target_times", []):
                p = ping_time_for_target(tm)
                if p:
                    slots.append(((d + p[2]) % 7, p[0], p[1]))
    return sorted(set(slots))


class SchedulerManager:
    def __init__(self):
        self.running = False
        self.thread = None
        self.config: Dict[str, Any] = {}
        self.log_callback: Optional[Callable[[str, str], None]] = None
        self.notification_callback: Optional[Callable[[str, str], None]] = None
        self.paused_until: Optional[float] = None
        self.wake_timer = None
        self.forced_reset_time: Optional[str] = None
        self.job_running = False
        self.usage = UsageMonitor(lambda: self.config)
        self.usage.log = self._log
        self.usage.on_update(self._on_usage_update)
        self.last_run_stats: Dict[str, Any] = {"timestamp": 0.0, "duration": 0.0, "exit_code": None, "command": ""}

    # ---------- конфиг ----------
    def set_config(self, config: dict):
        self.config = config
        self._reschedule()

    def save(self):
        save_config(self.config)

    def is_master_enabled(self) -> bool:
        return bool(self.config.get("master_enabled", True))

    def set_master_enabled(self, enabled: bool):
        self.config["master_enabled"] = enabled
        self.save()
        self._log(t("log.master_on") if enabled else t("log.master_off"), "success" if enabled else "warning")

    def get_last_run_stats(self) -> Dict[str, Any]:
        return self.last_run_stats

    def set_log_callback(self, callback: Callable):
        self.log_callback = callback

    def set_notification_callback(self, callback: Callable):
        self.notification_callback = callback
        self.usage.notify = self._notify

    def _log(self, message: str, tag: str = "normal"):
        if self.log_callback:
            self.log_callback(message, tag)

    def _notify(self, title: str, message: str):
        if self.config.get("notify", True) and self.notification_callback:
            self.notification_callback(title, message)

    # ---------- пауза ----------
    def pause(self, hours: float):
        self.paused_until = time.time() + (hours * 3600)
        self._log(t("log.paused", hours=hours), "warning")

    def resume(self):
        self.paused_until = None
        self._log(t("log.resumed"), "success")

    # ---------- квоты ----------
    def get_quota_status(self) -> Dict[str, Any]:
        """Сводка для UI и трея. Только данные из памяти — вызывать можно хоть каждую секунду."""
        u = self.usage
        return {
            "session": u.session_state(),
            "weekly": u.weekly_state(),
            "worst_pct": u.worst_pct(),
            "levels": u.alert_levels(),
            "tips": u.snapshot.get("tips", []),
            "account": u.account_info,
            "fetched_at": u.fetched_at,
            "fetching": u.fetching,
            "error": u.last_error,
            "forced_reset": self.forced_reset_time,
        }

    def refresh_live_quota(self, callback: Optional[Callable] = None):
        self.usage.request_refresh(callback)

    def _on_usage_update(self):
        # Свежие данные /usage важнее времени из текста старой ошибки
        if self.usage.last_error == "":
            self.forced_reset_time = None

    # ---------- запуск команды ----------
    def run_now(self):
        self._log(t("log.manual_run", cmd=self.config.get('command', '')), "command")
        self._execute_job()

    def _execute_job(self):
        if self.job_running:
            self._log(t("log.already_running"), "warning")
            return
        cmd = self.config.get('command', '')
        if not cmd.strip():
            self._log(t("log.empty_command"), "error")
            return
        self.job_running = True
        self.config["last_job_at"] = time.time()
        self.save()

        ss = self.usage.session_state()
        if ss.get("active"):
            self._log(t("log.window_already_open", when=ss["reset"].astimezone().strftime("%H:%M")), "warning")

        def on_complete(stdout: str, stderr: str, exit_code: int, duration: float):
            self.job_running = False
            combined = f"{stdout}\n{stderr}"
            reset_hint = parse_rate_limit_reset_time(combined) if exit_code != 0 else None
            if reset_hint:
                self.forced_reset_time = reset_hint
                self._log(t("log.limit_hit", when=reset_hint), "warning")
                self._notify(t("toast.limit.title"), t("toast.limit.body", when=reset_hint))

            if exit_code == 0:
                resp = stdout.strip() or t("log.empty_response")
                self._log(t("log.success", code=exit_code, dur=duration, resp=resp), "success")
                if ss.get("active"):
                    reset_at = ss["reset"].astimezone().strftime("%H:%M")
                else:
                    reset_at = (datetime.now() + timedelta(hours=QUOTA_WINDOW_HOURS)).strftime("%H:%M")
                self._notify(t("toast.ok.title"), t("toast.ok.body", when=reset_at))
            else:
                err = stderr.strip() or stdout.strip()
                self._log(t("log.failure", code=exit_code, dur=duration, err=err), "warning" if reset_hint else "error")
                if not reset_hint:
                    self._notify(t("toast.fail.title"), t("toast.fail.body", code=exit_code, err=err[:100]))

            self.last_run_stats = {
                "timestamp": time.time(),
                "duration": duration,
                "exit_code": exit_code,
                "command": cmd,
            }
            # Окно могло открыться — через пару секунд спросим /usage
            _later(3.0, self.usage.request_refresh)

        run_command(
            cmd,
            self.config.get('working_dir') or '.',
            self.config.get('hidden_console', True),
            self.config.get('wake_pc', False),
            on_complete,
            timeout=float(self.config.get('timeout_seconds', 45)),
        )

    def _job(self):
        if not self.config.get("master_enabled", True):
            self._log(t("log.skipped_off"), "warning")
            return
        if self.paused_until and time.time() < self.paused_until:
            self._log(t("log.skipped_paused"), "warning")
            return
        self._log(t("log.scheduled_run", cmd=self.config.get('command', '')), "command")
        self._execute_job()
        if self.config.get('wake_pc', False):
            self._set_wake_timer()

    # ---------- расписание ----------
    def _reschedule(self):
        schedule.clear()
        if not self.config:
            return
        mode = self.config.get('mode', 'fixed')
        if mode in ("fixed", "target"):
            for day_idx, hh, mm in planned_slots(self.config):
                try:
                    _WEEKDAY_JOBS[day_idx](schedule.every()).at(f"{hh:02}:{mm:02}").do(self._job)
                except Exception as e:
                    self._log(t("log.bad_time", time=f"{hh:02}:{mm:02}", err=e), "error")
        elif mode == 'interval':
            try:
                minutes = int(float(self.config.get('interval_hours', 1)) * 60)
            except (TypeError, ValueError):
                minutes = 0
            if minutes > 0:
                schedule.every(minutes).minutes.do(self._job)
        if self.config.get('wake_pc', False):
            self._set_wake_timer()

    def get_next_run(self) -> str:
        if not self.config.get("master_enabled", True):
            return t("next.off")
        if self.paused_until and time.time() < self.paused_until:
            rem = int(self.paused_until - time.time())
            h, r = divmod(rem, 3600)
            m, s = divmod(r, 60)
            return t("next.paused", time=f"{h:02}:{m:02}:{s:02}")
        next_run = schedule.next_run()
        if not next_run:
            return t("next.none")
        diff = next_run - datetime.now()
        if diff.total_seconds() < 0:
            return t("next.now")
        hours, remainder = divmod(int(diff.total_seconds()) % 86400, 3600)
        minutes, seconds = divmod(remainder, 60)
        if diff.days > 0:
            return t("next.days", d=diff.days, time=f"{hours:02}:{minutes:02}:{seconds:02}")
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    def next_run_clock(self) -> str:
        next_run = schedule.next_run()
        return next_run.strftime("%H:%M") if next_run else "--:--"

    def _last_missed_slot(self, now: datetime) -> Optional[datetime]:
        """Последний запланированный запуск за последние сутки (для наверстывания)."""
        best = None
        for day_idx, hh, mm in planned_slots(self.config):
            for back in range(0, 2):
                day = now - timedelta(days=back)
                if day.weekday() != day_idx:
                    continue
                slot = day.replace(hour=hh, minute=mm, second=0, microsecond=0)
                if slot <= now and now - slot <= timedelta(hours=CATCH_UP_LOOKBACK_HOURS):
                    if best is None or slot > best:
                        best = slot
        return best

    def _check_catch_up(self):
        if not self.config.get("catch_up_missed", True) or not self.is_master_enabled():
            return
        if self.config.get("mode") not in ("fixed", "target"):
            return
        now = datetime.now()
        slot = self._last_missed_slot(now)
        if not slot or float(self.config.get("last_job_at", 0.0)) >= slot.timestamp():
            return
        if self.usage.session_state().get("active"):
            self._log(t("log.catchup_skip_open", slot=slot.strftime("%H:%M")), "normal")
            self.config["last_job_at"] = time.time()
            self.save()
            return
        self._log(t("log.catchup_run", slot=slot.strftime("%H:%M")), "command")
        self._execute_job()

    def _set_wake_timer(self):
        next_run = schedule.next_run()
        if not next_run:
            return
        try:
            secs = max(1, int((next_run - datetime.now()).total_seconds()))
            due_time = ctypes.c_int64(-int(secs * 10_000_000))
            kernel32 = ctypes.windll.kernel32
            timer = kernel32.CreateWaitableTimerW(None, True, "ClaudePulseWakeTimer")
            if timer:
                kernel32.SetWaitableTimer(timer, ctypes.byref(due_time), 0, None, None, True)
                self.wake_timer = timer
        except Exception as e:
            self._log(t("log.wake_error", err=e), "error")

    # ---------- поток ----------
    def start(self):
        if not self.running:
            self.running = True
            self.usage.start()
            _later(CATCH_UP_DELAY, self._check_catch_up)
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()

    def stop(self):
        self.running = False
        self.usage.stop()
        if self.thread:
            self.thread.join(timeout=1.0)

    def _run_loop(self):
        while self.running:
            schedule.run_pending()
            time.sleep(1)
