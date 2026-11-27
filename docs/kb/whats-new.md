# What's new

Newest first. One entry per feature PR or upstream sync. Each entry lists what is new, what changed and what was removed, with links to KB pages.

## 2026-11-27 — flow helpers and scene transitions (backlog 3.4)

- **New:** [flow helpers](manim-stage/transitions.md): `all_of`, `sequence` (exact second offsets), `chain`, `delay`, `loop` and `tween`. They are Motion Canvas's names for Manim groups.
- **New:** in-scene `enter`/`exit` (fade, slide, zoom).
- **New:** `manim-stage compose lesson.sequence.json` renders scenes and joins them with overlapping fade/slide/wipe transitions. It is frame-exact, with audio placed and cross-faded (schema `sequence.schema.json`).

## 2026-11-27 — inspector and exposed properties (backlog 3.3, MF.5)

- **New:** [Inspector](manim-stage/inspector.md): the Mobject tree at the playhead (Ctrl+I, or follow the playhead). Click in the viewport to pick an object, which is outlined; the panel shows its class, bounds, colours, opacity, z-index and updaters.
- **New:** `self.expose(mobject, name, *props)` makes properties editable, with Preview (temporary overrides), Save (`properties.json`, undoable), Discard and Copy as Python. Plain `manim render` reproduces saved edits.
- **New:** runner `--inspect-at`; `PreviewService.inspect_at()`; render `env=` for previews.
- **Fixed:** sidecars redirected through `MANIM_STAGE_*` environment variables are always part of the cache key.

## 2026-11-27 — project theme and variables (backlog 3.2)

- **New:** [`project.theme()` and `project.var()`](manim-stage/project.md), stored in `.manim-stage/project.json` and read by preview and `manim render` alike.
- **New:** StageScene applies the theme's background and Text font. AnimatedCode takes the theme's code style and font.
- **New:** a Studio **Project** panel with colour pickers, fonts, code style and typed editors for the variables a scene reads. Writes are validated, atomic and undoable.
- **Changed:** the runner reports the project variables a scene read. The `project.json` schema is implemented (v1).

## 2026-11-27 — signals on ValueTracker (backlog 3.1)

- **New:** [`Signal`](manim-stage/signals.md) is a `ValueTracker` holding a number, list, array or colour, so `.animate.set_value` interpolates every component.
- **New:** lazy, cached, dependency-tracked `computed`; `self.bind(mobject, height=..., color=..., align=DOWN)` and `self.effect(fn)` as change-only updaters, disposed at scene end.
- **New:** `CycleError` with the dependency chain; `check_purity()`; `untracked()`.

## 2026-11-27 — M2 gate passed: narrated bubble-sort demo (backlog 2.7)

- **New:** `examples/bubble_sort/` and the [tutorial](tutorials/narrated-bubble-sort.md): narration + cues + AnimatedCode, with no `wait()` timing.
- **Report:** `docs/m2-gate-report.md`. Headless renders are pixel-reproducible, and the F03 scenario passes: a 30 → 35 s take, five cues moved, no Python edits.
- **Fixed:** AnimatedCode disables font ligatures (`==`, `->` and `!=` used to merge glyphs).
- **Faster:** AnimatedCode lays out uncached lines in one Pango call and skips Manim's system-font scan (cold demo timeline 43 s → 13 s).
- **Changed:** `run_capture` runs children in the scene's folder (`cwd=`), like the Studio. Narration events point at the user's line.

## 2026-11-27 — animated code edits (backlog 2.6)

