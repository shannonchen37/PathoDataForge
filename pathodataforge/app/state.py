"""Shared GUI state for the iMoonLab-PathoDataForge desktop app."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pandas as pd
from PySide6.QtCore import QObject, Signal

from pathodataforge.core.metadata_cleaner import CleanMetadataResult
from pathodataforge.core.scanner import ScanResult
from pathodataforge.utils.config import DEFAULT_CONFIG


STEP_ORDER = [
    ("import", "导入数据"),
    ("metadata", "读取元信息"),
    ("match", "预览匹配"),
    ("params", "预览取样"),
    ("feature", "特征提取"),
    ("run", "运行处理"),
    ("report", "查看报告"),
]

STEP_TODO = "未开始"
STEP_DONE = "已完成"
STEP_WARN = "有警告"
STEP_ERROR = "出错"


class AppState(QObject):
    """Single source of truth shared by all GUI pages."""

    changed = Signal()
    progress_changed = Signal(int, str)

    def __init__(self) -> None:
        super().__init__()
        self.wsi_dir = ""
        self.metadata_file = ""
        self.output_dir = str(DEFAULT_CONFIG["input"]["output_dir"])
        self.scan_result: ScanResult | None = None
        self.scanned_files: list[Path] = []
        self.metadata_df: pd.DataFrame | None = None
        self.metadata_fields: list[str] = []
        self.selected_case_id_column = ""
        self.selected_label_column = ""
        self.selected_filename_column = ""
        self.case_id_regex = ""
        self.match_result: CleanMetadataResult | None = None
        self.config: dict[str, Any] = deepcopy(DEFAULT_CONFIG)
        self.hardware_status = ""
        self.available_devices: list[str] = ["auto", "cpu"]
        self.run_status = "就绪"
        self.current_stage = "等待开始"
        self.current_slide = "无"
        self.current_patch_count = "0"
        self.progress = 0
        self.last_summary: dict[str, Any] | None = None
        self.output_paths: dict[str, str] = {}
        self.last_result_text = "暂无结果"
        self.step_status = {key: STEP_TODO for key, _ in STEP_ORDER}
        self.step_notes = {key: "" for key, _ in STEP_ORDER}
        self.sync_config_inputs()

    def sync_config_inputs(self) -> None:
        input_cfg = self.config.setdefault("input", {})
        input_cfg["wsi_dir"] = self.wsi_dir
        input_cfg["metadata_file"] = self.metadata_file
        input_cfg["output_dir"] = self.output_dir
        metadata_cfg = self.config.setdefault("metadata", {})
        metadata_cfg["case_id_column"] = self.selected_case_id_column
        metadata_cfg["label_column"] = self.selected_label_column
        metadata_cfg["filename_column"] = self.selected_filename_column
        metadata_cfg["case_id_regex"] = self.case_id_regex

    def set_paths(self, wsi_dir: str | None = None, metadata_file: str | None = None, output_dir: str | None = None) -> None:
        if wsi_dir is not None:
            self.wsi_dir = wsi_dir
        if metadata_file is not None:
            self.metadata_file = metadata_file
        if output_dir is not None:
            self.output_dir = output_dir
        self.sync_config_inputs()
        self.changed.emit()

    def set_metadata_columns(
        self,
        case_id_column: str,
        label_column: str,
        filename_column: str = "",
        case_id_regex: str = "",
    ) -> None:
        self.selected_case_id_column = case_id_column
        self.selected_label_column = label_column
        self.selected_filename_column = filename_column
        self.case_id_regex = case_id_regex
        self.sync_config_inputs()
        self.changed.emit()

    def update_step(self, key: str, status: str, note: str = "") -> None:
        self.step_status[key] = status
        self.step_notes[key] = note
        self.changed.emit()

    def set_progress(self, value: int, message: str = "") -> None:
        self.progress = max(0, min(100, int(value)))
        if message:
            self.current_stage = message
        self.progress_changed.emit(self.progress, self.current_stage)
        self.changed.emit()

    def set_summary(self, summary: dict[str, Any]) -> None:
        self.last_summary = summary
        reports = summary.get("reports", {})
        patches = summary.get("patches", {})
        summary_path = str(reports.get("summary_json", "") or "")
        output_root = Path(summary_path).parents[1] if summary_path else Path(self.output_dir)
        self.output_paths = {
            "root": str(output_root),
            "summary": summary_path,
            "manifest": str(patches.get("manifest_csv", "") or ""),
            "coordinates": str(output_root / "metadata" / "coordinates"),
            "features": str(output_root / "features"),
            "overlays": str(output_root / "reports" / "overlays"),
            "annotations": str(output_root / "reports" / "annotations"),
            "privacy_index": str(output_root / "privacy_index"),
            "metadata_cleaned": str(summary.get("metadata", {}).get("metadata_cleaned_csv", "") or ""),
            "mapping": str(summary.get("metadata", {}).get("mapping_csv", "") or ""),
        }
        kept = summary.get("patches", {}).get("kept", 0)
        discarded = summary.get("patches", {}).get("discarded", 0)
        self.last_result_text = f"完成：保留 {kept}，丢弃 {discarded}"
        self.changed.emit()

    @property
    def model_name(self) -> str:
        return str(self.config.get("features", {}).get("model_name", "ResNet50"))

    @property
    def cache_text(self) -> str:
        overwrite = bool(self.config.get("features", {}).get("overwrite", False))
        force_resample = bool(self.config.get("runtime", {}).get("force_resample", False))
        return "覆盖重算" if overwrite or force_resample else "复用缓存"

    def split_total(self) -> float:
        split = self.config.get("split", {})
        return float(split.get("train", 0)) + float(split.get("val", 0)) + float(split.get("test", 0))

    def validate_ready_to_run(self) -> list[str]:
        errors: list[str] = []
        if not self.scan_result or not self.scanned_files:
            errors.append("请先扫描 WSI 文件夹。")
        if self.metadata_df is None or not self.metadata_fields:
            errors.append("请先读取 Metadata 字段。")
        if not self.selected_case_id_column:
            errors.append("请选择病例 ID 字段。")
        if not self.selected_label_column:
            errors.append("请选择标签字段。")
        if not self.output_dir:
            errors.append("请选择输出目录。")
        if not self.match_result:
            errors.append("请先预览元信息匹配。")
        if self.match_result and self.match_result.matched_count == 0:
            errors.append("当前没有成功匹配的 WSI，请检查字段映射。")
        return errors
