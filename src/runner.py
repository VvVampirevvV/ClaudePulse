import subprocess
import threading
import os
import time
from typing import Callable

from src.procenv import clean_env

def run_command(
    command: str,
    working_dir: str,
    hidden: bool,
    wake_pc: bool,
    callback: Callable[[str, str, int, float], None],
    timeout: float = 45.0
):
    """
    Выполняет CLI-команду в отдельном потоке с защитой от зависаний по таймауту.
    """
    def target():
        start_time = time.time()
        creationflags = 0
        if hidden and os.name == 'nt':
            creationflags = subprocess.CREATE_NO_WINDOW
            
        process = None
        try:
            process = subprocess.Popen(
                command,
                cwd=working_dir,
                shell=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                env=clean_env(),
                stderr=subprocess.PIPE,
                creationflags=creationflags
            )
            
            stdout_bytes, stderr_bytes = process.communicate(timeout=timeout)
            duration = round(time.time() - start_time, 2)
            
            try:
                stdout_data = stdout_bytes.decode('utf-8')
            except UnicodeDecodeError:
                stdout_data = stdout_bytes.decode('cp866', errors='replace')
                
            try:
                stderr_data = stderr_bytes.decode('utf-8')
            except UnicodeDecodeError:
                stderr_data = stderr_bytes.decode('cp866', errors='replace')
            
            callback(stdout_data, stderr_data, process.returncode, duration)
            
        except subprocess.TimeoutExpired:
            duration = round(time.time() - start_time, 2)
            if process:
                try:
                    # Принудительно завершаем зависший процесс
                    if os.name == 'nt':
                        subprocess.run(f"taskkill /F /T /PID {process.pid}", shell=True, capture_output=True)
                    else:
                        process.kill()
                except Exception:
                    pass
            callback("", f"Ошибка: превышен таймаут выполнения ({timeout} сек). Процесс остановлен.", -2, duration)
            
        except Exception as e:
            duration = round(time.time() - start_time, 2)
            callback("", str(e), -1, duration)

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
