"""Foundation-model feature extraction for sampled WSI patches."""

from __future__ import annotations

import logging
import os
import queue
import threading
from pathlib import Path
from typing import Any, Callable

import numpy as np
from PIL import Image

from pathodataforge.core.sampling import coordinate_paths, slide_id_token
from pathodataforge.core.wsi_reader import WSIReader
from pathodataforge.utils.io import atomic_save_npy, safe_load_npy


MODEL_NAMES = ("ResNet50", "UNI", "UNI2-h", "CONCH", "Virchow2")


def feature_path(output_root: str | Path, row: dict[str, Any], model_name: str) -> Path:
    token = slide_id_token(row)
    model_token = model_name.replace("/", "_").replace("-", "_")
    return Path(output_root) / "features" / f"{token}_{model_token}_fts.npy"


def _import_torch():
    try:
        import torch

        return torch
    except Exception as exc:
        raise RuntimeError(
            "Feature extraction requires PyTorch. Install a suitable torch build first."
        ) from exc


def _resolve_device(device_cfg: str) -> str:
    torch = _import_torch()
    device_cfg = str(device_cfg or "auto").lower()
    if device_cfg == "auto":
        if torch.cuda.is_available():
            return "cuda:0"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        return "cpu"
    return device_cfg


def _login_huggingface(token: str | None) -> None:
    token = token or os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN")
    if not token:
        return
    try:
        from huggingface_hub import login

        login(token=token, add_to_git_credential=False)
    except Exception as exc:
        raise RuntimeError("huggingface_hub login failed. Check hf_token/HF_TOKEN.") from exc


def _image_batch_to_tensor(images: list[Image.Image], device: str):
    torch = _import_torch()
    mean = np.asarray([0.485, 0.456, 0.406], dtype=np.float32).reshape(1, 1, 3)
    std = np.asarray([0.229, 0.224, 0.225], dtype=np.float32).reshape(1, 1, 3)
    arrays = []
    for image in images:
        resized = image.convert("RGB").resize((224, 224), Image.Resampling.BICUBIC)
        arr = np.asarray(resized).astype(np.float32) / 255.0
        arr = (arr - mean) / std
        arrays.append(np.transpose(arr, (2, 0, 1)))
    tensor = torch.from_numpy(np.stack(arrays, axis=0))
    return tensor.to(device)


class LoadedFeatureModel:
    def __init__(
        self,
        model_name: str,
        model: Any,
        device: str,
        preprocess: Callable[[list[Image.Image]], Any],
        encode: Callable[[Any], Any],
    ) -> None:
        self.model_name = model_name
        self.model = model
        self.device = device
        self.preprocess = preprocess
        self.encode = encode


def load_feature_model(model_config: dict[str, Any], device_override: str | None = None) -> LoadedFeatureModel:
    """Load one of ResNet50, UNI, UNI2-h, CONCH, or Virchow2."""
    torch = _import_torch()
    model_name = str(model_config.get("model_name", "ResNet50"))
    canonical = model_name.lower()
    device = device_override or _resolve_device(str(model_config.get("device", "auto")))
    _login_huggingface(str(model_config.get("hf_token") or ""))

    if canonical in {"resnet50", "resnet-50"}:
        try:
            import torchvision
        except Exception as exc:
            raise RuntimeError("ResNet50 feature extraction requires torchvision.") from exc

        weights = torchvision.models.ResNet50_Weights.DEFAULT
        model = torchvision.models.resnet50(weights=weights)
        model.fc = torch.nn.Identity()
        model = model.to(device).eval()

        def preprocess(images: list[Image.Image]):
            return _image_batch_to_tensor(images, device)

        def encode(batch: Any):
            with torch.inference_mode():
                output = model(batch)
                return output.detach().cpu().float().numpy()

        return LoadedFeatureModel(model_name, model, device, preprocess, encode)

    if canonical in {"uni", "uni2-h", "uni2_h", "virchow2"}:
        try:
            import timm
        except Exception as exc:
            raise RuntimeError(
                "UNI/UNI2-h/Virchow2 feature extraction requires timm and huggingface_hub."
            ) from exc

        if canonical == "uni":
            model = timm.create_model(
                "hf-hub:MahmoodLab/UNI",
                pretrained=True,
                init_values=1e-5,
                dynamic_img_size=True,
            )
        elif canonical in {"uni2-h", "uni2_h"}:
            timm_kwargs = {
                "img_size": 224,
                "patch_size": 14,
                "depth": 24,
                "num_heads": 24,
                "init_values": 1e-5,
                "embed_dim": 1536,
                "mlp_ratio": 2.66667 * 2,
                "num_classes": 0,
                "no_embed_class": True,
                "mlp_layer": timm.layers.SwiGLUPacked,
                "act_layer": torch.nn.SiLU,
                "reg_tokens": 8,
                "dynamic_img_size": True,
            }
            model = timm.create_model("hf-hub:MahmoodLab/UNI2-h", pretrained=True, **timm_kwargs)
        else:
            model = timm.create_model(
                "hf-hub:paige-ai/Virchow2",
                pretrained=True,
                mlp_layer=timm.layers.SwiGLUPacked,
                act_layer=torch.nn.SiLU,
            )

        model = model.to(device).eval()

        def preprocess(images: list[Image.Image]):
            return _image_batch_to_tensor(images, device)

        def encode(batch: Any):
            with torch.inference_mode():
                use_amp = device.startswith("cuda") and str(model_config.get("precision", "auto")) != "fp32"
                if use_amp:
                    with torch.autocast(device_type="cuda", dtype=torch.float16):
                        output = model(batch)
                else:
                    output = model(batch)
                if canonical == "virchow2":
                    class_token = output[:, 0]
                    patch_tokens = output[:, 5:]
                    output = torch.cat([class_token, patch_tokens.mean(1)], dim=-1)
                elif getattr(output, "dim", lambda: 0)() == 3:
                    output = output[:, 0]
                return output.detach().cpu().float().numpy()

        return LoadedFeatureModel(model_name, model, device, preprocess, encode)

    if canonical == "conch":
        try:
            from conch.open_clip_custom import create_model_from_pretrained
        except Exception as exc:
            raise RuntimeError(
                "CONCH feature extraction requires: pip install git+https://github.com/Mahmoodlab/CONCH.git"
            ) from exc

        token = str(model_config.get("hf_token") or os.environ.get("HF_TOKEN") or "")
        source = str(model_config.get("checkpoint") or "hf_hub:MahmoodLab/CONCH")
        try:
            model, preprocess_one = create_model_from_pretrained(
                "conch_ViT-B-16",
                source,
                hf_auth_token=token or None,
            )
        except Exception:
            model, preprocess_one = create_model_from_pretrained(
                "conch_ViT-B-16",
                "hf_hub:MahmoodLab/conch",
                hf_auth_token=token or None,
            )
        model = model.to(device).eval()

        def preprocess(images: list[Image.Image]):
            tensors = [preprocess_one(image.convert("RGB")) for image in images]
            return torch.stack(tensors, dim=0).to(device)

        def encode(batch: Any):
            with torch.inference_mode():
                output = model.encode_image(batch, proj_contrast=False, normalize=False)
                return output.detach().cpu().float().numpy()

        return LoadedFeatureModel(model_name, model, device, preprocess, encode)

    raise ValueError(f"Unsupported feature model: {model_name}. Choose one of {', '.join(MODEL_NAMES)}")


