"""
Окружение для запуска claude.

Если Claude Pulse запущен из сессии Claude Code (из её терминала или приложения Claude), он наследует
служебные переменные этой сессии: CLAUDECODE, CLAUDE_CODE_SESSION_ID, CLAUDE_CODE_MESSAGING_SOCKET,
CLAUDE_CODE_SDK_HAS_HOST_AUTH_REFRESH, ANTHROPIC_BASE_URL и т.п. Тогда каждый наш `claude` обновляет вход
через ту сессию — и перестаёт работать, как только она закрылась или уснула (/usage молча пустеет).

Поэтому такие переменные убираем. Оставляем только те, что пользователь сам задал в Windows
(HKCU\\Environment и системное окружение): это его настройки, а не следы чужой сессии.
"""
import os
from typing import Dict, Set

_SESSION_MARKERS = ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_ENTRYPOINT")
_EXTRA = {"CLAUDECODE", "CLAUDE_PID", "CLAUDE_AGENT_SDK_VERSION", "CLAUDE_PREVIEW_CLASSIFIER_FLOOR",
          "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN"}


def _persistent_names() -> Set[str]:
    """Имена переменных, которые пользователь сохранил в Windows (они переживают перезагрузку)."""
    names: Set[str] = set()
    try:
        import winreg
        for root, path in ((winreg.HKEY_CURRENT_USER, r"Environment"),
                           (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")):
            try:
                with winreg.OpenKey(root, path) as key:
                    i = 0
                    while True:
                        try:
                            names.add(winreg.EnumValue(key, i)[0].upper())
                        except OSError:
                            break
                        i += 1
            except OSError:
                pass
    except ImportError:
        pass
    return names


def is_session_var(name: str) -> bool:
    # CLAUDE_* (CLAUDE_CODE_*, CLAUDE_EFFORT, CLAUDE_PID…) ставит сессия; CLAUDEPULSE_HOME — наша, её не трогаем
    up = name.upper()
    return up.startswith("CLAUDE_") or up in _EXTRA


def clean_env(env: Dict[str, str] = None, persistent: Set[str] = None) -> Dict[str, str]:
    """Копия окружения без следов чужой сессии Claude Code. Вне сессии — без изменений."""
    env = dict(os.environ if env is None else env)
    if not any(m in env for m in _SESSION_MARKERS):
        return env
    keep = _persistent_names() if persistent is None else {n.upper() for n in persistent}
    return {k: v for k, v in env.items() if not is_session_var(k) or k.upper() in keep}


def sanitize_process_env() -> int:
    """Очистить окружение самого процесса: все дочерние программы унаследуют уже чистое. Вернёт число убранных."""
    cleaned = clean_env()
    removed = [k for k in os.environ if k not in cleaned]
    for k in removed:
        del os.environ[k]
    return len(removed)
