# Flow helpers and scene transitions

- **Status:** Available
- **Renderer:** Cairo (composition works on any rendered video)
- **Since:** PR #29
- **Spec:** F09 · **Backlog:** 3.4 · **ADRs:** ADR-0013 · **Source:** `src/manim_stage/flow.py`, `src/manim_stage/compose.py`, `cli.py` (`compose`)
- **Motion Canvas origin:** flow generators `all`, `sequence`, `chain`, `delay`, `loop`, `tween`, and scene transitions (`fadeTransition`, `slideTransition`, `zoomInTransition`). **Built on:** Manim's `AnimationGroup`, `Succession`, `Wait` and `FadeIn`/`FadeOut`; scenes rendered by `manim render` and joined with PyAV.

## What it is

- **Flow helpers** give Motion Canvas's vocabulary for timing, and return ordinary Manim animations. They work inside `self.play(...)` and nest in any group.
- **Enter/exit transitions** bring a scene's content in, or take it out (fade, slide, zoom), within a scene.
- **Scene sequences** join separately rendered scenes into one video with **overlapping** transitions (fade, slide, wipe). Durations are exact, no frames are dropped or duplicated, and audio stays at the right times.

## Quick start: flow helpers

```python
from manim import *
from manim_stage import all_of, chain, delay, loop, sequence, tween

class Flow(Scene):
    def construct(self):
        dots = [Dot().shift(RIGHT * i) for i in range(4)]
        sq = Square()
        self.play(sequence(0.25, *(FadeIn(d) for d in dots)))            # start every 0.25 s
        self.play(chain(Create(sq), sq.animate.shift(UP)))               # one after another
        self.play(all_of(Indicate(sq), Flash(dots[0])))                  # together
        self.play(delay(0.5, Rotate(sq, PI / 4)))                        # wait, then animate
        self.play(loop(3, lambda i: dots[i].animate.shift(DOWN)))        # repeat
        self.play(tween(1.0, lambda t: sq.set_fill(RED, opacity=t)))     # any per-frame fn

with tempconfig({"frame_rate": 10, "dry_run": True, "disable_caching": True}):
    Flow().render()
```

| Helper | Returns (Manim) | Motion Canvas |
|---|---|---|
| `all_of(*anims, **kw)` | `AnimationGroup` | `all(...)` |
| `chain(*anims)` | `Succession` | `chain(...)` |
| `sequence(interval, *anims)` | `AnimationGroup`; each starts `interval` **seconds** after the previous one | `sequence(delay, ...)` |
| `delay(seconds, anim)` | `Succession(Wait, anim)` | `delay(...)` |
| `loop(n, lambda i: anim)` | `Succession` of n animations | `loop(n, ...)` |
| `tween(run_time, fn)` | `Tween` animation calling `fn(t)`, with t going 0 → 1 through `rate_func` | `tween(duration, fn)` |
| `enter(scene, "fade"\|"slide"\|"zoom", direction)` / `exit(...)` | `FadeIn` / `FadeOut` of everything on screen | scene transitions within a scene |

All of them show up on the [timeline](timeline.md) like any Manim group, with their members on nested lanes.

## Quick start: joining scenes

`lesson.sequence.json` (schema `docs/schemas/sequence.schema.json`):

```json
{"output": "lesson.mp4", "quality": "high_quality",
 "scenes": [
   {"file": "intro.py", "scene": "Intro"},
   {"file": "sort.py", "scene": "BubbleSort", "transition": "fade", "duration": 0.5},
   {"file": "outro.py", "scene": "Outro", "transition": "slide_left", "duration": 0.6}]}
```

```bash
manim-stage compose lesson.sequence.json          # renders each scene, then joins them
manim-stage compose lesson.sequence.json -q low_quality
```

## How it works

- **Each scene renders with `manim render`** at the chosen quality, so it gets Manim's own audio mix and output pipeline. A scene can also give a ready-made `video`.
- **Transitions overlap** the two scenes, as in a video editor. A 0.5 s fade at 30 fps blends the last 15 frames of one scene with the first 15 of the next. The output has exactly `sum(scene frames) − sum(overlaps)` frames.
- **Styles:**
  - `cut`;
  - `fade`;
  - `slide_left|right|up|down`: the new scene pushes the old one out;
  - `wipe_left|right|up|down`: a hard edge reveals the new scene in place.
- **Audio:** each scene's track is placed at its scene's start and faded across the overlap, so a sound at 1.0 s into scene two plays at that scene's start + 1.0 s in the output. This is tested to one frame.
- **Encoding:** H.264 (`yuv420p`, CRF 18) with AAC audio, via PyAV. All scenes must share size and frame rate; the command checks.

## Limitations and unsupported cases

- **Shared-element transitions** (morphing one scene's object into the next scene's) aren't automatic. Put both moments in one scene and use `Transform`/`ReplacementTransform`, which is how Manim expresses object identity.
- **Masks/irises** beyond wipes and slides aren't offered.
- **Not in the Studio preview yet.** The editor previews one scene at a time; `compose` makes the combined video.

## Related

- [Timeline](timeline.md), [Export](export.md), [Audio workspace](audio.md), [CLI](cli.md).
