# Manim Studio: Motion Canvas–Class Authoring Features for Manim

**Status:** Implementation specification / handoff to Claude  
**Date:** 2026-11-27  
**Primary codebase:** Manim Community Edition (ManimCE), Python  
**Reference implementation:** Motion Canvas (TypeScript), for behavior and user experience only  
**Working name:** `manim-studio` (rename after repository inspection)

## 1. Objective

Bring Manim's educational-animation authoring experience up to, and where sensible beyond, the strongest Motion Canvas capabilities **without replacing Manim, porting it to TypeScript, or building a competing renderer**. Python `Scene`, `Mobject`, `Animation`, existing renderer selection, CLI, and file outputs remain authoritative. Extend them through a backward-compatible, optional Python feature layer, a local preview service, and a browser-based editor.

The primary use case is high-quality, narrated computer-science education: algorithm traces, animated code edits, call stacks, graphs, concurrency, memory diagrams, protocols, and architecture.

**Important:** This is a product requirement specification, not a claim that each named feature is absent from the current Manim release. Claude must audit the checked-out version and existing plugins before writing code. Enhance or integrate existing functionality instead of duplicating it.

## 2. Nonnegotiable constraints

1. ManimCE remains the animation engine, scene model, renderer, and source of truth. Existing Manim scripts render identically by default.
2. Python is the public authoring API. The editor may use TypeScript/React but must never require TypeScript to define animations.
3. No hard fork by default. Prefer a standalone `manim-studio` Python package and editor with narrowly scoped upstream contributions. A fork is permissible only after a documented architecture decision.
4. Use existing Manim APIs for `Scene`, `Mobject`, `ValueTracker`, updaters, `Code`, `Text`, sections, sound, Cairo/OpenGL preview, and OpenGL interaction where supported.
5. Keep final render deterministic, including time, random seeds, fonts, assets, and project configuration. The editor preview and CLI output must agree within defined tolerances.
6. New editor capabilities must work on Windows, Linux, and macOS. Do not require a browser-hosted renderer or cloud service.
7. Explicitly label preview capabilities by renderer. Cairo and OpenGL may support different preview strategies; no silent fallback that alters results.
8. Use a local-only server by default; never execute arbitrary scene Python from remote browser clients. Bind to `127.0.0.1`, protect state-changing endpoints against CSRF/cross-origin access, and document the trust boundary: loading a user-provided Python scene executes local code.
9. Maintain clear licensing and attribution. Study Motion Canvas interfaces and documented behaviors, but do not copy its source or UI assets without separately confirming license obligations.
10. No regressions to existing Manim API, test suite, CLI output, or rendering behavior. Feature flags / opt-in syntax for new behavior.

## 3. Baseline audit: required first task

Before implementation, Claude must clone/inspect the actual requested ManimCE repository and commit; inventory:

- Manim version, Python floor, renderer architecture, CLI, scene timeline/partial movie caches, OpenGL live preview, interactive embedding, sections, audio APIs, existing `Code` implementation, frame rendering, object update lifecycle, serialization limits, plugins, configuration, and test infrastructure.
- `manim-voiceover`, editor/preview ecosystem (`manim_editor`, VS Code extensions, presentation/slide tools), and whether their maintenance and licensing suit reuse.
- Current Motion Canvas documentation for editor, time events, code animations, signals, project variables, transitions, media, plugins, and rendering.
- Existing Manim features satisfying the requirements below. Each requirement must be classified **Existing / Partial / Missing / Integration only / Not feasible** with file locations and test evidence.

Deliver `docs/capability-audit.md`, `docs/architecture-decisions.md`, and an updated implementation backlog before implementing P1. Do not infer gaps from marketing comparisons.

## 4. Target architecture

```text
Python Manim scene + optional Manim Studio APIs
                 |
       Instrumented Python runner
          /              \
   Manim renderers    Event/timeline manifest
          \              /
       Preview transport/API
                 |
         Local Studio editor
      (preview, timeline, inspector,
       audio waveform, cue editing)
                 |
       Saved project metadata
   (cue overrides, presets, markers)
```

### Core components

