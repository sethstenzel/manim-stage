# M3 gate report: composition and customisation

- **Date:** 2026-11-27
- **Spec gate (§11 M3):** "complete multi-scene lesson with configurable visuals and deterministic exports."
- **Verdict: PASSED.** Proceed to M4 (ecosystem and polish).

## Evidence

| Requirement | Evidence |
|---|---|
| Multi-scene lesson with configurable visuals | `examples/lesson_series/` and tutorial `docs/kb/tutorials/multi-scene-lesson.md`: three scenes using the project theme, a project variable, signals, flow helpers, an exposed property, and a composed sequence with two transitions |
| Deterministic exports | `tests/test_m3_gate.py`: two compositions of the same project decode to pixel-identical frames |
| Configurable visuals without source edits | Same test: changing the theme accent and the `speed` variable restyles and re-paces all three scenes. A saved inspector edit (title colour) appears in the export. |
| F06 accept (signals) | `tests/test_signals.py::test_array_signal_drives_bars_labels_and_indicator` |
| F07 accept (themes) | `tests/test_project.py::test_changing_the_theme_updates_every_scene_without_source_edits` |
| F08 accept (inspector) | `tests/test_inspector.py::test_saved_edit_is_reproduced_by_plain_manim_render`; UI journey in `tests/test_studio_ui.py` |
| F09 accept (transitions) | `tests/test_flow.py::test_three_real_scenes_two_transitions_with_audio`: exact frame counts, audio aligned to one frame |
| F10 accept (media/export) | `tests/test_assets.py`; `tests/test_export.py` (range export, metadata, frames vs reference, audio) |

## What M3 delivered

| Backlog | Feature | KB |
|---|---|---|
| 3.1 | `Signal` (a ValueTracker), `computed`, `bind`, `effect` | [signals](kb/manim-stage/signals.md) |
| 3.2 | Project theme + typed variables; Project panel | [project](kb/manim-stage/project.md) |
| 3.3 / MF.5 | Inspector, `expose()`, preview/save/undo/copy-as-Python | [inspector](kb/manim-stage/inspector.md) |
| 3.4 | Flow helpers; enter/exit; `manim-stage compose` | [transitions](kb/manim-stage/transitions.md) |
| 3.5 / MF.9 | Assets inventory/validation, render presets, Assets/environment panel | [assets](kb/manim-stage/assets.md) |
| 3.6 | Multi-scene lesson + gate test | [tutorial](kb/tutorials/multi-scene-lesson.md) |

## Issues found and fixed during M3

1. **Preview overrides were cached under the old revision.** A temp overrides file in the excluded cache folder wasn't a dependency, so the cache reused old frames. Sidecars redirected through `MANIM_STAGE_*` now always join the cache key.
2. **Bound updaters didn't re-place labels.** `bind(update=...)` now also runs when the bound properties change, because a new number changes the label's width.
3. **Placeholders in the inspector tree.** Manim's empty placeholder Mobjects from `wait()` are no longer listed.

## Known limitations carried forward

- **Shared-element transitions** across scenes are expressed with Manim `Transform` inside one scene, not inferred.
- **The inspector snapshots one frame.** Each inspection costs one replay.
- **Fonts for `Tex`/`MathTex`** come from LaTeX templates (MF.10).

## Next

M4: 4.1 editor plugin SDK, 4.2 educational helpers (call stack, data-structure layouts, graphs, sequence diagrams, trace-driven animation), 4.3 interactive demo parameters and rendered web playback, 4.4 performance, migration guide, examples and packaging. The remaining MF items are 1 (catalog), 4 (library panel), 6 (config panel), 7 (sections navigator), 8 (camera-aware preview) and 10 (text/LaTeX helpers).
