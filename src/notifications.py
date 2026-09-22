import os
import sys
import json
import threading
import subprocess
from typing import List, Optional, Tuple

APP_ID = "ClaudePulse"
PROTOCOL = "claudepulse"

# Скрипт постоянный: все тексты приходят через переменные окружения и попадают в XML
# через InnerText/SetAttribute — PowerShell не может выполнить ничего из текста уведомления.
_PS_SCRIPT = r"""
try {
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $xml.LoadXml('<toast activationType="protocol"><visual><binding template="ToastGeneric"><text/><text/></binding></visual><actions/></toast>')
    $toast = $xml.SelectSingleNode('/toast')
    $toast.SetAttribute('launch', $env:CP_TOAST_LAUNCH)
    $texts = $xml.GetElementsByTagName('text')
    $texts.Item(0).InnerText = $env:CP_TOAST_TITLE
    $texts.Item(1).InnerText = $env:CP_TOAST_BODY
    $actions = $xml.SelectSingleNode('/toast/actions')
    foreach ($a in (ConvertFrom-Json $env:CP_TOAST_ACTIONS)) {
        $el = $xml.CreateElement('action')
        $el.SetAttribute('content', $a.label)
        $el.SetAttribute('arguments', $a.link)
        $el.SetAttribute('activationType', 'protocol')
        $actions.AppendChild($el) | Out-Null
    }
    if ($actions.ChildNodes.Length -eq 0) { $toast.RemoveChild($actions) | Out-Null }
    $notification = [Windows.UI.Notifications.ToastNotification]::new($xml)
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:CP_TOAST_APPID).Show($notification)
} catch {}
"""


def _launch_command() -> str:
    """Чем Windows откроет ссылку claudepulse:… — собранный exe или python main.py."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" "%1"'
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    exe = pythonw if os.path.exists(pythonw) else sys.executable
    main = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
    return f'"{exe}" "{main}" "%1"'


def _persistent_icon(icon_path: str) -> str:
    """PNG-значок в %APPDATA%: папка распаковки exe временная и после выхода удаляется."""
    try:
        from PIL import Image
        from src.config import APPDATA_DIR
        APPDATA_DIR.mkdir(parents=True, exist_ok=True)
        target = APPDATA_DIR / "icon.png"
        Image.open(icon_path).convert("RGBA").resize((64, 64)).save(target)
        return str(target)
    except Exception:
        return ""


def register_app(icon_path: str = ""):
    """
    Регистрация для текущего пользователя (HKCU, без прав администратора):
    - имя и значок в уведомлениях Windows (AppUserModelId);
    - ссылка claudepulse:… — клик по уведомлению и его кнопки запускают программу с командой.
    """
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\AppUserModelId\{APP_ID}") as k:
            winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, "Claude Pulse")
            png = _persistent_icon(icon_path)
            if png:
                winreg.SetValueEx(k, "IconUri", 0, winreg.REG_SZ, png)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{PROTOCOL}") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "URL:Claude Pulse")
            winreg.SetValueEx(k, "URL Protocol", 0, winreg.REG_SZ, "")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{PROTOCOL}\shell\open\command") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, _launch_command())
    except Exception:
        pass


def send_toast(title: str, message: str, launch: str = f"{PROTOCOL}:open",
               actions: Optional[List[Tuple[str, str]]] = None):
    """Уведомление Windows 10/11. launch — что открыть по клику; actions — кнопки (подпись, ссылка)."""
    def _send():
        env = dict(os.environ)
        env["CP_TOAST_TITLE"] = title
        env["CP_TOAST_BODY"] = message
        env["CP_TOAST_LAUNCH"] = launch
        env["CP_TOAST_ACTIONS"] = json.dumps([{"label": a[0], "link": a[1]} for a in (actions or [])], ensure_ascii=False)
        env["CP_TOAST_APPID"] = APP_ID
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", _PS_SCRIPT],
                env=env,
                capture_output=True,
                creationflags=creationflags,
                timeout=20,
            )
        except Exception:
            pass

    threading.Thread(target=_send, daemon=True).start()
