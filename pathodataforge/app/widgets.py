"""Reusable Qt widget helpers."""

from __future__ import annotations

from typing import Iterable

import pandas as pd
from PySide6.QtWidgets import QComboBox, QTableWidget, QTableWidgetItem


def set_table_from_dataframe(
    table: QTableWidget,
    dataframe: pd.DataFrame,
    limit: int = 50,
) -> None:
    preview = dataframe.head(limit).copy()
    table.clear()
    table.setRowCount(len(preview))
    table.setColumnCount(len(preview.columns))
    table.setHorizontalHeaderLabels([str(column) for column in preview.columns])
    for row_index, (_, row) in enumerate(preview.iterrows()):
        for column_index, column in enumerate(preview.columns):
            item = QTableWidgetItem(str(row[column]))
            table.setItem(row_index, column_index, item)
    table.resizeColumnsToContents()


def populate_combo(
    combo: QComboBox,
    values: Iterable[str],
    preferred: str | None = None,
    allow_empty: bool = False,
) -> None:
    combo.blockSignals(True)
    combo.clear()
    if allow_empty:
        combo.addItem("")
    for value in values:
        combo.addItem(str(value))
    if preferred:
        matches = combo.findText(preferred)
        if matches >= 0:
            combo.setCurrentIndex(matches)
    combo.blockSignals(False)
