# M2 gate report: teaching workflow

- **Date:** 2026-11-27
- **Spec gate (§11 M2):** "publish the end-to-end narrated bubble sort demonstration and test its headless reproducibility."
- **Verdict: PASSED.** Proceed to M3 (composition and customisation).

## Evidence

| Requirement | Evidence |
|---|---|
| Narrated bubble-sort demo, published | `examples/bubble_sort/` (lesson, placeholder-audio script, README); tutorial `docs/kb/tutorials/narrated-bubble-sort.md` |
| Headless reproducibility | `tests/test_m2_gate.py::test_headless_reproducibility`. Two independent renders of all 300 frames are byte-identical PNGs. Plain `manim render` gives a 30.0 s MP4 with an AAC track and `.srt` subtitles. |
| F03 accept: 30 s → 35 s narration, five cues adjusted visually, re-render, animations aligned without changing `wait()` calls | `tests/test_m2_gate.py::test_f03_new_take_and_five_retimed_cues`. The cues are moved with the timeline's own `plan_move` + undoable edits, and every following animation starts within one frame of its cue (spec §9). Duration follows the 35 s take, `lesson.py` is byte-identical, and plain `manim render` gives 35.0 s. |
| F04 accept: voiceover, sound effect and animation stay aligned after cue changes and export correctly | `tests/test_audio.py::test_exported_audio_matches_the_preview_mix` (placement ≤ 1 frame, correlation > 0.98); `tests/test_voiceover.py` (bookmarks are cues and move with overrides); the gate test above |
| F05 accept: 25-line bubble sort through 10 edits; stable unchanged lines; deterministic at 30/60 fps; repeated tokens, multi-line, non-ASCII | `tests/test_code_diff.py` (incl. `test_bubble_sort_through_ten_edits_is_deterministic[30/60]`), `tests/test_code.py` |
| F03 cue rules: missing/duplicate/non-monotonic/orphaned cues, drag undo/redo, persistence, headless reproduction | `tests/test_cues.py`, `tests/test_cue_edit.py`, `tests/test_studio_ui.py::test_drag_cue_saves_sidecar_rerenders_and_undoes` |

## What M2 delivered

| Backlog | Feature | KB |
|---|---|---|
| 2.1 | `self.cue()`, `cues.json`, `validate`, `bake` | [cues](kb/manim-stage/cues.md) |
| 2.2 | Cue dragging with hold/ripple, preview, undo/redo | [cues → editing](kb/manim-stage/cues.md#editing-cues-in-the-studio) |
| 2.3 | Audio workspace: clips, processing, waveforms, synced preview, editing | [audio](kb/manim-stage/audio.md) |
| 2.4 | Narration / voiceover adapter: bookmarks as cues, word timings, manim-voiceover cache import | [narration](kb/manim-stage/narration.md) |
| 2.5 | `AnimatedCode` layout, ranges, highlighting | [animated-code](kb/manim-stage/animated-code.md) |
| 2.6 | Animated code edits: diff engine, `animate_to`, `replace`/`insert`/`remove` | [animated-code → edits](kb/manim-stage/animated-code.md#animated-edits) |
| 2.7 | Narrated bubble-sort demo + gate tests | [tutorial](kb/tutorials/narrated-bubble-sort.md) |

## Issues found and fixed during M2

1. **Ligatures.** JetBrains Mono turns `==`, `->` and `!=` into ligatures, merging glyphs and breaking the token-to-glyph mapping. Ligatures are now turned off; there is a regression test.
2. **Slow text layout.** A cold Pango call costs about 3.4 s on Windows, whatever the text. `AnimatedCode` now lays out all uncached lines in one call and caches lines as arrays; Manim's system-font scan is skipped for the bundled font. The demo's cold timeline pass dropped from 43 s to 13 s, and the gate tests from 270 s to 105 s.
3. **`Mobject.copy()` cost.** Copies of SVG-derived glyphs are slow, so code edits interpolate raw point/RGBA arrays instead (10 edits: 44 s → 5 s).
4. **Source attribution.** Narration events now point at the user's line, skipping stdlib frames such as `contextlib`.
5. **Working directory.** `run_capture` now runs children in the scene's folder, so relative asset paths behave as with `manim`.

## Known limitations carried forward

- **No TTS, transcription or recording in core**, by design (spec F04). The manim-voiceover fixes for 0.30 are listed as upstream contributions.
- **Long listings take a while the first time.** About 3 s per cold Pango call on Windows; Linux and macOS are much faster.
- **Studio cue editing writes `cues.json`;** there is no Python code action to write cue times back into `at=` defaults yet.

## Next

M3 (P2) in backlog order: 3.1 derived values on `ValueTracker` (signals), 3.2 project config, variables and themes, 3.3 `expose()` inspector editing, 3.4 transitions and flow helpers, 3.5 asset manager and render presets, 3.6 M3 gate. MF items continue alongside: the library panel, scene-tree inspector and config panel.
