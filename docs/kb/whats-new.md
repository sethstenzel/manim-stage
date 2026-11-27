# What's new

Newest first. One entry per feature PR or upstream sync. Each entry lists what is new, what changed and what was removed, with links to KB pages.

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
