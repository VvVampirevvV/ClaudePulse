import schedule
import time
import threading
from datetime import datetime, timedelta
from src.runner import run_command
from src.config import save_config
from src.claude_parser import ClaudeParser
from typing import Callable, Optional, Dict, Any
import ctypes

QUOTA_WINDOW_DURATION = 5 * 3600 # 5 часов в секундах

class SchedulerManager:
    def __init__(self):
        self.running = False
        self.thread = None
        self.config: Dict[str, Any] = {}
        self.log_callback: Optional[Callable[[str, str], None]] = None
        self.notification_callback: Optional[Callable[[str, str], None]] = None
        self.paused_until: Optional[float] = None
        self.wake_timer = None
        self.on_schedule_change: Optional[Callable[[], None]] = None
        self.claude_parser = ClaudeParser()
        self.forced_reset_time: Optional[str] = None # Если спарсено точное время из ошибки
        self.last_run_stats: Dict[str, Any] = {
            "timestamp": 0.0,
            "duration": 0.0,
            "exit_code": 0,
            "status": "Готов к работе",
            "summary": "Ожидание первого пинга"
        }

    def set_config(self, config: dict):
        self.config = config
        self._reschedule()

    def is_master_enabled(self) -> bool:
        return bool(self.config.get("master_enabled", True))

    def set_master_enabled(self, enabled: bool):
        self.config["master_enabled"] = enabled
        save_config(self.config)
        status_txt = "АКТИВИРОВАН (ON)" if enabled else "ПРИОСТАНОВЛЕН (OFF)"
        self._log(f"Мастер-переключатель: {status_txt}", "success" if enabled else "warning")
        self._notify_change()

    def get_last_run_stats(self) -> Dict[str, Any]:
        return self.last_run_stats
        
    def set_log_callback(self, callback: Callable):
        self.log_callback = callback
        
    def set_notification_callback(self, callback: Callable):
        self.notification_callback = callback
        
    def set_schedule_change_callback(self, callback: Callable):
        self.on_schedule_change = callback

    def _log(self, message: str, tag: str = "normal"):
        if self.log_callback:
            self.log_callback(message, tag)
        
    def pause(self, hours: float):
        self.paused_until = time.time() + (hours * 3600)
        self._log(f"Расписание приостановлено на {hours} ч.", "warning")
        self._notify_change()
            
    def resume(self):
        self.paused_until = None
        self._log("Расписание возобновлено.", "success")
        self._notify_change()

    def get_claude_details(self) -> Dict[str, Any]:
        """Возвращает информацию о подписке и токене Claude."""
        auth = self.claude_parser.get_auth_info()
        session = self.claude_parser.get_latest_session_details()
        return {
            "subscription": auth.get("subscriptionType", "Max"),
            "email": auth.get("email", ""),
            "model": session.get("model_name") or auth.get("model", "Opus 5"),
            "tokens_left": session.get("tokens_left", "100%"),
            "tokens_percent": session.get("tokens_percent", 100.0)
        }

    def get_quota_status(self) -> Dict[str, Any]:
        """
        Возвращает детальную информацию о реальном 5-часовом окне квоты:
        - Синхронизируется с реальными логами сессий Claude Code
        - Учитывает точное время сброса при переполнении лимитов
        """
        now = time.time()
        
        # 1. Проверяем реальную активность в сессиях Claude Code
        real_session = self.claude_parser.get_latest_session_details()
        if real_session["is_active_window"]:
            session_start = real_session["last_interaction_time"]
            current_config_start = self.config.get("quota_window_started_at", 0.0)
            
            # Если в сессии более свежий запуск, чем у нас в конфиге — синхронизируем
            if session_start > current_config_start:
                self.config["quota_window_started_at"] = session_start
                save_config(self.config)

        started_at = self.config.get("quota_window_started_at", 0.0)
        claude_info = self.get_claude_details()
        live_usage = self.claude_parser.get_live_usage()

        base_data = {
            **claude_info,
            "weekly_has_data": live_usage.get("has_data", False),
            "weekly_used_pct": live_usage.get("weekly_used_pct", 0),
            "weekly_remaining_pct": live_usage.get("weekly_remaining_pct", 100),
            "weekly_resets_str": live_usage.get("weekly_resets_str", ""),
            "fable_used_pct": live_usage.get("fable_used_pct", 0),
            "session_used_pct": live_usage.get("session_used_pct", 0),
            "session_resets_str": live_usage.get("session_resets_str", "")
        }

        # Если был перехвачен точный сброс (Rate Limit Exceeded)
        if self.forced_reset_time:
            return {
                "active": True,
                "remaining_seconds": 0,
                "remaining_str": f"Сброс в {self.forced_reset_time}",
                "progress": 0.95,
                "reset_time_str": self.forced_reset_time,
                "source": "Лимит исчерпан (Anthropic)",
                **base_data
            }

        if not started_at:
            return {
                "active": False,
                "remaining_seconds": 0,
                "remaining_str": "Лимиты не запущены",
                "progress": 0.0,
                "reset_time_str": "--:--",
                "source": "Ожидание первого запроса",
                **base_data
            }
            
        elapsed = now - started_at
        if elapsed < QUOTA_WINDOW_DURATION:
            remaining = QUOTA_WINDOW_DURATION - elapsed
            h, rem = divmod(int(remaining), 3600)
            m, s = divmod(rem, 60)
            reset_dt = datetime.fromtimestamp(started_at + QUOTA_WINDOW_DURATION)
            progress = min(1.0, max(0.0, elapsed / QUOTA_WINDOW_DURATION))
            return {
                "active": True,
                "remaining_seconds": remaining,
                "remaining_str": f"{h:02}:{m:02}:{s:02}",
                "progress": progress,
                "reset_time_str": reset_dt.strftime("%H:%M"),
                "source": "Claude Code (Синхронизировано)",
                **base_data
            }
        else:
            return {
                "active": False,
                "remaining_seconds": 0,
                "remaining_str": "Окно завершено (квота сброшена)",
                "progress": 1.0,
                "reset_time_str": "Готово",
                "source": "Окно истекло",
                **base_data
            }

    def refresh_live_quota(self, callback: Optional[Callable] = None):
        """Асинхронно запрашивает официальные недельные и сессионные квоты."""
        def _target():
            self.claude_parser.get_live_usage(force_refresh=True)
            self._notify_change()
            if callback:
                callback()
        threading.Thread(target=_target, daemon=True).start()

    def run_now(self):
        cmd = self.config.get('command', '')
        self._log(f"Ручной запуск. Выполняю: {cmd}", "command")
        self._execute_job(is_manual=True)

    def _execute_job(self, is_manual: bool = False):
        cmd = self.config.get('command', '')
        working_dir = self.config.get('working_dir', '.')
        hidden = self.config.get('hidden_console', True)
        wake_pc = self.config.get('wake_pc', False)
        timeout = float(self.config.get('timeout_seconds', 45))

        def on_complete(stdout: str, stderr: str, exit_code: int, duration: float):
            combined_output = f"{stdout}\n{stderr}"
            
            # Проверяем, вернул ли сервер Anthropic ошибку переполнения лимитов
            reset_time_match = self.claude_parser.parse_rate_limit_reset_time(combined_output)
            if reset_time_match:
                self.forced_reset_time = reset_time_match
                self._log(f"⚠️ Достигнут лимит сообщений! Точный сброс в: {reset_time_match}", "warning")
                if self.config.get("notify", True) and self.notification_callback:
                    self.notification_callback(
                        "Claude Pulse: Лимит сообщений!",
                        f"Квота исчерпана. Лимиты сбросятся в {reset_time_match}."
                    )
            else:
                self.forced_reset_time = None

            if exit_code == 0:
                self.config["quota_window_started_at"] = time.time()
                save_config(self.config)
                
                resp = stdout.strip() if stdout.strip() else "(пустой ответ)"
                self._log(f"Успех (Exit Code: 0, {duration}с):\n{resp}", "success")
                
                reset_time = (datetime.now() + timedelta(hours=5)).strftime("%H:%M")
                if self.config.get("notify", True) and self.notification_callback:
                    self.notification_callback(
                        "Claude Pulse: Сессия прогрета!",
                        f"5-часовое окно открыто. Сброс лимитов в {reset_time}."
                    )
            else:
                err = stderr.strip() if stderr.strip() else stdout.strip()
                self._log(f"Ответ (Exit Code: {exit_code}, {duration}с):\n{err}", "error" if not reset_time_match else "warning")
                if not reset_time_match and self.config.get("notify", True) and self.notification_callback:
                    self.notification_callback(
                        "Claude Pulse: Ошибка выполнения!",
                        f"Код {exit_code}: {err[:100]}"
                    )
                    
            self.last_run_stats = {
                "timestamp": time.time(),
                "duration": duration,
                "exit_code": exit_code,
                "command": cmd,
                "status": "200 OK" if exit_code == 0 else f"Ошибка {exit_code}",
                "summary": f"Пинг выполнен за {duration:.2f}с" if exit_code == 0 else f"Ошибка (код {exit_code})"
            }
            self._notify_change()
                    
        run_command(cmd, working_dir, hidden, wake_pc, on_complete, timeout=timeout)

    def _job(self):
        if not self.config.get("master_enabled", True):
            self._log("Запуск пропущен (Claude Pulse выключен).", "warning")
            return

        if self.paused_until and time.time() < self.paused_until:
            self._log("Запуск пропущен (активна пауза).", "warning")
            return
            
        cmd = self.config.get('command', '')
        self._log(f"Триггер расписания. Выполняю: {cmd}", "command")
        self._execute_job()
        
        if self.config.get('wake_pc', False):
            self._set_wake_timer()

    def _reschedule(self):
        schedule.clear()
        if not self.config:
            return
            
        mode = self.config.get('mode', 'fixed')
        if mode == 'fixed':
            times_list = self.config.get('times', ['05:00'])
            active_days = self.config.get('days', [])
            
            for day in active_days:
                for t in times_list:
                    try:
                        if day == "Пн": schedule.every().monday.at(t).do(self._job)
                        elif day == "Вт": schedule.every().tuesday.at(t).do(self._job)
                        elif day == "Ср": schedule.every().wednesday.at(t).do(self._job)
                        elif day == "Чт": schedule.every().thursday.at(t).do(self._job)
                        elif day == "Пт": schedule.every().friday.at(t).do(self._job)
                        elif day == "Сб": schedule.every().saturday.at(t).do(self._job)
                        elif day == "Вс": schedule.every().sunday.at(t).do(self._job)
                    except Exception as e:
                        self._log(f"Ошибка парсинга времени {t}: {e}", "error")
                    
            if self.config.get('wake_pc', False):
                self._set_wake_timer()

        elif mode == 'interval':
            hours = float(self.config.get('interval_hours', 1))
            minutes = int(hours * 60)
            if minutes > 0:
                schedule.every(minutes).minutes.do(self._job)
                
        self._notify_change()
                
    def get_next_run(self) -> str:
        if not self.config.get("master_enabled", True):
            return "Приостановлен (OFF)"
            
        if self.paused_until and time.time() < self.paused_until:
            rem = int(self.paused_until - time.time())
            h, r = divmod(rem, 3600)
            m, s = divmod(r, 60)
            return f"Пауза ({h:02}:{m:02}:{s:02})"
            
        next_run = schedule.next_run()
        if next_run:
            diff = next_run - datetime.now()
            if diff.total_seconds() < 0:
                return "Прямо сейчас"
                
            hours, remainder = divmod(int(diff.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            days = diff.days
            
            if days > 0:
                return f"{days}д {hours:02}:{minutes:02}:{seconds:02}"
            return f"{hours:02}:{minutes:02}:{seconds:02}"
        return "Не задано"

    def _set_wake_timer(self):
        next_run = schedule.next_run()
        if not next_run:
            return
            
        try:
            diff = next_run - datetime.now()
            secs = max(1, int(diff.total_seconds()))
            due_time = ctypes.c_int64(-int(secs * 10_000_000))
            
            kernel32 = ctypes.windll.kernel32
            timer = kernel32.CreateWaitableTimerW(None, True, "ClaudePulseWakeTimer")
            if timer:
                kernel32.SetWaitableTimer(timer, ctypes.byref(due_time), 0, None, None, True)
                self.wake_timer = timer
        except Exception as e:
            self._log(f"Ошибка установки таймера пробуждения: {e}", "error")

    def _notify_change(self):
        if self.on_schedule_change:
            self.on_schedule_change()

    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
            
    def _run_loop(self):
        while self.running:
            schedule.run_pending()
            self._notify_change()
            time.sleep(1)
