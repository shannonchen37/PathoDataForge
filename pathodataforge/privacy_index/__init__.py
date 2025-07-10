"""Privacy-preserving multi-dimensional WSI index utilities."""

from pathodataforge.privacy_index.anonymizer import ensure_local_secret_key, make_uid, pseudo_patient_uid
from pathodataforge.privacy_index.checksum import sha256_file
from pathodataforge.privacy_index.pipeline import PrivacyIndexResult
from pathodataforge.privacy_index.pipeline import run_privacy_index_dataframe
from pathodataforge.privacy_index.pipeline import run_privacy_index_pipeline

__all__ = [
    "PrivacyIndexResult",
    "ensure_local_secret_key",
    "make_uid",
    "pseudo_patient_uid",
    "run_privacy_index_dataframe",
    "run_privacy_index_pipeline",
    "sha256_file",
]