- **`manim_studio` Python package:** decorators/markers, reactive property helpers, code-diff animations, scene event tracing, validation, metadata import/export, CLI integration.
- **Runner process:** isolated child process that imports/renders scenes and reports structured events, exceptions, progress, frames, dependency changes, and timeline metadata. Support cancellation and restart. Python sandboxing is explicitly **out of scope**; only trusted local projects may run.
- **Preview service:** local HTTP/WebSocket or equivalent protocol with versioned messages; serves preview frames, seek/play/pause, scene metadata, event updates, logs, and editor settings. Avoid unbounded buffering.
- **Editor:** browser-based UI (preferred React/TypeScript), used only as a control and visualization layer. It must never become a second rendering engine.
- **Project metadata:** versioned, human-readable sidecar such as `.manim-studio/project.json` and `cues.json`, to avoid rewriting Python on every editor drag. Python remains authoritative for logical animation order.

### Timeline strategy (critical technical risk)

Manim typically executes imperative `construct()` code and mutates objects over time. Arbitrary backward seeking is **not** guaranteed by simply setting `Scene.time` or replaying updaters. Build explicit scene-event capture, stable animation IDs, deterministic replay from a fresh scene or safe checkpoints, and cached partial renders. Support seek in phases:

1. **P1:** accurate seek into cached/pre-rendered frames, with responsive timeline browsing.
2. **P2:** incremental re-render and seek to arbitrary times after edits, backed by event replay/checkpoints where safe.
3. **P3:** true live OpenGL scrubbing only for scenes proven replayable, with explicit fallback to frame-cache replay.

Never promise instant arbitrary seeking for side-effecting custom Python code. Document unsupported classes of scenes and expose warnings.

## 5. Feature requirements and acceptance criteria

Priorities: **P0** essential prerequisite, **P1** first useful release, **P2** expanded parity, **P3** advanced/stretch.

### F01 — Unified local Studio editor (P1)

**Goal:** Motion Canvas–style workflow with a scene picker, viewport, playback controls, settings, log/errors, and timeline.

- `manim studio path/to/lesson.py SceneName` (or documented plugin CLI equivalent) opens the editor and starts a local preview service.
- Scene discovery, play/pause, seek, step frame, speed, zoom/fit, frame/timecode, render quality preset, renderer capability indicators.
- File-change detection with debounced render cancellation/restart; clear Python traceback and a direct file/line reference when available.
- Hot reload should preserve playhead/selected scene when possible, and visibly reset if invalid.
- Optional snapshot/export, render range selection, accessible keyboard shortcuts, dark/light UI.

**Accept:** a developer can edit an existing unmodified Manim scene, save, view the updated preview, scrub an already-rendered range, and export a full-quality MP4; the CLI version continues to work unmodified.

### F02 — Visual timeline and events (P1)

- Trace scene `play`, `wait`, section boundaries, sound/voiceover starts, cue markers, and optional named object/animation tracks.
- Timeline has seconds/frames ruler, zoom, loop/range, markers, visible overlapping animations, selection, and jump-to-source metadata.
- Preview/playhead and timeline stay synchronized. Event durations reflect actual Manim execution (including animation groups, lag ratios, custom runtime, and frame rate).
- Define stable scene/event IDs across source edits where possible; deterministic collision handling.
- Metadata edits must not mutate Python source except through an explicit, reviewable code action.

**Accept:** complex scenes containing `AnimationGroup`, `LaggedStart`, waits, sounds, and sections produce correct time ranges and no duplicated events.

### F03 — Named timing cues and narration alignment (P1)

- Add opt-in Python syntax such as `self.wait_until("explain_swap")` or `self.cue("explain_swap")`; final API is subject to audit and ADR.
- Cues have unique IDs, defaults, optional descriptions, validation, and sidecar overrides editable on a timeline.
- Provide both **absolute** cue times and **relative/ripple** behavior; explicitly prevent negative waits and ambiguous cue order.
- Drag cue markers to adjust timing, with UI feedback of changed downstream cue times. Persist changes atomically, with undo/redo.
- Detect missing, duplicated, nonmonotonic, orphaned, or unreachable cues; fail validation with actionable messages.
- Export/bake cue metadata for clean reproducible CLI/headless rendering, including when Studio is not open.

