import pystray
from PIL import Image
from typing import Callable
import threading
import time

from src.config import APP_VERSION

class TrayManager:
    def __init__(self, icon_path: str, scheduler, show_window_callback: Callable, exit_callback: Callable):
        self.icon_path = icon_path
        self.scheduler = scheduler
        self.show_window_callback = show_window_callback
        self.exit_callback = exit_callback
        self.icon = None
        self.running = False

    def _get_quota_text(self) -> str:
        q = self.scheduler.get_quota_status()
        if q["active"]:
            return f"Квота: сброс в {q['reset_time_str']} ({q['remaining_str']})"
        return "Квота: не активна"

    def _create_menu(self):
        return pystray.Menu(
            pystray.MenuItem(
                lambda item: f"Claude Pulse {APP_VERSION}",
                None,
                enabled=False
            ),
            pystray.MenuItem(
                lambda item: f"След. запуск: {self.scheduler.get_next_run()}",
                None,
                enabled=False
            ),
            pystray.MenuItem(
                lambda item: self._get_quota_text(),
                None,
                enabled=False
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                lambda item: "✔ Claude Pulse: ВКЛ" if self.scheduler.is_master_enabled() else "✖ Claude Pulse: ВЫКЛ",
                lambda: self.scheduler.set_master_enabled(not self.scheduler.is_master_enabled())
            ),
            pystray.MenuItem("Открыть панель управления", self.show_window_callback, default=True),
            pystray.MenuItem("▶ Запустить сейчас", lambda: self.scheduler.run_now()),
            pystray.MenuItem(
                lambda item: "Возобновить" if self.scheduler.paused_until else "Пауза на 2 часа",
                lambda: self.scheduler.resume() if self.scheduler.paused_until else self.scheduler.pause(2.0)
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Выход", self.exit_callback)
        )

    def run(self):
        self.running = True
        try:
            image = Image.open(self.icon_path)
        except Exception:
            image = Image.new('RGB', (64, 64), color=(16, 185, 129))
            
        self.icon = pystray.Icon(
            "ClaudePulse",
            image,
            "Claude Pulse",
            menu=self._create_menu()
        )
        
        # Поток обновления тултипа
        threading.Thread(target=self._update_tooltip_loop, daemon=True).start()
        self.icon.run()
        
    def _update_tooltip_loop(self):
        while self.running and self.icon:
            try:
                next_run = self.scheduler.get_next_run()
                q = self.scheduler.get_quota_status()
                if q["active"]:
                    title_text = f"Claude Pulse\nКвота: {q['remaining_str']}\nСлед. запуск: {next_run}"
                else:
                    title_text = f"Claude Pulse\nСлед. запуск: {next_run}"
                    
                self.icon.title = title_text[:127] # Ограничение длины Windows NotifyIcon
            except Exception:
                pass
            time.sleep(1)
        
    def stop(self):
        self.running = False
        if self.icon:
            self.icon.stop()
