import sys
import os
import threading
from pathlib import Path

# Ensure src modules can be imported if running directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import load_config, APP_VERSION
from src.i18n import set_lang
from src.scheduler import SchedulerManager
from src.notifications import send_toast, register_app
from src import ipc, applog
from src.ui.main_window import MainWindow
from src.ui.tray import TrayManager
from src.single_instance import ensure_single_instance

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))  # запуск ссылкой claudepulse: идёт не из папки проекта
    return os.path.join(base_path, relative_path)

def main():
    command = ipc.parse_argv(sys.argv)  # запуск кликом по уведомлению: claudepulse:pause2h и т.п.

    # Защита от повторного запуска: разрешен только один экземпляр приложения.
    # Вторая копия передаёт команду первой и выходит; окно поднимаем только для «открыть».
    window_title = f"Claude Pulse {APP_VERSION}"
    if not ensure_single_instance(window_title, restore=command in (None, "open")):
        ipc.send(command or "open")
        sys.exit(0)

    config = load_config()
    set_lang(config.get("language", ""))

    # Initialize Scheduler
    scheduler = SchedulerManager()
    scheduler.set_config(config)
    scheduler.set_notification_callback(send_toast)

    icon_path = resource_path(os.path.join("assets", "icon.ico"))
    register_app(icon_path)
    applog.write(f"Claude Pulse {APP_VERSION} started")
    scheduler.start()
    
    app = None
    tray = None
    
    def on_closing():
        app.withdraw() # Hide window to tray
        
    def show_window(icon=None, item=None):
        def _restore():
            app.deiconify()
            app.lift()
            app.focus_force()
        app.after(0, _restore)
        
    def exit_app(icon=None, item=None):
        # Вызывается из потока трея — tkinter трогаем только из главного потока
        scheduler.stop()
        if tray:
            tray.stop()
        app.after(0, app.quit)
        
    app = MainWindow(scheduler, on_closing)
    tray = TrayManager(icon_path, scheduler, show_window, exit_app)
    
    # Run tray in a separate thread
    tray_thread = threading.Thread(target=tray.run, daemon=True)
    tray_thread.start()
    
    if command and command != "open":
        app.after(1000, lambda: app.handle_command(command))

    app.mainloop()

if __name__ == "__main__":
    main()
