"""Split per-frame preview cost into drawing vs PNG encoding (backlog 0.6)."""

import io
import sys
import time
from pathlib import Path

from manim import tempconfig

from manim_stage.capture import capture
from manim_stage.runner import load_scene_class

W, H, FPS = (int(a) for a in (sys.argv[1:4] or (1920, 1080, 30)))
cfg = {"frame_rate": FPS, "pixel_width": W, "pixel_height": H, "progress_bar": "none",
       "disable_caching": True, "verbosity": "WARNING"}  # fmt: skip

with tempconfig(cfg):
    cls = load_scene_class(Path(__file__).with_name("reference_scene.py"), "Reference")
    t = time.perf_counter()
    tl = capture(cls)
    t_timeline = time.perf_counter() - t
    n = tl.duration_frames
    times = [i / FPS for i in range(n)]

    t = time.perf_counter()
    capture(cls, frame_times=times, on_frame=lambda f: f.image)
    t_draw = time.perf_counter() - t

    imgs: list = []
    capture(cls, frame_times=times[:30], on_frame=lambda f: imgs.append(f.image))
    for level in (1, 6):
        t = time.perf_counter()
        for im in imgs:
            im.save(io.BytesIO(), format="PNG", compress_level=level)
        per = (time.perf_counter() - t) / len(imgs) * 1000
        print(f"png compress_level={level}: {per:.1f} ms/frame")

per_frame = (t_draw - t_timeline) / n * 1000
print(f"{W}x{H}@{FPS}: {n} frames; timeline-only pass {t_timeline:.2f}s; "
      f"draw all {t_draw:.2f}s = {per_frame:.1f} ms/frame drawing")  # fmt: skip
