"""YAML configuration loading and saving."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG: dict[str, Any] = {
    "input": {
        "wsi_dir": "",
        "metadata_file": "",
        "output_dir": "./PathoDataForge_output",
    },
    "metadata": {
        "case_id_column": "",
        "label_column": "",
        "filename_column": "",
        "case_id_regex": "",
    },
    "patch": {
        "patch_size": 512,
        "stride": 512,
        "level": 0,
        "max_patches_per_slide": 2000,
        "sampling_mode": "dense",
        "num_sample": 2000,
        "max_trials": 100000,
        "min_fg_ratio": 0.25,
        "use_bg_mask": True,
    },
    "quality": {
        "tissue_threshold": 0.5,
        "blur_threshold": 80.0,
        "brightness_min": 30,
        "brightness_max": 230,
    },
    "split": {
        "train": 0.7,
        "val": 0.15,
        "test": 0.15,
        "seed": 42,
    },
    "coordinates": {
        "enable": True,
        "format": "range_level0",
    },
    "visualization": {
        "save_overlay": True,
        "display_overlay": True,
        "downsample": 32,
        "outline_rgb": [37, 99, 235],
        "outline_width": 1,
        "style": "points",
        "show_tissue_mask": True,
        "max_box_count": 350,
        "jpeg_quality": 90,
    },
    "features": {
        "enable": True,
        "model_name": "ResNet50",
        "batch_size": 32,
        "num_workers": 0,
        "device": "auto",
        "precision": "auto",
        "hf_token": "",
        "overwrite": False,
    },
    "runtime": {
        "cpu_workers": 1,
        "gpu_workers": 1,
        "queue_maxsize": 8,
        "target_files": [],
    },
}


def deep_update(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge dictionaries without mutating the input base."""
    merged = deepcopy(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_update(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(config_path: str | Path) -> dict[str, Any]:
    """Load a YAML config and merge it over defaults."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Config file must contain a mapping: {path}")
    return deep_update(DEFAULT_CONFIG, loaded)


def save_config(config: dict[str, Any], output_path: str | Path) -> None:
    """Write a YAML config file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config, handle, sort_keys=False, allow_unicode=True)


def as_positive_int(value: Any, field_name: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{field_name} must be > 0")
    return parsed


def resolve_demo_defaults(config: dict[str, Any]) -> dict[str, Any]:
    """Use generated demo data when default input fields are still blank."""
    resolved = deepcopy(config)
    input_cfg = resolved.setdefault("input", {})
    wsi_dir = str(input_cfg.get("wsi_dir") or "").strip()
    metadata_file = str(input_cfg.get("metadata_file") or "").strip()
    demo_wsi = Path("demo_data/wsi")
    demo_metadata = Path("demo_data/metadata.csv")
    if not wsi_dir and not metadata_file and demo_wsi.exists() and demo_metadata.exists():
        input_cfg["wsi_dir"] = str(demo_wsi)
        input_cfg["metadata_file"] = str(demo_metadata)
        metadata_cfg = resolved.setdefault("metadata", {})
        metadata_cfg.setdefault("case_id_column", "case_id")
        metadata_cfg.setdefault("label_column", "label")
        if not metadata_cfg.get("case_id_column"):
            metadata_cfg["case_id_column"] = "case_id"
        if not metadata_cfg.get("label_column"):
            metadata_cfg["label_column"] = "label"
    return resolved
