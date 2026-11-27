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
| 0.6 | **Executable proof — frame cache seek:** `evaluate(on_frame)` → bounded disk cache. Measure first-preview latency and seek latency on a reference 10 s scene (spec §9). Golden test: cached frame == CLI render frame. | ☑ | ADR-0007. `docs/benchmarks.md`: 1080p 10 s scene cached in 8.0 s with 4 workers (17.9 s with 1); seek 8.5 ms median; frames pixel-identical to CLI. |
| 0.7 | **Regression baseline:** golden-frame tests for representative unmodified scenes with Studio disabled; confirm CLI output byte/pixel-identical with manim-stage installed. | ☑ | spec §10.1. `tests/test_regression.py`: byte-identical CLI output with manim-stage imported; golden frames for 3 scenes pass on Win/Linux/macOS (tolerance 0.1% pixels >24). |
| 0.8 | `docs/schemas/` v1 JSON Schemas: `ProjectManifest`, `SceneEvent`, `Cue`, `PreviewMessage`, `EditableProperty`; time model doc (frame index, half-open ranges, 48 kHz audio mapping). | ☑ | spec §8. Implemented: timeline, runner messages (validated against real output). Draft: cues, project, editable property. |
| 0.9 | M0 gate report: measurements, unsupported scene classes, go/no-go on deterministic replay | ☑ | spec §11 gate. `docs/m0-gate-report.md`: GO for M1 (Cairo). Seeds enforced; determinism warnings; supported/unsupported scene classes. |
| 0.10 | **Local knowledge base, first version** (`docs/kb/`, see "Knowledge base" below): structure, page template, index, example smoke-test harness, first pages for what exists (event capture, runner, upstream sync) | ☑ | requested by owner 2026-11-26. `docs/kb/` with 8 pages; `tests/test_kb_examples.py` runs every example and checks links; PR template enforces updates. |

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

| # | Item | Status | Notes |
|---|---|---|---|
| 1.1 | `PreviewService` (no Qt, no socket): revisions, cancel/restart, stale-message discard, typed `PreviewMessage` events; dependency-aware revisions (hash imported modules/assets) | ☑ | F01; gate-report risk 2; ADR-0010 |
| 1.2 | File watcher (debounce 200–500 ms) → new runner revision; traceback with file/line | ☑ | F01 |
| 1.3 | Editor shell (Python/PySide6): scene picker, viewport, play/pause/step/speed, timecode, zoom/fit, dark/light, keyboard shortcuts, accessibility | ☑ | F01, ADR-0012, ADR-0013 |
| 1.4 | Timeline UI: ruler (s/frames), zoom, range, play/wait/section/sound tracks, nested children, jump-to-source | ☑ | F02 |
| 1.5 | Snapshot + range/full export through Manim CLI with progress/cancel | ☑ | F01, F10 |
| 1.6 | `manim-stage studio` CLI; `[studio]` extra; packaging smoke test | ☑ |
| 1.7 | **M1 gate**: user-journey test, Studio latency benchmark, gate report | ☑ | `docs/m1-gate-report.md`: PASSED | ADR-0009 |

## Manim feature coverage in the editor (continuous, requested by owner 2026-11-27)

The editor must cover every Motion Canvas editor capability **and** surface Manim's own feature set intelligently, not just play back frames. Approach (ADR-0011): an **introspected catalog** of the pinned Manim build, so features added upstream appear automatically after a sync, and a test fails when a new public Manim export is not classified (forcing a KB/editor decision during `/upstream-sync`).

| # | Item | Status | Notes |
|---|---|---|---|
| MF.1 | `manim_stage.catalog`: introspect Mobjects, Animations, rate functions, colors, scene types, camera types, config options, plugins → JSON with category, signature, doc summary, KB link; coverage test over `manim.__all__` | ☐ | ADR-0011 |
| MF.2 | Rich event metadata: animation class + category, rate function name, run_time, lag_ratio, target mobject class/name, `.animate` method chain, updaters, `ValueTracker` | ☑ | F02. Animations: `catalog.animation_info`; updaters: counted per Mobject in the inspector; `ValueTracker`: `Signal` (3.1) |
| MF.3 | Timeline knows Manim: per-category colour + icon (non-colour signal too), rate-function curve drawn in event bars, lag-ratio staircase for `LaggedStart`, wait vs `wait_until` vs frozen frame, `skip_animations` sections shown | ☑ | F02 |
| MF.4 | Library panel: searchable catalog (Mobjects, Animations, rate functions with live curve, colours with swatches, scene types), docs summary, "copy Python" snippets | ☐ | |
| MF.5 | Scene-tree inspector for any frame: `scene.mobjects` families (class, name, bounds, colour, opacity, z-index, updaters), read-only by default; opt-in editable via `expose()` (F08) | ☑ | F08 |
| MF.6 | Manim config panel: quality presets (`-ql…-qk`), fps, resolution, background colour, renderer, format (mp4/mov/webm/gif/png), transparent, sections export | ☐ | F10 |
| MF.7 | Sections navigator: Manim `next_section` names/types, `skip_animations`, per-section export (`--save_sections`) | ☐ | F02, F10 |
| MF.8 | Camera-aware preview: `MovingCameraScene` frame overlay, `ZoomedScene`, `ThreeDScene` orientation readout; renderer capability labels (Cairo/OpenGL) | ☐ | spec §2.7 |
| MF.9 | Environment health: LaTeX availability, fonts (`manimpango.list_fonts()`), FFmpeg/PyAV codecs, installed Manim plugins (`manim.plugins` entry points) | ☑ | F10. `manim-stage doctor` + Studio Assets tab |
| MF.10 | Text/LaTeX helpers: font picker, `MathTex` substring colouring preview, `Tex` template selection | ☐ | F07 |

