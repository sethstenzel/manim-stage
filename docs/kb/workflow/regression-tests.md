# Regression tests and golden frames

- **Status:** Available
- **Source:** `tests/test_regression.py`, `tests/scenes/golden.py`, `tests/golden/`, `tests/test_parity.py`
- **Spec:** §2.1, §2.10, §10.1

## What it is

These tests prove that manim-stage never changes what Manim renders. They also catch rendering changes when Manim is upgraded.

| Check | How | Catches |
|---|---|---|
| No side effects | Render the same scenes with the plain `manim` CLI, and from a process that first imports every manim-stage module. The PNGs must be **byte-identical**. | manim-stage altering Manim state on import |
| Not a Manim plugin | No `manim.plugins` entry point belongs to manim-stage | Code that would run inside every `manim render` |
| Golden frames | 3 unmodified scenes (shapes/transforms, `LaggedStart`/`Succession`, `ValueTracker` + `always_redraw`) at 320×180, 10 fps. 5 frames each, compared with the frames stored in `tests/golden/` | Rendering or timing changes from a Manim upgrade |
| Preview parity | Cached preview frames are pixel-identical to the CLI render, on the same machine | Studio preview drifting from the export |

## Running

```bash
uv run pytest tests/test_regression.py tests/test_parity.py
```

## Tolerance

Cairo builds differ slightly between operating systems in antialiasing:
- A pixel counts as changed only if a channel moves by more than 24.
- A frame fails if more than 0.1% of its pixels change.

For scale, a small dot moving between two golden frames changes about 0.5%, and a 1-pixel shift of the whole frame about 3.5%. CI passes on Windows, Linux and macOS.

Text and LaTeX are excluded from golden scenes, because glyph rendering differs per OS. Preview parity (`test_parity.py`) covers them on each machine.

## After a Manim upgrade

If golden frames fail after `upstream_sync.py bump manim ...`:
1. Inspect the differing frames. Decide whether the change is an intended upstream rendering change or a regression.
2. If intended, regenerate: `MANIM_STAGE_UPDATE_GOLDEN=1 uv run pytest tests/test_regression.py`, then commit the new `tests/golden/` frames with the pin.
3. Record the change in the sync log and in [whats-new.md](../whats-new.md).

A frame-count change (`count.txt`) means Manim's timing changed, for example through new rounding rules. Read the upstream changelog before accepting it.

## Related

- [Upstream sync](upstream-sync.md) · [Frame cache](../manim-stage/frame-cache.md)
