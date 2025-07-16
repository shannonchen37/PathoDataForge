"""Qt worker for running the pipeline off the GUI thread."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from pathodataforge.core.pipeline import run_pipeline


class ProcessingWorker(QObject):
    progress = Signal(int, str)
    log = Signal(str)
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__()
        self.config = config

    @Slot()
    def run(self) -> None:
        try:
            summary = run_pipeline(
                self.config,
                logger_callback=self.log.emit,
                progress_callback=self.progress.emit,
            )
            self.finished.emit(summary)
        except Exception as exc:
            self.error.emit(str(exc))
