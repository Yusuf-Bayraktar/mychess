"""Uygulama loglarını kullanıcının log dizinindeki dönen bir dosyaya yazar.

Paketli uygulamada konsol olmadığı için yakalanmayan hatalar da (Tk geri
çağrıları hariç; onları ChessApp yakalar) buraya yönlendirilir.
"""

import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType

LOGGER_NAME: str = "mychess"
LOG_FILE_NAME: str = "mychess.log"
MAX_LOG_BYTES: int = 1_000_000
LOG_BACKUPS: int = 3

logger = logging.getLogger(__name__)
_log_file: Path | None = None


def default_log_dir() -> Path:
    """Platformun alışılmış log dizini (macOS: ~/Library/Logs/mychess)."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "mychess"
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Local"
        return root / "mychess" / "logs"
    base = os.environ.get("XDG_STATE_HOME")
    root = Path(base) if base else Path.home() / ".local" / "state"
    return root / "mychess"


def log_file() -> Path | None:
    """Etkin log dosyasının yolu; dosyaya yazılamıyorsa None."""
    return _log_file


def log_hint() -> str:
    """Hata mesajlarının sonuna eklenecek "ayrıntılar log dosyasında" notu."""
    return f"\n\nAyrıntılar: {_log_file}" if _log_file is not None else ""


def _log_thread_exception(args: threading.ExceptHookArgs) -> None:
    if args.exc_type is SystemExit or args.exc_value is None:
        return
    thread_name = args.thread.name if args.thread is not None else "?"
    logger.error(
        "Thread'de yakalanmayan hata (%s)",
        thread_name,
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )


def _log_uncaught_exception(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: TracebackType | None,
) -> None:
    if not issubclass(exc_type, KeyboardInterrupt):
        logger.critical(
            "Yakalanmayan hata", exc_info=(exc_type, exc_value, exc_traceback)
        )
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


def setup_logging(log_dir: Path | None = None) -> Path | None:
    """Dosyaya (ve konsol varsa stderr'e) log yazmayı açar; log dosyasını döndürür.

    Birden çok kez çağrılırsa yalnızca ilk çağrı etkilidir. Log dizini
    oluşturulamazsa uygulama loglamasız (yalnızca stderr) devam eder.
    """
    global _log_file
    package_logger = logging.getLogger(LOGGER_NAME)
    if package_logger.handlers:
        return _log_file

    package_logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s"
    )

    target_dir = log_dir if log_dir is not None else default_log_dir()
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / LOG_FILE_NAME
        file_handler = RotatingFileHandler(
            path, maxBytes=MAX_LOG_BYTES, backupCount=LOG_BACKUPS, encoding="utf-8"
        )
    except OSError:
        _log_file = None
    else:
        file_handler.setFormatter(formatter)
        package_logger.addHandler(file_handler)
        _log_file = path

    # Windows'ta konsolsuz paketlenmiş uygulamada sys.stderr None olur.
    if sys.stderr is not None:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.WARNING)
        stream_handler.setFormatter(formatter)
        package_logger.addHandler(stream_handler)

    threading.excepthook = _log_thread_exception
    sys.excepthook = _log_uncaught_exception
    return _log_file
