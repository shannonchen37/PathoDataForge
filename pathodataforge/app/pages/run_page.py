"""Run and export page."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pathodataforge.app.components import Card, StatCard, icon_button, open_path, primary_button
from pathodataforge.app.state import AppState


class RunPage(QWidget):
    start_requested = Signal()

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.state = state
        self.log_lines: list[str] = []
        self.overlay_path = ""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        left = QVBoxLayout()
        left.setSpacing(14)
        right = QVBoxLayout()
        right.setSpacing(14)

        left.addWidget(self._build_control_card())
        left.addWidget(self._build_stats_card())
        left.addWidget(self._build_output_card())
        left.addStretch(1)

        right.addWidget(self._build_overlay_card(), 2)
        right.addWidget(self._build_log_card(), 3)

        layout.addLayout(left, 0)
        layout.addLayout(right, 1)

    def _build_control_card(self) -> Card:
        card = Card("运行控制")
        buttons = QHBoxLayout()
        self.start_button = primary_button("开始处理")
        self.start_button.clicked.connect(self.start_requested)
        self.pause_button = icon_button("暂停")
        self.pause_button.setEnabled(False)
        self.pause_button.setToolTip("后续版本支持暂停。")
        self.stop_button = icon_button("停止")
        self.stop_button.setEnabled(False)
        self.stop_button.setToolTip("后续版本支持停止。")
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.pause_button)
        buttons.addWidget(self.stop_button)
        card.body.addLayout(buttons)
        self.stage_label = QLabel("当前阶段：等待开始")
        self.current_slide_label = QLabel("当前切片：无")
        self.current_patch_label = QLabel("当前 patch 数：0")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        card.body.addWidget(self.stage_label)
        card.body.addWidget(self.progress_bar)
        card.body.addWidget(self.current_slide_label)
        card.body.addWidget(self.current_patch_label)
        return card

    def _build_stats_card(self) -> Card:
        card = Card("实时统计")
        grid = QGridLayout()
        self.kept_card = StatCard("保留 patch 数")
        self.discarded_card = StatCard("丢弃 patch 数")
        self.coord_card = StatCard("坐标文件")
        self.feature_card = StatCard("特征文件")
        self.done_slide_card = StatCard("已处理切片")
        self.failed_slide_card = StatCard("失败切片")
        cards = [
            self.kept_card,
            self.discarded_card,
            self.coord_card,
            self.feature_card,
            self.done_slide_card,
            self.failed_slide_card,
        ]
        for index, item in enumerate(cards):
            grid.addWidget(item, index // 2, index % 2)
        card.body.addLayout(grid)
        return card

    def _build_output_card(self) -> Card:
        card = Card("输出路径")
        self.output_lines: dict[str, QLineEdit] = {}
        self.output_buttons: dict[str, QPushButton] = {}
        for key, label in [
            ("summary", "结果摘要"),
            ("manifest", "Patch 清单"),
            ("coordinates", "坐标目录"),
            ("features", "特征目录"),
        ]:
            row = QHBoxLayout()
            title = QLabel(label)
            title.setMinimumWidth(90)
            line = QLineEdit()
            line.setReadOnly(True)
            button = QPushButton("打开")
            button.setEnabled(False)
            button.clicked.connect(lambda _=False, k=key: open_path(self.output_lines[k].text(), self))
            row.addWidget(title)
            row.addWidget(line, 1)
            row.addWidget(button)
            card.body.addLayout(row)
            self.output_lines[key] = line
            self.output_buttons[key] = button
        return card

    def _build_overlay_card(self) -> Card:
        card = Card("采样预览图")
        self.overlay_label = QLabel("处理开始后将在这里显示组织区域与采样位置预览")
        self.overlay_label.setObjectName("OverlayCanvas")
        self.overlay_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overlay_label.setMinimumSize(520, 300)
        self.overlay_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.overlay_label.setWordWrap(True)
        card.body.addWidget(self.overlay_label, 1)
        return card

    def _build_log_card(self) -> Card:
        card = Card("运行日志与结果摘要")
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(220)
        self.summary_text = QPlainTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setMinimumHeight(170)
        card.body.addWidget(QLabel("运行日志"))
        card.body.addWidget(self.log_text, 2)
        card.body.addWidget(QLabel("结果摘要"))
        card.body.addWidget(self.summary_text, 1)
        return card

    def prepare_run(self) -> None:
        self.log_lines.clear()
        self.log_text.clear()
        self.summary_text.clear()
        self.progress_bar.setValue(0)
        self.stage_label.setText("当前阶段：启动中")
        self.start_button.setEnabled(False)
        self.start_button.setText("运行中")
        self.overlay_path = ""
        self.overlay_label.setPixmap(QPixmap())
        self.overlay_label.setText("正在处理，生成采样预览图后会自动显示。")
        for card in [
            self.kept_card,
            self.discarded_card,
            self.coord_card,
            self.feature_card,
            self.done_slide_card,
            self.failed_slide_card,
        ]:
            card.set_value("--", "")

    def finish_run_controls(self) -> None:
        self.start_button.setEnabled(True)
        self.start_button.setText("开始处理")

    def set_progress(self, value: int, message: str) -> None:
        self.progress_bar.setValue(value)
        if message:
            self.stage_label.setText(f"当前阶段：{message}")
            self.append_log(message)

    def append_log(self, message: str) -> None:
        text = str(message)
        self.log_lines.append(text)
        if len(self.log_lines) > 500:
            self.log_lines = self.log_lines[-500:]
        self.log_text.setPlainText("\n".join(self.log_lines))
        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)

    def set_output_paths(self, paths: dict[str, str]) -> None:
        for key, line in self.output_lines.items():
            value = paths.get(key, "")
            line.setText(value)
            line.setToolTip(value)
            self.output_buttons[key].setEnabled(bool(value) and Path(value).exists())

    def set_summary(self, summary: dict[str, Any]) -> None:
        patches = summary.get("patches", {})
        coords = summary.get("coordinates", {}).get("slides", []) or []
        features = summary.get("features", {}).get("results", []) or []
        slides = summary.get("slides", []) or []
        failed = [item for item in slides if item.get("error")]
        self.kept_card.set_value(patches.get("kept", 0), "通过 QC")
        self.discarded_card.set_value(patches.get("discarded", 0), "质控过滤")
        self.coord_card.set_value(len(coords), f"{sum(1 for item in coords if item.get('from_cache'))} 个来自缓存")
        self.feature_card.set_value(sum(1 for item in features if item.get("ok")), f"{sum(1 for item in features if item.get('from_cache'))} 个来自缓存")
        self.done_slide_card.set_value(len(slides) - len(failed))
        self.failed_slide_card.set_value(len(failed))
        self.current_slide_label.setText(f"当前切片：{len(slides)} / {summary.get('input', {}).get('scanned_files', len(slides))}")
        self.current_patch_label.setText(f"当前 patch 数：{patches.get('kept', 0)}")

        key_lines = [
            f"总 WSI 数：{summary.get('input', {}).get('scanned_files', 0)}",
            f"成功切片数：{len(slides) - len(failed)}",
            f"失败切片数：{len(failed)}",
            f"总 patch 数：{patches.get('kept', 0)}",
            f"特征文件数：{sum(1 for item in features if item.get('ok'))}",
            f"总耗时：{summary.get('duration_seconds', 0)} 秒",
        ]
        feature_paths = [str(item.get("feature_npy", "")) for item in features if item.get("feature_npy")]
        if feature_paths:
            key_lines.append(f"特征文件路径：{feature_paths[0]}")
        self.summary_text.setPlainText("\n".join(key_lines) + "\n\n" + json.dumps(summary, ensure_ascii=False, indent=2))
        overlay = str(summary.get("visualization", {}).get("first_overlay", "") or "")
        if overlay:
            self.set_overlay(overlay)
        else:
            reason = "本次未启用采样预览图保存，或坐标采样未生成预览图。"
            self.overlay_label.setPixmap(QPixmap())
            self.overlay_label.setText(reason)

    def set_overlay(self, path: str) -> None:
        self.overlay_path = path
        self._render_overlay()

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)
        self._render_overlay()

    def _render_overlay(self) -> None:
        if not self.overlay_path:
            return
        pixmap = QPixmap(self.overlay_path)
        if pixmap.isNull():
            self.overlay_label.setText("采样预览图文件无法读取。")
            return
        self.overlay_label.setPixmap(
            pixmap.scaled(
                self.overlay_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