def extract_features_for_slide(
    slide_path: str | Path,
    coordinate_npy: str | Path,
    output_npy: str | Path,
    level: int,
    patch_size: int,
    model: LoadedFeatureModel,
    batch_size: int = 32,
    overwrite: bool = False,
    logger: logging.Logger | None = None,
) -> dict[str, Any]:
    """Extract features for level-0 coordinate ranges and cache them as .npy."""
    coordinate_array = safe_load_npy(coordinate_npy, logger)
    if coordinate_array is None:
        raise FileNotFoundError(f"Coordinate npy not readable: {coordinate_npy}")

    output_path = Path(output_npy)
    cached = None if overwrite else safe_load_npy(output_path, logger)
    if cached is not None and cached.shape[0] == coordinate_array.shape[0]:
        return {
            "ok": True,
            "feature_npy": str(output_path),
            "n_features": int(cached.shape[0]),
            "feature_dim": int(cached.shape[1]) if cached.ndim == 2 else 0,
            "from_cache": True,
        }

    batch_size = max(1, int(batch_size))
    outputs: list[np.ndarray] = []
    with WSIReader(slide_path) as reader:
        for start in range(0, coordinate_array.shape[0], batch_size):
            batch_ranges = coordinate_array[start : start + batch_size]
            images = [
                reader.read_region_level0(int(x0), int(y0), level, (patch_size, patch_size))
                for x0, y0, _, _ in batch_ranges
            ]
            batch = model.preprocess(images)
            outputs.append(model.encode(batch))

    if outputs:
        features = np.concatenate(outputs, axis=0).astype(np.float32)
    else:
        features = np.zeros((0, 0), dtype=np.float32)
    atomic_save_npy(features, output_path)
    if logger:
        logger.info("Features saved: %s shape=%s", output_path, features.shape)
    return {
        "ok": True,
        "feature_npy": str(output_path),
        "n_features": int(features.shape[0]),
        "feature_dim": int(features.shape[1]) if features.ndim == 2 else 0,
        "from_cache": False,
    }


def feature_consumer(
    name: str,
    task_queue: "queue.Queue[dict[str, Any] | None]",
    output_root: str | Path,
    model_config: dict[str, Any],
    device: str,
    logger: logging.Logger,
    results: list[dict[str, Any]],
    stop_event: threading.Event,
) -> None:
    """Worker thread that owns a model instance and consumes feature tasks."""
    try:
        model = load_feature_model(model_config, device_override=device)
        logger.info("%s loaded %s on %s", name, model.model_name, model.device)
    except Exception as exc:
        logger.error("%s could not load feature model: %s", name, exc)
        results.append({"ok": False, "worker": name, "device": device, "error": str(exc)})
        stop_event.set()
        return

    while not stop_event.is_set():
        try:
            task = task_queue.get(timeout=1.0)
        except queue.Empty:
            continue
        if task is None:
            task_queue.task_done()
            break
        try:
            row = task["row"]
            out_npy = feature_path(output_root, row, str(model_config.get("model_name", "ResNet50")))
            result = extract_features_for_slide(
                slide_path=row["source_path"],
                coordinate_npy=task["coordinate_npy"],
                output_npy=out_npy,
                level=int(task["level"]),
                patch_size=int(task["patch_size"]),
                model=model,
                batch_size=int(model_config.get("batch_size", 32)),
                overwrite=bool(model_config.get("overwrite", False)),
                logger=logger,
            )
            result.update(
                {
                    "case_id": row.get("case_id", ""),
                    "slide_id": row.get("slide_id", ""),
                    "source_path": row.get("source_path", ""),
                    "model_name": model.model_name,
                    "worker": name,
                }
            )
            results.append(result)
        except Exception as exc:
            logger.exception("%s feature extraction failed: %s", name, exc)
            results.append({"ok": False, "worker": name, "error": str(exc), **task})
        finally:
            task_queue.task_done()
