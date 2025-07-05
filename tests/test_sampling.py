from pathlib import Path

import numpy as np
from PIL import Image

from pathodataforge.core.patch_extractor import extract_patches_for_slide
from pathodataforge.core.sampling import sample_slide_coordinates
from pathodataforge.core.wsi_reader import WSIReader


def test_sample_slide_coordinates_outputs_level0_ranges(tmp_path: Path) -> None:
    image_path = tmp_path / "CASE001_slide.png"
    image = np.full((768, 1024, 3), 245, dtype=np.uint8)
    image[128:640, 256:768] = (180, 90, 170)
    Image.fromarray(image, "RGB").save(image_path)

    row = {
        "case_id": "CASE001",
        "slide_id": "slide_0001",
        "source_path": str(image_path),
    }
    coords = sample_slide_coordinates(
        source_path=image_path,
        patch_config={
            "patch_size": 256,
            "stride": 256,
            "level": 0,
            "max_patches_per_slide": 10,
            "sampling_mode": "dense",
            "min_fg_ratio": 0.1,
            "use_bg_mask": True,
        },
        output_root=tmp_path / "out",
        row=row,
        visualization_config={"save_overlay": True, "downsample": 8},
    )

    assert coords.ranges_level0.ndim == 2
    assert coords.ranges_level0.shape[1] == 4
    assert np.all(coords.ranges_level0[:, 2] > coords.ranges_level0[:, 0])
    assert np.all(coords.ranges_level0[:, 3] > coords.ranges_level0[:, 1])
    assert (tmp_path / "out" / "metadata" / "coordinates").exists()
    assert (tmp_path / "out" / "reports" / "overlays").exists()


def test_dense_sampling_uses_non_overlapping_grid_even_when_stride_is_smaller(tmp_path: Path) -> None:
    image_path = tmp_path / "CASE002_slide.png"
    image = np.full((768, 768, 3), (180, 90, 170), dtype=np.uint8)
    Image.fromarray(image, "RGB").save(image_path)

    coords = sample_slide_coordinates(
        source_path=image_path,
        patch_config={
            "patch_size": 256,
            "stride": 128,
            "level": 0,
            "max_patches_per_slide": 20,
            "sampling_mode": "dense",
            "min_fg_ratio": 0.0,
            "use_bg_mask": False,
        },
        output_root=tmp_path / "out_dense",
        row={"case_id": "CASE002", "slide_id": "slide_0001", "source_path": str(image_path)},
    )

    ranges = coords.ranges_level0
    assert len(ranges) == 9
    assert np.all((ranges[:, 2] - ranges[:, 0]) == 256)
    assert np.all((ranges[:, 3] - ranges[:, 1]) == 256)
    for index, first in enumerate(ranges):
        for second in ranges[index + 1 :]:
            x_overlap = max(0, min(first[2], second[2]) - max(first[0], second[0]))
            y_overlap = max(0, min(first[3], second[3]) - max(first[1], second[1]))
            assert x_overlap * y_overlap == 0


def test_random_sampling_selects_from_foreground_dense_candidates(tmp_path: Path) -> None:
    image_path = tmp_path / "CASE003_slide.png"
    image = np.full((512, 1024, 3), 245, dtype=np.uint8)
    image[0:512, 256:768] = (180, 90, 170)
    Image.fromarray(image, "RGB").save(image_path)

    coords = sample_slide_coordinates(
        source_path=image_path,
        patch_config={
            "patch_size": 256,
            "stride": 256,
            "level": 0,
            "max_patches_per_slide": 3,
            "num_sample": 3,
            "sampling_mode": "random_tissue",
            "min_fg_ratio": 0.5,
            "use_bg_mask": True,
            "seed": 7,
        },
        output_root=tmp_path / "out_random",
        row={"case_id": "CASE003", "slide_id": "slide_0001", "source_path": str(image_path)},
    )

    ranges = coords.ranges_level0
    assert 0 < len(ranges) <= 3
    assert np.all(ranges[:, 0] % 256 == 0)
    assert np.all(ranges[:, 1] % 256 == 0)
    assert np.all(ranges[:, 0] >= 256)
    assert np.all(ranges[:, 2] <= 768)