- **New:** [`code.animate_to(new_source)`](manim-stage/animated-code.md#animated-edits): kept tokens slide, others fade, and highlights survive. Also `replace`, `insert` and `remove`.
- **New:** `manim_stage.code_diff`:
  - a patience line diff, then a token LCS;
  - moved-line detection;
  - `mapping=` overrides;
  - warnings for ambiguous repeated tokens.
- **Faster:** line layouts are cached as plain arrays, so edits only lay out changed lines (10 edits of a 26-line listing: 44 s → 5 s).

## 2026-11-27 — AnimatedCode layout (backlog 2.5)

- **New:** [`AnimatedCode`](manim-stage/animated-code.md) shows code as Pygments tokens, each a Manim `VGroup` of glyphs, on an exact character grid:
  - laid out in a bundled JetBrains Mono, so it looks the same on every OS;
  - grid anchors follow moves and scales.
- **New:** `lines()`, `word()`, `find()` and `find_all()` ranges; `get()` for any Manim animation; `highlight()` / `highlight_lines()` / `reset_highlight()`; `surround()` selection boxes.
- **New:** dependency `pygments`; the JetBrains Mono font (OFL) is bundled.

## 2026-11-27 — narration / voiceover adapter (backlog 2.4)

- **New:** [`with self.narration(name, file=, text=...) as n:`](manim-stage/narration.md). It plays a recorded voiceover, adds the text as a subcaption, and waits for the narration to end.
- **New:** `<bookmark mark='x'/>` in the text gives `n.wait_until('x')`, which is the named cue `name.x`, so it is draggable on the timeline.
- **New:** bookmark times come from explicit times, word timings (transcript JSON) or a text-position estimate. There is also a manim-voiceover `cache.json` importer.
- **New:** the Event panel shows the narration name, bookmarks and word timings.

## 2026-11-27 — audio clip editing (backlog 2.3b)

- **New:** Add audio… (Ctrl+Shift+A). External files are copied into `assets/audio/`.
- **New:** drag clips on the Audio lane to move them; drag their edges to trim.
- **New:** clip properties in the Event panel (start, trim, gain, fades, mute, solo, remove).
- **New:** muted clips stay visible on the timeline. Every edit is undoable.

## 2026-11-27 — audio workspace, part 1 (backlog 2.3a)

- **New:** [audio clips](manim-stage/audio.md) in `.manim-stage/audio.json`, covering:
  - start, trim, gain, fades, mute and solo;
  - rendered as non-destructive processed copies through Manim's `add_sound`, in both preview and plain `manim render`.
- **New:** waveforms on the Audio lane; the Event panel shows clip details.
- **New:** preview audio, synced to the playhead, with a speaker toggle in the transport. It uses `sounddevice`, is silent without an output device, and `MANIM_STAGE_NO_AUDIO=1` turns it off.
- **New:** `manim_stage.audio`: decode, process, mix and peaks, plus `docs/schemas/audio.schema.json`.

## 2026-11-27 — cue editing on the timeline (backlog 2.2)

- **New:** drag cue flags on the timeline. Hold mode bounds the drag by the next cue's wait; Shift ripples every later cue. A live preview shows where cues land and which animations shift.
- **New:** undo/redo (Ctrl+Z, Ctrl+Shift+Z / Ctrl+Y), Alt+Shift+arrow nudging, and Set time / Reset to default in the Event panel.
- **Changed:** new sidecars use 60 fps; cue waits are labelled `cue <name>` on the timeline; the editor's own sidecar writes don't trigger a second re-render.

## 2026-11-27 — named cues (backlog 2.1)

- **New:** [`self.cue(name, at=, after=, description=)`](manim-stage/cues.md) on `StageScene`, or any scene via `StageMixin`. It is Motion Canvas's `waitUntil`, built on Manim's `wait`.
- **New:** the `.manim-stage/cues.json` sidecar:
  - targets in absolute frames, rescaled across frame rates;
  - atomic writes with a `.bak` copy, and corruption fallback;
  - read by both the preview and plain `manim render`.
- **New:** `manim-stage validate` and `manim-stage bake`.
- **New:** a Cues lane on the timeline. Cue waits point at the user's line. Errors for negative waits, duplicates and bad names; warnings for orphaned overrides.
- **Changed:** `manim-stage scenes` and the runner's scene list report `stage` for StageScene classes.

## 2026-11-27 — M1 gate passed

- **Report:** `docs/m1-gate-report.md`. Unmodified Manim scenes are authorable in the Studio, and exports are unchanged (end-to-end journey test).
- **Fixed:** live reload now keeps the chosen preview quality and workers.
- **Changed:** the editor starts rendering the requested scene at once instead of waiting for scene discovery (about 0.8 s faster to first frame).
- **New:** `benchmarks/studio_latency.py`; results in `docs/benchmarks.md`.

## 2026-11-27 — `manim-stage` command (backlog 1.6)

- **New:** [`manim-stage`](manim-stage/cli.md) console script with these commands:
  - `studio`;
  - `scenes`;
  - `timeline` (text or JSON);
  - `doctor`, which checks Manim, Cairo, fonts, LaTeX, FFmpeg encoders, Qt and plugins;
  - `cache`.
- **New:** a packaging smoke test in CI, which builds the wheel, installs it cleanly with the studio extra and runs the command.
- **Changed:** the editor checks that the installed Manim build is supported before starting.

## 2026-11-27 — export and snapshots (backlog 1.5)

- **New:** [Export](manim-stage/export.md) through `manim render`, covering:
  - Manim quality presets and formats (MP4, WebM, MOV, GIF, PNG sequence, PNG);
  - transparency, `--save_sections`, and in/out range via `-n`;
  - progress, cancel, and a result check (size, fps, duration, codecs, audio, variable frame rate).
- **New:** the exact Manim command is shown and copyable, for headless reproduction.
- **New:** Save frame (full-quality PNG at the playhead, pixel-identical to the preview at the same quality) and Copy frame.
- **New:** runner `--snapshot-at SECONDS --out PNG`.

## 2026-11-27 — timeline (backlog 1.4, MF.3)

- **New:** [Timeline](manim-stage/timeline.md) in the Studio editor: sections, play/wait, nested group members (overlaps get their own rows), audio. It has a seconds/frames ruler with render progress, zoom, scroll, and the in/out range.
- **New:** Manim-aware bars: category colour and label, `rate_func` curve, hatched waits (frozen marked), skipped sections marked.
- **New:** Event panel with the animation's class, category, `run_time`, `rate_func` curve, `lag_ratio`, `.animate` chain, Mobject and source; jump to source.
- **New:** keyboard navigation of events (Alt+←/→, Enter, Ctrl+Enter).

## 2026-11-27 — animation metadata (backlog MF.2)

- **New:** timeline events describe each animation in Manim's terms: class, category (Manim's animation module), `.animate` method chain, run time, rate function name and sampled curve, lag ratio, animated Mobject. See [event capture → animation metadata](manim-stage/event-capture.md#animation-metadata).
- **New:** `manim_stage.catalog` (first part of the Manim feature catalog, ADR-0011).

## 2026-11-27 — Studio editor shell (backlog 1.3)

- **New:** [Studio editor](manim-stage/studio-editor.md) (PySide6): scene picker, viewport with zoom, play/pause/step/speed/loop/range, scrub bar with render progress, live reload, errors with jump-to-source, dark/light themes, keyboard shortcuts.
- **New:** `pip install "manim-stage[studio]"` and `python -m manim_stage.studio FILE [SCENE]`.
- Preview quality uses Manim's own presets (`-ql` … `-qk`).

## 2026-11-27 — live reload (backlog 1.2)

- **New:** [live reload](manim-stage/preview-service.md#live-reload): `PreviewService.watch()` re-renders when the scene or a dependency is saved (debounced, polling, cross-platform).
- **Changed:** syntax errors now point at the offending file and line.

## 2026-11-27 — preview service (backlog 1.1)

- **New:** [Preview service](manim-stage/preview-service.md): background rendering with revisions, cancellation, stale-message discard and typed events.
- **New:** dependency-aware revisions. Helper modules and assets a scene opens are part of the frame-cache key; editing them invalidates cached frames.
- **New:** `python -m manim_stage.runner FILE --list` lists scene classes; `RunnerProcess` streams runner messages.
- **Changed:** Manim's media folder for previews now lives under the cache folder, not in the project.

## 2026-11-27 — M1 plan

- **Decided:** the Studio editor is written in Python (PySide6), with no web server (ADR-0010, ADR-0012).
- **Decided:** Manim terminology everywhere. See the new [terminology table](reference/motion-canvas-equivalents.md#terminology-motion-canvas--manim-adr-0013) (ADR-0013).
- **Planned:** the editor surfaces every Manim feature through an introspected catalog (ADR-0011, backlog MF track).
- **New:** [`PORTING.md`](../../PORTING.md), a running record of how each Motion Canvas feature is ported into Manim.

## 2026-11-26 — M0 gate: deterministic replay (backlog 0.9)

- **Runner always seeds randomness** (`--seed`, default 0, part of the revision). Seeded `random`/`numpy.random` scenes now replay identically across workers.
- **New:** determinism warnings for wall-clock reads, OS entropy and import-time randomness. See [Scene runner → determinism warnings](manim-stage/runner.md#determinism-warnings).
- **M0 gate report:** `docs/m0-gate-report.md`. The verdict is GO for M1 on Cairo.

## 2026-11-26 — data contracts (backlog 0.8)

- **New:** [Data formats and the time model](reference/data-formats.md); JSON Schemas in `docs/schemas/`.
  - Timeline and runner messages are validated against real runner output.
  - Draft schemas for cues, project manifest and editable properties.
  - Project paths reject traversal.

## 2026-11-26 — regression baseline (backlog 0.7)

- **New:** [Regression tests and golden frames](workflow/regression-tests.md).
  - Importing manim-stage leaves Manim CLI output byte-identical.
  - Golden frames of 3 unmodified scenes, checked on Windows, Linux and macOS.

## 2026-11-26 — knowledge base created (backlog 0.10)

- **New pages:** [Event capture](manim-stage/event-capture.md), [Scene runner](manim-stage/runner.md), [Frame cache](manim-stage/frame-cache.md).
- **New Manim pages** (pinned `main@8c258a0`): [Evaluate and timeline export](manim/evaluate-and-timeline.md), [Sound and sections](manim/sound-and-sections.md).
- **Reference:** [Motion Canvas equivalents](reference/motion-canvas-equivalents.md), [Upstream sync](workflow/upstream-sync.md).

## 2026-11-26 — frame cache and parallel preview (PR #4)

- `FrameCache`, `run_capture(cache_dir=..., workers=N)`.
- Cached frames are pixel-identical to the Manim CLI render.
- A 10 s 1080p scene is cached in 8 s with 4 workers.

## 2026-11-26 — event capture and runner (PR #2)

- `manim_stage.capture.capture`, `SceneTimeline`/`SceneEvent`, `manim_stage.runner.run_capture`.

## 2026-11-26 — Manim pinned to `main@8c258a0` (ADR-0003)

- Gained: `Manager.evaluate`, timeline export, frame-quantized clock, PyAV audio mixer, MP4 chapters.
