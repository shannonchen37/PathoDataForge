"""Patch-level quality control."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from pathodataforge.core.tissue_detector import tissue_ratio_from_patch


@dataclass(slots=True)
class PatchQuality:
    tissue_ratio: float
    blur_score: float
    mean_brightness: float
    keep: bool
    discard_reason: str


def laplacian_variance(image: Image.Image) -> float:
    rgb = np.asarray(image.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def mean_brightness(image: Image.Image) -> float:
    rgb = np.asarray(image.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    return float(np.mean(gray))


def evaluate_patch(
    image: Image.Image,
    tissue_threshold: float = 0.5,
    blur_threshold: float = 80.0,
    brightness_min: float = 30,
    brightness_max: float = 230,
) -> PatchQuality:
    tissue_ratio = tissue_ratio_from_patch(image)
    blur_score = laplacian_variance(image)
    brightness = mean_brightness(image)

    reasons: list[str] = []
    if tissue_ratio < tissue_threshold:
        reasons.append("low_tissue")
    if blur_score < blur_threshold:
        reasons.append("blur")
    if brightness < brightness_min:
        reasons.append("too_dark")
    if brightness > brightness_max:
        reasons.append("too_bright")

    return PatchQuality(
        tissue_ratio=tissue_ratio,
        blur_score=blur_score,
        mean_brightness=brightness,
        keep=not reasons,
        discard_reason=";".join(reasons),
    )