**Accept:** replace a 30-second narration with a 35-second recording, adjust five cues visually, rerender, and confirm animations align without manually changing five `wait()` calls in Python.

### F04 — Audio and voiceover workspace (P1/P2)

- Import local WAV/MP3/other supported audio, show timeline waveform, play/pause synchronized with scene, offset, trim, mute/solo, volume, and fade controls.
- Integrate established Manim audio/`manim-voiceover` capabilities through adapters; do not reimplement speech recognition, microphone recording, or TTS in core.
- Display narration segments/captions/word timings when explicitly supplied; optional transcription integration in P2, off by default.
- Render mixdown exactly as previewed within an acceptable sync tolerance (target ≤1 video frame at configured FPS for cue positions).
- Avoid destructive edits to source recordings. No automatic remote speech uploads.

**Accept:** a voiceover, sound effect, and scene animation stay aligned after cue changes and appear correctly in exported video.

### F05 — Semantic source-code animation engine (P1)

- Provide an enhanced Python API (e.g. `AnimatedCode`) for syntax-highlighted source, line/column range selection, line highlighting, carets, selection boxes, scrolling, and auto-fit.
- First-class transitions between source versions: insert, delete, replace, move, emphasize; configurable animation timing/easing.
- Structural diff matching with stable token/line identities; prefer patience/Myers diff then optional syntax-aware matching. Detect duplicate tokens and ambiguous matches and provide explicit override mappings.
- Support Python first, then JavaScript/TypeScript, Rust, C/C++, Go, Bash, and SQL via a maintained syntax highlighter. Honor font metrics and Unicode/tab widths.
- Expose typed `CodeRange`/`Span`, `highlight_lines()`, `animate_to(new_code)`, and semantic edit descriptors rather than requiring manually animated text glyphs.
- Existing `manim.Code` remains supported; adapter/extension must avoid breaking its API.

**Accept:** animate a 25-line Python bubble sort implementation through 10 edits with stable unchanged-line positioning, highlighting, and deterministic rendering at 30/60 FPS. Include tests for repeated tokens, multiline edits, and non-ASCII text.

### F06 — Reactive signals, derived state, and reusable properties (P2)

- Integrate with Manim's `ValueTracker`, updaters, and `.animate` rather than introducing an incompatible state model.
- Optional typed Python `Signal[T]`, `computed(...)`, `effect(...)`, and `bind(mobject, ...)` APIs with dependency tracking, invalidation, lifecycle cleanup, and cycle detection.
- Support animated interpolation for numeric, color, point/vector, and compatible structured properties, with a deterministic evaluation order.
- Prevent unnecessary frame recomputation and provide diagnostics for cyclic graphs, impure effects, and nondeterministic reads.

**Accept:** changing an array-value signal updates value labels, bar height, and a comparison indicator consistently without separate manual updaters, with clean disposal when scene ends.

### F07 — Project-wide variables, themes, and reusable presets (P2)

- Project configuration for colors, font families, code styles, margins, aspect ratio, FPS, semantic palette, and lesson variables.
- Editor-adjustable parameters with validated schemas and default values; require explicit opt-in to live-edit exposed scene values.
- Named reusable animation templates, layout primitives, educational diagram components, and consistent visual themes.
- Config resolved deterministically across CLI/Studio, renderer, and CI; support environment-independent assets.

**Accept:** change theme/accent color and update all participating scenes without editing each scene source.

### F08 — Inspector and property editing (P2)

- Inspect opted-in named objects, scene tree hierarchy, position, bounds, transforms, z-index, colors, opacity, and declared editable properties.
- Select object on viewport/timeline and inspect source ID. Property change previews are ephemeral until intentionally persisted to sidecar or copied as Python.
- Avoid claiming complete introspection for arbitrary custom `Mobject` subclasses; display read-only / unsupported status.
- Provide safe editing controls, undo/redo, and exact representation of non-editable dynamic properties.

**Accept:** select a labeled node, adjust its exposed fill color, preview result, save/reopen, and reproduce same render headlessly.

### F09 — Scene transitions and choreography (P2)

