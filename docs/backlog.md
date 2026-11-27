# Implementation backlog

Ordered. Each item is one reviewable PR with tests and docs (spec §11, §12.4). Status: ☐ todo · ◐ in progress · ☑ done.
Feature IDs refer to `spec.md` §5. ADRs are in `architecture-decisions.md`.

## M0 — Audit and technical proof (P0)

| # | Item | Status | Notes |
|---|---|---|---|
| 0.1 | Repo foundation, upstream pins, sync process | ☑ | ADR-0001/0002 |
| 0.2 | Capability audit, ADRs 0003–0009, backlog | ☑ | PR #2 |
| 0.3 | **Owner decision on ADR-0003** (target Manim 0.30/MAIN) | ☑ | accepted 2026-11-26; manim re-pinned to main@8c258a0 |
| 0.3a | Spike: `Manager.evaluate` timeline + frame parity on Manim main (`spikes/`) | ☑ | frames pixel-identical to CLI; see spikes/README.md |
| 0.4 | Python package skeleton: `pyproject.toml` (hatchling, uv-pinned Manim), `manim_stage/_compat.py`, pytest, ruff, CI matrix (Win/Linux/macOS × py3.11–3.13) against pinned Manim | ☑ | ADR-0009 |
| 0.5 | **Executable proof — event capture:** runner that evaluates an unmodified scene in a child process, emits JSON-lines `SceneEvent`s with frame indices, nested group children and stable IDs. Tests: `AnimationGroup`, `LaggedStart`, waits, sounds, sections, zero-duration, loops (spec F02 accept). | ☑ | ADR-0004/0005. `manim_stage.events/capture/runner`; nested spans cross-checked against observed Manim frames. Cue markers and stable IDs across source edits come with F03. |
| 0.6 | **Executable proof — frame cache seek:** `evaluate(on_frame)` → bounded disk cache. Measure first-preview latency and seek latency on a reference 10 s scene (spec §9). Golden test: cached frame == CLI render frame. | ☐ | ADR-0007 |
| 0.7 | **Regression baseline:** golden-frame tests for representative unmodified scenes with Studio disabled; confirm CLI output byte/pixel-identical with manim-stage installed. | ☐ | spec §10.1 |
| 0.8 | `docs/schemas/` v1 JSON Schemas: `ProjectManifest`, `SceneEvent`, `Cue`, `PreviewMessage`, `EditableProperty`; time model doc (frame index, half-open ranges, 48 kHz audio mapping). | ☐ | spec §8 |
| 0.9 | M0 gate report: measurements, unsupported scene classes, go/no-go on deterministic replay | ☐ | spec §11 gate |
| 0.10 | **Local knowledge base, first version** (`docs/kb/`, see "Knowledge base" below): structure, page template, index, example smoke-test harness, first pages for what exists (event capture, runner, upstream sync) | ☐ | requested by owner 2026-11-26 |

## Knowledge base (continuous, requested by owner)

A local, offline knowledge base in `docs/kb/` covering **every feature and how to use it**, kept current on every update.

- **Scope:**
  - **manim-stage features:** every public API, CLI command, editor capability and file format.
  - **Manim features we build on or expose:** e.g. `Manager.evaluate`, timeline export, `add_sound`, sections, `Code`. Pages note the pinned Manim commit and renderer limits (Cairo vs OpenGL).
  - **Motion Canvas reference behaviour** where a manim-stage feature mirrors or exceeds it. Described in our own words; no MC code.
- **Each page:**
  - what it is and when to use it;
  - a minimal runnable example;
  - options, limitations and unsupported cases, with renderer labels;
  - status (Existing / Partial / Planned) and the version or commit it was introduced or changed in;
  - links to the spec feature ID, ADRs and source.
- **Index:**
  - `docs/kb/README.md`, by feature and by task ("align narration", "animate a code edit");
  - `docs/kb/whats-new.md`, newest first.
- **Kept honest:** every fenced Python example in the KB is smoke-tested in CI (spec §10.10), so stale docs fail the build.
- **Update rules (definition of done):**
  1. Every feature PR adds or updates its KB page(s) and a `whats-new.md` entry; no KB update, no merge.
  2. Every upstream sync (`/upstream-sync`) records new, changed or removed upstream features relevant to us in the KB and in `whats-new.md`.
  3. KB pages for planned features are marked **Planned** and must not describe behaviour as working until it is.
- **Later (optional):** an offline static site build (e.g. MkDocs) and an editor help panel served from the same pages.

## M1 — Studio MVP (P1)

| # | Item | Notes |
|---|---|---|
| 1.1 | Preview service: 127.0.0.1, host/origin checks, CSRF token, versioned WebSocket protocol, revision discard, cancel/restart | F01, spec §2.8 |
| 1.2 | File watcher (debounce 200–500 ms) → new runner revision; traceback with file/line | F01 |
| 1.3 | Editor shell (React/TS): scene picker, viewport, play/pause/step/speed, timecode, zoom/fit, dark/light, keyboard shortcuts, accessibility | F01 |
| 1.4 | Timeline UI: ruler (s/frames), zoom, range, play/wait/section/sound tracks, nested children, jump-to-source | F02 |
| 1.5 | Snapshot + range/full export through Manim CLI with progress/cancel | F01, F10 |
| 1.6 | `manim-stage studio` CLI; wheel ships prebuilt editor | ADR-0009 |

## M2 — Teaching workflow (P1)

| # | Item | Notes |
|---|---|---|
| 2.1 | `StageScene.cue()` + resolver + `cues.json` (atomic, versioned) + `validate` + `bake` | F03, ADR-0006 |
| 2.2 | Timeline cue drag with ripple/hold, undo/redo, downstream preview | F03 |
| 2.3 | Audio workspace: multi-clip import, PyAV peaks → wavesurfer.js, offset/trim/gain/fade/mute/solo, mixdown via pre-processed assets + `add_sound` | F04 |
| 2.4 | manim-voiceover adapter (+ upstream PRs: 0.30 compat, manual bookmark times #113, pre-recorded audio #100) | F04 |
| 2.5 | `AnimatedCode` layout: Pygments tokens, token IDs, anchored grid, bundled font, `CodeRange`, `highlight_lines` | F05, ADR-0008 |
| 2.6 | Diff engine (patience line→token, moves, overrides) + `animate_to`; tests: repeated tokens, multi-line, non-ASCII, 500+ lines | F05 |
| 2.7 | End-to-end narrated bubble-sort demo + headless reproducibility test | M2 gate |

## M3 / M4 (P2/P3) — outline only, refine after M2

- F06 signals on `ValueTracker` storage.
- F07 project config / themes.
- F08 `expose()` inspector.
- F09 transitions (file-level crossfades).
- F10 asset validator, presets, video input.
- F11 editor plugin SDK with handshake.
- F12 educational layouts and trace-driven animation.

## Upstream contributions to propose (spec §12.5)

- Manim: public run-loop listener registration (replace private `_use_loop` subclassing).
- Manim: `evaluate()` early stop after the last requested frame.
- Manim: timeline entries with frame indices and nested children.
- Manim: section index JSON with start times.
- manim-voiceover: 0.30 compatibility, manual bookmark times, pre-recorded audio, offset/gain.
