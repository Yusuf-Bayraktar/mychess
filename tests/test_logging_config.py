import logging
import sys
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from mychess import logging_config


@pytest.fixture
def clean_logging() -> Iterator[None]:
    """setup_logging'in değiştirdiği global durumu test sonunda geri alır."""
    package_logger = logging.getLogger(logging_config.LOGGER_NAME)
    old_handlers = list(package_logger.handlers)
    old_level = package_logger.level
    old_thread_hook = threading.excepthook
    old_sys_hook = sys.excepthook
    old_log_file = logging_config._log_file
    package_logger.handlers.clear()
    yield
    for handler in package_logger.handlers:
        handler.close()
    package_logger.handlers[:] = old_handlers
    package_logger.setLevel(old_level)
    threading.excepthook = old_thread_hook
    sys.excepthook = old_sys_hook
    logging_config._log_file = old_log_file


def read_log(path: Path) -> str:
    for handler in logging.getLogger(logging_config.LOGGER_NAME).handlers:
        handler.flush()
    return path.read_text(encoding="utf-8")


def test_writes_package_logs_to_file(tmp_path: Path, clean_logging: None) -> None:
    path = logging_config.setup_logging(tmp_path)

    assert path == tmp_path / logging_config.LOG_FILE_NAME
    assert logging_config.log_file() == path
    assert str(path) in logging_config.log_hint()

    logging.getLogger("mychess.main").info("motor başladı")
    assert "motor başladı" in read_log(path)


def test_setup_is_idempotent(tmp_path: Path, clean_logging: None) -> None:
    logging_config.setup_logging(tmp_path)
    handlers = list(logging.getLogger(logging_config.LOGGER_NAME).handlers)
    logging_config.setup_logging(tmp_path / "baska")

    assert logging.getLogger(logging_config.LOGGER_NAME).handlers == handlers


def test_thread_exceptions_are_logged(tmp_path: Path, clean_logging: None) -> None:
    path = logging_config.setup_logging(tmp_path)
    assert path is not None

    def boom() -> None:
        raise RuntimeError("thread patladı")

    worker = threading.Thread(target=boom, name="motor-thread")
    worker.start()
    worker.join()

    content = read_log(path)
    assert "motor-thread" in content
    assert "RuntimeError: thread patladı" in content


def test_unwritable_log_dir_falls_back(tmp_path: Path, clean_logging: None) -> None:
    blocker = tmp_path / "dosya"
    blocker.write_text("")  # dizin yerine dosya: mkdir başarısız olur

    assert logging_config.setup_logging(blocker / "logs") is None
    assert logging_config.log_hint() == ""
