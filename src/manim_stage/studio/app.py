"""Start the Studio editor: ``python -m manim_stage.studio lesson.py [Scene]``.

The full CLI (``manim-stage studio``) arrives with backlog 1.6.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def default_cache_dir() -> Path:
    """Per-user cache folder (frames can be large; keep them out of the project)."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "manim-stage" / "frames"


def default_workers() -> int:
    """Parallel drawing pays off from 4 workers (docs/benchmarks.md); leave cores free."""
    return max(1, min(4, (os.cpu_count() or 2) // 2))


def create_window(
    file: str | Path,
    scene: str | None = None,
    *,
    quality: str = "low_quality",
    workers: int | None = None,
    cache_dir: str | Path | None = None,
    watch: bool = True,
):
    """Build the main window (QApplication must exist). Returns (window, service)."""
    from PySide6.QtWidgets import QApplication

    from .service import PreviewService
    from .ui.main_window import MainWindow, studio_settings
    from .ui.theme import apply_theme

    app = QApplication.instance()
    dark = studio_settings().value("dark", True, type=bool)
    apply_theme(app, dark)
    service = PreviewService(file, cache_dir=cache_dir or default_cache_dir())
    window = MainWindow(service, scene=scene, quality=quality, workers=workers or default_workers())
    window.act_theme.setText("Light theme" if dark else "Dark theme")
    window.transport.refresh_icons()
    if watch:
        service.watch()
    return window, service


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m manim_stage.studio", description="manim-stage Studio editor"
    )
    parser.add_argument("file", type=Path, help="Python file with Manim Scene classes")
    parser.add_argument("scene", nargs="?", help="Scene class to open (default: the first)")
    parser.add_argument(
        "-q",
        "--quality",
        default="low_quality",
        help="Manim quality preset for the preview (default: low_quality)",
    )
    parser.add_argument("--workers", type=int, default=None, help="parallel drawing processes")
    parser.add_argument("--cache-dir", type=Path, default=None, help="frame cache folder")
    parser.add_argument("--no-watch", action="store_true", help="don't re-render on save")
    args = parser.parse_args(argv)
    if not args.file.is_file():
        parser.error(f"{args.file} is not a file")
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("The Studio editor needs PySide6: pip install 'manim-stage[studio]'", file=sys.stderr)
        return 2
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("manim-stage Studio")
    window, _ = create_window(
        args.file,
        args.scene,
        quality=args.quality,
        workers=args.workers,
        cache_dir=args.cache_dir,
        watch=not args.no_watch,
    )
    window.show()
    return app.exec()