- Declarative transition helpers for scene-to-scene cuts, fades, slides, wipes, masks where renderer support permits.
- Parallel and sequential composition helpers using current Manim animation grouping semantics.
- Shared-element transitions only where object identity/mapping is explicitly declared; degrade gracefully for incompatible geometry.
- Ensure transition audio/video sync and deterministic export.

**Accept:** three educational scenes linked by two transitions render with stable durations, no dropped/duplicated frames, and correct audio alignment.

### F10 — Media assets, export, and render workflow (P2)

- Asset manager for local images, SVGs, fonts, audio, and video when existing Manim/FFmpeg facilities allow it. Validate paths and missing assets before rendering.
- Visual render presets for 1080p/4K, 30/60 FPS, transparent output where supported, and image sequence/video formats already exposed by Manim.
- Segment/range export, progress, cancel, encoding logs, and retry. Existing Manim output formats must remain intact.
- Explicit color-space, alpha, variable-frame-rate, codec, and media-duration handling. Document platform/codec dependencies.

**Accept:** export a bounded selection and full video; inspect metadata (size, FPS, duration, codecs), compare representative frames to reference, confirm audio sync.

### F11 — Extensible editor/plugin API (P2)

- Publish documented versioned hooks for panels, event metadata, object inspectors, project settings, custom tool commands, and exporters.
- Bridge existing Python-side Manim plugins rather than replacing them; editor plugins must not gain direct arbitrary filesystem access through remote requests.
- Validate compatibility/version handshake and gracefully disable incompatible plugins.

**Accept:** sample plugin adds a named event track and inspector panel without modifying Studio core.

### F12 — Reproducibility, educational tooling, and advanced interactivity (P3)

- Optional pedagogical utilities: call-stack visualizer, array/linked-list/tree layouts, graph edges, algorithm state tracers, protocol sequence diagrams.
- Data-driven execution traces produced by a trusted Python function and animated by Manim; do not require unsafe live execution inside a viewer.
- Optional interactive control widgets for local demo parameters; distinguish editor-time interactive preview from exportable linear video.
- Stretch: portable web playback of **rendered** animation with selectable chapters/cues; do not promise that arbitrary Python scenes execute client-side.

**Accept:** demonstrate an instrumented sorting algorithm with step/speed controls in local preview and faithful deterministic linear video export.

## 6. Feature-gap decision matrix

| Motion Canvas capability | Manim baseline to verify | Planned approach | Priority |
|---|---|---|---|
| Browser editor + real-time project preview | OpenGL live preview, external editor tools | New unified editor; reuse preview/render paths | P1 |
| Seekable timeline | Scene play/section timing and partial movie cache | Event manifest + cached-frame seeking | P1 |
| Editable `waitUntil` time events | Waits and sections; voiceover plugin | Named cues + sidecar timing | P1 |
| Audio-aligned authoring | `add_sound`, voiceover ecosystem | Waveform and cue alignment UI | P1 |
| Animated code diffs and spans | `Code`, highlighting and animations | Semantic `AnimatedCode` extension | P1 |
| Signals / derived properties | `ValueTracker`, updaters, redraw | Optional reactive layer | P2 |
| Editor-exposed project variables | Manim config and Python variables | Typed editor metadata + themes | P2 |
| Object inspector | OpenGL scene access and Mobjects | Opt-in property inspector | P2 |
| Scene transitions | Existing animation/group primitives | Composition helper APIs | P2 |
| Media management / output | Manim audio, raster/video/export paths | Workflow UI, validations, range exports | P2 |
| Plugin-driven editor | Manim Python plugins | Separate versioned editor extension API | P2 |

The matrix is a **hypothesis** pending the baseline audit, not a statement that Manim has no existing implementation.

## 7. Public API design sketches (illustrative, not final)

Keep source idiomatic Python and make additions opt-in:

```python
from manim import *
from manim_studio import StudioScene, AnimatedCode


class BubbleSortLesson(StudioScene):
    def construct(self):
        code = AnimatedCode("a = [4, 2, 3]", language="python")
        self.add(code)

        self.wait_until("introduce_array", default=1.0)
        self.play(code.animate_to("a = [2, 4, 3]"), run_time=1.2)
        self.wait_until("explain_swap", default=3.0)
        self.next_section("Summary")
```

