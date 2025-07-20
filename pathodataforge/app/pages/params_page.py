"""WSI preview and sampling confirmation page."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QDoubleSpinBox,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pathodataforge.app.components import Card, icon_button
from pathodataforge.app.state import STEP_DONE, AppState
from pathodataforge.app.wsi_preview import WSIPreviewPanel
from pathodataforge.utils.config import DEFAULT_CONFIG, load_config, save_config


class ParamsPage(QWidget):
    config_loaded = Signal(object)

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.state = state
        self._updating = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("WSI 预览与取样")
        title.setObjectName("PageTitle")
        subtitle = QLabel("先浏览切片整体形态，需要时用绿色画笔标注关注区域，再确认 patch 尺度和取样方式。")
        subtitle.setObjectName("MutedText")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.preview_panel = WSIPreviewPanel(self.state)
        layout.addWidget(self.preview_panel, 1)

        bottom = QHBoxLayout()
        bottom.setSpacing(12)
        bottom.addWidget(self._build_sampling_card(), 3)
        bottom.addWidget(self._build_config_card(), 1)
        layout.addLayout(bottom)

        self._connect_changes()
        self.apply_config(self.state.config)

    def refresh_from_state(self) -> None:
        self.preview_panel.refresh_slides()

    def _build_sampling_card(self) -> Card:
        card = Card("取样确认")
        self.patch_size_slider, self.patch_size_value = self._int_slider_pair(
            64,
            4096,
            64,
            "单个 patch 的边长，单位为像素。",
        )
        self.stride_slider, self.stride_value = self._int_slider_pair(
            32,
            4096,
            32,
            "滑窗采样时相邻 patch 的步长；小于 Patch 大小时会按 Patch 大小执行，避免重叠。",
        )
        self.max_patches_slider, self.max_patches_value = self._int_slider_pair(
            1,
            100000,
            50,
            "随机采样或 top_quality 模式的目标 patch 数；dense 模式会输出全部组织候选 patch。",
        )
        self.min_fg_slider, self.min_fg_value = self._double_slider_pair(
            0.0,
            1.0,
            0.01,
            "候选 patch 在组织 mask 中的最低前景比例。",
        )
        self.level_combo = QComboBox()
        self.level_combo.setEditable(True)
        self.level_combo.addItems(["0", "1", "2", "5x", "10x", "20x", "40x"])
        self.level_combo.setToolTip("可填写金字塔层级或目标倍率，例如 20x。")
        self.sampling_mode_combo = QComboBox()
        self.sampling_mode_combo.addItems(["dense", "random_tissue", "top_quality"])
        self.sampling_mode_combo.setToolTip("dense 为网格采样，random_tissue 为组织区域随机采样，top_quality 会优先选择前景比例更高的位置。")
        self.use_bg_mask_check = QCheckBox("启用组织前景过滤")
        self.use_bg_mask_check.setToolTip("使用缩略图组织 mask 过滤明显背景区域。")

        self._slider_row(card.body, "Patch 大小", self.patch_size_slider, self.patch_size_value)
        self._slider_row(card.body, "步长", self.stride_slider, self.stride_value)
        self._row(card.body, "层级 / 倍率", self.level_combo)
        self._row(card.body, "采样模式", self.sampling_mode_combo)
        self._slider_row(card.body, "最小前景比例", self.min_fg_slider, self.min_fg_value)
        self._slider_row(card.body, "随机/优选 patch 数", self.max_patches_slider, self.max_patches_value)
        card.body.addWidget(self.use_bg_mask_check)
        note = QLabel("dense 会先去除背景，并输出全部非重叠组织候选 patch；random_tissue 会从这些候选中随机选择指定数量。")
        note.setObjectName("MutedText")
        note.setWordWrap(True)
        card.body.addWidget(note)
        return card

    def _build_config_card(self) -> Card:
        card = Card("配置")
        actions = QHBoxLayout()
        reset_button = icon_button("恢复取样默认")
        reset_button.clicked.connect(self.reset_defaults)
        save_button = icon_button("保存配置")
        save_button.clicked.connect(self.save_current_config)
        load_button = icon_button("加载配置")
        load_button.clicked.connect(self.load_config_file)
        actions.addWidget(reset_button)
        actions.addWidget(save_button)
        actions.addWidget(load_button)
        actions.addStretch(1)
        card.body.addLayout(actions)
        return card

    def apply_config(self, config: dict[str, Any]) -> None:
        self._updating = True
        patch = config.get("patch", {})
        self._set_pair_value(self.patch_size_slider, self.patch_size_value, int(patch.get("patch_size", DEFAULT_CONFIG["patch"]["patch_size"])))
        self._set_pair_value(self.stride_slider, self.stride_value, int(patch.get("stride", DEFAULT_CONFIG["patch"]["stride"])))
        target_count = int(
            patch.get(
                "max_patches_per_slide",
                patch.get("num_sample", DEFAULT_CONFIG["patch"]["max_patches_per_slide"]),
            )
        )
        self._set_pair_value(self.max_patches_slider, self.max_patches_value, target_count)
        self._set_pair_value(self.min_fg_slider, self.min_fg_value, float(patch.get("min_fg_ratio", DEFAULT_CONFIG["patch"]["min_fg_ratio"])))
        self.level_combo.setCurrentText(str(patch.get("level", DEFAULT_CONFIG["patch"]["level"])))
        mode = str(patch.get("sampling_mode", "dense"))
        if mode == "random":
            mode = "random_tissue"
        self.sampling_mode_combo.setCurrentText(mode if self.sampling_mode_combo.findText(mode) >= 0 else "dense")
        self.use_bg_mask_check.setChecked(bool(patch.get("use_bg_mask", True)))
        self._updating = False
        self.sync_to_state()

    def sync_to_state(self) -> None:
        if self._updating:
            return
        level_text = self.level_combo.currentText().strip()
        level: int | str = int(level_text) if level_text.isdigit() else level_text
        target_count = self.max_patches_slider.value()
        cfg = self.state.config
        cfg["patch"] = {
            **cfg.get("patch", {}),
            "patch_size": self.patch_size_slider.value(),
            "stride": max(self.patch_size_slider.value(), self.stride_slider.value()),
            "level": level,
            "max_patches_per_slide": target_count,
            "sampling_mode": self.sampling_mode_combo.currentText(),
            "num_sample": target_count,
            "min_fg_ratio": self.min_fg_value.value(),
            "use_bg_mask": self.use_bg_mask_check.isChecked(),
        }
        self.state.sync_config_inputs()
        self.state.step_status["params"] = STEP_DONE
        self.state.step_notes["params"] = "WSI 预览与取样已确认"
        self.state.changed.emit()

    def reset_defaults(self) -> None:
        current = deepcopy(self.state.config)
        current["patch"] = deepcopy(DEFAULT_CONFIG["patch"])
        self.apply_config(current)

    def save_current_config(self) -> None:
        self.sync_to_state()
        path, _ = QFileDialog.getSaveFileName(self, "保存配置", "pathodataforge_config.yaml", "YAML (*.yaml *.yml)")
        if path:
            save_config(self.state.config, path)

    def load_config_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "加载配置", "", "YAML (*.yaml *.yml)")
        if not path:
            return
        try:
            config = load_config(path)
        except Exception as exc:
            QMessageBox.critical(self, "加载失败", str(exc))
            return
        self.config_loaded.emit(config)

    def _connect_changes(self) -> None:
        for slider in [
            self.patch_size_slider,
            self.stride_slider,
            self.max_patches_slider,
            self.min_fg_slider,
        ]:
            slider.valueChanged.connect(lambda *_: self.sync_to_state())
        self.level_combo.currentTextChanged.connect(lambda *_: self.sync_to_state())
        self.sampling_mode_combo.currentTextChanged.connect(lambda *_: self.sync_to_state())
        self.use_bg_mask_check.toggled.connect(lambda *_: self.sync_to_state())

    def _set_pair_value(self, slider: QSlider, value_widget: QWidget, value: int | float) -> None:
        slider.blockSignals(True)
        if isinstance(value_widget, QDoubleSpinBox):
            scaled_value = int(round(float(value) * 100))
            slider.setValue(max(slider.minimum(), min(slider.maximum(), scaled_value)))
            value_widget.blockSignals(True)
            value_widget.setValue(float(value))
            value_widget.blockSignals(False)
        elif isinstance(value_widget, QSpinBox):
            int_value = int(round(float(value)))
            slider.setValue(max(slider.minimum(), min(slider.maximum(), int_value)))
            value_widget.blockSignals(True)
            value_widget.setValue(int_value)
            value_widget.blockSignals(False)
        slider.blockSignals(False)

    @staticmethod
    def _row(parent_layout: QVBoxLayout, label: str, widget: QWidget) -> None:
        row = QHBoxLayout()
        title = QLabel(label)
        title.setMinimumWidth(96)
        title.setToolTip(widget.toolTip())
        row.addWidget(title)
        row.addWidget(widget, 1)
        parent_layout.addLayout(row)

    @staticmethod
    def _slider_row(parent_layout: QVBoxLayout, label: str, slider: QSlider, value_widget: QWidget) -> None:
        row = QHBoxLayout()
        title = QLabel(label)
        title.setMinimumWidth(96)
        title.setToolTip(slider.toolTip())
        row.addWidget(title)
        row.addWidget(slider, 1)
        value_widget.setMinimumWidth(84)
        value_widget.setMaximumWidth(110)
        row.addWidget(value_widget)
        parent_layout.addLayout(row)

    @staticmethod
    def _int_slider_pair(
        minimum: int,
        maximum: int,
        step: int,
        tooltip: str,
    ) -> tuple[QSlider, QSpinBox]:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setSingleStep(step)
        slider.setPageStep(max(step, (maximum - minimum) // 10))
        slider.setToolTip(tooltip)
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        spin.setToolTip(tooltip)
        slider.valueChanged.connect(spin.setValue)
        spin.valueChanged.connect(slider.setValue)
        return slider, spin

    @staticmethod
    def _double_slider_pair(
        minimum: float,
        maximum: float,
        step: float,
        tooltip: str,
    ) -> tuple[QSlider, QDoubleSpinBox]:
        scale = 100
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(int(round(minimum * scale)), int(round(maximum * scale)))
        slider.setSingleStep(max(1, int(round(step * scale))))
        slider.setPageStep(10)
        slider.setToolTip(tooltip)
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(2)
        spin.setSingleStep(step)
        spin.setToolTip(tooltip)
        slider.valueChanged.connect(lambda value: spin.setValue(value / scale))
        spin.valueChanged.connect(lambda value: slider.setValue(int(round(value * scale))))
        return slider, spin
