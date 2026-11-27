# Porting log: Motion Canvas → Manim

A running, reviewable record of **how Motion Canvas features are brought into Manim**: the decisions taken, what was implemented and where, and the processes used. Updated in every PR that ports, designs or changes a feature (see "How this file is maintained").

- **Engine:** Manim (pinned in `upstreams.json`) stays the renderer, scene model and source of truth.
- **Reference:** Motion Canvas (pinned `v3.17.2`) is studied for behaviour only. No code or assets are copied (spec §2.9, `NOTICE`).
- **Language:** everything is Python, including the editor (PySide6, ADR-0012).
- **Vocabulary:** Manim's (ADR-0013). Motion Canvas concepts are ported as Python APIs built on Manim primitives.

Related: ADRs in `docs/architecture-decisions.md`, backlog in `docs/backlog.md`, user docs in `docs/kb/`, concept table in `docs/kb/reference/motion-canvas-equivalents.md`.

## 1. Porting method

How each Motion Canvas feature is ported. Every feature goes through these steps; the per-feature records in §3 cite them.

1. **Study the behaviour, not the code.** Read Motion Canvas docs and, if needed, its source at the pinned tag (`.upstream/motion-canvas`) to understand *behaviour*. Write findings in our own words in `docs/audit/motion-canvas.md`. Never paste its source.
2. **Find the Manim equivalent first.** Check the pinned Manim for an existing feature (`docs/capability-audit.md`). Prefer wrapping or extending it over adding something new.
3. **Choose the Manim-shaped design.** Map the concept onto Manim primitives (`Scene`, `Mobject`, `Animation`, `play`/`wait`, `rate_func`, `ValueTracker`, updaters, sections, `config`). Keep the Motion Canvas concept available as a Python API with a `snake_case` name. Record the choice as an ADR when it affects public API or architecture.
4. **Decide what to improve.** Note Motion Canvas weak spots found in step 1 (e.g. silent drops, non-atomic writes) and fix them in the port.
5. **Implement opt-in.** Unmodified Manim scenes must render identically (golden tests). Manim internals only via `_compat.py`.
6. **Test.** Unit tests, a golden or parity test if rendering is involved, and a KB example that CI executes.
7. **Document.** KB page (with "Motion Canvas origin" and "Built on" lines), row in the concept table, `whats-new.md` entry, and a record in §3 of this file.

## 2. Decision log

Newest first. One line per decision; details in the linked ADR or PR.

