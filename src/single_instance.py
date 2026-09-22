import os
import zlib
import ctypes
from ctypes import wintypes
import sys

# Глобальный уникальный идентификатор мьютекса для Claude Pulse
MUTEX_NAME = "Global\\ClaudePulse_SingleInstance_Mutex_9981"
# Отдельный профиль (CLAUDEPULSE_HOME) — отдельный экземпляр, например для второго аккаунта или тестов
if os.getenv("CLAUDEPULSE_HOME"):
    MUTEX_NAME += "_%08x" % zlib.crc32(os.getenv("CLAUDEPULSE_HOME").encode("utf-8"))
ERROR_ALREADY_EXISTS = 183
SW_RESTORE = 9

_single_instance_mutex = None

def ensure_single_instance(window_title: str = "Claude Pulse") -> bool:
    """
    Гарантирует запуск только одной копии приложения (Single Instance).
    
    Если копия уже запущена:
    - Находит существующее окно Claude Pulse (даже если оно свернуто в трей).
    - Разворачивает его на передний план (SW_RESTORE + SetForegroundWindow).
    - Возвращает False (вызывающий процесс должен немедленно завершиться).
    
    Если это первый запуск:
    - Захватывает мьютекс Windows на все время жизни процесса.
    - Возвращает True.
    """
    global _single_instance_mutex

    try:
        # use_last_error: ctypes сохраняет код ошибки сразу после вызова. Отдельный вызов
        # kernel32.GetLastError() мог вернуть чужой устаревший 183 и «найти» несуществующую копию.
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
        user32 = ctypes.windll.user32

        # 1. Создаем глобальный именованный мьютекс Windows
        ctypes.set_last_error(0)
        _single_instance_mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        last_error = ctypes.get_last_error()

        if last_error == ERROR_ALREADY_EXISTS:
            # Экземпляр уже запущен! Ищем существующее окно
            hwnd = user32.FindWindowW(None, window_title)

            # Если по точному названию не найдено, пробуем найти окно, содержащее "Claude Pulse"
            if not hwnd:
                try:
                    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
                    found_hwnd = []

                    def enum_windows_callback(h, _):
                        length = user32.GetWindowTextLengthW(h)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(h, buff, length + 1)
                            if "Claude Pulse" in buff.value:
                                found_hwnd.append(h)
                                return False
                        return True

                    user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)
                    if found_hwnd:
                        hwnd = found_hwnd[0]
                except Exception:
                    pass

            if hwnd:
                try:
                    # Разворачиваем окно из трея / свернутого состояния и выводим на передний план
                    user32.ShowWindow(hwnd, SW_RESTORE)
                    user32.SetForegroundWindow(hwnd)
                except Exception:
                    pass

            return False

        return True
    except Exception:
        # В случае непредвиденных ограничений Win32 продолжаем запуск
        return True
