"""Журнал в файл: %APPDATA%\\ClaudePulse\\logs\\claudepulse.log (3 файла по 512 КБ)."""
import logging
from logging.handlers import RotatingFileHandler

from src.config import APPDATA_DIR

LOG_DIR = APPDATA_DIR / "logs"
LOG_FILE = LOG_DIR / "claudepulse.log"

_LEVELS = {"error": logging.ERROR, "warning": logging.WARNING}
_logger = None


def _get_logger():
    global _logger
    if _logger is None:
        _logger = logging.getLogger("claudepulse")
        _logger.setLevel(logging.INFO)
        _logger.propagate = False
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(LOG_FILE, maxBytes=512 * 1024, backupCount=2, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S"))
            _logger.addHandler(handler)
        except OSError:
            _logger.addHandler(logging.NullHandler())
    return _logger


def write(message: str, tag: str = "normal"):
    """Строка в файл журнала. Ошибки записи никогда не роняют программу."""
    try:
        _get_logger().log(_LEVELS.get(tag, logging.INFO), message.replace("\n", "\n    "))
    except Exception:
        pass
