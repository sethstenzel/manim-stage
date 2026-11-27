# Manim: evaluate and timeline export

- **Status in Manim:** experimental. Present on the 0.30 line (our pin `main@8c258a0`), absent from 0.22.1.
- **Manim docs at the pin:** `docs/source/guides/evaluation.rst`, `docs/source/guides/timeline.rst`, `docs/source/guides/deep_dive.rst`.
- **Used by:** [Event capture](../manim-stage/event-capture.md), [Frame cache](../manim-stage/frame-cache.md) (through `manim_stage._compat`).

## What it is

`Manager.evaluate()` runs a scene's `setup`/`construct`/`tear_down` without encoding video. It can also:
- **record a timeline:** `capture_timeline=True`, then `manager.timeline`;
- **draw chosen frames:** `frame_times=[...]`, `on_frame=callback`. Each frame is the image a full render would show at that time.

The CLI equivalent of the timeline is `manim --timeline-output timeline.json --dry_run file.py Scene`.

## Quick start

```python
from manim import Circle, Create, Manager, Scene, tempconfig


class Example(Scene):
    def construct(self):
        self.next_section("intro")
        self.play(Create(Circle()), run_time=0.5)
        self.wait(0.25)


with tempconfig({"frame_rate": 4, "progress_bar": "none", "verbosity": "WARNING"}):
    manager = Manager(Example())
    manager.evaluate(capture_timeline=True)
    for entry in manager.timeline.to_dict()["entries"]:
        print(entry["kind"], entry["start"], entry.get("end"))

frames = []
with tempconfig({"frame_rate": 4, "pixel_width": 160, "pixel_height": 90,
                 "progress_bar": "none", "verbosity": "WARNING"}):
    Manager(Example()).evaluate(frame_times=[0.3], on_frame=frames.append)
print(frames[0].frame_index, frames[0].time)  # 1 0.25
```

## Frame quantization

On the 0.30 line, scene time advances in **whole frames**:
- A play of `d` seconds shows `ceil(d * fps)` frames, so `run_time=0.5` at 15 fps lasts 8 frames = 0.533 s.
- Every later event shifts by the rounding.
- Frame *i* covers `[i/fps, (i+1)/fps)`.
- Waits also round up.

manim-stage therefore stores all times as frame indices.

## Things to know

- **One evaluation per scene instance.** Create a new instance to evaluate again. Construct and evaluate under the same `tempconfig`.
- **Each evaluation runs to the end of the scene**, even after the last requested frame. A seek therefore costs one full (non-drawing) run. That is cheap: about 0.4 s for a 10 s scene.
- **The timeline lists entries in call order**, not time order. It has float seconds and no frame indices, no IDs, and no members of `AnimationGroup`/`LaggedStart`. manim-stage adds these.
- **`source.line`** is the first stack frame outside the `manim` package. Calls made through helper code outside the scene file are attributed to that helper.
- **`--format png-sequence` omits the frames of frozen `wait`s** (62 PNGs vs 72 video frames in our spike). Compare against `evaluate` frames or decoded MP4 frames, not PNG file indices.
- **The API is experimental and may change without deprecation.** manim-stage only touches it in `src/manim_stage/_compat.py`.

## Related

- [Event capture](../manim-stage/event-capture.md) · `docs/audit/manim-core.md` · `spikes/README.md`
