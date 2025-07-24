"""Capture GUI screenshots and a README GIF using synthetic demo data."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _process_events(app, rounds: int = 4) -> None:
    for _ in range(rounds):
        app.processEvents()


def _save_window(window, app, path: Path) -> None:
    _process_events(app, 8)
    pixmap = window.grab()
    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(path))


def _mock_summary(output_root: Path, overlay_path: Path) -> dict[str, object]:
    summary_path = output_root / "reports" / "summary.json"
    manifest_path = output_root / "metadata" / "patch_manifest.csv"
    return {
        "input": {"scanned_files": 4, "metadata_file": "demo_data/metadata.csv"},
        "metadata": {
            "matched_count": 4,
            "unmatched_count": 0,
            "metadata_cleaned_csv": str(output_root / "metadata" / "metadata_cleaned.csv"),
            "mapping_csv": str(output_root / "metadata" / "mapping.csv"),
        },
        "patches": {
            "kept": 128,
            "discarded": 12,
            "manifest_csv": str(manifest_path),
        },
        "coordinates": {
            "slides": [
                {"coordinate_npy": str(output_root / "metadata" / "coordinates" / "demo_coors.npy"), "from_cache": False}
            ]
        },
        "features": {
            "results": [
                {"ok": True, "feature_npy": str(output_root / "features" / "demo_resnet50_fts.npy"), "from_cache": False}
            ]
        },
        "slides": [
            {"source_path": "CASE001_slide_01.png"},
            {"source_path": "CASE001_slide_02.tiff"},
            {"source_path": "CASE002_slide_01.png"},
            {"source_path": "CASE003_slide_01.tiff"},
        ],
        "visualization": {"save_overlay": True, "first_overlay": str(overlay_path)},
        "reports": {"summary_json": str(summary_path)},
        "duration_seconds": 18.4,
    }


def _write_mock_manifest(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "patch_path,case_id,slide_id,label,tissue_ratio,blur_score,keep",
                "patches/CASE001_slide_0001.png,CASE001,slide_0001,adenocarcinoma,0.91,142.5,True",
                "patches/CASE002_slide_0001.png,CASE002,slide_0001,benign,0.84,128.7,True",
                "patches/CASE003_slide_0001.png,CASE003,slide_0001,squamous,0.88,136.9,True",
            ]
        ),
        encoding="utf-8",
    )


def _build_gif(png_paths: list[Path], gif_path: Path, max_bytes: int = 10 * 1024 * 1024) -> None:
    frames: list[Image.Image] = []
    width = 1050
    for path in png_paths:
        image = Image.open(path).convert("RGB")
        ratio = width / image.width
        resized = image.resize((width, int(image.height * ratio)), Image.Resampling.LANCZOS)
        frames.append(resized.convert("P", palette=Image.Palette.ADAPTIVE, colors=128))

    duration = 1350
    while True:
        gif_path.parent.mkdir(parents=True, exist_ok=True)
        frames[0].save(
            gif_path,
            save_all=True,
            append_images=frames[1:],
            optimize=True,
            duration=duration,
            loop=0,
            disposal=2,
        )
        if gif_path.stat().st_size <= max_bytes or width <= 760:
            break
        width = int(width * 0.9)
        frames.clear()
        for path in png_paths:
            image = Image.open(path).convert("RGB")
            ratio = width / image.width
            resized = image.resize((width, int(image.height * ratio)), Image.Resampling.LANCZOS)
            frames.append(resized.convert("P", palette=Image.Palette.ADAPTIVE, colors=96))


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from pathodataforge.app.main_window import MainWindow
    from pathodataforge.core.metadata_cleaner import clean_metadata
    from pathodataforge.core.scanner import scan_wsi_folder
    from pathodataforge.utils.io import read_metadata_table
    from scripts.generate_demo_data import generate_demo_data

    generate_demo_data()

    assets = PROJECT_ROOT / "docs" / "assets"
    screenshots = assets / "screenshots"
    output_root = Path("docs/demo_output")
    demo_wsi = Path("demo_data/wsi")
    demo_metadata = Path("demo_data/metadata.csv")

    app = QApplication([])
    with tempfile.TemporaryDirectory(prefix="imoonlab_capture_") as temp_cwd:
        os.chdir(temp_cwd)
        window = MainWindow()
        window.resize(1400, 900)
        window.show()
        os.chdir(PROJECT_ROOT)

        window.state.set_paths(str(demo_wsi), str(demo_metadata), str(output_root))
        scan_result = scan_wsi_folder(demo_wsi)
        window.state.scan_result = scan_result
        window.state.scanned_files = scan_result.files
        window.project_page.set_scan_result(scan_result)
        window.state.metadata_df = read_metadata_table(demo_metadata)
        window.state.metadata_fields = list(window.state.metadata_df.columns)
        window.state.set_metadata_columns("case_id", "label", "", "")
        result = clean_metadata(scan_result.files, demo_metadata, "case_id", "label", "")
        window.state.match_result = result
        window.metadata_page.refresh_from_state()
        window.metadata_page.set_match_result(result)
        window.project_page.refresh_from_state()
        window.params_page.refresh_from_state()
        window.report_page.refresh_from_state()
        window.state.update_step("import", "已完成", "4 个文件")
        window.state.update_step("metadata", "已完成", "3 条记录")
        window.state.update_step("match", "已完成", "4/4")
        window.state.update_step("params", "已完成", "WSI 预览与取样已确认")
        window.state.update_step("feature", "已完成", "模型：ResNet50")
        _process_events(app, 10)

        captures: list[tuple[int, str, str]] = [
            (0, "01_project_import.png", "项目导入"),
            (1, "02_metadata_match.png", "元信息匹配"),
            (2, "03_wsi_preview_sampling.png", "WSI 预览与取样"),
            (3, "04_feature_runtime.png", "特征提取"),
            (4, "05_run_export.png", "运行与导出"),
            (5, "06_result_report.png", "结果报告"),
        ]
        paths: list[Path] = []

        window.set_page(0)
        path = screenshots / "01_project_import.png"
        _save_window(window, app, path)
        paths.append(path)

        window.set_page(1)
        path = screenshots / "02_metadata_match.png"
        _save_window(window, app, path)
        paths.append(path)

        window.set_page(2)
        window.params_page.preview_panel.refresh_slides()
        _process_events(app, 12)
        window.params_page.preview_panel.generate_sampling_preview()
        _process_events(app, 16)
        path = screenshots / "03_wsi_preview_sampling.png"
        _save_window(window, app, path)
        paths.append(path)
        overlay = window.params_page.preview_panel.last_sampling_overlay
        overlay_path = PROJECT_ROOT / "docs" / "demo_output" / "reports" / "overlays" / "sampling_preview.jpg"
        if overlay is not None:
            overlay_path.parent.mkdir(parents=True, exist_ok=True)
            overlay.save(overlay_path, quality=86)

        window.set_page(3)
        path = screenshots / "04_feature_runtime.png"
        _save_window(window, app, path)
        paths.append(path)

        manifest = output_root / "metadata" / "patch_manifest.csv"
        _write_mock_manifest(manifest)
        summary = _mock_summary(output_root, overlay_path if overlay_path.exists() else Path(""))
        window.state.set_summary(summary)
        window.run_page.set_output_paths(window.state.output_paths)
        window.run_page.set_progress(82, "正在提取 ResNet50 特征")
        window.run_page.append_log("已完成组织候选采样")
        window.run_page.append_log("已生成坐标缓存与采样预览图")
        window.run_page.set_summary(summary)
        window.set_page(4)
        path = screenshots / "05_run_export.png"
        _save_window(window, app, path)
        paths.append(path)

        window.report_page.refresh_from_state()
        window.set_page(5)
        path = screenshots / "06_result_report.png"
        _save_window(window, app, path)
        paths.append(path)

        _build_gif(paths, assets / "imoonlab-pathodataforge-demo.gif")

    gif_path = assets / "imoonlab-pathodataforge-demo.gif"
    print(f"GIF: {gif_path} ({gif_path.stat().st_size / 1024 / 1024:.2f} MB)")
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
