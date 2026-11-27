# M1 gate report: Studio MVP

- **Date:** 2026-11-27
- **Spec gate (§11 M1):** "unmodified Manim scripts are authorable in Studio, and headless exports are unchanged."
- **Verdict: PASSED.** Proceed to M2 (teaching workflow: cues, audio, `AnimatedCode`).

## Acceptance evidence

| Requirement | Evidence |
|---|---|
| F01 accept: edit an unmodified scene, save, see the updated preview, scrub, export a full-quality MP4; CLI unchanged | `tests/test_journey.py::test_edit_preview_scrub_export_unmodified_scene`. An unmodified Manim file is opened in the real editor. The test edits a colour and saves; the editor re-renders by itself and keeps the playhead, and the changed pixels are verified. It scrubs the range, then exports 1080p60 H.264 from the Studio. The export's frames match a plain `manim render` of the same file (max channel difference ≤ 2, i.e. encoder noise). |
| CLI keeps working, and output is unchanged with manim-stage installed | `tests/test_journey.py::test_plain_manim_cli_still_renders_with_manim_stage_installed`; `tests/test_regression.py` (byte-identical CLI output, golden frames on 3 OSes) |
| F02 accept: groups, `LaggedStart`, waits, sounds and sections give correct time ranges without duplicates | `tests/test_capture.py`, `tests/test_timeline_model.py::test_no_duplicates_and_everything_placed` |
| Live reload with debounce and cancel/restart; stale frames never shown | `tests/test_watcher.py`, `tests/test_service.py::test_new_render_cancels_old_and_drops_its_messages` |
| Errors: traceback and file:line, including syntax errors | `tests/test_service.py::test_scene_error_reports_file_and_line`, `tests/test_watcher.py::test_syntax_error_points_at_the_line_and_recovers_on_save`, `tests/test_studio_ui.py::test_error_shows_location_and_open_button` |
| Range selection and snapshot | `tests/test_studio_ui.py::test_export_dialog_range_command_and_run`, `test_snapshot_and_copy_frame`; `tests/test_export.py::test_snapshot_equals_preview_frame` (pixel-identical) |
| Accessibility: keyboard, accessible names, non-colour signals | `tests/test_studio_ui.py::test_every_control_has_an_accessible_name`, keyboard tests in the same file; [Studio editor → accessibility](kb/manim-stage/studio-editor.md#accessibility) |
| Packaging: installable wheel with the editor and the `manim-stage` command | CI `package` job: build, check contents, clean install with `[studio]` and the pinned Manim, run the commands |
| Cross-platform | CI: Windows, Linux, macOS × Python 3.11–3.13. The Qt tests run offscreen everywhere. |

## Measurements (spec §9)

Full tables: `docs/benchmarks.md` → "Studio editor latency".

| Target | Result | Status |
|---|---|---|
| Scrub cached frames, median ≤ 100 ms (720p) | 18 ms median, 20 ms p95, end to end in the editor (25/27 ms at 1080p) | Met |
| File-change debounce 200–500 ms, cancel stale work | 0.3 s debounce; the old revision is killed and its messages dropped | Met |
| First usable cached preview, simple 10 s 1080p scene ≤ 10 s | 8.0 s at 1080p30 with 4 workers. At 1080p60: 12.6 s for all 630 frames, first frame after 3.3 s. | Met at 30 fps; 60 fps preview is slower but streams |
| Bounded cache, LRU | Byte budget, the current revision is protected, safe with concurrent writers; `manim-stage cache` to inspect or clear | Met |
| Preview vs export agreement | Preview frames are pixel-identical to Manim's PNG output (M0). The Studio export *is* `manim render`. | Met |

## What M1 delivered

| Backlog | Feature | KB |
|---|---|---|
| 1.1 | `PreviewService`: revisions, cancel, stale-message discard, dependency-aware cache keys | [preview-service](kb/manim-stage/preview-service.md) |
| 1.2 | Live reload (polling watcher, debounce), syntax-error locations | [preview-service → live reload](kb/manim-stage/preview-service.md#live-reload) |
| 1.3 | PySide6 editor shell: scene picker, viewport, transport, log, themes, shortcuts | [studio-editor](kb/manim-stage/studio-editor.md) |
| 1.4 + MF.2/MF.3 | Manim-aware timeline: categories, rate curves, nested group lanes, Event panel, jump to source | [timeline](kb/manim-stage/timeline.md), [event-capture → metadata](kb/manim-stage/event-capture.md#animation-metadata) |
| 1.5 | Export via `manim render` (formats, `-t`, sections, `-n` range, progress, cancel, PyAV result check); Save frame and Copy frame | [export](kb/manim-stage/export.md) |
| 1.6 | `manim-stage` CLI (`studio`, `scenes`, `timeline`, `doctor`, `cache`); packaging smoke test | [cli](kb/manim-stage/cli.md) |

## Issues found and fixed during M1

1. **PySide6 6.12.0 on Python 3.11 corrupts refcounts on every signal emission**, which aborted the interpreter on Linux CI. It was reproduced in WSL. The fix pins PySide6 < 6.12 for Python 3.11 and adds a guard test (`tests/test_qt_sanity.py`). `doctor` warns about it, and it is listed as an upstream report.
2. **Qt objects finalised on runner threads** (cyclic GC). Fixed: windows are deleted on close, and no Qt call ever runs off the GUI thread (the bridge drains a queue on a GUI timer).
3. **Live reload lost the chosen preview quality.** Found by the latency benchmark; fixed with a regression test.
4. **A concurrent `trim()` could remove an empty revision folder mid-`put()`.** Fixed with a retry.
5. Watcher tests were flaky on coarse Windows clocks. Fixed by injecting the clock.

## Known limitations carried forward

- **Audio** is not played during preview and has no waveform yet (M2, 2.3).
- **The timeline is read-only.** Timing edits come with cues (M2, 2.1–2.2).
- **The OpenGL renderer** is labelled unsupported in the preview.
- **Range export snaps to whole `play`/`wait` calls** (Manim's `-n`). This is documented.
- **~3 s to first frame** is dominated by child start-up and `import manim`. A warm runner pool is planned for M4 performance work.

## Next

M2 (teaching workflow) in backlog order: 2.1 cues, 2.2 cue dragging, 2.3 audio workspace, 2.4 voiceover adapter, 2.5–2.6 `AnimatedCode`, 2.7 narrated bubble-sort demo (M2 gate). The MF items (library panel, scene-tree inspector, config panel, sections navigator, camera-aware preview) are interleaved where they support those features.
