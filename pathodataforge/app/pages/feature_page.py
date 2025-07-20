"""Feature extraction and runtime resource page."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pathodataforge.app.components import Card, CollapsibleSection, icon_button
from pathodataforge.app.state import STEP_DONE, AppState
from pathodataforge.utils.config import DEFAULT_CONFIG


MODEL_INFO = {
    "ResNet50": {
        "type": "ImageNet 预训练 CNN",
        "dim": "2048",
        "usage": "基线特征、MIL 输入、快速测试",
    },
    "UNI": {
        "type": "病理基础模型",
        "dim": "1024",
        "usage": "病理表征、MIL 输入",
    },
    "UNI2-h": {
        "type": "大规模病理基础模型",
        "dim": "1536",
        "usage": "高质量病理表征，资源占用较高",
    },
    "CONCH": {
        "type": "病理图文模型",
        "dim": "512",
        "usage": "病理图像表征和跨模态任务",
    },
    "Virchow2": {
        "type": "大规模病理基础模型",
        "dim": "2560",
        "usage": "高维病理特征，建议 GPU/MPS",
    },
}


class FeaturePage(QWidget):
    refresh_hardware_requested = Signal()

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.state = state
        self._updating = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        title = QLabel("特征提取")
        title.setObjectName("PageTitle")
        subtitle = QLabel("特征提取会在运行处理时自动执行，本页用于配置模型、运行设备和工作进程。")
        subtitle.setObjectName("MutedText")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        columns = QHBoxLayout()
        columns.setSpacing(14)
        left = QVBoxLayout()
        right = QVBoxLayout()
        left.setSpacing(14)
        right.setSpacing(14)
        left.addWidget(self._build_feature_card())
        left.addWidget(self._build_model_info_card())
        left.addWidget(self._build_runtime_card())
        right.addWidget(self._build_processing_card())
        right.addWidget(self._build_hardware_card())
        left.addStretch(1)
        right.addStretch(1)
        columns.addLayout(left, 1)
        columns.addLayout(right, 1)
        layout.addLayout(columns)
        layout.addStretch(1)

        self.apply_config(self.state.config)

    def _build_feature_card(self) -> Card:
        card = Card("模型选择")
        self.feature_model_combo = QComboBox()
        self.feature_model_combo.addItems(["ResNet50", "UNI", "UNI2-h", "CONCH", "Virchow2"])
        self.feature_model_combo.currentTextChanged.connect(self._model_changed)
        self._row(card.body, "特征模型", self.feature_model_combo)
        return card

    def _build_model_info_card(self) -> Card:
        card = Card("当前模型说明")
        self.model_type_label = QLabel("")
        self.model_dim_label = QLabel("")
        self.model_usage_label = QLabel("")
        for label in [
            self.model_type_label,
            self.model_dim_label,
            self.model_usage_label,
        ]:
            label.setWordWrap(True)
            card.body.addWidget(label)
        return card

    def _build_runtime_card(self) -> Card:
        card = Card("运行资源")
        self.feature_device_combo = QComboBox()
        self.feature_device_combo.addItems(["auto", "cpu"])
        self.feature_precision_combo = QComboBox()
        self.feature_precision_combo.addItems(["auto", "fp32", "fp16"])
        self.feature_batch_spin = self._spin(1, 4096, 1, "特征提取批大小。")
        self.cpu_workers_spin = self._spin(1, 64, 1, "坐标采样阶段 CPU 进程数。")
        self.gpu_workers_spin = self._spin(1, 16, 1, "CUDA 多卡特征工作进程数；MPS/CPU 通常设为 1。")
        self.queue_size_spin = self._spin(1, 256, 1, "CPU 采样与特征工作进程之间的任务队列大小。")
        self.target_files_edit = QLineEdit()
        self.target_files_edit.setPlaceholderText("可选，多个文件名用逗号分隔")
        for widget in [
            self.feature_device_combo,
            self.feature_precision_combo,
            self.feature_batch_spin,
            self.cpu_workers_spin,
            self.gpu_workers_spin,
            self.queue_size_spin,
            self.target_files_edit,
        ]:
            if isinstance(widget, QComboBox):
                widget.currentTextChanged.connect(lambda *_: self.sync_to_state())
            elif isinstance(widget, QLineEdit):
                widget.editingFinished.connect(self.sync_to_state)
            else:
                widget.valueChanged.connect(lambda *_: self.sync_to_state())  # type: ignore[attr-defined]

        self._row(card.body, "运行设备", self.feature_device_combo)
        self._row(card.body, "精度", self.feature_precision_combo)
        self._row(card.body, "批大小", self.feature_batch_spin)
        self._row(card.body, "CPU 采样进程数", self.cpu_workers_spin)
        self._row(card.body, "GPU 特征进程数", self.gpu_workers_spin)
        self._row(card.body, "队列大小", self.queue_size_spin)
        self._row(card.body, "指定文件", self.target_files_edit)
        return card

    def _build_processing_card(self) -> Card:
        card = Card("处理参数")

        quality_title = QLabel("质控")
        quality_title.setObjectName("CardTitle")
        card.body.addWidget(quality_title)
        quality_grid = QGridLayout()
        quality_grid.setHorizontalSpacing(10)
        quality_grid.setVerticalSpacing(8)
        self.tissue_spin = self._double_spin(0.0, 1.0, 0.05, 2, "patch 通过 QC 所需的组织占比。")
        self.blur_spin = self._double_spin(0.0, 10000.0, 5.0, 1, "Laplacian 方差阈值，低于该值视为模糊。")
        self.brightness_min_spin = self._spin(0, 255, 5, "平均亮度低于该值视为过暗。")
        self.brightness_max_spin = self._spin(0, 255, 5, "平均亮度高于该值视为过亮。")
        self._grid_pair(quality_grid, 0, 0, "组织阈值", self.tissue_spin)
        self._grid_pair(quality_grid, 0, 2, "模糊阈值", self.blur_spin)
        self._grid_pair(quality_grid, 1, 0, "亮度下限", self.brightness_min_spin)
        self._grid_pair(quality_grid, 1, 2, "亮度上限", self.brightness_max_spin)
        card.body.addLayout(quality_grid)

        advanced = CollapsibleSection("高级采样与输出", expanded=False)
        self.max_candidates_spin = self._spin(1, 5000000, 1000, "patch 提取阶段最多评估的候选数量。")
        self.max_trials_spin = self._spin(1, 10000000, 1000, "随机采样阶段最多尝试次数。")
        self.sample_seed_spin = self._spin(0, 2147483647, 1, "采样随机种子，用于复现实验。")
        self.coord_output_check = QCheckBox("输出坐标 npy / csv")
        self.coord_output_check.setToolTip("保存 level 0 坐标范围，便于复用和断点续跑。")
        self.save_overlay_check = QCheckBox("保存采样预览图")
        self.save_overlay_check.setToolTip("保存带采样框的 WSI 缩略图。")
        self.display_overlay_check = QCheckBox("运行结束后预览采样图")
        self.overlay_downsample_spin = self._spin(4, 256, 4, "采样预览图相对 level 0 的下采样倍率。")
        self.overlay_width_spin = self._spin(1, 12, 1, "采样预览标记线宽。")
        self.overlay_quality_spin = self._spin(40, 100, 5, "overlay JPEG 保存质量。")
        self._row(advanced.content_layout, "最大候选数", self.max_candidates_spin)
        self._row(advanced.content_layout, "最大尝试数", self.max_trials_spin)
        self._row(advanced.content_layout, "采样随机种子", self.sample_seed_spin)
        advanced.content_layout.addWidget(self.coord_output_check)
        advanced.content_layout.addWidget(self.save_overlay_check)
        advanced.content_layout.addWidget(self.display_overlay_check)
        self._row(advanced.content_layout, "采样图下采样", self.overlay_downsample_spin)
        self._row(advanced.content_layout, "采样标记线宽", self.overlay_width_spin)
        self._row(advanced.content_layout, "JPEG 质量", self.overlay_quality_spin)
        card.body.addWidget(advanced)

        for widget in [
            self.tissue_spin,
            self.blur_spin,
            self.brightness_min_spin,
            self.brightness_max_spin,
            self.max_candidates_spin,
            self.max_trials_spin,
            self.sample_seed_spin,
            self.overlay_downsample_spin,
            self.overlay_width_spin,
            self.overlay_quality_spin,
        ]:
            widget.valueChanged.connect(lambda *_: self.sync_to_state())  # type: ignore[attr-defined]
        for checkbox in [
            self.coord_output_check,
            self.save_overlay_check,
            self.display_overlay_check,
        ]:
            checkbox.toggled.connect(lambda *_: self.sync_to_state())
        return card

    def _build_hardware_card(self) -> Card:
        refresh = icon_button("刷新硬件")
        refresh.clicked.connect(self.refresh_hardware_requested)
        card = Card("硬件状态", refresh)
        self.hardware_status_text = QPlainTextEdit()
        self.hardware_status_text.setReadOnly(True)
        self.hardware_status_text.setMinimumHeight(150)
        card.body.addWidget(self.hardware_status_text)
        return card

    def set_hardware_status(self, text: str, devices: list[str]) -> None:
        self.hardware_status_text.setPlainText(text)
        current = self.feature_device_combo.currentText()
        self.feature_device_combo.blockSignals(True)
        self.feature_device_combo.clear()
        self.feature_device_combo.addItems(devices)
        self.feature_device_combo.setCurrentText(current if current in devices else "auto")
        self.feature_device_combo.blockSignals(False)
        self.sync_to_state()

    def apply_config(self, config: dict[str, object]) -> None:
        self._updating = True
        features = config.get("features", {}) if isinstance(config.get("features", {}), dict) else {}
        runtime = config.get("runtime", {}) if isinstance(config.get("runtime", {}), dict) else {}
        patch = config.get("patch", {}) if isinstance(config.get("patch", {}), dict) else {}
        quality = config.get("quality", {}) if isinstance(config.get("quality", {}), dict) else {}
        coords = config.get("coordinates", {}) if isinstance(config.get("coordinates", {}), dict) else {}
        vis = config.get("visualization", {}) if isinstance(config.get("visualization", {}), dict) else {}
        self.feature_model_combo.setCurrentText(str(features.get("model_name", "ResNet50")))
        self.feature_precision_combo.setCurrentText(str(features.get("precision", "auto")))
        self.feature_batch_spin.setValue(int(features.get("batch_size", DEFAULT_CONFIG["features"]["batch_size"])))
        self.cpu_workers_spin.setValue(int(runtime.get("cpu_workers", DEFAULT_CONFIG["runtime"]["cpu_workers"])))
        self.gpu_workers_spin.setValue(int(runtime.get("gpu_workers", DEFAULT_CONFIG["runtime"]["gpu_workers"])))
        self.queue_size_spin.setValue(int(runtime.get("queue_maxsize", DEFAULT_CONFIG["runtime"]["queue_maxsize"])))
        self.target_files_edit.setText(", ".join(runtime.get("target_files", []) or []))
        self.tissue_spin.setValue(float(quality.get("tissue_threshold", DEFAULT_CONFIG["quality"]["tissue_threshold"])))
        self.blur_spin.setValue(float(quality.get("blur_threshold", DEFAULT_CONFIG["quality"]["blur_threshold"])))
        self.brightness_min_spin.setValue(int(quality.get("brightness_min", DEFAULT_CONFIG["quality"]["brightness_min"])))
        self.brightness_max_spin.setValue(int(quality.get("brightness_max", DEFAULT_CONFIG["quality"]["brightness_max"])))
        self.max_candidates_spin.setValue(
            int(
                patch.get(
                    "max_candidates_per_slide",
                    max(
                        int(patch.get("max_patches_per_slide", DEFAULT_CONFIG["patch"]["max_patches_per_slide"])) * 20,
                        int(patch.get("max_patches_per_slide", DEFAULT_CONFIG["patch"]["max_patches_per_slide"])) + 1000,
                    ),
                )
            )
        )
        self.max_trials_spin.setValue(int(patch.get("max_trials", DEFAULT_CONFIG["patch"]["max_trials"])))
        self.sample_seed_spin.setValue(int(patch.get("seed", 42)))
        self.coord_output_check.setChecked(bool(coords.get("enable", DEFAULT_CONFIG["coordinates"]["enable"])))
        self.save_overlay_check.setChecked(bool(vis.get("save_overlay", DEFAULT_CONFIG["visualization"]["save_overlay"])))
        self.display_overlay_check.setChecked(bool(vis.get("display_overlay", DEFAULT_CONFIG["visualization"]["display_overlay"])))
        self.overlay_downsample_spin.setValue(int(vis.get("downsample", DEFAULT_CONFIG["visualization"]["downsample"])))
        self.overlay_width_spin.setValue(int(vis.get("outline_width", DEFAULT_CONFIG["visualization"]["outline_width"])))
        self.overlay_quality_spin.setValue(int(vis.get("jpeg_quality", DEFAULT_CONFIG["visualization"]["jpeg_quality"])))
        device = str(features.get("device", "auto"))
        if self.feature_device_combo.findText(device) >= 0:
            self.feature_device_combo.setCurrentText(device)
        self._updating = False
        self._update_model_info()
        self.sync_to_state()

    def sync_to_state(self) -> None:
        if self._updating:
            return
        target_files = [item.strip() for item in self.target_files_edit.text().split(",") if item.strip()]
        cfg = self.state.config
        cfg["features"] = {
            **cfg.get("features", {}),
            "enable": True,
            "model_name": self.feature_model_combo.currentText(),
            "batch_size": self.feature_batch_spin.value(),
            "device": self.feature_device_combo.currentText(),
            "precision": self.feature_precision_combo.currentText(),
            "hf_token": "",
            "overwrite": False,
        }
        cfg["runtime"] = {
            **cfg.get("runtime", {}),
            "cpu_workers": self.cpu_workers_spin.value(),
            "gpu_workers": self.gpu_workers_spin.value(),
            "queue_maxsize": self.queue_size_spin.value(),
            "target_files": target_files,
            "force_resample": False,
        }
        cfg["patch"] = {
            **cfg.get("patch", {}),
            "max_candidates_per_slide": self.max_candidates_spin.value(),
            "max_trials": self.max_trials_spin.value(),
            "seed": self.sample_seed_spin.value(),
        }
        cfg["quality"] = {
            "tissue_threshold": self.tissue_spin.value(),
            "blur_threshold": self.blur_spin.value(),
            "brightness_min": self.brightness_min_spin.value(),
            "brightness_max": self.brightness_max_spin.value(),
        }
        cfg["coordinates"] = {
            "enable": self.coord_output_check.isChecked(),
            "format": "range_level0",
        }
        cfg["visualization"] = {
            **DEFAULT_CONFIG["visualization"],
            "save_overlay": self.save_overlay_check.isChecked(),
            "display_overlay": self.display_overlay_check.isChecked(),
            "downsample": self.overlay_downsample_spin.value(),
            "outline_width": self.overlay_width_spin.value(),
            "jpeg_quality": self.overlay_quality_spin.value(),
        }
        self.state.sync_config_inputs()
        feature_state = f"模型：{self.feature_model_combo.currentText()}"
        self.state.step_status["feature"] = STEP_DONE
        self.state.step_notes["feature"] = feature_state
        self._update_model_info()
        self.state.changed.emit()

    def _sync_enabled(self) -> None:
        self.sync_to_state()

    def _model_changed(self) -> None:
        self._update_model_info()
        self.sync_to_state()

    def _update_model_info(self) -> None:
        model = self.feature_model_combo.currentText()
        info = MODEL_INFO.get(model, MODEL_INFO["ResNet50"])
        self.model_type_label.setText(f"模型类型：{info['type']}")
        self.model_dim_label.setText(f"输出维度：{info['dim']}")
        self.model_usage_label.setText(f"适合用途：{info['usage']}")

    @staticmethod
    def _grid_pair(grid: QGridLayout, row: int, column: int, label: str, widget: QWidget) -> None:
        title = QLabel(label)
        title.setToolTip(widget.toolTip())
        widget.setMaximumWidth(110)
        grid.addWidget(title, row, column)
        grid.addWidget(widget, row, column + 1)

    @staticmethod
    def _row(parent_layout: QVBoxLayout, label: str, widget: QWidget) -> None:
        row = QHBoxLayout()
        title = QLabel(label)
        title.setMinimumWidth(130)
        row.addWidget(title)
        row.addWidget(widget, 1)
        parent_layout.addLayout(row)

    @staticmethod
    def _spin(minimum: int, maximum: int, step: int, tooltip: str) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        spin.setToolTip(tooltip)
        return spin

    @staticmethod
    def _double_spin(minimum: float, maximum: float, step: float, decimals: int, tooltip: str) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        spin.setDecimals(decimals)
        spin.setToolTip(tooltip)
        return spin
