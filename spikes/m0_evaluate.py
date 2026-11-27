"""M0 spike against Manim main: timeline capture, frame drawing, timing, parity with CLI render."""
import json
import math
import struct
import sys
import time
import wave
from pathlib import Path

HERE = Path(__file__).parent
t0 = time.perf_counter()
from manim import *  # noqa: E402
t_import = time.perf_counter() - t0

# 0.5 s 440 Hz tone
wav = HERE / "beep.wav"
with wave.open(str(wav), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000)
    w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / 48000))) for i in range(24000)))


class Lesson(Scene):
    def construct(self):
        sq, c, t = Square(), Circle().shift(LEFT * 3), Triangle().shift(RIGHT * 3)
        self.play(Create(sq), run_time=0.5)
        self.add_sound(str(wav), time_offset=0.1)
        self.play(AnimationGroup(FadeIn(c), sq.animate.shift(UP), run_time=1.0))
        self.play(LaggedStart(FadeIn(t), Indicate(sq), Rotate(c, PI), lag_ratio=0.5, run_time=1.5))
        self.next_section("loop")
        for _ in range(3):
            self.play(sq.animate.rotate(PI / 4), run_time=1 / 3)
        self.wait(0.7)
        self.remove(sq)  # zero-duration change (play run_time=0 is rejected by manim)


fps = 15
results = {"import_s": round(t_import, 3)}
with tempconfig({"frame_rate": fps, "pixel_height": 480, "pixel_width": 854, "disable_caching": True, "progress_bar": "none"}):
    # 1) timeline only
    t = time.perf_counter()
    m = Manager(Lesson()); m.evaluate(capture_timeline=True)
    results["evaluate_timeline_s"] = round(time.perf_counter() - t, 3)
    tl = m.timeline.to_dict()
    (HERE / "timeline.json").write_text(json.dumps(tl, indent=1))

    # 2) every frame drawn (preview frame cache fill)
    n = int(round(tl["duration"] * fps))
    frames = {}
    t = time.perf_counter()
    Manager(Lesson()).evaluate(frame_times=[i / fps for i in range(n)],
                               on_frame=lambda f: frames.__setitem__(f.frame_index, f.image.copy()))
    results["evaluate_all_frames_s"] = round(time.perf_counter() - t, 3)
    results["frames_expected"] = n
    results["frames_drawn"] = len(frames)
    results["frame_indices_contiguous"] = sorted(frames) == list(range(n))
    out = HERE / "frames"; out.mkdir(exist_ok=True)
    for i in (0, n // 2, n - 1):
        frames[i].save(out / f"eval_{i:04d}.png")

    # 3) one late frame only (seek cost = full replay)
    t = time.perf_counter()
    Manager(Lesson()).evaluate(frame_times=[(n - 1) / fps], on_frame=lambda f: None)
    results["evaluate_one_late_frame_s"] = round(time.perf_counter() - t, 3)

results["timeline_entries"] = [
    {k: e.get(k) for k in ("kind", "start", "end", "run_time", "name")}
    | {"line": (e.get("source") or {}).get("line"),
       "anims": [a["type"].rsplit(".", 1)[-1] for a in e.get("animations", [])]}
    for e in tl["entries"]
]
results["duration"] = tl["duration"]
print(json.dumps(results, indent=1))
