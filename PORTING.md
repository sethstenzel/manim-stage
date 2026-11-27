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
- **Status:** In progress. Data ported (M0); UI in M1 (backlog 1.4, MF.3).
- **MC behaviour:** one fast pass over the scene computes durations, slide and time-event positions; the timeline shows scenes, slides, time events and audio.
- **Manim mapping:** `Manager.evaluate(capture_timeline=True)` gives play/wait/section/sound entries; a run-loop listener (`_compat.py`) records frame-exact play ranges; nested `AnimationGroup`/`LaggedStart` child spans are computed from `rate_func`, `lag_ratio` and run times.
- **Improvements over MC:** per-animation and nested tracks; frame-integer time model (no float drift); stable event IDs `scene:kind:path:line#occurrence`; each event knows its Manim animation class, category (from Manim's `manim.animation.*` module layout), `.animate` method chain, rate function and its sampled curve, lag ratio and target Mobject (MF.2), so the timeline can show *what* happens, not just *when*.
- **Implementation:** `src/manim_stage/capture.py`, `events.py`, `_compat.py`, `catalog.py`. Tests: `tests/test_capture.py`, `tests/test_catalog.py`. KB: `docs/kb/manim-stage/event-capture.md`.

### Seeking / preview (MC: replay the scene in the browser to any frame)
- **Status:** Ported for cached frames (P1). P3 live scrubbing not feasible (no Manim state snapshot).
- **Manim mapping:** frames drawn by Manim through `evaluate(on_frame=…)` in child processes into a content-addressed LRU disk cache.
- **Improvements over MC:** preview is pixel-identical to the final render; parallel drawing.
- **Implementation:** `runner.py`, `framecache.py`. Tests: `test_runner.py`, `test_parity.py`. KB: `frame-cache.md`, `runner.md`.

### Time events / `waitUntil` (MC: named, draggable waits)
- **Status:** Designed (ADR-0006, ADR-0013). Backlog 2.1–2.2.
- **Manim mapping:** `self.cue("name", at=, after=)`, a named `wait`; overrides in `.manim-stage/cues.json` as absolute frames.
- **Improvements over MC:** validation (negative waits, duplicates, order), orphan tombstones, atomic writes, undo, headless `bake`.

### Code block and code animation (MC: `Code` node, token diff)
- **Status:** Designed (ADR-0008). Backlog 2.5–2.6.
- **Manim mapping:** `AnimatedCode` (a `VGroup` of token mobjects) beside `manim.Code`; `CodeRange`, `lines()`, `word()`, `find()`; `animate_to()` returns a Manim `Animation`.

### Signals (MC: `createSignal`, computed, effects)
- **Status:** Designed (ADR-0013). Backlog 3.1.
- **Manim mapping:** `Signal` subclasses `ValueTracker`; `computed()` derives read-only values; `effect()` registers updaters.

### Flow helpers (MC: `all`, `sequence`, `chain`, `delay`, `loop`, `tween`)
- **Status:** Designed (ADR-0013). Backlog 3.4.
- **Manim mapping:** `all_of` → `AnimationGroup`, `sequence` → `LaggedStart`, `chain` → `Succession`, `tween(run_time, fn)` → custom `Animation`.

### Audio (MC: one audio track with offset)
- **Status:** Not started. Backlog 2.3–2.4.
- **Manim mapping:** `Scene.add_sound`, manim-voiceover adapter.

### Project variables (MC: `variables`)
- **Status:** Designed (ADR-0013). Backlog 3.2.
- **Manim mapping:** `stage.variables` + project theme layered on `ManimConfig`.

### Inspector (MC: read-only node inspector)
- **Status:** Not started. Backlog MF.5, 3.3.
- **Manim mapping:** Mobject family tree at any frame; opt-in editing via `expose()`.

### Scene transitions (MC: slide/fade/zoom transitions)
- **Status:** Designed (ADR-0013). Backlog 3.4.
- **Manim mapping:** `slide_transition`, `fade_transition`, `zoom_transition` as Manim `Animation`s.

### Editor plugins (MC: editor/runtime plugins)
- **Status:** Not started. Backlog 4.1.
- **Manim mapping:** `manim_stage.plugins` entry points with a version handshake; bridges Manim's own plugins.

### Editor shell (MC: browser editor with live project preview)
- **Status:** In progress. Engine (1.1), live reload (1.2) and the PySide6 shell (1.3) ported; timeline (1.4) and export (1.5) next.
- **MC behaviour:** the editor runs the project in the page; Vite hot-reloads changed modules and the player re-runs the scene, keeping the playhead.
- **Manim mapping:** `PreviewService` (no Qt, no socket) runs each revision in fresh runner children; frames come from the cache; PySide6 UI subscribes to typed `PreviewMessage`s.
- **Improvements over MC:** a crashing or hanging scene can't take down the editor (separate process, killable tree); dependency-aware cache keys; stale results can never overwrite current ones (integer `seq`).
- **Shell (1.3):** MC's viewport + playback bar + settings become a `QMainWindow`: scene picker (MC's scene list → Manim `Scene` classes found by importing the file in a child), a viewport that only displays cached frames, transport with speed/loop/range, and a scrub bar showing which frames are rendered. Preview resolution uses Manim's quality presets (`-ql`…`-qk`) instead of MC's resolution/scale settings. Playback is a Qt-free `Playback` model (wall clock × speed; holds on unrendered frames instead of skipping), so it is unit-tested.
- **Hot reload:** MC relies on Vite's HMR. Ported as `PreviewService.watch()`: a stdlib polling watcher over the scene file and its recorded dependencies, debounced (default 0.3 s), which starts a new revision (the old one is killed). Syntax errors point at their line.
- **Implementation:** `src/manim_stage/studio/service.py`, `watcher.py`, `playback.py`, `app.py`, `ui/` (main window, viewport, transport, log, theme, icons); `deps.py`, `runner.py` (`RunnerProcess`, `--list`). Tests: `test_service.py`, `test_watcher.py`, `test_playback.py`, `test_studio_ui.py` (pytest-qt, offscreen on all CI OSes). KB: `preview-service.md`, `studio-editor.md`.

## 4. Processes in use

- **Upstream sync:** `docs/upstream-sync.md`, `/upstream-sync` skill, weekly watch workflow. Each sync classifies upstream changes Adopt/Adapt/Inspire/Ignore and updates the KB and this file when a port is affected.
- **PR flow:** one backlog item per PR; CI on Windows/Linux/macOS × Python 3.11–3.13; merge when green. PR template checklist includes KB and this file.
- **Regression guard:** golden frames + byte-identical CLI output with manim-stage imported (`tests/test_regression.py`).
- **Docs kept honest:** every KB code example runs in CI (`tests/test_kb_examples.py`).
- **Determinism:** runner enforces a seed; static scan warns about clock/entropy reads.

## How this file is maintained

- Any PR that ports, designs or changes a Motion Canvas–derived feature updates §2 (decision) and §3 (record: status, mapping, improvements, implementation paths, tests, KB page).
- New processes or changes to existing ones go in §4.
- Upstream syncs that touch a ported feature add a line to §2.
