"""Clinical metadata cleaning, matching, and anonymized mapping."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from pathodataforge.core.anonymizer import generate_anonymized_filename
from pathodataforge.utils.io import read_metadata_table


STANDARD_METADATA_COLUMNS = [
    "case_id",
    "slide_id",
    "original_filename",
    "anonymized_filename",
    "label",
    "source_path",
    "status",
]


@dataclass(slots=True)
class CleanMetadataResult:
    metadata: pd.DataFrame
    mapping: pd.DataFrame
    fields: list[str]
    matched_count: int
    unmatched_count: int
    unmatched_files: list[str]


def _safe_str(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    return str(value).strip()


def normalize_case_id(value: object) -> str:
    """Normalize a case ID for matching while preserving the original elsewhere."""
    text = _safe_str(value).lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def normalize_filename(value: object) -> str:
    return Path(_safe_str(value)).name.lower()


def infer_case_id_from_filename(path: str | Path, case_id_regex: str | None = "") -> str:
    """Infer a likely case ID from a slide filename."""
    stem = Path(path).stem
    if case_id_regex:
        try:
            custom_match = re.search(case_id_regex, stem)
        except re.error as exc:
            raise ValueError(f"Invalid case ID regex: {case_id_regex}") from exc
        if custom_match:
            if custom_match.lastindex:
                return custom_match.group(1)
            return custom_match.group(0)

    tcga_match = re.search(r"(TCGA-[A-Z0-9]{2}-[A-Z0-9]{4})", stem, flags=re.IGNORECASE)
    if tcga_match:
        return tcga_match.group(1).upper()

    patterns = [
        r"(case[-_ ]?\d+)",
        r"(patient[-_ ]?\d+)",
        r"(pt[-_ ]?\d+)",
        r"(sample[-_ ]?\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, stem, flags=re.IGNORECASE)
        if match:
            return re.sub(r"[-_ ]+", "", match.group(1)).upper()

    for delimiter in ("_slide", "-slide", " slide"):
        index = stem.lower().find(delimiter)
        if index > 0:
            return stem[:index]
    return re.split(r"[_\-\s]+", stem, maxsplit=1)[0]


def _validate_columns(
    metadata_df: pd.DataFrame,
    case_id_column: str,
    label_column: str,
    filename_column: str | None,
) -> None:
    missing = [
        column
        for column in (case_id_column, label_column)
        if not column or column not in metadata_df.columns
    ]
    if filename_column and filename_column not in metadata_df.columns:
        missing.append(filename_column)
    if missing:
        raise ValueError(f"Missing metadata columns: {', '.join(missing)}")


def _first_row_index_by_normalized_case(
    metadata_df: pd.DataFrame,
    case_id_column: str,
) -> dict[str, int]:
    index: dict[str, int] = {}
    for row_index, value in metadata_df[case_id_column].items():
        normalized = normalize_case_id(value)
        if normalized and normalized not in index:
            index[normalized] = int(row_index)
    return index


def _first_row_index_by_filename(
    metadata_df: pd.DataFrame,
    filename_column: str,
) -> dict[str, int]:
    index: dict[str, int] = {}
    if not filename_column:
        return index
    for row_index, value in metadata_df[filename_column].items():
        filename = normalize_filename(value)
        stem = Path(filename).stem.lower()
        for key in {filename, stem}:
            if key and key not in index:
                index[key] = int(row_index)
    return index


def clean_metadata(
    wsi_files: Iterable[str | Path],
    metadata_file: str | Path,
    case_id_column: str,
    label_column: str,
    filename_column: str | None = "",
    case_id_regex: str | None = "",
) -> CleanMetadataResult:
    """Match WSI files to clinical metadata and produce anonymized tables."""
    metadata_df = read_metadata_table(metadata_file)
    filename_column = filename_column or ""
    _validate_columns(metadata_df, case_id_column, label_column, filename_column)

    case_index = _first_row_index_by_normalized_case(metadata_df, case_id_column)
    filename_index = _first_row_index_by_filename(metadata_df, filename_column)

    rows: list[dict[str, object]] = []
    mapping_rows: list[dict[str, object]] = []
    unmatched_files: list[str] = []
    case_to_patient_index: dict[str, int] = {}
    slide_counts_by_case: dict[str, int] = {}

    for path_like in sorted(wsi_files, key=lambda value: str(value).lower()):
        path = Path(path_like)
        original_filename = path.name
        inferred_case_id = infer_case_id_from_filename(path, case_id_regex=case_id_regex)
        inferred_norm = normalize_case_id(inferred_case_id)

        row_index: int | None = None
        if filename_index:
            row_index = filename_index.get(original_filename.lower())
            if row_index is None:
                row_index = filename_index.get(path.stem.lower())
        if row_index is None:
            row_index = case_index.get(inferred_norm)

        if row_index is not None:
            metadata_row = metadata_df.loc[row_index]
            case_id = _safe_str(metadata_row[case_id_column]) or inferred_case_id
            label = _safe_str(metadata_row[label_column])
            status = "matched"
        else:
            case_id = inferred_case_id
            label = ""
            status = "unmatched"
            unmatched_files.append(original_filename)

        case_norm = normalize_case_id(case_id) or inferred_norm or normalize_case_id(path.stem)
        if case_norm not in case_to_patient_index:
            case_to_patient_index[case_norm] = len(case_to_patient_index) + 1
        slide_counts_by_case[case_norm] = slide_counts_by_case.get(case_norm, 0) + 1

        patient_index = case_to_patient_index[case_norm]
        slide_index = slide_counts_by_case[case_norm]
        slide_id = f"slide_{slide_index:04d}"
        anonymized_filename = generate_anonymized_filename(patient_index, slide_index, path)

        cleaned_row = {
            "case_id": case_id,
            "slide_id": slide_id,
            "original_filename": original_filename,
            "anonymized_filename": anonymized_filename,
            "label": label,
            "source_path": str(path),
            "status": status,
        }
        rows.append(cleaned_row)
        mapping_rows.append(
            {
                "original_filename": original_filename,
                "anonymized_filename": anonymized_filename,
                "case_id": case_id,
            }
        )

    cleaned = pd.DataFrame(rows, columns=STANDARD_METADATA_COLUMNS)
    mapping = pd.DataFrame(
        mapping_rows,
        columns=["original_filename", "anonymized_filename", "case_id"],
    )
    matched_count = int((cleaned["status"] == "matched").sum()) if not cleaned.empty else 0
    unmatched_count = int((cleaned["status"] == "unmatched").sum()) if not cleaned.empty else 0
    return CleanMetadataResult(
        metadata=cleaned,
        mapping=mapping,
        fields=list(metadata_df.columns),
        matched_count=matched_count,
        unmatched_count=unmatched_count,
        unmatched_files=unmatched_files,
    )
