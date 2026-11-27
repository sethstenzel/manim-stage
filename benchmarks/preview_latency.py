"""Spec §9 preview latency benchmark (backlog 0.6).

Targets (spec §9, to revise after measuring):
- first usable cached preview of a simple 10 s 1080p scene <= 10 s (deps warm)
- median scrub response on cached frames <= 100 ms at 720p

Run:  uv run python benchmarks/preview_latency.py [--json out.json]
Measures the runner in a fresh child process (as the Studio will use it), cold and
warm cache, then random-access frame reads + PNG decode from the cache.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import random
import statistics
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image

from manim_stage.framecache import FrameCache
from manim_stage.runner import run_capture

SCENE_FILE = Path(__file__).with_name("reference_scene.py")
CASES = [
    ("720p30", 1280, 720, 30, 1),
    ("1080p30", 1920, 1080, 30, 1),
    ("1080p30", 1920, 1080, 30, 4),
    ("1080p30", 1920, 1080, 30, 8),
]


def machine() -> dict[str, str]:
    return {
        "os": platform.platform(),
        "cpu": platform.processor() or platform.machine(),
        "cpus": str(os.cpu_count()),
        "python": sys.version.split()[0],
    }


def bench(label: str, w: int, h: int, fps: int, workers: int, reads: int = 300) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        t = time.perf_counter()
        cold = run_capture(
            SCENE_FILE, "Reference", fps=fps, width=w, height=h, cache_dir=tmp,
            workers=workers, timeout=900,
        )  # fmt: skip
        cold_wall = time.perf_counter() - t
        t = time.perf_counter()
        warm = run_capture(SCENE_FILE, "Reference", fps=fps, width=w, height=h, cache_dir=tmp)
        warm_wall = time.perf_counter() - t

        cache = FrameCache(tmp)
        n = cold.timeline.duration_frames
        rng = random.Random(0)
        samples = []
        for _ in range(reads):
            i = rng.randrange(n)
            t = time.perf_counter()
            p = cache.get(cold.revision, i)
            Image.open(p).load()  # decode, as a server would before re-encoding or sending
            samples.append((time.perf_counter() - t) * 1000)
        frame_bytes = statistics.median(p.stat().st_size for p in cold.frames.values())
    samples.sort()
    return {
        "case": label,
        "workers": workers,
        "frames": n,
        "duration_s": n / fps,
        "cold_wall_s": round(cold_wall, 2),
        "cold_child": cold.timings,
        "timeline_ready_s": cold.timings.get("timeline"),
        "warm_wall_s": round(warm_wall, 2),
        "warm_frames_drawn": warm.frames_drawn,
        "seek_ms_median": round(statistics.median(samples), 1),
        "seek_ms_p95": round(samples[int(len(samples) * 0.95)], 1),
        "frame_png_kb_median": round(frame_bytes / 1024, 1),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()
    results = {"machine": machine(), "cases": [bench(*c) for c in CASES]}
    print(json.dumps(results, indent=1))
    if args.json:
        args.json.write_text(json.dumps(results, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