```python
from manim_studio import Signal, computed

index = Signal(0)
is_even = computed(lambda: index.value % 2 == 0)
# Exact binding/interpolation API to be selected after ValueTracker audit.
```

Do **not** ship these signatures without designing replay/cue semantics, tests, and backward compatibility. In particular, clarify whether `default` means absolute scene time, relative time, or a duration, and prefer explicit names such as `at=` or `after=`.

## 8. Data and protocol contracts

Specify and version JSON schemas before UI implementation:

- `ProjectManifest`: schema version, Manim and Studio versions, project root (nonportable paths normalized), settings, scene IDs, asset references, cue file reference.
- `SceneEvent`: stable ID, source path/line, type, scene ID, parent/group ID, start/end seconds, frame start/end, track, metadata, renderer support.
- `Cue`: ID, scene ID, description, default positioning semantics, override time, ripple mode, related audio segment, validation status.
- `PreviewMessage`: request ID, scene/manifest revision, command, progress, frame content/reference, error, cancellation, capabilities.
- `EditableProperty`: object ID, property key, typed value, units, allowed range/options, writable/read-only flag, persistence destination.

Time representation: use rational frame counts or exact frame-index mapping, not uncontrolled floating-point accumulation. Define frame boundary rounding, inclusive/exclusive ranges, and audio sample conversions.

Persistence must be atomic, with migration/versioning, corruption recovery, backup on schema migrations, and path traversal protections. Store project-relative paths when possible. No secrets in metadata.

## 9. Performance and quality targets

Treat these as measurable targets to benchmark and revise after a prototype, not guaranteed results:

- First usable cached timeline preview on a simple 10-second 1080p scene: target ≤10 seconds on a documented reference machine after dependencies are warm.
- Scrubbing already cached preview frames: target median ≤100 ms response at 720p; slow re-render distinguished in UI.
- File change debounce 200–500 ms, cancel stale work, and prevent outdated frames from replacing current previews.
- Memory budget configurable; bounded frame cache with LRU eviction and disk budget, no indefinite growth.
- Cue synchronization ≤1 frame at export FPS when source narration timing is known.
- No perceptible mismatch in a renderer-identical preview/export path; establish image-diff thresholds separately for Cairo and OpenGL.
- All authoring UI supports keyboard navigation, accessible names, non-color-only signals, and 125–200% text scaling.

## 10. Test plan

1. **Regression:** run upstream Manim tests unchanged; golden-frame tests for representative existing scenes with all Studio features disabled.
2. **Renderer parity:** Cairo/OpenGL capability matrix, explicitly allowed differences, image comparisons, transparency and 3D scenes.
3. **Timeline correctness:** parallel animations, nested groups, rate functions, waits, sections, sound, custom animations, zero-duration cases, variable FPS.
4. **Replay correctness:** custom Python side effects, nondeterministic random/time operations, mutable updaters, unsupported seeks, scene reimports; warn rather than silently misrender.
5. **Code animation:** inserts/deletes/moves, duplicates, multi-line edits, syntax rules, Unicode, proportional/monospaced fonts, 500+ lines, token matching stability.
6. **Cue editor:** missing/duplicate cues, ripple collisions, drag undo/redo, voiceover replacement, persistence, headless reproduction.
7. **Security:** bind/host validation, CORS/CSRF, websocket origin check, path traversal, malicious project files, subprocess cancellation and cleanup.
8. **Cross-platform CI:** supported Python versions and Windows/macOS/Linux smoke tests; include Linux headless rendering.
9. **User journeys:** author a lesson, add narration, edit cue timing, preview, export MP4, reopen project, render same content via CLI.
10. **Docs/examples:** automated smoke-test every copy-paste example and at least three polished lesson demos.

## 11. Milestones and dependencies

### M0 — Audit and technical proof (P0)

- Pin Manim commit/version and produce capability audit, compatibility matrix, architecture ADRs, proof that runner can record event metadata and preview existing scenes without changing rendering behavior.
- Prototype seek by cached frame and validate source event maps. Identify renderer caveats.
- **Gate:** documented, executable architecture proof and baseline tests. Stop and propose revised scope if deterministic replay cannot be made safe.

