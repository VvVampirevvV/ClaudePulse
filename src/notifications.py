import subprocess
import threading
import os

def send_toast(title: str, message: str):
    """
    Отправляет нативное всплывающее Toast-уведомление Windows 10/11 через PowerShell.
    Выполняется асинхронно без сторонних C-зависимостей.
    """
    def _send():
        t = title.replace('"', '`"').replace("'", "''")
        m = message.replace('"', '`"').replace("'", "''")
        
        ps_script = f"""
        try {{
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
            $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
            $textNodes = $template.GetElementsByTagName("text")
            $textNodes.Item(0).AppendChild($template.CreateTextNode("{t}")) | Out-Null
            $textNodes.Item(1).AppendChild($template.CreateTextNode("{m}")) | Out-Null
            $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
            $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Claude Pulse")
            $notifier.Show($toast)
        }} catch {{}}
        """
        try:
            creationflags = 0
            if os.name == 'nt':
                creationflags = subprocess.CREATE_NO_WINDOW
                
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                creationflags=creationflags,
                timeout=5
            )
        except Exception:
            pass

    threading.Thread(target=_send, daemon=True).start()
