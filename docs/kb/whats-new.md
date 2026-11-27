# What's new

Newest first. One entry per feature PR or upstream sync. Each entry lists what is new, what changed and what was removed, with links to KB pages.

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