### M1 — Usable Studio MVP (P1)

- Local runner/service, scene discovery, live-reload preview, cached timeline, playback controls, source errors, range selection and snapshot.
- **Gate:** unmodified Manim scripts are authorable in Studio, and headless exports are unchanged.

### M2 — Teaching workflow (P1)

- Named timing cues, timeline drag/ripple, waveform and voiceover adapter, animated source-code diffs.
- **Gate:** publish the end-to-end narrated bubble sort demonstration and test its headless reproducibility.

### M3 — Composition and customization (P2)

- Signals, project variables, object inspector, reusable themes, transitions, render presets, media asset manager.
- **Gate:** complete multi-scene lesson with configurable visuals and deterministic exports.

### M4 — Ecosystem and polish (P2/P3)

- Editor plugin SDK, performance optimizations, advanced educational helpers, comprehensive docs and migration guides.
- **Gate:** three third-party-style examples, cross-platform release packaging, compatibility test suite.

Do not implement all of M1–M4 in one change. Keep small, independently reviewable commits/PRs with passing tests and updated documentation.

## 12. Claude execution instructions

1. **Ask for the actual repository URL/path and intended branch if not provided.** Never assume the repository is a writable upstream Manim checkout.
2. Read repository `AGENTS.md`, `CONTRIBUTING`, dependency metadata, tests, and current architecture before making changes.
3. Complete M0 first. Return a concise report with exact source references, an updated feature inventory, risks, and suggested first PR. Do not jump into a giant rewrite.
4. For every feature, open a scoped issue/design note with: observed existing behavior, missing behavior, affected modules, API proposal, test scenarios, rollback strategy, and acceptance criteria.
5. Prefer wrapping stable Manim APIs or contributing narrow improvements upstream. Do not monkeypatch core scene internals without a documented short-lived compatibility adapter and tests.
6. Keep Python dependencies optional where possible; pin editor build dependencies; provide development and release instructions.
7. On each milestone, supply a working demo, tests, performance measurements, migration notes, screenshots where useful, and known limitations.
8. Do not claim a feature is finished if only a UI mockup exists or if it works only on one renderer without marking limitations.
9. Surface architecture conflicts and scope choices for approval; do not silently alter Manim defaults or remove existing APIs.
10. Preserve authorship/license headers and ensure all new code and third-party asset usage comply with their respective licenses.

## 13. Definition of done

A first production-ready release must allow a Python developer to open an existing Manim lesson, view/scrub a synchronized scene timeline, animate source-code changes cleanly, align narration by named draggable cues, render the same lesson from the headless CLI, and retain current Manim scene/renderer compatibility. Subsequent P2/P3 capabilities are not blockers for this initial release but each has independent acceptance tests.

## 14. Primary references (verify again during implementation)

- Manim Community main docs: https://docs.manim.community/en/stable/
- Manim repository: https://github.com/ManimCommunity/manim
- Manim renderer/live preview: https://docs.manim.community/en/stable/guides/configuration.html
- Manim `Scene` and existing interaction: https://docs.manim.community/en/stable/reference/manim.scene.scene.Scene.html
- Manim voiceovers: https://docs.manim.community/en/stable/guides/add_voiceovers.html
- Manim plugins: https://docs.manim.community/en/stable/plugins.html
- Motion Canvas docs: https://motioncanvas.io/docs/
- Motion Canvas time events: https://motioncanvas.io/docs/time-events/
- Motion Canvas code animation: https://motioncanvas.io/docs/code/
- Motion Canvas code blocks: https://motioncanvas.io/docs/code-block/
- Motion Canvas signals: https://motioncanvas.io/docs/signals/
- Motion Canvas project variables: https://motioncanvas.io/docs/project-variables/
- Motion Canvas media: https://motioncanvas.io/docs/media/
- Motion Canvas authoring plugins: https://motioncanvas.io/docs/plugins/
- Motion Canvas rendering: https://motioncanvas.io/docs/rendering/

**Out of scope:** porting Motion Canvas code, recreating its browser Canvas engine, making Python user scenes safe to run from untrusted sources, replacing Manim's rendering pipeline, and promising arbitrary real-time reverse execution of every Python scene.