## M2 — Teaching workflow (P1)

| # | Item | Status | Notes |
|---|---|---|---|
| 2.1 | `StageScene.cue()` + resolver + `cues.json` (atomic, versioned) + `validate` + `bake` | ☑ | F03, ADR-0006 |
| 2.2 | Timeline cue drag with ripple/hold, undo/redo, downstream preview | ☑ | F03 |
| 2.3 | Audio workspace: multi-clip import, PyAV peaks → waveform, offset/trim/gain/fade/mute/solo, mixdown via pre-processed assets + `add_sound` | ☑ | 2.3a core (PR #20), 2.3b editing UI (PR #21) | F04 |
| 2.4 | manim-voiceover adapter (+ upstream PRs: 0.30 compat, manual bookmark times #113, pre-recorded audio #100) | ☑ | `self.narration()`; bookmarks = cues; cache import. Upstream PRs still to propose | F04 |
| 2.5 | `AnimatedCode` layout: Pygments tokens, token IDs, anchored grid, bundled font, `CodeRange`, `highlight_lines` | ☑ | F05, ADR-0008 |
| 2.6 | Diff engine (patience line→token, moves, overrides) + `animate_to`; tests: repeated tokens, multi-line, non-ASCII, 500+ lines | ☑ | F05 |
| 2.7 | End-to-end narrated bubble-sort demo + headless reproducibility test | ☑ | M2 gate PASSED: `docs/m2-gate-report.md` |

## M3 — Composition and customization (P2)

| # | Item | Status | Notes |
|---|---|---|---|
| 3.1 | Derived values on `ValueTracker` (F06 in Manim terms, ADR-0013): derived trackers, bound updaters, dependency tracking, cycle detection, disposal | ☑ | F06 |
| 3.2 | Project config / variables / themes (`project.json` settings, `stage.theme`) resolved identically in CLI and Studio | ☑ | F07 |
| 3.3 | `expose()` editable properties + inspector editing, sidecar persistence, undo/redo, copy-as-Python | ☑ | F08 |
| 3.4 | Transitions + choreography helpers; multi-scene sequence with cross-scene transitions | ☑ | F09 |
| 3.5 | Asset manager + validator; render presets; range export; export metadata inspection | ☑ | F10 (range export and metadata inspection since 1.5) |
| 3.6 | M3 gate: multi-scene lesson with configurable visuals, deterministic exports | ☑ | PASSED: `docs/m3-gate-report.md` |

## M4 — Ecosystem and polish (P2/P3)

| # | Item | Status | Notes |
|---|---|---|---|
| 4.1 | Editor plugin SDK: `manim_stage.plugins` entry points, handshake, panels/tracks/inspectors/commands/exporters; sample plugin | ☑ | F11 |
| 4.2 | Educational helpers: call stack, array/linked list/tree layouts, graph edges, sequence diagrams, trace-driven animation | ☑ | F12 |
| 4.3 | Interactive demo parameters (editor-time) vs linear export; rendered web playback with chapters | ☐ | F12 |
| 4.4 | Performance pass, migration guide, three third-party-style examples, release packaging, compatibility suite | ☐ | M4 gate |

## Upstream contributions to propose (spec §12.5)

- PySide6 6.12.0: signal emission loses references to `None`/`True` on CPython 3.11 (Linux); repro in `tests/test_qt_sanity.py`. Report to Qt for Python (PYSIDE bug tracker).

- Manim: `media_dir/texts` SVG cache is not safe for concurrent processes (0-byte file after parallel runs; see docs/benchmarks.md).
- Manim: public run-loop listener registration (replace private `_use_loop` subclassing).
- Manim: `evaluate()` early stop after the last requested frame.
- Manim: timeline entries with frame indices and nested children.
- Manim: section index JSON with start times.
- manim-voiceover: 0.30 compatibility, manual bookmark times, pre-recorded audio, offset/gain.
