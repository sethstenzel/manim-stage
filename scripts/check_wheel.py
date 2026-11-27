"""Packaging smoke check (backlog 1.6): the wheel has the editor, entry point and extras.

python scripts/check_wheel.py dist/manim_stage-*.whl
"""

import sys
import zipfile

REQUIRED = [
    "manim_stage/__init__.py",
    "manim_stage/py.typed",
    "manim_stage/cli.py",
    "manim_stage/runner.py",
    "manim_stage/studio/service.py",
    "manim_stage/studio/ui/main_window.py",
    "manim_stage/studio/ui/timeline.py",
    "manim_stage/fonts/JetBrainsMono-Regular.ttf",
    "manim_stage/fonts/OFL.txt",
    "manim_stage/catalog.py",
    "manim_stage/edu.py",
    "manim_stage/demo.py",
    "manim_stage/web.py",
    "manim_stage/plugins.py",
    "manim_stage/typography.py",
    "manim_stage/camera_info.py",
    "manim_stage/manimcfg.py",
    "manim_stage/studio/ui/library_panel.py",
    "manim_stage/studio/ui/text_panel.py",
]


def main(path: str) -> int:
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        missing = [f for f in REQUIRED if f not in names]
        meta = next(n for n in names if n.endswith(".dist-info/METADATA"))
        eps = next(n for n in names if n.endswith(".dist-info/entry_points.txt"))
        metadata = z.read(meta).decode()
        entry_points = z.read(eps).decode()
    problems = [f"missing {f}" for f in missing]
    if "manim-stage = manim_stage.cli:main" not in entry_points:
        problems.append("console script manim-stage missing")
    if "Provides-Extra: studio" not in metadata:
        problems.append("extra 'studio' missing")
    if any(n.endswith((".pyc", "__pycache__/")) for n in names):
        problems.append("compiled files packaged")
    for p in problems:
        print("FAIL", p)
    print("wheel OK" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
