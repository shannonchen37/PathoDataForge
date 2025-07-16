"""Application-wide Qt style sheet."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


def apply_light_theme(app: QApplication) -> None:
    """Force a readable light palette regardless of the OS appearance."""
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#F6F8FB"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#0F172A"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#F8FAFC"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#0F172A"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#1E3A8A"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#0F172A"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#94A3B8"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#DBEAFE"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#0F172A"))
    app.setPalette(palette)


APP_QSS = """
QMainWindow, QWidget#AppRoot, QWidget#PageContent, QStackedWidget {
    background: #F6F8FB;
    color: #0F172A;
    font-size: 13px;
}
QWidget {
    color: #0F172A;
    font-size: 13px;
}
QLabel {
    background: transparent;
}
QFrame#TopHeader, QFrame#LeftNav, QFrame#BottomStatus {
    background: #FFFFFF;
    border: 1px solid #D9E2EF;
    border-radius: 8px;
}
QLabel#AppTitle {
    font-size: 24px;
    font-weight: 800;
    color: #0F172A;
}
QLabel#AppSubtitle, QLabel#MutedText, QLabel#CardNote {
    color: #64748B;
}
QLabel#PageTitle {
    font-size: 20px;
    font-weight: 800;
}
QFrame#Card, QFrame#StatCard {
    background: #FFFFFF;
    border: 1px solid #D9E2EF;
    border-radius: 8px;
}
QLabel#CardTitle {
    color: #334155;
    font-weight: 800;
    font-size: 14px;
}
QLabel#StatTitle {
    color: #64748B;
    font-size: 12px;
    font-weight: 700;
}
QLabel#StatValue {
    color: #0F172A;
    font-size: 20px;
    font-weight: 800;
}
QLabel#Chip {
    background: #EFF6FF;
    border: 1px solid #BFDBFE;
    border-radius: 8px;
    color: #1D4ED8;
    padding: 5px 9px;
    font-weight: 700;
}
QLabel#SuccessChip {
    background: #ECFDF5;
    border: 1px solid #BBF7D0;
    border-radius: 8px;
    color: #15803D;
    padding: 5px 9px;
    font-weight: 700;
}
QLabel#WarnChip {
    background: #FFFBEB;
    border: 1px solid #FDE68A;
    border-radius: 8px;
    color: #B45309;
    padding: 5px 9px;
    font-weight: 700;
}
QLabel#ErrorChip {
    background: #FEF2F2;
    border: 1px solid #FECACA;
    border-radius: 8px;
    color: #B91C1C;
    padding: 5px 9px;
    font-weight: 700;
}
QPushButton {
    background: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 7px;
    color: #1E3A8A;
    min-height: 32px;
    padding: 4px 12px;
    font-weight: 700;
}
QPushButton:hover {
    border-color: #2563EB;
    background: #EFF6FF;
}
QPushButton:disabled {
    background: #E2E8F0;
    border-color: #CBD5E1;
    color: #94A3B8;
}
QPushButton#PrimaryButton {
    background: #2563EB;
    border-color: #2563EB;
    color: #FFFFFF;
}
QPushButton#PrimaryButton:hover {
    background: #1D4ED8;
}
QPushButton#DangerButton {
    color: #B91C1C;
    border-color: #FCA5A5;
}
QPushButton#NavButton {
    text-align: left;
    padding: 9px 12px;
    min-height: 48px;
    background: #FFFFFF;
    border: 1px solid transparent;
    color: #334155;
}
QPushButton#NavButton[active="true"] {
    background: #EFF6FF;
    border: 1px solid #93C5FD;
    color: #1D4ED8;
}
QPushButton#NavButton[stepStatus="已完成"] {
    color: #166534;
}
QPushButton#NavButton[stepStatus="有警告"] {
    color: #92400E;
}
QPushButton#NavButton[stepStatus="出错"] {
    color: #B91C1C;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 7px;
    min-height: 34px;
    padding: 3px 8px;
    color: #0F172A;
    selection-background-color: #DBEAFE;
    selection-color: #0F172A;
}
QLineEdit:read-only {
    background: #F8FAFC;
    color: #475569;
}
QPlainTextEdit, QTableWidget {
    background: #FFFFFF;
    border: 1px solid #D9E2EF;
    border-radius: 8px;
    color: #0F172A;
    selection-background-color: #DBEAFE;
    selection-color: #0F172A;
}
QTableWidget {
    gridline-color: #E2E8F0;
    alternate-background-color: #F8FAFC;
}
QHeaderView::section {
    background: #F1F5F9;
    border: 0;
    border-right: 1px solid #E2E8F0;
    color: #334155;
    padding: 7px;
    font-weight: 800;
}
QProgressBar {
    border: 1px solid #CBD5E1;
    border-radius: 7px;
    background: #E2E8F0;
    height: 17px;
    text-align: center;
}
QProgressBar::chunk {
    background: #2563EB;
    border-radius: 6px;
}
QCheckBox {
    spacing: 8px;
}
QSlider::groove:horizontal {
    height: 6px;
    background: #E2E8F0;
    border-radius: 3px;
}
QSlider::sub-page:horizontal {
    background: #2563EB;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #FFFFFF;
    border: 2px solid #2563EB;
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}
QSlider::handle:horizontal:hover {
    border-color: #1D4ED8;
}
QScrollArea {
    border: none;
    background: #F6F8FB;
}
QScrollArea > QWidget, QScrollArea > QWidget > QWidget {
    background: #F6F8FB;
    color: #0F172A;
}
QStatusBar {
    background: #FFFFFF;
    color: #0F172A;
    border-top: 1px solid #D9E2EF;
}
QToolButton#CollapseButton {
    border: none;
    background: transparent;
    color: #1D4ED8;
    font-weight: 800;
}
QWidget#OverlayCanvas {
    background: #F8FAFC;
    border: 1px dashed #CBD5E1;
    border-radius: 8px;
    color: #64748B;
}
"""
