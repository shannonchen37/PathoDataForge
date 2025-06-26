"""Coordinate sampling and WSI overlay visualization."""

from __future__ import annotations

import math
import json
import random
from hashlib import sha256
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

from pathodataforge.core.patch_extractor import select_level
from pathodataforge.core.tissue_detector import create_tissue_mask, mask_region_ratio
from pathodataforge.core.wsi_reader import WSIReader
from pathodataforge.utils.io import atomic_save_npy, safe_load_npy


@dataclass(slots=True)
class CoordinateSet:
    level: int
    patch_size: int
    level_downsample: float
    ranges_level0: np.ndarray
    table: pd.DataFrame
    from_cache: bool = False


def slide_id_token(row: pd.Series | dict[str, Any]) -> str:
    case_id = str(row.get("case_id", "case")).replace("/", "_")
    slide_id = str(row.get("slide_id", "slide")).replace("/", "_")
    original = Path(str(row.get("source_path", row.get("original_filename", "")))).stem
    return f"{case_id}_{slide_id}_{original}"


def coordinate_paths(
    output_root: str | Path,
    row: pd.Series | dict[str, Any],
) -> dict[str, Path]:
    root = Path(output_root)
    token = slide_id_token(row)
    return {
        "npy": root / "metadata" / "coordinates" / f"{token}_coors.npy",
        "csv": root / "metadata" / "coordinates" / f"{token}_coors.csv",
        "meta": root / "metadata" / "coordinates" / f"{token}_coors.meta.json",
        "overlay": root / "reports" / "overlays" / f"{token}_sampled_overlay.jpg",
    }


