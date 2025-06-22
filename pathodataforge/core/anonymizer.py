"""Filename anonymization helpers."""

from __future__ import annotations

import re
from pathlib import Path


def sanitize_filename_token(value: object, fallback: str = "unknown") -> str:
    """Return a filesystem-friendly token for patch names."""
    text = str(value or "").strip()
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("._-")
    return text or fallback


def generate_anonymized_filename(
    patient_index: int,
    slide_index: int,
    original_path: str | Path,
) -> str:
    suffix = Path(original_path).suffix.lower()
    return f"patient_{patient_index:06d}_slide_{slide_index:04d}{suffix}"
