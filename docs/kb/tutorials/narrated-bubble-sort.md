# Tutorial: a narrated bubble-sort lesson

- **Status:** Available (the M2 end-to-end demo)
- **Since:** PR #25
- **Spec:** §11 M2 gate, F03 accept, F04, F05 · **Source:** `examples/bubble_sort/`

This walks through `examples/bubble_sort/`, a 30-second lesson that uses everything M2 added:
- [narration](../manim-stage/narration.md) for the recorded voice and subcaptions;
- [named cues](../manim-stage/cues.md) for when things happen;
- [AnimatedCode](../manim-stage/animated-code.md) for the algorithm, its highlights and an animated edit.

The scene is plain Manim otherwise, and contains no `self.wait(...)` timing.

## 1. Get narration

manim-stage doesn't synthesise speech. Record `narration.wav` (any format PyAV reads works), or make a placeholder:

```bash
cd examples/bubble_sort
python make_audio.py              # 30 s speech-like placeholder → narration.wav
```

## 2. The scene, in short

```python no-run
class BubbleSortLesson(StageScene):
    def construct(self):
        ...
        with self.narration("voice", file="narration.wav", text=SCRIPT, wait=False) as voice:
            self.play(Write(title), FadeIn(code), run_time=1.5)

        self.cue("show_array", at=3.0, description="'walks the array'")
        self.play(Create(bars))
        self.cue("compare", at=6.0)
        self.play(code.highlight_lines(5))
        ...
        self.cue("optimise", at=20.0)
        self.play(code.animate_to(OPTIMISED))       # the early-exit version, token by token
        voice.wait_for_end()                         # hold until the narration ends
```

Each `cue(..., at=…)` is a default. The real times come from `.manim-stage/cues.json` once you move a cue.

## 3. Render it, or open it in the Studio

```bash
manim render lesson.py BubbleSortLesson -ql      # plain Manim: video + audio + .srt subtitles
manim-stage studio lesson.py BubbleSortLesson    # preview, scrub, retime
```

In the Studio:
- the **Cues** lane shows `show_array`, `compare`, `swap`, `largest_done` and `optimise`;
- the **Audio** lane shows the narration's waveform;
- the **Captions** lane shows the script.

## 4. Re-time to a new take

Say you re-record and the new take is 35 seconds, with pauses in new places:

1. Replace `narration.wav` with the new recording. The Studio re-renders by itself, because the file is a dependency of the scene.
2. Play it and **drag each cue** to where the voice says the matching words. Hold **Shift** to ripple later cues along.
3. Every drag is saved to `.manim-stage/cues.json` and can be undone (Ctrl+Z).
4. `manim render lesson.py BubbleSortLesson` renders the new timing; it reads the same sidecar.

No Python changes. This is the spec's F03 acceptance scenario, and `tests/test_m2_gate.py` runs it automatically:
- it swaps in a 35 s take and moves five cues through the same planning code the timeline uses;
- it checks that every animation after a cue starts within one frame of it;
- it checks that `lesson.py` is byte-for-byte unchanged and that `manim render` produces a 35 s video.

## 5. Make it reproducible

- `manim-stage validate lesson.py` checks the cues. `manim-stage bake lesson.py` pins them.
- Commit `lesson.py`, `.manim-stage/cues.json` and the recording.
- Renders are deterministic: two independent renders give pixel-identical frames (tested).

## Related

- [Named cues](../manim-stage/cues.md), [Narration](../manim-stage/narration.md), [AnimatedCode](../manim-stage/animated-code.md), [Timeline](../manim-stage/timeline.md), [Audio workspace](../manim-stage/audio.md).