def _coordinate_cache_signature(patch_config: dict[str, Any]) -> str:
    mode = str(patch_config.get("sampling_mode", "dense")).lower().replace("-", "_")
    patch_size = int(patch_config.get("patch_size", 512))
    payload = {
        "algorithm": "foreground_dense_nonoverlap_all_v3",
        "patch_size": patch_size,
        "stride": max(patch_size, int(patch_config.get("stride", patch_size))),
        "level": str(patch_config.get("level", 0)),
        "sampling_mode": mode,
        "max_patches_per_slide": "all" if mode == "dense" else int(patch_config.get("max_patches_per_slide", 2000)),
        "num_sample": "all" if mode == "dense" else int(patch_config.get("num_sample", patch_config.get("max_patches_per_slide", 2000))),
        "max_trials": "all" if mode == "dense" else int(patch_config.get("max_trials", 100000)),
        "min_fg_ratio": round(float(patch_config.get("min_fg_ratio", 0.25)), 6),
        "use_bg_mask": bool(patch_config.get("use_bg_mask", True)),
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return sha256(encoded).hexdigest()


def _cache_signature_matches(meta_path: Path, patch_config: dict[str, Any]) -> bool:
    if not meta_path.exists():
        return False
    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return str(payload.get("signature", "")) == _coordinate_cache_signature(patch_config)


def ranges_level0_to_level_xy(
    ranges_level0: np.ndarray,
    downsample: float,
) -> list[tuple[int, int]]:
    coords: list[tuple[int, int]] = []
    for x0, y0, _, _ in ranges_level0.astype(np.int64):
        coords.append((int(round(x0 / downsample)), int(round(y0 / downsample))))
    return coords


def _grid_positions(length: int, patch_size: int, stride: int | None = None) -> list[int]:
    if length < patch_size:
        return []
    step = max(patch_size, int(stride or patch_size))
    return list(range(0, length - patch_size + 1, step))


def _candidate_level_coords(
    level_width: int,
    level_height: int,
    patch_size: int,
    stride: int,
    mode: str,
    num_sample: int,
    seed: int,
    max_trials: int,
) -> list[tuple[int, int]]:
    if level_width < patch_size or level_height < patch_size:
        return []

    mode = mode.lower().replace("-", "_")
    if mode == "random_tissue":
        mode = "random"
    if mode == "top_quality":
        mode = "dense"
    if mode == "dense":
        return [
            (x, y)
            for y in _grid_positions(level_height, patch_size, max(stride, patch_size))
            for x in _grid_positions(level_width, patch_size, max(stride, patch_size))
        ]

    if mode != "random":
        raise ValueError(f"Unsupported sampling_mode: {mode}")

    rng = random.Random(seed)
    seen: set[tuple[int, int]] = set()
    picked: list[tuple[int, int]] = []
    x_max = level_width - patch_size
    y_max = level_height - patch_size
    trials = 0
    while len(picked) < num_sample and trials < max_trials:
        trials += 1
        coord = (rng.randint(0, x_max), rng.randint(0, y_max))
        if coord not in seen:
            seen.add(coord)
            picked.append(coord)
    return picked


def _foreground_dense_candidates(
    level_width: int,
    level_height: int,
    patch_size: int,
    stride: int,
    mask: np.ndarray | None,
    min_fg_ratio: float,
) -> list[tuple[float, int, int]]:
    """Return non-overlapping dense candidates that pass the tissue mask."""
    candidates: list[tuple[float, int, int]] = []
    for y in _grid_positions(level_height, patch_size, max(stride, patch_size)):
        for x in _grid_positions(level_width, patch_size, max(stride, patch_size)):
            ratio = 1.0
            if mask is not None:
                ratio = mask_region_ratio(mask, x, y, patch_size, (level_width, level_height))
                if ratio < min_fg_ratio:
                    continue
            candidates.append((ratio, x, y))
    return candidates


def _random_foreground_ranges(
    level_width: int,
    level_height: int,
    patch_size: int,
    downsample: float,
    n_tiles: int,
    seed: int,
    max_trials: int,
    mask: np.ndarray | None,
    min_fg_ratio: float,
) -> list[tuple[int, int, int, int]]:
    if level_width < patch_size or level_height < patch_size or n_tiles <= 0:
        return []

    rng = random.Random(seed)
    x_max = level_width - patch_size
    y_max = level_height - patch_size
    seen: set[tuple[int, int]] = set()
    ranges: list[tuple[int, int, int, int]] = []
    trials = 0
    while len(ranges) < n_tiles and trials < max_trials:
        trials += 1
        x = rng.randint(0, x_max)
        y = rng.randint(0, y_max)
        if (x, y) in seen:
            continue
        seen.add((x, y))
        if mask is not None:
            ratio = mask_region_ratio(mask, x, y, patch_size, (level_width, level_height))
            if ratio < min_fg_ratio:
                continue
        ranges.append(_range_level0(x, y, patch_size, downsample))
    return ranges


def _range_level0(x: int, y: int, patch_size: int, downsample: float) -> tuple[int, int, int, int]:
    x0 = int(round(x * downsample))
    y0 = int(round(y * downsample))
    edge = int(round(patch_size * downsample))
    return x0, y0, x0 + edge, y0 + edge


def _coordinate_table(
    ranges_level0: np.ndarray,
    level: int,
    patch_size: int,
    downsample: float,
) -> pd.DataFrame:
    if ranges_level0.size == 0:
        return pd.DataFrame(
            columns=[
                "x0_level0",
                "y0_level0",
                "x1_level0",
                "y1_level0",
                "x_center_level0",
                "y_center_level0",
                "x_level",
                "y_level",
                "level",
                "patch_size",
                "coordinate_format",
            ]
        )
    table = pd.DataFrame(
        ranges_level0,
        columns=["x0_level0", "y0_level0", "x1_level0", "y1_level0"],
    )
    table["x_center_level0"] = ((table["x0_level0"] + table["x1_level0"]) / 2).round().astype(int)
    table["y_center_level0"] = ((table["y0_level0"] + table["y1_level0"]) / 2).round().astype(int)
    table["x_level"] = (table["x0_level0"] / downsample).round().astype(int)
    table["y_level"] = (table["y0_level0"] / downsample).round().astype(int)
    table["level"] = level
    table["patch_size"] = patch_size
    table["coordinate_format"] = "range_level0"
    return table


def sample_slide_coordinates(
    source_path: str | Path,
    patch_config: dict[str, Any],
    output_root: str | Path,
    row: pd.Series | dict[str, Any],
    visualization_config: dict[str, Any] | None = None,
    force: bool = False,
) -> CoordinateSet:
    """Sample coordinates and cache them as Nx4 level-0 patch ranges."""
    paths = coordinate_paths(output_root, row)
    cached = None
    if not force and _cache_signature_matches(paths["meta"], patch_config):
        cached = safe_load_npy(paths["npy"])
    if cached is not None:
        level = int(patch_config.get("level", 0)) if not str(patch_config.get("level", "")).endswith("x") else 0
        with WSIReader(source_path) as reader:
            info = reader.info()
            level = select_level(info, patch_config.get("level", 0))
            downsample = info.level_downsamples[level]
        patch_size = int(patch_config.get("patch_size", 512))
        table = _coordinate_table(cached.astype(np.int64), level, patch_size, downsample)
        return CoordinateSet(level, patch_size, downsample, cached.astype(np.int64), table, True)

    with WSIReader(source_path) as reader:
        info = reader.info()
        level = select_level(info, patch_config.get("level", 0))
        level_width, level_height = info.level_dimensions[level]
        downsample = info.level_downsamples[level]
        patch_size = int(patch_config.get("patch_size", 512))
        stride = max(patch_size, int(patch_config.get("stride", patch_size)))
        mode = str(patch_config.get("sampling_mode", "dense")).lower().replace("-", "_")
        num_sample = int(patch_config.get("num_sample", patch_config.get("max_patches_per_slide", 2000)))
        max_trials = int(patch_config.get("max_trials", 100000))
        seed = int(patch_config.get("seed", 42))
        min_fg_ratio = float(patch_config.get("min_fg_ratio", 0.25))
        use_bg_mask = bool(patch_config.get("use_bg_mask", True))
        max_patches = int(patch_config.get("max_patches_per_slide", 2000))

        mask = None
        if use_bg_mask:
            mask = create_tissue_mask(reader.thumbnail((1024, 1024)))

        dense_candidates = _foreground_dense_candidates(
            level_width=level_width,
            level_height=level_height,
            patch_size=patch_size,
            stride=stride,
            mask=mask,
            min_fg_ratio=min_fg_ratio,
        )

        if mode in {"random", "random_tissue", "random"}:
            rng = random.Random(seed)
            shuffled = list(dense_candidates)
            rng.shuffle(shuffled)
            ranges = [
                _range_level0(x, y, patch_size, downsample)
                for _, x, y in shuffled[: min(num_sample, max_patches)]
            ]
        else:
            if mode == "top_quality":
                dense_candidates.sort(reverse=True)
                selected_candidates = dense_candidates[:max_patches]
            else:
                selected_candidates = dense_candidates
            ranges = []
            for _, x, y in selected_candidates:
                ranges.append(_range_level0(x, y, patch_size, downsample))

        ranges_array = np.asarray(ranges, dtype=np.int64).reshape((-1, 4))
        paths["npy"].parent.mkdir(parents=True, exist_ok=True)
        atomic_save_npy(ranges_array, paths["npy"])
        table = _coordinate_table(ranges_array, level, patch_size, downsample)
        paths["csv"].parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(paths["csv"], index=False)
        paths["meta"].write_text(
            json.dumps(
                {
                    "signature": _coordinate_cache_signature(patch_config),
                    "coordinate_format": "range_level0",
                    "algorithm": "foreground_dense_nonoverlap_all_v3",
                    "n_coordinates": int(ranges_array.shape[0]),
                    "level": int(level),
                    "patch_size": int(patch_size),
                    "level_downsample": float(downsample),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        vis_cfg = visualization_config or {}
        if bool(vis_cfg.get("save_overlay", False)):
            overlay = build_sampling_overlay(
                reader,
                ranges_array,
                downsample_factor=int(vis_cfg.get("downsample", 32)),
                outline_rgb=tuple(vis_cfg.get("outline_rgb", [37, 99, 235])),
                outline_width=int(vis_cfg.get("outline_width", 1)),
                style=str(vis_cfg.get("style", "points")),
                show_tissue_mask=bool(vis_cfg.get("show_tissue_mask", True)),
                max_box_count=int(vis_cfg.get("max_box_count", 350)),
            )
            paths["overlay"].parent.mkdir(parents=True, exist_ok=True)
            overlay.save(paths["overlay"], quality=int(vis_cfg.get("jpeg_quality", 90)))

        return CoordinateSet(level, patch_size, downsample, ranges_array, table, False)


def build_sampling_overlay(
    reader: WSIReader,
    ranges_level0: np.ndarray,
    downsample_factor: int = 32,
    outline_rgb: tuple[int, int, int] = (37, 99, 235),
    outline_width: int = 1,
    style: str = "points",
    show_tissue_mask: bool = True,
    max_box_count: int = 350,
) -> Image.Image:
    info = reader.info()
    thumb_size = (
        max(1, int(math.ceil(info.width / max(1, downsample_factor)))),
        max(1, int(math.ceil(info.height / max(1, downsample_factor)))),
    )
    thumb = reader.thumbnail(thumb_size).convert("RGB")
    composed = thumb.convert("RGBA")
    sx = thumb.width / float(info.width)
    sy = thumb.height / float(info.height)

    if show_tissue_mask:
        mask = create_tissue_mask(thumb)
        alpha = Image.fromarray((mask.astype(np.uint8) * 42), mode="L")
        tissue_layer = Image.new("RGBA", thumb.size, (22, 163, 74, 0))
        tissue_layer.putalpha(alpha)
        composed = Image.alpha_composite(composed, tissue_layer)

    mark_layer = Image.new("RGBA", thumb.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(mark_layer)
    color = tuple(int(v) for v in outline_rgb)
    ranges = ranges_level0.astype(np.int64)
    mode = style.lower().replace("-", "_")
    draw_boxes = mode in {"box", "boxes", "rect", "rectangles"} or len(ranges) <= max_box_count
    if draw_boxes:
        for x0, y0, x1, y1 in ranges[:max_box_count]:
            draw.rectangle(
                [int(x0 * sx), int(y0 * sy), int(x1 * sx), int(y1 * sy)],
                outline=(*color, 185),
                width=max(1, outline_width),
            )
    else:
        radius = max(2, min(5, int(round(max(thumb.width, thumb.height) / 420))))
        for x0, y0, x1, y1 in ranges:
            cx = int(((x0 + x1) / 2) * sx)
            cy = int(((y0 + y1) / 2) * sy)
            draw.ellipse(
                [cx - radius, cy - radius, cx + radius, cy + radius],
                fill=(*color, 190),
                outline=(255, 255, 255, 150),
            )
    composed = Image.alpha_composite(composed, mark_layer)
    return composed.convert("RGB")


def sampling_worker(payload: dict[str, Any]) -> dict[str, Any]:
    row = payload["row"]
    output_root = payload["output_root"]
    paths = coordinate_paths(output_root, row)
    try:
        coordinates = sample_slide_coordinates(
            source_path=row["source_path"],
            patch_config=payload["patch_config"],
            output_root=output_root,
            row=row,
            visualization_config=payload.get("visualization_config", {}),
            force=payload.get("force", False),
        )
        return {
            "ok": True,
            "source_path": row["source_path"],
            "case_id": row.get("case_id", ""),
            "slide_id": row.get("slide_id", ""),
            "coordinate_npy": str(paths["npy"]),
            "coordinate_csv": str(paths["csv"]),
            "overlay": str(paths["overlay"]) if paths["overlay"].exists() else "",
            "n_coordinates": int(coordinates.ranges_level0.shape[0]),
            "from_cache": coordinates.from_cache,
            "level": coordinates.level,
            "patch_size": coordinates.patch_size,
            "level_downsample": coordinates.level_downsample,
        }
    except Exception as exc:
        return {
            "ok": False,
            "source_path": row.get("source_path", ""),
            "case_id": row.get("case_id", ""),
            "slide_id": row.get("slide_id", ""),
            "error": str(exc),
        }