| Date | Decision | Why | Where |
|---|---|---|---|
| 2026-11-27 | Compatibility suite = corpus of unmodified Manim scenes per feature family, each pixel-compared with `manim render`, plus StageMixin opt-in no-op check; third-party examples use public API only | M4 gate; spec §2.1/§2.5 | PR #39 |
| 2026-11-27 | Text/LaTeX helpers generate Manim-native calls (`Text(font=)`, `MathTex(tex_to_color_map=, tex_template=)`); project TeX template applied with Manim's `set_default` and restored at tear_down; LaTeX preview in a child process | MF.10; Manim terminology and mechanisms; never block the editor on LaTeX | PR #38 |
| 2026-11-27 | Camera state recorded per rendered frame as a PNG text chunk (survives the frame cache; no protocol change); viewport maps clicks/selection through the camera frame; badge names scene type + camera | Manim 0.30: every camera frame is animatable; spec §2.7 no silent renderer substitution | PR #37 |
| 2026-11-27 | Config panel edits Manim's own `manim.cfg` [CLI] (not a new sidecar), so plain Manim, preview and export agree; `manim.cfg` joins the preview cache key. Sections navigator is built on `next_section`/`--save_sections`; a section export is an in/out range | Manim methodology first; no parallel config format | PR #36 |
| 2026-11-27 | Manim feature catalog is introspected from the installed `manim` (no hand-kept lists); grouped by Manim's package layout; `ease_*` rate functions listed with `rate_functions.` prefix; Library tab copies snippets only (never edits scenes) | ADR-0011; editor must know all Manim features and pick up new upstream ones | PR #35 |
| 2026-11-27 | Demo parameters are a separate, never-saved channel (`demo.param`, `MANIM_STAGE_DEMO` override file) reusing project-variable types; exports use defaults unless baked. Web playback = static page over the rendered MP4; chapters from Manim sections; captions embedded as VTTCues so it works from file:// | F12: distinguish editor-time preview from linear export; no server, no scene code in the browser | PR #34 |
| 2026-11-27 | Educational helpers are Manim VGroups whose methods return animations; tree layout feeds Manim's `Graph` instead of a new graph class; traces recorded first (trusted function, JSON) then replayed with `play_trace` | F12; audit: Manim has `Graph`/`Table` but no array/stack/sequence helpers; no live execution in the viewer | PR #33 |
| 2026-11-27 | Plugin SDK v1: entry points + api_version handshake; hooks for lanes/panels/inspector/commands/exporters through a narrow StudioAPI; per-hook failure isolation | F11; MC has no handshake; keep editor stable | PR #32 |
| 2026-11-27 | M3 gate passed (themed three-scene lesson; deterministic compose; restyle via project only) | Spec §11 M3 | PR #31 |
| 2026-11-27 | Asset validation = static scan resolved with Manim's rules + audio clips + fonts; presets map to Manim CLI flags | Fail before rendering; no second path resolver to drift from Manim | PR #30 |
| 2026-11-27 | Flow helpers return Manim groups (`sequence` in exact seconds); cross-scene transitions composed after `manim render` with overlap semantics | MC vocabulary, Manim objects; Manim renders scenes separately | PR #29 |
| 2026-11-27 | Inspector = replay-to-frame snapshot of Mobject families; `expose()` opt-in edits saved to `properties.json`, previews via env-redirected temp file (always a cache dependency) | F08 with headless reproduction; no source mutation; correct cache invalidation | PR #28 |
| 2026-11-27 | Theme + typed variables in `project.json`; `var()` read = opt-in to editing; StageScene applies background/font and restores; runner reports used variables | F07 in Manim terms; deterministic across CLI/Studio; no source edits to restyle | PR #27 |
| 2026-11-27 | `Signal` is a `ValueTracker` (values flattened into points); `computed` lazy+cached with tracking stack; `bind`/`effect` change-only updaters disposed at scene end | Manim concept kept (ADR-0013); `.animate` works for free; no per-frame recompute | PR #26 |
| 2026-11-27 | M2 gate passed. AnimatedCode: ligatures off, all uncached lines in one Pango call, no system-font scan; `run_capture` cwd = scene folder | Exact glyph↔char mapping; a cold Pango call costs ~3.4 s on Windows; relative assets behave like `manim` | PR #25 |
| 2026-11-27 | Code diff = patience lines → token LCS + moved lines + overrides + ambiguity warnings; `CodeEdit` interpolates raw arrays; line-glyph cache | MC behaviour plus explicit control; deterministic and fast enough for many edits | PR #24 |
| 2026-11-27 | AnimatedCode: token = VGroup of glyphs; one MarkupText per line; marker glyph for exact grid; VectorizedPoint anchors; bundled JetBrains Mono; 1-based lines/cols | Fast, exact, OS-independent layout that survives transforms; editor-style coordinates | PR #23 |
| 2026-11-27 | Voiceover = `self.narration()` on add_sound/add_subcaption/cues; bookmarks are cues `<name>.<mark>`; no TTS in core; manim-voiceover cache importer instead of a runtime dependency | manim-voiceover breaks on 0.30; keep concepts (ADR-0013); draggable bookmarks | PR #22 |
| 2026-11-27 | Clip edits store the whole clip list per undo step; imports copied into `assets/audio/`; silent clips shown on the timeline | Exact undo; portable project-relative paths (§8); muted clips stay editable | PR #21 |
| 2026-11-27 | Audio clips = cached processed copies added via `add_sound` in `StageMixin.setup()`; preview mix from timeline sound events; playback via sounddevice | Manim mixes the final audio (spec §2.1); non-destructive (F04); avoids the PySide6-Addons dependency | PR #20 |
| 2026-11-27 | Cue drag: hold (bounded by next cue's wait) vs ripple (Shift); undo via QUndoStack; atomic write + immediate render + watcher acknowledge; new sidecars at 60 fps | Prevent negative waits in the UI as well as the resolver; exact at 15/30/60 fps | PR #19 |
| 2026-11-27 | `cue()` is a mixin method issuing `Scene.wait`; name-based cue IDs; sidecar read by plain `manim render`; negative waits are errors | Manim terms (ADR-0013); headless parity (ADR-0006); MC's silent clamping/dropping avoided | PR #18 |
| 2026-11-27 | M1 gate passed; live reload reuses the last render settings; requested scene renders before discovery finishes | Gate evidence in `docs/m1-gate-report.md`; the reload bug was found by the latency benchmark | PR #17 |
| 2026-11-27 | Export = visible `manim render` command; range via `-n` snapped to whole calls; PyAV result check | Manim stays the renderer (spec §2.1); reproducible headlessly (§13); no lossy re-cut | PR #15 |
| 2026-11-27 | PySide6 < 6.12 on Python 3.11 (6.12.0 drops None/True refs per signal on 3.11/Linux → abort); guard test | Found via Linux CI SIGABRT; reproduced in WSL; 6.11.3 and 3.12+ clean | PR #14 |
| 2026-11-27 | Background → GUI events via a deque drained by a GUI timer; windows delete on close | No cross-thread Qt calls; Qt objects never finalised on runner threads | PR #14 |
| 2026-11-27 | Timeline lanes by nesting depth with row packing; category colour + text label + rate curve per bar; Event panel; read-only until cues | Shows *what* Manim does, not just when; overlaps visible (spec F02); no colour-only signals (§9) | PR #14 |
| 2026-11-27 | Classify animations by Manim's own module layout (`manim.animation.creation` → creation, …) and sample rate functions in the runner | Categories stay correct for subclasses and new upstream animations; editor never imports user code | ADR-0011, PR #13 |
| 2026-11-27 | Editor shell: QMainWindow + custom QPainter widgets; own drawn icons; preview quality = Manim quality presets; preferences in an INI file | Python-only (ADR-0012); Manim vocabulary (ADR-0013); no third-party icon assets | PR #12 |
| 2026-11-27 | Live reload by polling `stat()` of the scene + dependencies (no watchdog dependency), 0.3 s debounce | Small watched set; identical behaviour on all OSes; handles atomic-rename saves | PR #11 |
| 2026-11-27 | Revision key includes every local module/asset the scene opened (audit hook, PEP 578); service drops messages from superseded revisions | MC's Vite HMR knows the module graph; Manim scenes need an equivalent so edits to helpers invalidate cached frames | ADR-0010, PR #10 |
| 2026-11-27 | Port MC concepts as Python APIs on Manim primitives (`Signal` is a `ValueTracker`, `all_of`/`sequence`/`chain` return Manim groups, `self.cue` is a named `wait`) | Owner: keep Manim's abstractions and terms, keep MC concepts accessible | ADR-0013 |
| 2026-11-27 | Editor in Python + PySide6, in a `[studio]` extra | Owner: one cohesive Python application, including the editor | ADR-0012 |
| 2026-11-27 | No network server; in-process `PreviewService` controls runner processes | A Python editor in-process makes a socket unnecessary attack surface | ADR-0010 |
| 2026-11-27 | Editor surfaces all Manim features via an introspected catalog with a coverage test | New upstream Manim features appear automatically; unclassified ones fail CI | ADR-0011 |
| 2026-11-27 | ADRs 0004–0009 accepted | Owner | `docs/architecture-decisions.md` |
| 2026-11-26 | Cached-frame seeking (not MC-style JS replay); timeline sent before frames; parallel drawing | MC re-runs the scene in the browser; Manim can't seek, so we cache frames. Meets §9 targets | ADR-0007, PR #4 |
| 2026-11-26 | Runner = fresh child process per revision, JSON-lines | Manim holds process-global state; no safe reload | ADR-0004 |
| 2026-11-26 | Timeline from Manim's own `Manager.evaluate` timeline + one run-loop listener | MC computes its timeline in a non-drawing pass; Manim 0.30 has an equivalent | ADR-0005 |
| 2026-11-26 | Target Manim 0.30 line | 0.22's clock depends on cache state; 0.30 is frame-quantized | ADR-0003 |
| 2026-11-26 | Standalone repo, Manim as a dependency, MC as reference only | A fork can't track two parents; spec forbids a hard fork | ADR-0001 |

## 3. Feature records

One record per Motion Canvas feature. Status: **Ported** (implemented and tested), **In progress**, **Designed** (ADR exists), **Not started**.

### Timeline (MC: editor timeline built from a non-drawing pass)
- **Status:** Ported (data M0; UI 1.4 + MF.3). Editing by drag comes with cues (2.2).
- **MC behaviour:** one fast pass over the scene computes durations, slide and time-event positions; the timeline shows scenes, slides, time events and audio.
- **Manim mapping:** `Manager.evaluate(capture_timeline=True)` gives play/wait/section/sound entries; a run-loop listener (`_compat.py`) records frame-exact play ranges; nested `AnimationGroup`/`LaggedStart` child spans are computed from `rate_func`, `lag_ratio` and run times.
- **Improvements over MC:** per-animation and nested tracks; frame-integer time model (no float drift); stable event IDs `scene:kind:path:line#occurrence`; each event knows its Manim animation class, category (from Manim's `manim.animation.*` module layout), `.animate` method chain, rate function and its sampled curve, lag ratio and target Mobject (MF.2), so the timeline can show *what* happens, not just *when*.
- **UI (1.4, MF.3):** MC's timeline track rows become lanes named in Manim terms (Sections, Animations, Level n for group members, Audio, Captions). Overlapping group members are packed into rows (greedy interval partitioning), so `AnimationGroup` members never hide each other. Bars are coloured and labelled by Manim category and draw their sampled `rate_func`. An Event panel explains the selected call in Manim vocabulary. Selection is kept across re-renders via stable IDs. Layout is Qt-free (`timeline_model.py`) and unit-tested.
- **Implementation:** `src/manim_stage/capture.py`, `events.py`, `_compat.py`, `catalog.py`; UI `studio/timeline_model.py`, `studio/ui/timeline.py`, `studio/ui/event_panel.py`. Tests: `tests/test_capture.py`, `tests/test_catalog.py`, `tests/test_timeline_model.py`, `tests/test_studio_ui.py`. KB: `event-capture.md`, `timeline.md`.

### Seeking / preview (MC: replay the scene in the browser to any frame)
- **Status:** Ported for cached frames (P1). P3 live scrubbing not feasible (no Manim state snapshot).
- **Manim mapping:** frames drawn by Manim through `evaluate(on_frame=…)` in child processes into a content-addressed LRU disk cache.
- **Improvements over MC:** preview is pixel-identical to the final render; parallel drawing.
- **Implementation:** `runner.py`, `framecache.py`. Tests: `test_runner.py`, `test_parity.py`. KB: `frame-cache.md`, `runner.md`.

### Time events / `waitUntil` (MC: named, draggable waits)
- **Status:** Ported (2.1 API/sidecar/CLI; 2.2 timeline dragging).
- **MC behaviour:** `yield* waitUntil("event")` pauses the scene until the event's time. Times are absolute (scene-relative), live in the scene's `.meta` file, and are dragged on the timeline. An event without a stored time waits 0. Negative waits are clamped in the editor only.
- **Manim mapping:**
  - `self.cue("name", at=, after=, description=)` on `StageScene`, or on any Manim scene via `StageMixin` (`MovingCameraScene`, `ThreeDScene`, …). It issues a plain `Scene.wait` for the remaining frames.
  - `at=` means absolute seconds, `after=` is relative like `wait()`, and neither makes a marker.
  - Overrides are in `.manim-stage/cues.json` as absolute frames at a stated frame rate, rescaled to the render rate.
- **Improvements over MC:**
  - explicit defaults (`at`/`after`) in code;
  - errors with file:line for negative waits, whether the default or the override is at fault (MC only clamps in the UI);
  - duplicates and invalid names are errors;
  - orphaned overrides warn and are kept as tombstones (MC drops them silently);
  - atomic writes with a backup and corruption fallback;
  - `validate`/`bake` CLI;
  - plain `manim render` reads the sidecar (headless reproducibility);
  - name-based IDs, so moving the call keeps the timing.
- **Editing (2.2):** MC drags time events and ripples later ones in its timeline. Ported with explicit modes and constraints:
  - **hold** (default): bounded by the next cue's wait, so no negative waits are possible;
  - **ripple:** Shift;
  - a live preview of shifted animations;
  - every edit is a `QUndoStack` command that rewrites the sidecar atomically and re-renders, with the watcher echo suppressed;
  - keyboard nudge and an exact-time field for accessibility;
  - the planning rules are a Qt-free `plan_move` with unit tests.
- **Implementation:** `src/manim_stage/cues.py` (store, resolver, Manim-free), `studio/cue_edit.py` (drag planning, undoable edits), `scene.py` (`StageMixin`, `StageScene`), `capture.py` (`cue` events, wait attribution), `cuetools.py` + `cli.py` (`validate`, `bake`), and the timeline Cues lane. Tests: `tests/test_cues.py`. KB: `docs/kb/manim-stage/cues.md`.

### Narration / voiceover (Manim ecosystem: manim-voiceover; MC: none)
- **Status:** Ported (2.4).
- **Ecosystem behaviour:** manim-voiceover's `with self.voiceover(text=...) as tracker`:
  - synthesises speech with a TTS service and adds it with `add_sound`;
  - adds subcaptions and waits for the end;
  - maps `<bookmark mark/>` tags to times via TTS word boundaries or Whisper.
  - It doesn't run on Manim 0.30, has no pre-recorded audio (#100) and no manual bookmark times (#113).
- **Manim mapping:** `StageMixin.narration(name, file=…, text=…)` built on `add_sound`, `add_subcaption`, `wait` and named cues:
  - `n.wait_until(mark)` is `self.cue(f"{name}.{mark}", at=…)`;
  - bookmark defaults come from explicit times, word timings or a linear text estimate;
  - a manim-voiceover `cache.json` importer reuses its generated audio and word boundaries.
- **Improvements:**
  - works with recordings;
  - bookmarks are draggable, validated and sidecar-persisted cues;
  - runs on 0.30;
  - no TTS, recording or recognition in core (spec F04).
- **Implementation:** `src/manim_stage/voiceover.py`, `scene.py` (`narration`), `capture.py` (narration tagging). Tests: `tests/test_voiceover.py`. KB: `docs/kb/manim-stage/narration.md`.

### Code block and code animation (MC: `Code` node, token diff)
- **Status:** Ported (2.5 layout and ranges; 2.6 animated edits).
- **MC behaviour:**
  - `Code` renders highlighted code with a monospace grid;
  - `lines()`, `word()` and `findFirstRange()` address ranges;
  - `selection` dims everything outside it;
  - edits tween between versions with a token diff.
- **Manim mapping:**
  - `AnimatedCode(VGroup)` holds one `VGroup` of glyphs per Pygments token, so every Manim animation applies to code parts;
  - one `MarkupText` (Pango) call per line with coloured, bold and italic spans;
  - a full-block marker glyph pins column 0 and the baseline of each line, so glyphs sit on an exact grid;
  - two `VectorizedPoint` anchors keep the grid valid after transforms;
  - ranges are `CodeRange`s, 1-based like editors;
  - highlighting returns Manim animations (`set_opacity`).
- **Improvements over MC:**
  - any Pygments language and style;
  - a bundled font (JetBrains Mono, OFL), so layout is identical across OSes;
  - ranges plug into any Manim animation (`code.get(range)`).
- **Edits (2.6):**
  - MC tweens code with a token-level patience diff: unchanged tokens slide, others cross-fade. Ported as `CodeEdit(Animation)`:
    - a line-level patience diff first, then a token LCS inside changed regions;
    - moved-line detection;
    - `mapping=` overrides and ambiguity warnings;
    - `replace`/`insert`/`remove` pin tokens outside the edit.
  - New versions lay out on the old grid, so unchanged tokens are pixel-stable.
  - Kept tokens keep their highlight level.
  - On finish the mobject *becomes* the new code (tokens, source, glyphs).
  - **Performance:** interpolation works on raw point and RGBA arrays (no `Mobject.copy()`, which deep-copies SVG state), and line glyphs are cached as arrays (10 edits: 44 s → 5 s).
- **Implementation:** `src/manim_stage/code.py`, `code_diff.py`, `src/manim_stage/fonts/`. Tests: `tests/test_code.py`, `tests/test_code_diff.py`. KB: `docs/kb/manim-stage/animated-code.md`.

### Signals (MC: `createSignal`, computed, effects)
- **Status:** Ported (3.1).
- **MC behaviour:**
  - signals are callable getters/setters;
  - `createComputed` is lazy and cached, with automatic dependency tracking;
  - node properties accept signals, so views follow state;
  - tweening a signal animates everything bound to it.
- **Manim mapping:**
  - `Signal` **subclasses `ValueTracker`**: numbers, lists, arrays and colours are flattened into the tracker's points, so Manim's `.animate.set_value` interpolates them unchanged;
  - `computed` is a pull-based cache over a global tracking stack, with cycle detection;
  - `bind`/`effect` are Manim updaters that only act when their inputs changed;
  - `StageMixin` disposes them at `tear_down`.
- **Improvements over MC:**
  - works with every existing `ValueTracker` idiom;
  - `align=` keeps edges fixed when resizing (bars on a baseline);
  - purity check and cycle-chain errors;
  - deterministic pull order for preview/export parity.
- **Implementation:** `src/manim_stage/signals.py`, `scene.py`. Tests: `tests/test_signals.py` (including the F06 acceptance array scene). KB: `docs/kb/manim-stage/signals.md`.

### Flow helpers (MC: `all`, `sequence`, `chain`, `delay`, `loop`, `tween`)
- **Status:** Ported (3.4).
- **Manim mapping:**
  - `all_of` → `AnimationGroup`; `chain` → `Succession`;
  - `delay` → `Succession(Wait, anim)`;
  - `sequence(interval, ...)` → `AnimationGroup` of delayed members. It uses exact seconds, like MC, rather than `LaggedStart`'s ratio of run time;
  - `loop` → `Succession`;
  - `tween(run_time, fn)` → a small `Animation` calling `fn(rate_func(alpha))`.
  - Everything returns plain Manim animations, so they nest and show on the timeline.
- **Implementation:** `src/manim_stage/flow.py`. Tests: `tests/test_flow.py`. KB: `docs/kb/manim-stage/transitions.md`.

### Rendering / export (MC: Render panel, image sequence or FFmpeg exporter in the browser)
- **Status:** Ported (1.5).
- **MC behaviour:** the editor renders the project in the browser tab and saves frames or a video via an exporter plugin; snapshots save the current frame.
- **Manim mapping:** an export *is* a `manim render` command (quality `-q`, `--format`, `-t`, `--save_sections`, `-n` range, `--media_dir`, `-o`, `--seed`). The Studio builds, shows and runs it, parses Manim's progress bar, and can cancel it. Save frame uses a runner child (`--snapshot-at`).
- **Improvements over MC:**
  - headless reproducibility by construction (the shown command *is* the export);
  - the result is checked with PyAV (size, fps, average fps / variable frame rate, duration, codecs, audio);
  - exports honour the preview seed;
  - the snapshot is pixel-identical to the preview at the same quality.
- **Deviation:** frame-exact range cuts are not offered, because Manim renders whole animations. The range snaps to whole `play`/`wait` calls and the dialog says so.
- **Implementation:** `src/manim_stage/export.py`, `studio/ui/export_dialog.py`, `runner.py` (`--snapshot-at`). Tests: `tests/test_export.py`, `tests/test_studio_ui.py`. KB: `docs/kb/manim-stage/export.md`.

### Project launcher (MC: `npm init @motion-canvas`, `npm run serve`)
- **Status:** Ported (1.6).
- **Manim mapping:** the `manim-stage` console script (`studio`, `scenes`, `timeline`, `doctor`, `cache`) sits beside `manim`, which stays the renderer. There is no project scaffolding step: any folder with Manim scenes works (project sidecars arrive in M2/M3).
- **Improvements over MC:** `doctor` explains in Manim terms what the machine can render (LaTeX for `Tex`, Pango fonts for `Text`, encoders per export format). `timeline` exposes event capture headlessly.
- **Implementation:** `src/manim_stage/cli.py`, `doctor.py`. Tests: `tests/test_cli.py`; CI `package` job. KB: `docs/kb/manim-stage/cli.md`.

### Media assets (MC: imported images/audio/video in the project)
- **Status:** Ported (3.5).
- **MC behaviour:** a Vite project imports media files; a missing file fails when the scene runs.
- **Manim mapping:**
  - a static scan of the scene for `ImageMobject`, `SVGMobject`, `add_sound`, narration files and fonts, resolved with Manim's own rules;
  - audio-workspace clips are included;
  - `manim-stage assets` (CI-friendly exit code) and the Studio Assets tab;
  - Add asset… copies into `assets/<kind>/` and offers the Manim call;
  - render presets map onto `-q`/`-r`/`--fps`/`--format`/`-t`.
- **Improvements over MC:**
  - missing assets and fonts are caught before rendering;
  - environment checks explain what this machine can render.
- **Implementation:** `src/manim_stage/assets.py`, `export.py` (`PRESETS`), `studio/ui/assets_panel.py`, `export_dialog.py`. Tests: `tests/test_assets.py`, `tests/test_studio_ui.py`. KB: `docs/kb/manim-stage/assets.md`.

### Audio (MC: one audio track with offset)
- **Status:** Ported (2.3a core, 2.3b editing). The voiceover adapter (2.4) is next.
- **MC behaviour:** a project has one audio file with an offset. The editor shows its waveform under the timeline and plays it with the preview; the renderer muxes it into the video.
- **Manim mapping:**
  - Manim already mixes any number of `add_sound` calls.
  - The audio workspace's clips (`.manim-stage/audio.json`) become `add_sound(processed copy, time_offset=start)` in `StageMixin.setup()`. The copy is trimmed, gained and faded, and cached by content.
  - So plain `manim render` produces the same mix, and source recordings are never modified.
- **Improvements over MC:**
  - many clips per scene, with trim, gain, fades, mute and solo;
  - the preview mix is built from the timeline's own sound events (code sounds and clips), so it matches the render; tested by correlating the exported AAC track with the preview mix;
  - playback re-syncs if it drifts by more than about a frame, and degrades to silence without a device.
- **Choices:**
  - `sounddevice` (MIT, small) for playback instead of QtMultimedia, which ships in the large PySide6-Addons wheel;
  - PyAV decoding (already a Manim dependency).
- **Editing (2.3b):**
  - imports are copied into `assets/audio/`, so paths stay portable;
  - drag to move, edge-drag to trim (the audio stays anchored in time);
  - an Event-panel property editor;
  - muted and not-soloed clips are injected into the timeline as silent events, so they stay editable;
  - each change is an `AudioEdit` (whole clip list before/after) on the shared undo stack.
- **Implementation:** `src/manim_stage/audio.py`, `studio/audio_edit.py`, `scene.py` (`setup` clips), `capture.py` (clip tagging), `studio/audio_player.py`, UI waveforms in `studio/ui/timeline.py`. Tests: `tests/test_audio.py`, `tests/test_studio_ui.py`. KB: `docs/kb/manim-stage/audio.md`.

### Project variables and theme (MC: `variables`, project settings)
- **Status:** Ported (3.2).
- **MC behaviour:** a project passes untyped variables to scenes (`useScene().variables`); the editor has project settings but no typed variable UI.
- **Manim mapping:**
  - `.manim-stage/project.json` holds a theme (semantic colours whose defaults are Manim's colour constants, Text font, code font and style) and typed variables;
  - scenes call `project.theme()` / `project.var(name, default, min=, max=, options=)`, which is the explicit opt-in;
  - StageScene applies the background (`camera.background_color`) and font (`Text.set_default`) and restores them at `tear_down`;
  - AnimatedCode takes its code style and font from the theme;
  - the runner reports the variables a scene read, and the Studio's Project panel edits them, with undo.
- **Improvements over MC:**
  - typed and validated values, with failures naming the variable;
  - a theme layer;
  - one file for CLI, Studio and CI;
  - a tracked dependency, so edits invalidate the cache.
- **Implementation:** `src/manim_stage/project.py`, `scene.py`, `code.py`, `runner.py`, `studio/ui/project_panel.py`. Tests: `tests/test_project.py` (F07 acceptance: two scenes recolour on one accent change), `tests/test_studio_ui.py`. KB: `docs/kb/manim-stage/project.md`.

### Inspector (MC: read-only node inspector)
- **Status:** Ported (3.3, MF.5).
- **MC behaviour:** select a node in the viewport and see its properties, read-only.
- **Manim mapping:**
  - the runner replays to a frame (`--inspect-at`) and snapshots `scene.mobjects` families through Manim's public getters;
  - the viewport maps clicks to scene units for a bounds hit-test (topmost z, deepest);
  - `self.expose(mobject, name, *props)` is the explicit opt-in;
  - saved edits live in `properties.json` and are applied by `expose()`, so headless renders match;
  - unsaved previews use a temporary overrides file via `MANIM_STAGE_PROPERTIES`, which always joins the cache key;
  - edits are undoable sidecar commands, plus Copy as Python.
- **Improvements over MC:**
  - editing with preview, save, undo and a code action;
  - works for any Mobject class read-only, never claiming more than Manim reports.
- **Implementation:** `src/manim_stage/inspector.py`, `scene.py`, `runner.py`, `capture.py` (`with_scene`), `studio/service.py` (`inspect_at`, render `env`), `studio/ui/inspector_panel.py`, `viewport.py`. Tests: `tests/test_inspector.py` (F08 acceptance), `tests/test_studio_ui.py`. KB: `docs/kb/manim-stage/inspector.md`.

### Scene transitions (MC: slide/fade/zoom transitions)
- **Status:** Ported (3.4).
- **MC behaviour:** a scene starts with a transition animated over the previous scene's last frame.
- **Manim mapping:**
  - Manim renders each scene to its own video, so cross-scene transitions are composed after rendering. `manim-stage compose` renders every scene with `manim render`, then overlaps adjacent scenes (fade, slide, wipe) frame by frame with PyAV, places and cross-fades audio, and encodes H.264 + AAC;
  - in-scene `enter`/`exit` cover the "transition as an animation" case.
- **Improvements over MC:**
  - the total length is exactly `sum − overlaps`, tested for no dropped or duplicated frames;
  - audio alignment is tested to a frame;
  - one JSON sequence file plus one command.
- **Deviation:** shared-element transitions are expressed in Manim's way (both moments in one scene with `Transform`), not inferred.
- **Implementation:** `src/manim_stage/compose.py`, `flow.py` (`enter`/`exit`), `cli.py`. Tests: `tests/test_flow.py` (F09 acceptance with three rendered scenes). KB: `docs/kb/manim-stage/transitions.md`.

### Editor plugins (MC: editor/runtime plugins)
- **Status:** Ported (4.1).
- **MC behaviour:** a plugin object can add editor tabs, timeline content and exporters; there is no version handshake.
- **Manim mapping:**
  - `manim_stage.plugins` entry points (Python packaging, like Manim's `manim.plugins`), plus a `MANIM_STAGE_PLUGINS` env var for development;
  - a plugin declares `api_version`, and mismatched plugins are disabled with the reason;
  - hooks: `timeline_events` (own lane `plugin:<name>`), `panels` (dock tabs), `inspector_rows`, `commands`, `exporters`;
  - a narrow `StudioAPI` (read timeline/playhead, seek, status, log);
  - each hook is caught, so a failure disables only that plugin;
  - Manim plugins are listed beside them.
- **Improvements over MC:** a compatibility handshake, failure isolation, and a CLI listing.
- **Implementation:** `src/manim_stage/plugins.py`, `studio/ui/main_window.py` (`load_plugins`, `_WindowAPI`), `plugins_panel.py`, `timeline_model.py` (plugin lanes), `export_dialog.py` (post-export actions); sample `examples/plugins/stage_beats/`. Tests: `tests/test_plugins.py` (F11 acceptance). KB: `docs/kb/manim-stage/plugins.md`.

### Editor shell (MC: browser editor with live project preview)
- **Status:** Ported (M1 gate passed, `docs/m1-gate-report.md`).
- **MC behaviour:** the editor runs the project in the page; Vite hot-reloads changed modules and the player re-runs the scene, keeping the playhead.
- **Manim mapping:** `PreviewService` (no Qt, no socket) runs each revision in fresh runner children; frames come from the cache; PySide6 UI subscribes to typed `PreviewMessage`s.
- **Improvements over MC:** a crashing or hanging scene can't take down the editor (separate process, killable tree); dependency-aware cache keys; stale results can never overwrite current ones (integer `seq`).
- **Shell (1.3):** MC's viewport + playback bar + settings become a `QMainWindow`: scene picker (MC's scene list → Manim `Scene` classes found by importing the file in a child), a viewport that only displays cached frames, transport with speed/loop/range, and a scrub bar showing which frames are rendered. Preview resolution uses Manim's quality presets (`-ql`…`-qk`) instead of MC's resolution/scale settings. Playback is a Qt-free `Playback` model (wall clock × speed; holds on unrendered frames instead of skipping), so it is unit-tested.
- **Hot reload:** MC relies on Vite's HMR. Ported as `PreviewService.watch()`: a stdlib polling watcher over the scene file and its recorded dependencies, debounced (default 0.3 s), which starts a new revision (the old one is killed). Syntax errors point at their line.
- **Implementation:** `src/manim_stage/studio/service.py`, `watcher.py`, `playback.py`, `app.py`, `ui/` (main window, viewport, transport, log, theme, icons); `deps.py`, `runner.py` (`RunnerProcess`, `--list`). Tests: `test_service.py`, `test_watcher.py`, `test_playback.py`, `test_studio_ui.py` (pytest-qt, offscreen on all CI OSes). KB: `preview-service.md`, `studio-editor.md`.

## 4. Processes in use

- **Milestone gates:** each milestone ends with a gate report (`docs/m0-gate-report.md`, `m1-`, `m2-`), an end-to-end test of the spec's acceptance scenario, and measurements.

- **Upstream sync:** `docs/upstream-sync.md`, `/upstream-sync` skill, weekly watch workflow. Each sync classifies upstream changes Adopt/Adapt/Inspire/Ignore and updates the KB and this file when a port is affected.
- **PR flow:** one backlog item per PR; CI on Windows/Linux/macOS × Python 3.11–3.13; merge when green. PR template checklist includes KB and this file.
- **Regression guard:** golden frames + byte-identical CLI output with manim-stage imported (`tests/test_regression.py`).
- **Docs kept honest:** every KB code example runs in CI (`tests/test_kb_examples.py`).
- **Determinism:** runner enforces a seed; static scan warns about clock/entropy reads.

## How this file is maintained

- Any PR that ports, designs or changes a Motion Canvas–derived feature updates §2 (decision) and §3 (record: status, mapping, improvements, implementation paths, tests, KB page).
- New processes or changes to existing ones go in §4.
- Upstream syncs that touch a ported feature add a line to §2.
