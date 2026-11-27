# Event capture

- **Status:** Available
- **Renderer:** Cairo (OpenGL untested)
- **Since:** PR #2
- **Spec:** F02 · **ADRs:** ADR-0005 · **Source:** `src/manim_stage/capture.py`, `src/manim_stage/events.py`, `src/manim_stage/_compat.py`

## What it is

`capture()` runs an **unmodified** Manim scene once, without encoding video. It returns a `SceneTimeline`: every `play`, `wait`, section, sound and caption, with frame-exact start and end. Members of `AnimationGroup`, `LaggedStart` and `Succession` are listed as nested `animation` events. This is the data the Studio timeline will draw.

## Quick start

```python
from pathlib import Path

from manim import tempconfig

from manim_stage.capture import capture
from manim_stage.runner import load_scene_class

Path("demo_scene.py").write_text('''
from manim import *

class Demo(Scene):
    def construct(self):
        s = Square()
        self.play(Create(s), run_time=0.5)
        self.play(LaggedStart(FadeIn(Circle()), s.animate.shift(RIGHT), lag_ratio=0.5))
        self.next_section("end")
        self.wait(0.3)
''')

with tempconfig({"frame_rate": 15, "pixel_width": 320, "pixel_height": 180,
                 "progress_bar": "none", "verbosity": "WARNING"}):
    timeline = capture(load_scene_class(Path("demo_scene.py"), "Demo"))

for e in timeline.events:
    indent = "  " * e.track.count("/")
    print(f"{indent}{e.kind:9} [{e.start_frame:3}, {e.end_frame:3})  {e.label}  id={e.id}")
assert timeline.duration_frames == timeline.events[-1].end_frame
```

Output:

```text
play      [  0,   8)  Create(Square)  id=Demo:play:demo_scene.py:7#0
play      [  8,  31)  LaggedStart(Group)  id=Demo:play:demo_scene.py:8#0
  animation [  8,  23)  FadeIn(Circle)  id=Demo:play:demo_scene.py:8#0/0
  animation [ 16,  31)  .animate(Square)  id=Demo:play:demo_scene.py:8#0/1
section   [ 31,  31)  end  id=Demo:section:demo_scene.py:9#0
wait      [ 31,  36)  wait  id=Demo:wait:demo_scene.py:10#0
```

The two 1 s members with `lag_ratio=0.5` give the `LaggedStart` a length of 1.5 s, which is 23 frames at 15 fps. The second member starts halfway through the first.

Call `capture()` inside the `tempconfig` that sets frame rate and resolution, and import the scene under that same config: Manim picks Cairo vs OpenGL base classes when a class is defined. `load_scene_class` imports the file as a fresh module each time. To run the scene in a separate process instead, use the [Scene runner](runner.md).

## How it works

- **Times are frame indices.** Ranges are half-open: `[start_frame, end_frame)`. Seconds = `frame / timeline.frame_rate`. Manim rounds every play and wait **up** to whole frames (see [frame quantization](../manim/evaluate-and-timeline.md#frame-quantization)), so `run_time=0.5` at 15 fps lasts 8 frames.
- **Plays and waits** (`track="main"`) are contiguous. Each starts where the previous one ended, and the last ends at `duration_frames`.
- **Event IDs** are `"{scene}:{kind}:{file}:{line}#{occurrence}"`. Occurrence counts repeats of the same call site in execution order, so a `play` inside a 3-iteration loop gives `#0`, `#1`, `#2`. IDs are deterministic across runs of the same source. Nested animations append `/index`.
- **Markers:**
  - Sections are zero-length (`start_frame == end_frame`) on track `sections`.
  - Sounds are on track `audio`. A sound can start between frames, so its exact start is kept in `meta["start_seconds"]`.
  - Captions are on track `captions`.
- **Ordering:** events are sorted by `start_frame`, stable. Manim itself lists entries in call order, where a sound with `time_offset` can appear before plays that start earlier.

### Nested animations

Each member's span is computed the way Manim samples it:
- frame *k* of a play is at `k / fps`;
- each top-level animation gets `alpha = t / run_time`;
- a group maps that through its `rate_func` to group time, and a member is running while `start ≤ group time` and its own alpha `< 1`.

Groups nest recursively (`track="main/1"`, `"main/2"`, …). A test checks these spans against per-frame opacities recorded inside Manim.
- A play with **one** group shows that group's members directly under the play.
- A play with **several** animations shows each of them, which also covers different `run_time`s in one `play`.

## Options

| Argument | Default | Meaning |
|---|---|---|
| `scene_cls` | — | The scene class (not an instance); a fresh instance is evaluated |
| `frame_times` | `None` | Scene times (seconds) whose frames to draw during the same pass |
| `on_frame` | `None` | Called with each drawn frame (`.frame_index`, `.time`, `.image`) |

`SceneTimeline.to_dict()` / `from_dict()` give the versioned JSON (`"schema": "manim_stage.timeline", "version": 1`).

## Limitations and unsupported cases

- **Needs the Manim 0.30 line** (`Manager.evaluate`). `manim_stage._compat.require_supported()` explains what is missing on older Manim.
- **IDs follow source lines.** Editing lines above a call changes its ID. Stable IDs across edits are planned with cues (F03).
- **Not hashed:** imported helper modules and assets. Only the scene file's hash is recorded.
- **`play(run_time=0)`** is rejected by Manim itself (`ValueError`).
- **Custom `Animation` subclasses** that override `interpolate` with non-standard timing are shown with their outer span only.
- **Wrappers:** if code outside the scene file calls `self.play` for you, Manim records *that* file and line as the source.

## Related

- [Scene runner](runner.md) · [Frame cache](frame-cache.md) · [Manim evaluate and timeline export](../manim/evaluate-and-timeline.md)
- Motion Canvas equivalent: its timeline shows scenes, slides, time events and audio, with no per-animation tracks. See [equivalents](../reference/motion-canvas-equivalents.md).
