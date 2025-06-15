"""I/O helpers used by the processing pipeline."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def read_metadata_table(path: str | Path) -> pd.DataFrame:
    """Read clinical metadata from CSV or Excel."""
    metadata_path = Path(path)
    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata file not found: {metadata_path}")

    suffix = metadata_path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(metadata_path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(metadata_path)
    raise ValueError(f"Unsupported metadata file type: {suffix}")


def ensure_directory(path: str | Path) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def write_json(data: dict[str, Any], path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def atomic_save_npy(array: np.ndarray, path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with tmp_path.open("wb") as handle:
        np.save(handle, array)
    os.replace(tmp_path, output_path)


def safe_load_npy(path: str | Path, logger: logging.Logger | None = None) -> np.ndarray | None:
    npy_path = Path(path)
    if not npy_path.exists():
        return None
    try:
        return np.load(npy_path, allow_pickle=False)
    except Exception as exc:
        broken_path = npy_path.with_suffix(npy_path.suffix + ".broken")
        if logger:
            logger.warning("Broken npy cache %s: %s; renaming to %s", npy_path, exc, broken_path)
        try:
            os.replace(npy_path, broken_path)
        except OSError:
            pass
        return None


def relative_or_absolute(path: str | Path, base_dir: str | Path) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return Path(base_dir) / candidate