def test_dense_sampling_ignores_patch_count_and_returns_all_candidates(tmp_path: Path) -> None:
    image_path = tmp_path / "CASE004_slide.png"
    image = np.full((1024, 1024, 3), (180, 90, 170), dtype=np.uint8)
    Image.fromarray(image, "RGB").save(image_path)

    coords = sample_slide_coordinates(
        source_path=image_path,
        patch_config={
            "patch_size": 256,
            "stride": 256,
            "level": 0,
            "max_patches_per_slide": 4,
            "sampling_mode": "dense",
            "min_fg_ratio": 0.0,
            "use_bg_mask": False,
        },
        output_root=tmp_path / "out_dense_limited",
        row={"case_id": "CASE004", "slide_id": "slide_0001", "source_path": str(image_path)},
    )

    ranges = coords.ranges_level0
    assert len(ranges) == 16
    assert len(set(ranges[:, 1].tolist())) > 1
    assert ranges[:, 1].max() > 0


def test_coordinate_cache_requires_matching_sampling_signature(tmp_path: Path) -> None:
    image_path = tmp_path / "CASE005_slide.png"
    image = np.full((768, 768, 3), (180, 90, 170), dtype=np.uint8)
    Image.fromarray(image, "RGB").save(image_path)
    row = {"case_id": "CASE005", "slide_id": "slide_0001", "source_path": str(image_path)}
    config = {
        "patch_size": 256,
        "stride": 256,
        "level": 0,
        "max_patches_per_slide": 9,
        "sampling_mode": "dense",
        "min_fg_ratio": 0.0,
        "use_bg_mask": False,
    }

    first = sample_slide_coordinates(image_path, config, tmp_path / "out_cache", row)
    second = sample_slide_coordinates(image_path, config, tmp_path / "out_cache", row)
    changed = sample_slide_coordinates(
        image_path,
        {**config, "stride": 512},
        tmp_path / "out_cache",
        row,
    )

    assert first.from_cache is False
    assert second.from_cache is True
    assert changed.from_cache is False
    assert changed.ranges_level0.shape[0] == 4


def test_dense_patch_extraction_keeps_all_coordinate_candidates(tmp_path: Path) -> None:
    image_path = tmp_path / "CASE006_slide.png"
    image = np.zeros((512, 512, 3), dtype=np.uint8)
    image[:, :, 0] = np.arange(512, dtype=np.uint16)[None, :] % 255
    image[:, :, 1] = 90
    image[:, :, 2] = np.arange(512, dtype=np.uint16)[:, None] % 255
    Image.fromarray(image.astype(np.uint8), "RGB").save(image_path)
    row = {"case_id": "CASE006", "slide_id": "slide_0001", "source_path": str(image_path), "label": "A"}
    coords = sample_slide_coordinates(
        image_path,
        {
            "patch_size": 256,
            "stride": 256,
            "level": 0,
            "max_patches_per_slide": 1,
            "sampling_mode": "dense",
            "min_fg_ratio": 0.0,
            "use_bg_mask": False,
        },
        tmp_path / "out_extract",
        row,
    )

    with WSIReader(image_path) as reader:
        records, summary = extract_patches_for_slide(
            reader,
            row,
            tmp_path / "out_extract",
            {
                "patch_size": 256,
                "stride": 256,
                "level": 0,
                "max_patches_per_slide": 1,
                "sampling_mode": "dense",
            },
            {
                "tissue_threshold": 0.0,
                "blur_threshold": -1.0,
                "brightness_min": 0,
                "brightness_max": 255,
            },
            coordinate_ranges_level0=coords.ranges_level0,
        )

    kept = [record for record in records if record["keep"]]
    assert coords.ranges_level0.shape[0] == 4
    assert len(kept) == 4
    assert summary["kept_patches"] == 4
