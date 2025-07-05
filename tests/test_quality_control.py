import cv2
import numpy as np
from PIL import Image

from pathodataforge.core.quality_control import evaluate_patch


def test_quality_control_discards_blank_patch() -> None:
    image = Image.new("RGB", (256, 256), "white")
    quality = evaluate_patch(image, tissue_threshold=0.5, blur_threshold=80.0)
    assert not quality.keep
    assert "low_tissue" in quality.discard_reason


def test_quality_control_keeps_textured_tissue_patch() -> None:
    rng = np.random.default_rng(123)
    image = np.zeros((256, 256, 3), dtype=np.uint8)
    image[:, :] = (185, 105, 180)
    noise = rng.normal(0, 35, image.shape).astype(np.int16)
    image = np.clip(image.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    for y in range(12, 256, 24):
        cv2.line(image, (0, y), (255, 255 - y), (90, 35, 130), 2)

    quality = evaluate_patch(
        Image.fromarray(image, "RGB"),
        tissue_threshold=0.5,
        blur_threshold=80.0,
        brightness_min=30,
        brightness_max=230,
    )
    assert quality.keep
    assert quality.tissue_ratio > 0.5
    assert quality.blur_score > 80.0
