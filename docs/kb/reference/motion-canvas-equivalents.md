# Motion Canvas equivalents

How Motion Canvas features map to manim-stage. Behaviour is described in our own words; no Motion Canvas code or assets are used (spec §2.9).

- **Motion Canvas reference:** pinned `v3.17.2`. Docs: https://motion-canvas.io/docs/ (moved from motioncanvas.io).
- **Project health:** effectively dormant since Feb 2025.
- **Detail:** `docs/audit/motion-canvas.md`.

| Motion Canvas | What it does there | manim-stage | Status |
|---|---|---|---|
| Editor (viewport, playback, settings) | Browser editor running the animation in the page | Studio: a Python (PySide6) desktop editor; Manim renders in a child process, the editor only displays frames | Planned (M1) |
| Timeline | Scenes, slides, time events and audio waveform; one non-drawing pass computes it | [Event capture](../manim-stage/event-capture.md) gives the data. Adds per-animation and nested tracks MC lacks | Data: Available. UI: Planned (M1) |
| Seeking | Replays the scene from its start in JS; no frame cache | [Frame cache](../manim-stage/frame-cache.md): pre-rendered frames, ~9 ms seek | Available |
| `waitUntil` / time events | Named events; absolute scene-relative times in a `.meta` sidecar; drag ripples later events | `self.cue(...)` with `cues.json` (ADR-0006). Adds validation, orphan detection, atomic writes, undo, headless bake | Planned (M2) |
| Audio | One audio track per project, offset only (multi-sound unreleased) | Multi-clip audio workspace: offset/trim/gain/fade; voiceover adapter | Planned (M2) |
| Code animations | Token-level patience diff; unchanged tokens slide, changed ones cross-fade | `AnimatedCode`. Adds move detection, override mappings, stagger | Planned (M2) |
| Signals | Lazy computed values with dependency tracking | Derived values built on `ValueTracker` and updaters (no separate signal model) | Planned (M3) |
| Project variables | Reactive variables, untyped, no editor UI | Typed, validated project variables and themes | Planned (M3) |
| Inspector | Read-only node inspection | Opt-in inspector with editing persisted to a sidecar | Planned (M3) |
| Transitions | Slide/fade/zoom between scenes | File-level transitions between scenes | Planned (M3) |
| Rendering | In the browser tab only; image sequence or FFmpeg | Manim CLI stays the renderer; headless and reproducible | Available (Manim) |
| Plugins | Three layers, no version handshake | Versioned editor plugin API with handshake | Planned (M4) |

## Concepts: Motion Canvas → manim-stage API (ADR-0013)

Motion Canvas concepts are ported into Manim's model. They stay available under Python names and are built on Manim primitives, so they mix freely with plain Manim code.

| Motion Canvas concept | manim-stage API | Built on (Manim) | Status |
|---|---|---|---|
| Scene (generator function) | unchanged: `Scene` subclass, `construct()` | `Scene` | Available (Manim) |
| Node, scene graph | unchanged: `Mobject` families (`submobjects`) | `Mobject` | Available (Manim) |
| `yield* tween(...)` | `self.play(...)`; `tween(run_time, fn)` | `Animation` | Planned (M3) |
| `all(...)` / `sequence(...)` / `chain(...)` / `delay` / `loop` | `all_of`, `sequence`, `chain`, `delay`, `loop` | `AnimationGroup` / `LaggedStart` / `Succession` | Planned (M3) |
| `waitFor(s)` | unchanged: `self.wait(s)` | `Scene.wait` | Available (Manim) |
| `waitUntil("name")`, time events | [`self.cue("name", at=, after=)`](../manim-stage/cues.md) | `Scene.wait` | Available (drag on timeline: Planned 2.2) |
| Timing functions / easing | unchanged: `rate_func` | `manim.rate_functions` | Available (Manim) |
| `createSignal`, computed, effects | `Signal`, `computed`, `effect` | `ValueTracker`, updaters | Planned (M3) |
| Project variables | `stage.variables`, project theme | `config` | Planned (M3) |
| Slides | unchanged: sections (`next_section`) | `Scene.next_section` | Available (Manim) |
| Code block, `lines()`, `word()`, ranges | `AnimatedCode`, `CodeRange`, `lines()`, `word()`, `find()` | `VGroup` of token Mobjects | Planned (M2) |
| Scene transitions | `slide_transition`, `fade_transition`, `zoom_transition` | `Animation` | Planned (M3) |
| References (`createRef`) | ordinary Python attributes | — | n/a |
| Editor plugins | Studio plugins (`manim_stage.plugins` entry points) | — | Planned (M4) |

## Terminology: Motion Canvas → Manim (ADR-0013)

manim-stage keeps Manim's vocabulary. When a Motion Canvas idea is brought in, it gets the Manim name below.

| Motion Canvas term | manim-stage / Manim term | Notes |
|---|---|---|
| Scene (generator function) | `Scene` subclass, `construct()` | Unchanged Manim scenes work |
| Node, scene graph | `Mobject` and its family (`submobjects`) | Inspector shows Mobject families |
| `yield* tween(...)`, generators | `self.play(animation)`, `Animation` | |
| `all(...)` / `sequence(...)` / `chain(...)` | `AnimationGroup` / `LaggedStart` / `Succession` | Timeline shows children |
| `waitFor(s)` | `self.wait(s)` | |
| `waitUntil("name")`, time events | `self.cue("name", ...)`, a named, editable `wait` | ADR-0006 |
| Timing function / easing | `rate_func` (`manim.rate_functions`) | Curves drawn in the timeline |
| Signal, `createSignal`, computed | `ValueTracker`, updaters, `always_redraw`; derived values (M3) | |
| Project variables | `config` + project theme | M3 |
| Slide | Section (`self.next_section`) | |
| Code block, code ranges | `AnimatedCode`, `CodeRange` (with `manim.Code` still available) | M2 |
| Transitions between scenes | Scene transitions built from Manim `Animation`s | M3 |
| Player / viewport | Viewport | |
| Editor plugin | Studio plugin (`manim_stage.plugins`) | M4 |
