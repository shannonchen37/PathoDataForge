"""Runtime hardware and dependency helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class GPUInfo:
    index: int
    name: str
    total_memory_gb: float


def get_gpu_info() -> list[GPUInfo]:
    """Return visible CUDA devices, if PyTorch and CUDA are available."""
    try:
        import torch
    except Exception:
        return []

    try:
        if not torch.cuda.is_available():
            return []
        devices: list[GPUInfo] = []
        for index in range(torch.cuda.device_count()):
            props = torch.cuda.get_device_properties(index)
            devices.append(
                GPUInfo(
                    index=index,
                    name=str(props.name),
                    total_memory_gb=round(float(props.total_memory) / (1024**3), 2),
                )
            )
        return devices
    except Exception:
        return []


def describe_gpus() -> str:
    devices = get_gpu_info()
    if devices:
        return "; ".join(
        f"cuda:{device.index} {device.name} ({device.total_memory_gb:.2f} GB)"
        for device in devices
        )

    try:
        import torch

        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "Apple MPS available (unified memory; dedicated VRAM not reported by PyTorch)"
    except Exception:
        pass
    return "No CUDA GPU detected; Apple MPS unavailable"


def has_mps() -> bool:
    try:
        import torch

        return bool(hasattr(torch.backends, "mps") and torch.backends.mps.is_available())
    except Exception:
        return False
