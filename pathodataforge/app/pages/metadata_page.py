"""Metadata matching page."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from pathodataforge.app.components import Card, StatCard, icon_button, make_item, setup_table
from pathodataforge.app.state import AppState
from pathodataforge.core.metadata_cleaner import CleanMetadataResult, infer_case_id_from_filename


class MetadataPage(QWidget):
    preview_requested = Signal()
    auto_guess_requested = Signal()
    export_requested = Signal()

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.state = state
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        title = QLabel("元信息匹配")
        title.setObjectName("PageTitle")
        subtitle = QLabel("将 WSI 文件与临床元信息按病例 ID 或文件名建立对应关系。")
        subtitle.setObjectName("MutedText")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        mapping_card = Card("字段映射")
        self.case_combo = QComboBox()
        self.label_combo = QComboBox()
        self.filename_combo = QComboBox()
        self.regex_edit = QLineEdit()
        self.regex_edit.setPlaceholderText("可选，例如 (TCGA-[A-Z0-9]{2}-[A-Z0-9]{4})")
        for combo in [self.case_combo, self.label_combo, self.filename_combo]:
            combo.currentTextChanged.connect(self._sync_columns)
        self.regex_edit.editingFinished.connect(self._sync_columns)
        self._add_labeled_row(mapping_card.body, "病例 ID 字段", self.case_combo)
        self._add_labeled_row(mapping_card.body, "标签字段", self.label_combo)
        self._add_labeled_row(mapping_card.body, "文件名字段", self.filename_combo)
        self._add_labeled_row(mapping_card.body, "病例 ID 正则", self.regex_edit)

        actions = QHBoxLayout()
        preview_button = icon_button("预览匹配")
        preview_button.clicked.connect(self.preview_requested)
        guess_button = icon_button("自动猜测字段")
        guess_button.clicked.connect(self.auto_guess_requested)
        export_button = icon_button("导出匹配报告")
        export_button.clicked.connect(self.export_requested)
        actions.addWidget(preview_button)
        actions.addWidget(guess_button)
        actions.addWidget(export_button)
        actions.addStretch(1)
        mapping_card.body.addLayout(actions)

        summary_card = Card("匹配摘要")
        grid = QGridLayout()
        self.fields_card = StatCard("字段数")
        self.rows_card = StatCard("记录数")
        self.wsi_card = StatCard("WSI 文件数")
        self.matched_card = StatCard("匹配成功数")
        self.unmatched_card = StatCard("未匹配数")
        self.missing_label_card = StatCard("标签缺失数")
        cards = [
            self.fields_card,
            self.rows_card,
            self.wsi_card,
            self.matched_card,
            self.unmatched_card,
            self.missing_label_card,
        ]
        for index, card in enumerate(cards):
            grid.addWidget(card, index // 3, index % 3)
            grid.setColumnStretch(index % 3, 1)
        summary_card.body.addLayout(grid)
        self.match_warning = QLabel("")
        self.match_warning.setObjectName("WarnChip")
        self.match_warning.hide()
        summary_card.body.addWidget(self.match_warning)

        preview_card = Card("匹配预览")
        self.match_table = QTableWidget()
        setup_table(self.match_table)
        preview_card.body.addWidget(self.match_table, 1)

        layout.addWidget(mapping_card)
        layout.addWidget(summary_card)
        layout.addWidget(preview_card, 1)

    def refresh_from_state(self) -> None:
        self.set_fields(self.state.metadata_fields)
        self.case_combo.setCurrentText(self.state.selected_case_id_column)
        self.label_combo.setCurrentText(self.state.selected_label_column)
        self.filename_combo.setCurrentText(self.state.selected_filename_column)
        self.regex_edit.setText(self.state.case_id_regex)
        self.fields_card.set_value(len(self.state.metadata_fields))
        self.rows_card.set_value(0 if self.state.metadata_df is None else len(self.state.metadata_df))
        self.wsi_card.set_value(len(self.state.scanned_files))
        if self.state.match_result:
            self.set_match_result(self.state.match_result)

    def set_fields(self, fields: list[str]) -> None:
        current = (
            self.case_combo.currentText(),
            self.label_combo.currentText(),
            self.filename_combo.currentText(),
        )
        for combo, value, allow_empty in [
            (self.case_combo, current[0], False),
            (self.label_combo, current[1], False),
            (self.filename_combo, current[2], True),
        ]:
            combo.blockSignals(True)
            combo.clear()
            if allow_empty:
                combo.addItem("")
            combo.addItems(fields)
            if value and combo.findText(value) >= 0:
                combo.setCurrentText(value)
            combo.blockSignals(False)
        self._sync_columns()

    def set_match_result(self, result: CleanMetadataResult) -> None:
        metadata = result.metadata.copy()
        missing_label_count = int((metadata["label"].fillna("").astype(str).str.strip() == "").sum()) if not metadata.empty else 0
        self.matched_card.set_value(result.matched_count)
        self.unmatched_card.set_value(result.unmatched_count)
        self.missing_label_card.set_value(missing_label_count)
        total = max(1, result.matched_count + result.unmatched_count)
        rate = result.matched_count / total
        if rate < 0.8:
            self.match_warning.setText(f"匹配成功率 {rate:.0%}，请检查字段映射或病例 ID 正则。")
            self.match_warning.show()
        else:
            self.match_warning.hide()

        self.match_table.clear()
        self.match_table.setColumnCount(6)
        self.match_table.setHorizontalHeaderLabels(
            ["原始文件名", "提取 case_id", "匹配 case_id", "标签", "匹配状态", "原因"]
        )
        self.match_table.setRowCount(len(metadata))
        regex = self.regex_edit.text().strip()
        for row_index, (_, row) in enumerate(metadata.iterrows()):
            original = str(row.get("original_filename", ""))
            source = str(row.get("source_path", original))
            try:
                extracted = infer_case_id_from_filename(Path(source), case_id_regex=regex)
            except Exception:
                extracted = infer_case_id_from_filename(Path(source))
            label = str(row.get("label", "") or "")
            status_raw = str(row.get("status", ""))
            if not label.strip():
                status, color, reason = "标签缺失", "#DC2626", "元信息标签为空"
            elif status_raw == "matched":
                status, color, reason = "成功", "#16A34A", ""
            else:
                status, color, reason = "未匹配", "#F59E0B", "未找到对应病例"
            self.match_table.setItem(row_index, 0, make_item(original, original))
            self.match_table.setItem(row_index, 1, make_item(extracted))
            self.match_table.setItem(row_index, 2, make_item(row.get("case_id", "")))
            self.match_table.setItem(row_index, 3, make_item(label))
            self.match_table.setItem(row_index, 4, make_item(status, color=color))
            self.match_table.setItem(row_index, 5, make_item(reason))
        self.match_table.resizeColumnsToContents()

    def _sync_columns(self) -> None:
        self.state.set_metadata_columns(
            self.case_combo.currentText(),
            self.label_combo.currentText(),
            self.filename_combo.currentText(),
            self.regex_edit.text().strip(),
        )

    @staticmethod
    def _add_labeled_row(parent_layout: QVBoxLayout, label: str, widget: QWidget) -> None:
        row = QHBoxLayout()
        title = QLabel(label)
        title.setMinimumWidth(100)
        row.addWidget(title)
        row.addWidget(widget, 1)
        parent_layout.addLayout(row)

