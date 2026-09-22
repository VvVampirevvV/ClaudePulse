import time
import threading
import webbrowser
from typing import Callable, Optional

import pystray
from PIL import Image, ImageDraw

from src.i18n import t
from src.usage_monitor import format_duration

# Цвет значка по израсходованной доле лимита (худшей из сессии и недели)
LEVEL_COLORS = {
    "unknown": (113, 113, 122),
    "ok": (16, 185, 129),
    "warn": (245, 158, 11),
    "critical": (239, 68, 68),
}


def usage_level(worst_pct: Optional[int], levels) -> str:
    if worst_pct is None:
        return "unknown"
    levels = sorted(levels) or [80, 95]
    if worst_pct >= levels[-1]:
        return "critical"
    if worst_pct >= levels[0]:
        return "warn"
    return "ok"


def make_icon(level: str, size: int = 64) -> Image.Image:
    """Круглый значок с молнией; цвет круга — уровень расхода лимита."""
    scale = 4  # рисуем крупно и уменьшаем — гладкие края
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((2 * scale, 2 * scale, s - 2 * scale, s - 2 * scale), fill=LEVEL_COLORS[level] + (255,))
    bolt = [(0.56, 0.12), (0.26, 0.56), (0.47, 0.56), (0.40, 0.88), (0.74, 0.42), (0.53, 0.42), (0.62, 0.12)]
    d.polygon([(x * s, y * s) for x, y in bolt], fill=(255, 255, 255, 255))
    return img.resize((size, size), Image.LANCZOS)


class TrayManager:
    def __init__(self, icon_path: str, scheduler, show_window_callback: Callable, exit_callback: Callable):
        self.icon_path = icon_path
        self.scheduler = scheduler
        self.show_window_callback = show_window_callback
        self.exit_callback = exit_callback
        self.icon = None
        self.running = False
        self._level = None

    def _quota_line(self) -> str:
        q = self.scheduler.get_quota_status()
        s, w = q["session"], q["weekly"]
        parts = []
        if s.get("known"):
            if s.get("active"):
                parts.append(t("tray.session", pct=s["pct"], left=format_duration(s["remaining"])))
            else:
                parts.append(t("tray.session_fresh"))
        if w.get("known"):
            parts.append(t("tray.weekly", pct=w["pct"]))
        return " · ".join(parts) if parts else t("tray.no_data")

    def _create_menu(self):
        s = self.scheduler
        return pystray.Menu(
            pystray.MenuItem(lambda item: "Claude Pulse", None, enabled=False),
            pystray.MenuItem(lambda item: self._quota_line(), None, enabled=False),
            pystray.MenuItem(lambda item: t("tray.next", next=s.get_next_run()), None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                lambda item: t("tray.on") if s.is_master_enabled() else t("tray.off"),
                lambda: s.set_master_enabled(not s.is_master_enabled())
            ),
            pystray.MenuItem(lambda item: t("tray.open"), self.show_window_callback, default=True),
            pystray.MenuItem(lambda item: t("tray.run_now"), lambda: s.run_now()),
            pystray.MenuItem(lambda item: t("tray.refresh"), lambda: s.refresh_live_quota()),
            pystray.MenuItem(
                lambda item: t("tray.resume") if s.paused_until else t("tray.pause2h"),
                lambda: s.resume() if s.paused_until else s.pause(2.0)
            ),
            pystray.MenuItem(lambda item: t("tray.pause_today"), lambda: s.pause_today(),
                             visible=lambda item: not s.paused_until),
            pystray.MenuItem(lambda item: t("tray.update", version=s.updates.latest or ""),
                             lambda: webbrowser.open(s.updates.url),
                             visible=lambda item: bool(s.updates.latest)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(lambda item: t("tray.exit"), self.exit_callback)
        )

    def run(self):
        self.running = True
        self.icon = pystray.Icon("ClaudePulse", make_icon("unknown"), "Claude Pulse", menu=self._create_menu())
        threading.Thread(target=self._update_loop, daemon=True).start()
        self.icon.run()

    def _update_loop(self):
        while self.running and self.icon:
            try:
                q = self.scheduler.get_quota_status()
                level = usage_level(q["worst_pct"], q["levels"])
                if level != self._level:
                    self._level = level
                    self.icon.icon = make_icon(level)
                title = f"Claude Pulse\n{self._quota_line()}\n{t('tray.next', next=self.scheduler.get_next_run())}"
                self.icon.title = title[:127]  # ограничение Windows NotifyIcon
                self.icon.update_menu()  # пересобрать пункты: пауза, обновление, текст с процентами
            except Exception:
                pass
            time.sleep(5)

    def stop(self):
        self.running = False
        if self.icon:
            self.icon.stop()
