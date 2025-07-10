"""Pipeline entry points for de-identified WSI index generation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from pathodataforge.privacy_index.index_builder import build_privacy_index


@dataclass(slots=True)
class PrivacyIndexResult:
    manifest_csv: Path
    private_mapping_csv: Path
    manifest: pd.DataFrame
    private_mapping: pd.DataFrame


def run_privacy_index_pipeline(
    raw_root: str | Path,
    processed_root: str | Path,
    *,
    clinical_table: str | Path | None = None,
    secret_key: str | bytes | None = None,
    test_mode: bool = False,
) -> PrivacyIndexResult:
    raw = Path(raw_root)
    clinical_path = Path(clinical_table) if clinical_table else raw / "clinical_tables" / "synthetic_clinical.csv"
    clinical_df = pd.read_csv(clinical_path)
    return run_privacy_index_dataframe(
        clinical_df,
        processed_root,
        wsi_root=raw / "wsi_files",
        annotation_root=raw / "annotation_files",
        secret_key=secret_key,
        test_mode=test_mode,
    )


def run_privacy_index_dataframe(
    clinical_df: pd.DataFrame,
    processed_root: str | Path,
    *,
    wsi_root: str | Path | None = None,
    annotation_root: str | Path | None = None,
    secret_key: str | bytes | None = None,
    test_mode: bool = False,
) -> PrivacyIndexResult:
    processed = Path(processed_root)
    manifests_dir = processed / "manifests"
    private_dir = processed / "mappings_private"
    logs_dir = processed / "logs"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    private_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    manifest, private_mapping = build_privacy_index(
        clinical_df,
        processed,
        wsi_root=wsi_root,
        annotation_root=annotation_root,
        secret_key=secret_key,
        test_mode=test_mode,
    )
    manifest_csv = manifests_dir / "manifest.csv"
    private_mapping_csv = private_dir / "private_id_mapping.csv"
    manifest.to_csv(manifest_csv, index=False)
    private_mapping.to_csv(private_mapping_csv, index=False)
    log_payload: dict[str, Any] = {
        "manifest_csv": str(manifest_csv),
        "private_mapping_csv": str(private_mapping_csv),
        "records": int(len(manifest)),
        "unique_patients": int(manifest["patient_uid"].nunique()) if "patient_uid" in manifest else 0,
    }
    (logs_dir / "privacy_index_run.json").write_text(
        json.dumps(log_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return PrivacyIndexResult(
        manifest_csv=manifest_csv,
        private_mapping_csv=private_mapping_csv,
        manifest=manifest,
        private_mapping=private_mapping,
    )
