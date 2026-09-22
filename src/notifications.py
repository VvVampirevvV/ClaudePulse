import subprocess
import threading
import os

# Скрипт постоянный: заголовок и текст приходят через переменные окружения,
# поэтому PowerShell не может выполнить ничего из текста (например, `$(...)` в сообщении об ошибке).
_PS_SCRIPT = r"""
try {
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
    $textNodes = $template.GetElementsByTagName("text")
    $textNodes.Item(0).AppendChild($template.CreateTextNode($env:CP_TOAST_TITLE)) | Out-Null
    $textNodes.Item(1).AppendChild($template.CreateTextNode($env:CP_TOAST_BODY)) | Out-Null
    $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
    $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Claude Pulse")
    $notifier.Show($toast)
} catch {}
"""


def send_toast(title: str, message: str):
    """Нативное Toast-уведомление Windows 10/11 через PowerShell (асинхронно)."""
    def _send():
        env = dict(os.environ)
        env["CP_TOAST_TITLE"] = title
        env["CP_TOAST_BODY"] = message
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
