"""Download and smoke-test iMoonLab-PathoDataForge feature models from the command line."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pathodataforge.core.feature_extractor import MODEL_NAMES, load_feature_model
from pathodataforge.core.runtime import describe_gpus


def _load_test_image(path: Path | None, size: int) -> Image.Image:
    if path and path.exists():
        image = Image.open(path).convert("RGB")
        width, height = image.size
        edge = min(width, height, max(size, 64))
        left = max(0, (width - edge) // 2)
        top = max(0, (height - edge) // 2)
        return image.crop((left, top, left + edge, top + edge)).resize((size, size))

    rng = np.random.default_rng(1337)
    image = np.zeros((size, size, 3), dtype=np.uint8)
    image[:, :] = (185, 105, 180)
    noise = rng.normal(0, 35, image.shape).astype(np.int16)
    image = np.clip(image.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(image, "RGB")


def smoke_test_model(
    model_name: str,
    image: Image.Image,
    output_dir: Path,
    device: str,
    hf_token: str,
    forward: bool,
) -> dict[str, Any]:
    started = time.perf_counter()
    result: dict[str, Any] = {
        "model_name": model_name,
        "ok": False,
        "device_requested": device,
    }
    try:
        loaded = load_feature_model(
            {
                "model_name": model_name,
                "device": device,
                "hf_token": hf_token,
                "precision": "auto",
            }
        )
        result["device"] = loaded.device
        result["load_seconds"] = round(time.perf_counter() - started, 3)
        if forward:
            forward_started = time.perf_counter()
            batch = loaded.preprocess([image])
            features = loaded.encode(batch)
            features = np.asarray(features, dtype=np.float32)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{model_name.replace('-', '_')}_smoke_feature.npy"
            np.save(output_path, features)
            result.update(
                {
                    "feature_shape": list(features.shape),
                    "feature_npy": str(output_path),
                    "forward_seconds": round(time.perf_counter() - forward_started, 3),
                }
            )
        result["ok"] = True
    except Exception as exc:
        result["error"] = str(exc)
    result["total_seconds"] = round(time.perf_counter() - started, 3)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Download and smoke-test feature models.")
    parser.add_argument(
        "--models",
        nargs="+",
        default=list(MODEL_NAMES),
        choices=list(MODEL_NAMES),
        help="Models to download/test.",
    )
    parser.add_argument("--device", default="auto", help="auto, cpu, cuda:0, or mps.")
    parser.add_argument("--hf-token", default="", help="Optional Hugging Face token.")
    parser.add_argument(
        "--image",
        default="demo_data/wsi/CASE001_slide_01.png",
        help="Image used for one-patch smoke test.",
    )
    parser.add_argument(
        "--output-dir",
        default="PathoDataForge_output/model_smoke",
        help="Where to save smoke-test feature vectors.",
    )
    parser.add_argument(
        "--no-forward",
        action="store_true",
        help="Only load/download the model; skip the one-image forward pass.",
    )
    args = parser.parse_args()

    image = _load_test_image(Path(args.image), 224)
    output_dir = Path(args.output_dir)
    summary = {
        "hardware": describe_gpus(),
        "models": [
            smoke_test_model(
                model_name=model,
                image=image,
                output_dir=output_dir,
                device=args.device,
                hf_token=args.hf_token,
                forward=not args.no_forward,
            )
            for model in args.models
        ],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if all(item.get("ok") for item in summary["models"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
