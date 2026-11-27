"""Studio editor latency (M1 gate, spec §9).

Measures, in the real editor window (offscreen Qt), on the 10 s reference scene:

- **open → first frame**: window created → first rendered frame on screen;
- **open → timeline**: window created → timeline shown;
- **open → all frames**: every preview frame cached;
- **save → first new frame**: file saved → first frame of the new revision on screen
  (includes the 0.3 s debounce);
- **save → all frames**;
- **seek**: playhead moved to a random cached frame → frame shown (median / p95),
  including PNG decode on a pixmap-cache miss.

Run:  uv run python benchmarks/studio_latency.py [--quality low_quality|medium_quality|high_quality]
      [--workers N] [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from manim_stage.studio.app import create_window  # noqa: E402

HERE = Path(__file__).parent


def pump(app, cond, timeout=600.0) -> float:
    t0 = time.perf_counter()
    while not cond():
        app.processEvents()
        time.sleep(0.002)
        if time.perf_counter() - t0 > timeout:
            raise TimeoutError
    return time.perf_counter() - t0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quality", default="medium_quality")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()
    app = QApplication(sys.argv[:1])
    tmp = Path(tempfile.mkdtemp(prefix="studio-bench-"))
    scene = tmp / "reference_scene.py"
    shutil.copy(HERE / "reference_scene.py", scene)
    out: dict[str, float | int | str] = {"quality": args.quality, "workers": args.workers}

    t0 = time.perf_counter()
    win, svc = create_window(
        scene,
        "Reference",
        quality=args.quality,
        workers=args.workers,
        cache_dir=tmp / "cache",
        watch=True,
    )
    win.show()
    pump(app, lambda: win.timeline.canvas.layout_ is not None)
    out["open_to_timeline_s"] = round(time.perf_counter() - t0, 3)
    pump(app, lambda: win.viewport.has_frame)
    out["open_to_first_frame_s"] = round(time.perf_counter() - t0, 3)
    pump(app, lambda: win.shown_state and win.shown_state[2] == "done")
    out["open_to_all_frames_s"] = round(time.perf_counter() - t0, 3)
    total = svc.current.timeline.duration_frames
    out["frames"] = total

    # seek latency over cached frames
    rng = random.Random(0)
    samples = []
    for _ in range(200):
        f = rng.randrange(total)
        s = time.perf_counter()
        win.seek(f)
        app.processEvents()
        samples.append((time.perf_counter() - s) * 1000)
    samples.sort()
    out["seek_median_ms"] = round(statistics.median(samples), 2)
    out["seek_p95_ms"] = round(samples[int(len(samples) * 0.95)], 2)

    # edit & save
    seq = win.shown_state[0]
    src = scene.read_text(encoding="utf-8")
    t1 = time.perf_counter()
    scene.write_text(src.replace("color=BLUE", "color=GREEN"), encoding="utf-8")
    pump(app, lambda: svc.current.seq > seq and svc.current.frames and win.viewport.has_frame)
    out["save_to_first_new_frame_s"] = round(time.perf_counter() - t1, 3)
    pump(app, lambda: win.shown_state[0] > seq and win.shown_state[2] == "done")
    out["save_to_all_frames_s"] = round(time.perf_counter() - t1, 3)
    out["save_frames_drawn"] = svc.current.frames_drawn
    out["save_frames_total"] = len(svc.current.frames)

    win.close()
    app.processEvents()
    shutil.rmtree(tmp, ignore_errors=True)
    print(json.dumps(out, indent=2))
    if args.json:
        args.json.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
