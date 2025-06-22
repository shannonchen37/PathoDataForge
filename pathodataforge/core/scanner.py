"""Input scanning utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pathodataforge.utils.io import read_metadata_table


SUPPORTED_WSI_EXTENSIONS = {
    ".svs",
    ".tif",
    ".tiff",
    ".ndpi",
    ".mrxs",
    ".png",
    ".jpg",
    ".jpeg",
}

SUPPORTED_METADATA_EXTENSIONS = {".csv", ".xlsx", ".xls"}

# TCGA/GDC downloads often place manifests, clinical carts, checksum files, and
# temporary parcel files in the same folder as slides. They are useful project
# sidecars, but they are not candidate pathology images and should not appear as
# unsupported WSI files in the GUI.
IGNORED_AUXILIARY_EXTENSIONS = {
    ".csv",
    ".json",
    ".log",
    ".md5",
    ".parcel",
    ".partial",
    ".sha1",
    ".sha256",
    ".tsv",
    ".txt",
    ".xls",
    ".xlsx",
    ".xml",
    ".yaml",
    ".yml",
}

IGNORED_AUXILIARY_NAMES = {
    ".ds_store",
    "thumbs.db",
}


@dataclass(slots=True)
class ScanResult:
    wsi_dir: Path
    files: list[Path] = field(default_factory=list)
    unsupported_files: list[Path] = field(default_factory=list)

    @property
    def image_file_count(self) -> int:
        return len(self.files)

    @property
    def supported_format_count(self) -> int:
        return len({path.suffix.lower() for path in self.files})

    @property
    def unsupported_count(self) -> int:
        return len(self.unsupported_files)

    def preview(self, limit: int = 20) -> list[str]:
        return [str(path) for path in self.files[:limit]]

    def to_dict(self) -> dict[str, object]:
        return {
            "wsi_dir": str(self.wsi_dir),
            "image_file_count": self.image_file_count,
            "supported_format_count": self.supported_format_count,
            "unsupported_count": self.unsupported_count,
            "preview": self.preview(),
        }


def scan_wsi_folder(wsi_dir: str | Path) -> ScanResult:
    """Recursively scan a folder for supported WSI/image files."""
    root = Path(wsi_dir).expanduser()
    if not root.exists():
        raise FileNotFoundError(f"WSI folder not found: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"WSI path is not a folder: {root}")

    files: list[Path] = []
    unsupported: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name.lower() in IGNORED_AUXILIARY_NAMES:
            continue
        suffix = path.suffix.lower()
        if suffix in SUPPORTED_WSI_EXTENSIONS:
            files.append(path)
        elif suffix in IGNORED_AUXILIARY_EXTENSIONS:
            continue
        elif suffix:
            unsupported.append(path)
    return ScanResult(wsi_dir=root, files=files, unsupported_files=unsupported)


def read_metadata_fields(metadata_file: str | Path) -> list[str]:
    """Return metadata column names for GUI combo boxes."""
    path = Path(metadata_file)
    if path.suffix.lower() not in SUPPORTED_METADATA_EXTENSIONS:
        raise ValueError(f"Unsupported metadata file type: {path.suffix}")
    return list(read_metadata_table(path).columns)
