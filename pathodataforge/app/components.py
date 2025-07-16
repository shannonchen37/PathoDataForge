"""Reusable PySide6 widgets for the iMoonLab-PathoDataForge GUI."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


def repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def middle_elide(text: str, limit: int = 76) -> str:
    if len(text) <= limit:
        return text
    keep = max(8, (limit - 3) // 2)
    return f"{text[:keep]}...{text[-keep:]}"


def open_path(path: str, parent: QWidget | None = None) -> None:
    if not path:
        QMessageBox.warning(parent, "无法打开", "路径为空。")
        return
    target = Path(path).expanduser()
    if not target.exists():
        QMessageBox.warning(parent, "无法打开", f"路径不存在：{target}")
        return
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))


class Card(QFrame):
    def __init__(self, title: str, right_widget: QWidget | None = None) -> None:
        super().__init__()
        self.setObjectName("Card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 14)
        outer.setSpacing(10)
        header = QHBoxLayout()
        header.setSpacing(8)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("CardTitle")
        self.title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.title_label.setMaximumHeight(28)
        header.addWidget(self.title_label, 1)
        if right_widget is not None:
            header.addWidget(right_widget)
        outer.addLayout(header, 0)
        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        self.body.setAlignment(Qt.AlignmentFlag.AlignTop)
        outer.addLayout(self.body, 1)


class StatCard(QFrame):
    def __init__(self, title: str, value: str = "--", note: str = "") -> None:
        super().__init__()
        self.setObjectName("StatCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("StatTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("StatValue")
        self.value_label.setWordWrap(True)
        self.note_label = QLabel(note)
        self.note_label.setObjectName("CardNote")
        self.note_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.note_label)

    def set_value(self, value: object, note: object | None = None) -> None:
        self.value_label.setText(str(value))
        if note is not None:
            self.note_label.setText(str(note))


class StatusChip(QLabel):
    def __init__(self, text: str = "", kind: str = "info") -> None:
        super().__init__(text)
        self.set_kind(kind)

    def set_kind(self, kind: str) -> None:
        object_name = {
            "success": "SuccessChip",
            "warn": "WarnChip",
            "error": "ErrorChip",
        }.get(kind, "Chip")
        self.setObjectName(object_name)
        repolish(self)


class NavButton(QPushButton):
    def __init__(self, index: int, title: str) -> None:
        super().__init__()
        self.index = index
        self.title = title
        self.note = ""
        self.status = "未开始"
        self.setObjectName("NavButton")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_active(False)
        self.set_status("未开始")

    def set_active(self, active: bool) -> None:
        self.setChecked(active)
        self.setProperty("active", "true" if active else "false")
        repolish(self)

    def set_status(self, status: str, note: str = "") -> None:
        self.status = status
        self.note = note
        suffix = f"\n{status}"
        if note:
            suffix += f" · {note}"
        self.setText(f"{self.index}. {self.title}{suffix}")
        self.setProperty("stepStatus", status)
        repolish(self)


class PathInputRow(QWidget):
    path_changed = Signal(str)

    def __init__(
        self,
        mode: str,
        dialog_title: str,
        file_filter: str = "",
    ) -> None:
        super().__init__()
        self.mode = mode
        self.dialog_title = dialog_title
        self.file_filter = file_filter
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        self.line_edit = QLineEdit()
        self.line_edit.editingFinished.connect(self._emit_path)
        self.select_button = QPushButton("选择")
        self.select_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        self.select_button.clicked.connect(self._browse)
        self.open_button = QPushButton("打开")
        self.open_button.clicked.connect(lambda: open_path(self.path(), self))
        self.clear_button = QPushButton("清空")
        self.clear_button.clicked.connect(self.clear)
        layout.addWidget(self.line_edit, 1)
        layout.addWidget(self.select_button)
        layout.addWidget(self.open_button)
        layout.addWidget(self.clear_button)

    def path(self) -> str:
        return self.line_edit.text().strip()

    def set_path(self, path: str) -> None:
        self.line_edit.setText(path)
        self.line_edit.setToolTip(path)
        self.open_button.setEnabled(bool(path))

    def clear(self) -> None:
        self.set_path("")
        self.path_changed.emit("")

    def _emit_path(self) -> None:
        self.line_edit.setToolTip(self.path())
        self.open_button.setEnabled(bool(self.path()))
        self.path_changed.emit(self.path())

    def _browse(self) -> None:
        if self.mode == "dir":
            path = QFileDialog.getExistingDirectory(self, self.dialog_title, self.path())
        else:
            path, _ = QFileDialog.getOpenFileName(
                self,
                self.dialog_title,
                str(Path(self.path()).parent) if self.path() else "",
                self.file_filter,
            )
        if path:
            self.set_path(path)
            self.path_changed.emit(path)


class CollapsibleSection(QWidget):
    def __init__(self, title: str, expanded: bool = False) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.button = QToolButton()
        self.button.setObjectName("CollapseButton")
        self.button.setText(title)
        self.button.setCheckable(True)
        self.button.setChecked(expanded)
        self.button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.button.toggled.connect(self._toggle)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(8)
        layout.addWidget(self.button)
        layout.addWidget(self.content)
        self._toggle(expanded)

    def _toggle(self, checked: bool) -> None:
        self.content.setVisible(checked)
        self.button.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)


def setup_table(table: QTableWidget) -> None:
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(34)
    table.horizontalHeader().setStretchLastSection(True)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)


def make_item(text: object, tooltip: str | None = None, color: str | None = None) -> QTableWidgetItem:
    item = QTableWidgetItem(str(text))
    if tooltip:
        item.setToolTip(tooltip)
    if color:
        item.setForeground(QColor(color))
    return item


def icon_button(text: str, standard_icon: QStyle.StandardPixmap | None = None) -> QPushButton:
    button = QPushButton(text)
    if standard_icon is not None:
        app = QApplication.instance()
        if app is not None:
            button.setIcon(app.style().standardIcon(standard_icon))
    return button


def primary_button(text: str, standard_icon: QStyle.StandardPixmap | None = None) -> QPushButton:
    button = icon_button(text, standard_icon)
    button.setObjectName("PrimaryButton")
    return button


def add_open_button(layout: QHBoxLayout, get_path: Callable[[], str], parent: QWidget) -> QPushButton:
    button = QPushButton("打开")
    button.clicked.connect(lambda: open_path(get_path(), parent))
    layout.addWidget(button)
    return button
