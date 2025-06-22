"""WSI reader abstraction with OpenSlide and Pillow fallbacks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps


@dataclass(slots=True)
class WSIInfo:
    width: int
    height: int
    level_count: int
    level_dimensions: list[tuple[int, int]]
    level_downsamples: list[float]
    reader_backend: str
    objective_power: float | None = None


class WSIReader:
    """Small compatibility layer over OpenSlide and PIL images."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._slide: Any | None = None
        self._image: Image.Image | None = None
        self._backend = "pillow"
        self._open()

    def __enter__(self) -> "WSIReader":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def _open(self) -> None:
        if not self.path.exists():
            raise FileNotFoundError(f"Image file not found: {self.path}")

        try:
            import openslide  # type: ignore

            self._slide = openslide.OpenSlide(str(self.path))
            self._backend = "openslide"
            return
        except Exception:
            self._slide = None

        image = Image.open(self.path)
        try:
            image.seek(0)
        except EOFError:
            pass
        self._image = ImageOps.exif_transpose(image)
        self._backend = "pillow"

    @property
    def backend(self) -> str:
        return self._backend

    def info(self) -> WSIInfo:
        if self._slide is not None:
            dimensions = [tuple(map(int, item)) for item in self._slide.level_dimensions]
            downsamples = [float(item) for item in self._slide.level_downsamples]
            objective = self._objective_power_from_properties()
            width, height = dimensions[0]
            return WSIInfo(
                width=width,
                height=height,
                level_count=len(dimensions),
                level_dimensions=dimensions,
                level_downsamples=downsamples,
                reader_backend=self._backend,
                objective_power=objective,
            )

        assert self._image is not None
        width, height = self._image.size
        dimensions = [(width, height)]
        downsamples = [1.0]
        downsample = 2
        while width // downsample >= 256 and height // downsample >= 256:
            dimensions.append((max(1, width // downsample), max(1, height // downsample)))
            downsamples.append(float(downsample))
            downsample *= 2
        return WSIInfo(
            width=width,
            height=height,
            level_count=len(dimensions),
            level_dimensions=dimensions,
            level_downsamples=downsamples,
            reader_backend=self._backend,
            objective_power=None,
        )

    def _objective_power_from_properties(self) -> float | None:
        if self._slide is None:
            return None
        candidates = [
            "openslide.objective-power",
            "aperio.AppMag",
            "hamamatsu.SourceLens",
        ]
        for key in candidates:
            value = self._slide.properties.get(key)
            if value:
                try:
                    return float(value)
                except ValueError:
                    continue
        return None

    def thumbnail(self, max_size: tuple[int, int] = (1024, 1024)) -> Image.Image:
        if self._slide is not None:
            return self._slide.get_thumbnail(max_size).convert("RGB")

        assert self._image is not None
        image = self._image.convert("RGB").copy()
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        return image

    def read_region_level(
        self,
        x: int,
        y: int,
        level: int,
        size: tuple[int, int],
    ) -> Image.Image:
        """Read a patch using coordinates in the selected level."""
        info = self.info()
        level = max(0, min(level, info.level_count - 1))
        downsample = info.level_downsamples[level]

        if self._slide is not None:
            location = (int(round(x * downsample)), int(round(y * downsample)))
            return self._slide.read_region(location, level, size).convert("RGB")

        assert self._image is not None
        base_image = self._image.convert("RGB")
        left = int(round(x * downsample))
        top = int(round(y * downsample))
        base_width = max(1, int(round(size[0] * downsample)))
        base_height = max(1, int(round(size[1] * downsample)))
        right = left + base_width
        bottom = top + base_height

        canvas = Image.new("RGB", (base_width, base_height), "white")
        clipped = (
            max(0, left),
            max(0, top),
            min(base_image.width, right),
            min(base_image.height, bottom),
        )
        if clipped[2] > clipped[0] and clipped[3] > clipped[1]:
            crop = base_image.crop(clipped)
            canvas.paste(crop, (clipped[0] - left, clipped[1] - top))
        if canvas.size != size:
            canvas = canvas.resize(size, Image.Resampling.BILINEAR)
        return canvas

    def read_region_level0(
        self,
        x0: int,
        y0: int,
        level: int,
        size: tuple[int, int],
    ) -> Image.Image:
        """Read a patch using level-0 top-left coordinates."""
        info = self.info()
        level = max(0, min(level, info.level_count - 1))
        if self._slide is not None:
            return self._slide.read_region((int(x0), int(y0)), level, size).convert("RGB")

        assert self._image is not None
        downsample = info.level_downsamples[level]
        base_image = self._image.convert("RGB")
        base_width = max(1, int(round(size[0] * downsample)))
        base_height = max(1, int(round(size[1] * downsample)))
        right = int(x0) + base_width
        bottom = int(y0) + base_height
        canvas = Image.new("RGB", (base_width, base_height), "white")
        clipped = (
            max(0, int(x0)),
            max(0, int(y0)),
            min(base_image.width, right),
            min(base_image.height, bottom),
        )
        if clipped[2] > clipped[0] and clipped[3] > clipped[1]:
            crop = base_image.crop(clipped)
            canvas.paste(crop, (clipped[0] - int(x0), clipped[1] - int(y0)))
        if canvas.size != size:
            canvas = canvas.resize(size, Image.Resampling.BILINEAR)
        return canvas

    def close(self) -> None:
        if self._slide is not None:
            self._slide.close()
            self._slide = None
        if self._image is not None:
            self._image.close()
            self._image = None
