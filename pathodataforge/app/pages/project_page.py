"""Project import page."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from pathodataforge.app.components import (
    Card,
    PathInputRow,
    StatCard,
    icon_button,
    make_item,
    middle_elide,
    setup_table,
)
from pathodataforge.app.state import AppState
from pathodataforge.core.scanner import ScanResult


def _file_size(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError:
        return "--"
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} TB"


class ProjectPage(QWidget):
    scan_requested = Signal()
    metadata_requested = Signal()
    check_requested = Signal()

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.state = state
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        title = QLabel("项目导入")
        title.setObjectName("PageTitle")
        subtitle = QLabel("选择 WSI、元信息和输出目录，然后完成项目检查。")
        subtitle.setObjectName("MutedText")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        path_card = Card("数据路径")
        self.wsi_row = PathInputRow("dir", "选择 WSI 文件夹")
        self.metadata_row = PathInputRow("file", "选择 Metadata 文件", "Metadata (*.csv *.xlsx *.xls)")
        self.output_row = PathInputRow("dir", "选择输出目录")
        self.wsi_row.path_changed.connect(lambda value: self.state.set_paths(wsi_dir=value))
        self.metadata_row.path_changed.connect(lambda value: self.state.set_paths(metadata_file=value))
        self.output_row.path_changed.connect(lambda value: self.state.set_paths(output_dir=value))
        self._add_labeled_row(path_card.body, "WSI 文件夹", self.wsi_row)
        self._add_labeled_row(path_card.body, "元信息文件", self.metadata_row)
        self._add_labeled_row(path_card.body, "输出目录", self.output_row)

        action_card = Card("操作")
        action_row = QHBoxLayout()
        scan_button = icon_button("扫描 WSI")
        scan_button.clicked.connect(self.scan_requested)
        metadata_button = icon_button("读取元信息")
        metadata_button.clicked.connect(self.metadata_requested)
        check_button = icon_button("一键检查项目")
        check_button.clicked.connect(self.check_requested)
        action_row.addWidget(scan_button)
        action_row.addWidget(metadata_button)
        action_row.addWidget(check_button)
        action_row.addStretch(1)
        action_card.body.addLayout(action_row)
        self.warning_label = QLabel("")
        self.warning_label.setObjectName("WarnChip")
        self.warning_label.hide()
        action_card.body.addWidget(self.warning_label)

        summary_card = Card("扫描摘要")
        summary_grid = QGridLayout()
        self.file_count_card = StatCard("发现文件数")
        self.supported_count_card = StatCard("支持格式数")
        self.unsupported_count_card = StatCard("不支持文件数")
        self.metadata_rows_card = StatCard("元信息记录数")
        for index, card in enumerate(
            [
                self.file_count_card,
                self.supported_count_card,
                self.unsupported_count_card,
                self.metadata_rows_card,
            ]
        ):
            summary_grid.addWidget(card, 0, index)
            summary_grid.setColumnStretch(index, 1)
        summary_card.body.addLayout(summary_grid)

        preview_card = Card("文件预览")
        self.file_table = QTableWidget()
        setup_table(self.file_table)
        preview_card.body.addWidget(self.file_table, 1)

        layout.addWidget(path_card)
        layout.addWidget(action_card)
        layout.addWidget(summary_card)
        layout.addWidget(preview_card, 1)

    def refresh_from_state(self) -> None:
        self.wsi_row.set_path(self.state.wsi_dir)
        self.metadata_row.set_path(self.state.metadata_file)
        self.output_row.set_path(self.state.output_dir)
        if self.state.scan_result:
            self.set_scan_result(self.state.scan_result)
        self.metadata_rows_card.set_value(
            0 if self.state.metadata_df is None else len(self.state.metadata_df)
        )

    def set_scan_result(self, result: ScanResult) -> None:
        self.file_count_card.set_value(result.image_file_count)
        self.supported_count_card.set_value(result.supported_format_count)
        self.unsupported_count_card.set_value(result.unsupported_count)
        if result.unsupported_count:
            self.warning_label.setText(f"发现 {result.unsupported_count} 个不支持文件，流程可继续。")
            self.warning_label.show()
        else:
            self.warning_label.hide()

        rows: list[tuple[Path, bool]] = [(path, True) for path in result.files]
        rows.extend((path, False) for path in result.unsupported_files)
        self.file_table.clear()
        self.file_table.setColumnCount(5)
        self.file_table.setHorizontalHeaderLabels(["文件名", "后缀", "状态", "文件大小", "所在路径"])
        self.file_table.setRowCount(len(rows))
        for row_index, (path, supported) in enumerate(rows):
            status = "支持" if supported else "不支持"
            color = "#16A34A" if supported else "#F59E0B"
            full_path = str(path)
            self.file_table.setItem(row_index, 0, make_item(path.name, full_path))
            self.file_table.setItem(row_index, 1, make_item(path.suffix.lower()))
            self.file_table.setItem(row_index, 2, make_item(status, color=color))
            self.file_table.setItem(row_index, 3, make_item(_file_size(path)))
            self.file_table.setItem(row_index, 4, make_item(middle_elide(full_path), full_path))
        self.file_table.resizeColumnsToContents()

    @staticmethod
    def _add_labeled_row(parent_layout: QVBoxLayout, label: str, widget: QWidget) -> None:
        row = QHBoxLayout()
        title = QLabel(label)
        title.setMinimumWidth(92)
        row.addWidget(title)
        row.addWidget(widget, 1)
        parent_layout.addLayout(row)

