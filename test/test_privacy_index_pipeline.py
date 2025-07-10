from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pandas as pd
import pytest

from pathodataforge.privacy_index import ensure_local_secret_key, pseudo_patient_uid, run_privacy_index_pipeline


ROOT = Path(__file__).parent
RAW_ROOT = ROOT / "synthetic_raw"
PROCESSED_ROOT = ROOT / "synthetic_processed"
SECRET = "unit-test-secret-key"


@pytest.fixture()
def privacy_result(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PATHOLOGY_DEID_SECRET_KEY", SECRET)
    if PROCESSED_ROOT.exists():
        shutil.rmtree(PROCESSED_ROOT)
    return run_privacy_index_pipeline(RAW_ROOT, PROCESSED_ROOT)


def test_deidentified_id_is_stable() -> None:
    first = pseudo_patient_uid("P001", SECRET)
    second = pseudo_patient_uid("P001", SECRET)
    assert first == second
    assert first.startswith("PSEUDO_")


def test_different_patients_have_different_ids() -> None:
    assert pseudo_patient_uid("P001", SECRET) != pseudo_patient_uid("P002", SECRET)


def test_gui_local_secret_is_created_and_reused(tmp_path: Path) -> None:
    secret_file = tmp_path / "deid_secret.key"
    first_key, first_path, created = ensure_local_secret_key(secret_file)
    second_key, second_path, reused = ensure_local_secret_key(secret_file)
    assert created is True
    assert reused is False
    assert first_path == second_path == secret_file
    assert first_key == second_key
    assert secret_file.exists()


def test_manifest_has_no_sensitive_fields(privacy_result) -> None:
    manifest = pd.read_csv(privacy_result.manifest_csv)
    forbidden = {
        "patient_name",
        "id_card",
        "phone",
        "birth_date",
        "real_patient_id",
        "hospital_id",
        "raw_pathology_id",
        "姓名",
        "身份证",
        "手机号",
        "出生日期",
        "真实患者ID",
        "医院原始ID",
    }
    assert forbidden.isdisjoint(set(manifest.columns))
    text = manifest.to_csv(index=False)
    for raw_value in ["Synthetic Alpha", "P001", "HOSP001", "ID000000000001", "13000000001"]:
        assert raw_value not in text


def test_wsi_checksum_is_generated(privacy_result) -> None:
    manifest = pd.read_csv(privacy_result.manifest_csv)
    assert manifest["checksum_sha256"].str.len().eq(64).all()
    for _, row in manifest.iterrows():
        digest = hashlib.sha256(Path(row["wsi_path"]).read_bytes()).hexdigest()
        assert digest == row["checksum_sha256"]


def test_multi_level_index_is_complete(privacy_result) -> None:
    manifest = pd.read_csv(privacy_result.manifest_csv)
    required = [
        "patient_uid",
        "case_uid",
        "slide_uid",
        "wsi_uid",
        "patch_uid",
        "annotation_uid",
    ]
    for column in required:
        assert column in manifest.columns
        assert manifest[column].fillna("").astype(str).str.len().gt(0).all()


def test_private_mapping_is_separated_from_public_manifest(privacy_result) -> None:
    manifest_text = Path(privacy_result.manifest_csv).read_text(encoding="utf-8")
    private_mapping = pd.read_csv(privacy_result.private_mapping_csv)
    assert "real_patient_id" in private_mapping.columns
    assert "patient_name" in private_mapping.columns
    assert "P001" in private_mapping["real_patient_id"].tolist()
    assert "P001" not in manifest_text
    assert "Synthetic Alpha" not in manifest_text


def test_gitignore_protects_private_files() -> None:
    gitignore = Path(".gitignore").read_text(encoding="utf-8")
    for pattern in [
        "test/synthetic_processed/mappings_private/",
        "*mapping*.csv",
        "*private*.csv",
        "*.key",
        ".env",
    ]:
        assert pattern in gitignore
