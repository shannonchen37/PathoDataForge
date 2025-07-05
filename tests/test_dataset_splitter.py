import pandas as pd

from pathodataforge.core.dataset_splitter import assign_splits, split_case_ids


def test_split_case_ids_is_deterministic() -> None:
    cases = [f"CASE{i:03d}" for i in range(10)]
    first = split_case_ids(cases, seed=123)
    second = split_case_ids(cases, seed=123)
    assert first == second
    assert set(first) == set(cases)


def test_assign_splits_keeps_case_in_single_split() -> None:
    metadata = pd.DataFrame(
        {
            "case_id": ["A", "A", "B", "B", "C", "D", "E"],
            "slide_id": ["s1", "s2", "s1", "s2", "s1", "s1", "s1"],
        }
    )
    result = assign_splits(metadata, seed=99)
    split_counts_per_case = result.groupby("case_id")["split"].nunique()
    assert split_counts_per_case.max() == 1
    assert set(result["split"]).issubset({"train", "val", "test"})
