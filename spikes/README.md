# Spikes

Throwaway experiments that back ADR decisions. Not product code, not tested in CI.

## m0_evaluate.py / m0_compare_cli.py — Manim main `Manager.evaluate` (2026-11-26)

Environment: Windows 11, Python 3.13.5, Manim `8c258a0` (main). The scene has `Create`, `AnimationGroup`, `LaggedStart`, `add_sound`, a section, a 3-iteration loop and a frozen `wait`. Output was 854×480 at 15 fps.

```bash
uv venv --python 3.13 .venv-main
uv pip install --python .venv-main/Scripts/python.exe "manim @ git+https://github.com/ManimCommunity/manim@8c258a0082dc760d9a93671bbdfaca3cc53a6f91"
.venv-main/Scripts/python.exe -I spikes/m0_evaluate.py          # writes timeline.json, frames/
manim render -r 854,480 --fps 15 --format png-sequence --disable_caching spikes/m0_evaluate.py Lesson
.venv-main/Scripts/python.exe -I spikes/m0_compare_cli.py
```

| Measurement | Result |
|---|---|
| `import manim` | 0.68 s |
| `evaluate(capture_timeline=True)` (4.8 s scene) | 0.08 s |
| `evaluate` drawing all 72 frames | 0.42 s (contiguous indices 0–71) |
| `evaluate` drawing one late frame (seek by replay) | 0.02 s |
| Evaluated frames vs CLI `png-sequence` (frames 0, 36) | **pixel-identical** (max diff 0) |
| CLI MP4 frame count / duration | 72 / 4.8 s, which matches `evaluate` |

Findings:
- **Frame quantization is real.** `run_time=0.5` at 15 fps lasts 8 frames (0.5333 s). Every later event shifts, so cue math must be done in frame indices (ADR-0005/0006).
- **Loops repeat the same source line** (line 31 three times). This confirms that occurrence-indexed IDs are needed.
- **The timeline has no nested children.** `AnimationGroup` and `LaggedStart` show as single entries, so the private-listener shim is needed for child ranges.
- **The sound entry is emitted out of order.** The sound at 0.633 s is listed before the play that starts at 0.533 s, because entries follow call order, not time order. Our adapter must sort by time.
- **`png-sequence` omits frozen-wait frames** (62 PNGs vs 72 movie frames), so PNG index ≠ movie frame index after a frozen wait. Golden tests should compare against `evaluate` or decoded MP4 frames.
- **`play(run_time=0)` raises `ValueError`.** Zero-duration events exist only as non-play calls (`add`, `remove`, sections, sounds).
- This scene is trivial. Latency on heavy scenes (Tex, many mobjects, 1080p) must be measured in backlog item 0.6.
