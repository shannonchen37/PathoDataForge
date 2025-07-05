"""Generate demo pathology-like images and metadata."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import yaml
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "demo_data"
WSI_DIR = DEMO_DIR / "wsi"


def _draw_tissue(seed: int, width: int = 2048, height: int = 1536) -> np.ndarray:
    rng = np.random.default_rng(seed)
    image = np.full((height, width, 3), 248, dtype=np.uint8)
    mask = np.zeros((height, width), dtype=np.uint8)

    centers = [
        (width // 2, height // 2),
        (width // 2 - 260, height // 2 + 110),
        (width // 2 + 280, height // 2 - 130),
    ]
    colors = [
        (204, 150, 210),
        (222, 170, 198),
        (184, 118, 192),
    ]
    for index, center in enumerate(centers):
        axes = (
            int(rng.integers(width // 5, width // 3)),
            int(rng.integers(height // 5, height // 3)),
        )
        angle = float(rng.integers(0, 180))
        cv2.ellipse(mask, center, axes, angle, 0, 360, 255, -1)
        cv2.ellipse(image, center, axes, angle, 0, 360, colors[index], -1)

    noise = rng.normal(0, 28, image.shape).astype(np.int16)
    tissue_pixels = mask > 0
    textured = np.clip(image.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    image[tissue_pixels] = textured[tissue_pixels]

    for _ in range(5000):
        x = int(rng.integers(80, width - 80))
        y = int(rng.integers(80, height - 80))
        if mask[y, x] == 0:
            continue
        radius = int(rng.integers(1, 4))
        color = (
            int(rng.integers(95, 145)),
            int(rng.integers(45, 95)),
            int(rng.integers(120, 180)),
        )
        cv2.circle(image, (x, y), radius, color, -1)

    for _ in range(45):
        x0 = int(rng.integers(120, width - 120))
        y0 = int(rng.integers(120, height - 120))
        x1 = min(width - 1, max(0, x0 + int(rng.integers(-160, 160))))
        y1 = min(height - 1, max(0, y0 + int(rng.integers(-160, 160))))
        if mask[y0, x0] > 0:
            cv2.line(image, (x0, y0), (x1, y1), (150, 80, 160), 2)

    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def generate_demo_data() -> None:
    WSI_DIR.mkdir(parents=True, exist_ok=True)

    slides = [
        ("CASE001", "adenocarcinoma", "CASE001_slide_01.png"),
        ("CASE001", "adenocarcinoma", "CASE001_slide_02.tiff"),
        ("CASE002", "benign", "CASE002_slide_01.png"),
        ("CASE003", "squamous", "CASE003_slide_01.tiff"),
    ]
    for index, (_, _, filename) in enumerate(slides, start=1):
        image = Image.fromarray(_draw_tissue(seed=2024 + index))
        image.save(WSI_DIR / filename)

    metadata = pd.DataFrame(
        [
            {"case_id": "CASE001", "label": "adenocarcinoma", "age": 61},
            {"case_id": "CASE002", "label": "benign", "age": 54},
            {"case_id": "CASE003", "label": "squamous", "age": 67},
        ]
    )
    metadata.to_csv(DEMO_DIR / "metadata.csv", index=False)

    demo_config = {
        "input": {
            "wsi_dir": str(WSI_DIR.relative_to(ROOT)),
            "metadata_file": str((DEMO_DIR / "metadata.csv").relative_to(ROOT)),
            "output_dir": "./PathoDataForge_output",
        },
        "metadata": {
            "case_id_column": "case_id",
            "label_column": "label",
            "filename_column": "",
        },
        "patch": {
            "patch_size": 512,
            "stride": 512,
            "level": 0,
            "max_patches_per_slide": 120,
            "sampling_mode": "dense",
            "num_sample": 120,
            "max_trials": 10000,
            "min_fg_ratio": 0.25,
            "use_bg_mask": True,
        },
        "quality": {
            "tissue_threshold": 0.5,
            "blur_threshold": 80.0,
            "brightness_min": 30,
            "brightness_max": 230,
        },
        "split": {
            "train": 0.7,
            "val": 0.15,
            "test": 0.15,
            "seed": 42,
        },
        "coordinates": {
            "enable": True,
            "format": "range_level0",
        },
        "visualization": {
            "save_overlay": True,
            "display_overlay": True,
            "downsample": 16,
            "outline_rgb": [37, 99, 235],
            "outline_width": 1,
            "style": "points",
            "show_tissue_mask": True,
            "max_box_count": 350,
            "jpeg_quality": 90,
        },
        "features": {
            "enable": True,
            "model_name": "ResNet50",
            "batch_size": 8,
            "num_workers": 0,
            "device": "auto",
            "precision": "auto",
            "hf_token": "",
            "overwrite": False,
        },
        "runtime": {
            "cpu_workers": 1,
            "gpu_workers": 1,
            "queue_maxsize": 8,
            "target_files": [],
        },
    }
    config_path = ROOT / "configs" / "demo.yaml"
    with config_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(demo_config, handle, sort_keys=False, allow_unicode=True)

    print(f"Demo WSI images: {WSI_DIR}")
    print(f"Demo metadata: {DEMO_DIR / 'metadata.csv'}")
    print(f"Demo config: {config_path}")


if __name__ == "__main__":
    generate_demo_data()
