"""Logging setup for CLI, GUI, and pipeline runs."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Callable


class CallbackLogHandler(logging.Handler):
    """Forward formatted log records to a GUI callback."""

    def __init__(self, callback: Callable[[str], None]) -> None:
        super().__init__()
        self.callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.callback(self.format(record))
        except Exception:
            self.handleError(record)


def setup_logger(
    name: str = "pathodataforge",
    log_file: str | Path | None = None,
    gui_callback: Callable[[str], None] | None = None,
    level: int = logging.INFO,
) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(level)
    logger.addHandler(stream_handler)

    if log_file is not None:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)

    if gui_callback is not None:
        callback_handler = CallbackLogHandler(gui_callback)
        callback_handler.setFormatter(formatter)
        callback_handler.setLevel(level)
        logger.addHandler(callback_handler)

    return logger
