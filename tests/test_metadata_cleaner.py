from pathlib import Path

import pandas as pd

from pathodataforge.core.anonymizer import generate_anonymized_filename
from pathodataforge.core.metadata_cleaner import clean_metadata
from pathodataforge.core.metadata_cleaner import infer_case_id_from_filename


def test_metadata_matching_and_anonymized_mapping(tmp_path: Path) -> None:
    wsi_dir = tmp_path / "wsi"
    wsi_dir.mkdir()
    files = [
        wsi_dir / "CASE001_slide_a.png",
        wsi_dir / "CASE002_slide_b.tiff",
        wsi_dir / "UNKNOWN_slide_c.png",
    ]
    for path in files:
        path.touch()

    metadata_path = tmp_path / "metadata.csv"
    pd.DataFrame(
        [
            {"case_id": "CASE001", "label": "tumor"},
            {"case_id": "CASE002", "label": "normal"},
        ]
    ).to_csv(metadata_path, index=False)

    result = clean_metadata(files, metadata_path, "case_id", "label")

    assert result.matched_count == 2
    assert result.unmatched_count == 1
    assert list(result.metadata["status"]) == ["matched", "matched", "unmatched"]
    assert result.mapping.loc[0, "anonymized_filename"] == "patient_000001_slide_0001.png"
    assert set(result.metadata.columns) >= {"case_id", "slide_id", "label", "source_path"}


def test_generate_anonymized_filename_preserves_suffix() -> None:
    name = generate_anonymized_filename(7, 3, "raw_slide.SVS")
    assert name == "patient_000007_slide_0003.svs"


def test_infer_tcga_case_id_from_filename() -> None:
    case_id = infer_case_id_from_filename("TCGA-AB-1234-01Z-00-DX1.abcdef.svs")
    assert case_id == "TCGA-AB-1234"
