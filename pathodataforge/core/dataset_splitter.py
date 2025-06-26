"""Case-level train/validation/test splitting."""

from __future__ import annotations

import random
from typing import Iterable

import pandas as pd


def split_case_ids(
    case_ids: Iterable[object],
    train: float = 0.7,
    val: float = 0.15,
    test: float = 0.15,
    seed: int = 42,
) -> dict[str, str]:
    """Split unique case IDs so a patient never appears in multiple splits."""
    unique_cases = sorted({str(case_id) for case_id in case_ids if str(case_id)})
    if not unique_cases:
        return {}

    total = train + val + test
    if total <= 0:
        raise ValueError("Split ratios must sum to a positive value")
    train_ratio = train / total
    val_ratio = val / total
    test_ratio = test / total

    rng = random.Random(seed)
    rng.shuffle(unique_cases)

    n_cases = len(unique_cases)
    if n_cases == 1:
        counts = {"train": 1, "val": 0, "test": 0}
    elif n_cases == 2:
        counts = {"train": 1, "val": 0, "test": 1 if test_ratio > 0 else 0}
        if counts["test"] == 0:
            counts["val"] = 1
    else:
        n_train = max(1, int(round(n_cases * train_ratio)))
        n_val = int(round(n_cases * val_ratio))
        n_test = n_cases - n_train - n_val

        if val_ratio > 0 and n_val == 0:
            n_val = 1
            n_train = max(1, n_train - 1)
        if test_ratio > 0 and n_test == 0:
            if n_train > 1:
                n_train -= 1
            elif n_val > 1:
                n_val -= 1
            n_test = 1
        while n_train + n_val + n_test > n_cases:
            if n_train >= n_val and n_train > 1:
                n_train -= 1
            elif n_val > 0:
                n_val -= 1
            else:
                n_test -= 1
        while n_train + n_val + n_test < n_cases:
            n_train += 1
        counts = {"train": n_train, "val": n_val, "test": n_test}

    split_map: dict[str, str] = {}
    offset = 0
    for split_name in ("train", "val", "test"):
        for case_id in unique_cases[offset : offset + counts[split_name]]:
            split_map[case_id] = split_name
        offset += counts[split_name]
    return split_map


def assign_splits(
    metadata: pd.DataFrame,
    train: float = 0.7,
    val: float = 0.15,
    test: float = 0.15,
    seed: int = 42,
) -> pd.DataFrame:
    if "case_id" not in metadata.columns:
        raise ValueError("metadata must contain a case_id column")
    split_map = split_case_ids(metadata["case_id"], train, val, test, seed)
    result = metadata.copy()
    result["split"] = result["case_id"].astype(str).map(split_map).fillna("train")
    return result
