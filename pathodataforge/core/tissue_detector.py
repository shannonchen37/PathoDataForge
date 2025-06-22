"""Tissue mask and region-ratio helpers."""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image


def pil_to_rgb_array(image: Image.Image) -> np.ndarray:
    return np.asarray(image.convert("RGB"))


def create_tissue_mask(
    thumbnail: Image.Image,
    saturation_threshold: int = 20,
    value_threshold: int = 235,
) -> np.ndarray:
    """Create a low-resolution binary tissue mask from a thumbnail."""
    rgb = pil_to_rgb_array(thumbnail)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]

    _, otsu_sat = cv2.threshold(
        saturation,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU,
    )
    mask = ((saturation > saturation_threshold) | (otsu_sat > 0)) & (value < value_threshold)
    mask_uint8 = mask.astype(np.uint8) * 255
    kernel = np.ones((5, 5), np.uint8)
    mask_uint8 = cv2.morphologyEx(mask_uint8, cv2.MORPH_OPEN, kernel)
    mask_uint8 = cv2.morphologyEx(mask_uint8, cv2.MORPH_CLOSE, kernel)
    return mask_uint8 > 0


def tissue_ratio_from_patch(
    image: Image.Image,
    saturation_threshold: int = 20,
    value_threshold: int = 235,
) -> float:
    rgb = pil_to_rgb_array(image)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    tissue = (saturation > saturation_threshold) & (value < value_threshold)
    return float(np.mean(tissue))


def mask_region_ratio(
    mask: np.ndarray,
    x: int,
    y: int,
    patch_size: int,
    level_dimensions: tuple[int, int],
) -> float:
    """Estimate tissue ratio for a level-space patch from the thumbnail mask."""
    if mask.size == 0:
        return 0.0

    level_width, level_height = level_dimensions
    mask_height, mask_width = mask.shape[:2]
    if level_width <= 0 or level_height <= 0:
        return 0.0

    x0 = int(np.floor(x * mask_width / level_width))
    y0 = int(np.floor(y * mask_height / level_height))
    x1 = int(np.ceil((x + patch_size) * mask_width / level_width))
    y1 = int(np.ceil((y + patch_size) * mask_height / level_height))

    x0 = max(0, min(mask_width, x0))
    y0 = max(0, min(mask_height, y0))
    x1 = max(0, min(mask_width, x1))
    y1 = max(0, min(mask_height, y1))
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return float(np.mean(mask[y0:y1, x0:x1]))
