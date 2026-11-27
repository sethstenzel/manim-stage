# Compatibility

- **Status:** Tested in CI on every pull request
- **Since:** PR #39
- **Spec:** §2.1 (Manim stays authoritative), §2.5 (preview = Manim output), §11 M4 gate · **Source:** `tests/test_compat_suite.py`, `tests/compat/scenes.py`, `tests/test_parity.py`, `tests/test_regression.py`

## What is guaranteed

| Guarantee | How it's tested |
|---|---|
| **Studio preview frames are pixel-identical to `manim render`** for unmodified scenes | `test_compat_suite.py`: ten scenes, one per Manim feature family (table below), compared frame by frame with `manim render --format png-sequence` |
| **Opting in changes nothing by itself.** A scene with `StageMixin` draws exactly what the plain scene draws. | `test_compat_suite.py::test_opting_into_stagescene_changes_no_pixels` |
| **Installing manim-stage changes nothing Manim renders** | `test_regression.py` (golden frames, rendered by the plain Manim CLI) |
| **Parallel preview workers produce the same frames as one** | `test_parity.py` |
| **Exports are deterministic** | `test_determinism.py`, `test_m2_gate.py`, `test_m3_gate.py` |

## Manim feature families in the compatibility corpus

| Scene | Covers |
|---|---|
| `Geometry` | `Square`, `Circle`, `Star`, boolean ops (`Union`, `Difference`), `Rotate` |
| `Typography` | `Text`, `MarkupText`, `Paragraph`, `TransformMatchingShapes` |
| `Graphing` | `NumberPlane`, `Axes.plot`, `MoveAlongPath`, rate functions |
| `Updaters` | `ValueTracker`, `always_redraw`, `add_updater` + `become` |
| `Composition` | `LaggedStart`, `Succession`, `Indicate`, `Transform` |
| `Images` | `ImageMobject` from a pixel array, `.animate` |
| `Sections` | `next_section` |
| `CameraMove` | `self.camera.frame.animate` (moving camera) |
| `Zoomed` | `ZoomedScene` |
| `ThreeD` | `ThreeDScene`, `Surface`, `Cube`, `move_camera` |

Add a scene to `tests/compat/scenes.py` when a feature family is missing. Every test picks it up.

## Platforms

| | Tested |
|---|---|
| OS | Windows, Linux (Ubuntu), macOS (CI matrix) |
| Python | 3.11, 3.12, 3.13 |
| Manim | pinned `main@8c258a0` (the 0.30 line; `manim --version` reports 0.22.1). New upstream versions go through the [upstream sync process](../../upstream-sync.md). |
| Qt | PySide6 6.8+, but below 6.12 on Python < 3.12 (a 6.12 regression; `manim-stage doctor` warns) |

## Not covered

- **LaTeX (`MathTex`, `Tex`)** isn't installed in CI. These scenes work through the same code path, but pixel parity isn't tested for them.
- **The OpenGL renderer** isn't used for previews (they're always Cairo, and the badge says so). Exports can use OpenGL through `manim.cfg`.
- **Frozen waits** aren't written by `--format png-sequence`. Parity for them is tested through the timeline and video exports instead.

## Related

- [Upstream sync](../../upstream-sync.md), [Benchmarks](../../benchmarks.md), [Camera-aware preview](../manim-stage/camera.md).
