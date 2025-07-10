"""HMAC-based de-identification helpers."""

from __future__ import annotations

import hmac
import os
import secrets
from hashlib import sha256
from pathlib import Path


SECRET_ENV_VAR = "PATHOLOGY_DEID_SECRET_KEY"
TEST_SECRET_KEY = "pathodataforge-synthetic-test-key"
LOCAL_SECRET_ENV_VAR = "PATHODATAFORGE_DEID_SECRET_FILE"
LOCAL_SECRET_PATH = Path.home() / ".pathodataforge" / "deid_secret.key"


def local_secret_path(secret_file: str | Path | None = None) -> Path:
    if secret_file:
        return Path(secret_file).expanduser()
    env_path = os.environ.get(LOCAL_SECRET_ENV_VAR)
    if env_path:
        return Path(env_path).expanduser()
    return LOCAL_SECRET_PATH


def ensure_local_secret_key(secret_file: str | Path | None = None) -> tuple[bytes, Path, bool]:
    """Load or create a machine-local de-identification key for the GUI."""
    path = local_secret_path(secret_file)
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value.encode("utf-8"), path, False
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    value = secrets.token_urlsafe(48)
    path.write_text(value, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return value.encode("utf-8"), path, True


def get_secret_key(
    secret_key: str | bytes | None = None,
    *,
    test_mode: bool = False,
    env_var: str = SECRET_ENV_VAR,
) -> bytes:
    """Return a secret key without hard-coding production secrets."""
    if secret_key:
        return secret_key if isinstance(secret_key, bytes) else secret_key.encode("utf-8")
    env_value = os.environ.get(env_var)
    if env_value:
        return env_value.encode("utf-8")
    if test_mode:
        return TEST_SECRET_KEY.encode("utf-8")
    raise RuntimeError(f"请先设置环境变量 {env_var}，再生成正式脱敏索引。")


def hmac_sha256(value: str, secret_key: str | bytes | None = None, *, test_mode: bool = False) -> str:
    key = get_secret_key(secret_key, test_mode=test_mode)
    return hmac.new(key, str(value).encode("utf-8"), sha256).hexdigest()


def pseudo_patient_uid(
    real_patient_id: str,
    secret_key: str | bytes | None = None,
    *,
    test_mode: bool = False,
    length: int = 12,
) -> str:
    digest = hmac_sha256(str(real_patient_id), secret_key, test_mode=test_mode)
    return f"PSEUDO_{digest[:length]}"


def make_uid(
    prefix: str,
    *parts: object,
    secret_key: str | bytes | None = None,
    test_mode: bool = False,
    length: int = 12,
) -> str:
    payload = "|".join(str(part) for part in parts if str(part) != "")
    digest = hmac_sha256(payload, secret_key, test_mode=test_mode)
    return f"{prefix}_{digest[:length]}"
