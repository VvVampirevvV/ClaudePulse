"""Проверка новой версии на GitHub: раз в сутки, один GET без авторизации, никаких данных о пользователе."""
import json
import re
import threading
import time
import urllib.request
from typing import Callable, Optional, Dict, Any, Tuple

from src.config import APP_VERSION
from src.i18n import t

REPO = "VvVampirevvV/ClaudePulse"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{REPO}/releases/latest"
FIRST_CHECK_DELAY = 30
CHECK_EVERY = 24 * 3600


def parse_version(tag: str) -> Tuple[int, ...]:
    """'v3.2' / '3.2.1' / '3.1 VER WORK' -> (3, 2) / (3, 2, 1) / (3, 1). Мусор -> ()."""
    m = re.match(r'\s*v?(\d+(?:\.\d+)*)', tag or "")
    if not m:
        return ()
    parts = [int(x) for x in m.group(1).split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def is_newer(latest: str, current: str = APP_VERSION) -> bool:
    lv, cv = parse_version(latest), parse_version(current)
    return bool(lv) and bool(cv) and lv > cv


class UpdateChecker:
    def __init__(self, get_config: Callable[[], Dict[str, Any]], save: Callable[[], None]):
        self._get_config = get_config
        self._save = save
        self.notify: Optional[Callable[[str, str], None]] = None
        self.log: Optional[Callable[[str, str], None]] = None
        self.latest: Optional[str] = None   # новая версия, если есть
        self.url = RELEASES_URL
        self._running = False

    def start(self):
        if self._running:
            return
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._running = False

    def _loop(self):
        time.sleep(FIRST_CHECK_DELAY)
        while self._running:
            if self._get_config().get("check_updates", True):
                self.check()
            for _ in range(CHECK_EVERY):
                if not self._running:
                    return
                time.sleep(1)

    def check(self) -> Optional[str]:
        try:
            req = urllib.request.Request(API_URL, headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"ClaudePulse/{APP_VERSION}",
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.load(resp)
        except Exception:
            return None
        tag = str(data.get("tag_name") or "")
        if not is_newer(tag):
            self.latest = None
            return None
        self.latest = tag.lstrip("v")
        self.url = data.get("html_url") or RELEASES_URL
        cfg = self._get_config()
        if cfg.get("update_notified") != self.latest:
            cfg["update_notified"] = self.latest
            self._save()
            if self.log:
                self.log(t("log.update_available", version=self.latest), "success")
            if self.notify:
                self.notify(t("toast.update.title", version=self.latest), t("toast.update.body"))
        return self.latest
