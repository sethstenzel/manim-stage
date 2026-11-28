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
| Audio | One audio track per project, offset only (multi-sound unreleased) | [Audio workspace](../manim-stage/audio.md): many clips per scene with start/trim/gain/fades/mute/solo on Manim's `add_sound`; waveforms; synced preview | Available |
| Code animations | Token-level patience diff; unchanged tokens slide, changed ones cross-fade | [`AnimatedCode`](../manim-stage/animated-code.md): `animate_to` / `replace` / `insert` / `remove`. Line-level patience diff, then a token LCS; adds moved-line detection, override mappings and ambiguity warnings | Available |
| Signals | Lazy computed values with dependency tracking | [`Signal`](../manim-stage/signals.md) *is* a `ValueTracker`; `computed`, `bind`, `effect` are cached updaters | Available |
| Project variables | Reactive variables, untyped, no editor UI | [Typed, validated `project.var()` + theme](../manim-stage/project.md) with a Studio Project panel | Available |
| Inspector | Read-only node inspection | [Inspector](../manim-stage/inspector.md): any Mobject read-only; `expose()`d properties editable with preview, save (sidecar), undo, copy as Python | Available |
| Transitions | Slide/fade/zoom between scenes | [`manim-stage compose`](../manim-stage/transitions.md): overlapping fade/slide/wipe between rendered scenes, frame-exact with audio; in-scene `enter`/`exit` | Available |
| Rendering | In the browser tab only; image sequence or FFmpeg | Manim CLI stays the renderer; headless and reproducible | Available (Manim) |
| (none; Manim ecosystem) manim-voiceover `self.voiceover()` + bookmarks | TTS narration with text bookmarks | [`self.narration()`](../manim-stage/narration.md): recorded audio, bookmarks as draggable cues, word timings, cache import | Available |
| Plugins | Three layers, no version handshake | [Studio plugins](../manim-stage/plugins.md): entry points, API-version handshake, timeline lanes, panels, inspector rows, commands, exporters | Available |

## Concepts: Motion Canvas → manim-stage API (ADR-0013)

Motion Canvas concepts are ported into Manim's model. They stay available under Python names and are built on Manim primitives, so they mix freely with plain Manim code.

| Motion Canvas concept | manim-stage API | Built on (Manim) | Status |
|---|---|---|---|
| Scene (generator function) | unchanged: `Scene` subclass, `construct()` | `Scene` | Available (Manim) |
| Node, scene graph | unchanged: `Mobject` families (`submobjects`) | `Mobject` | Available (Manim) |
| `yield* tween(...)` | `self.play(...)`; [`tween(run_time, fn)`](../manim-stage/transitions.md) | `Animation` | Available |
| `all(...)` / `sequence(...)` / `chain(...)` / `delay` / `loop` | [`all_of`, `sequence`, `chain`, `delay`, `loop`](../manim-stage/transitions.md) | `AnimationGroup` / `Succession` / `Wait` | Available |
| `waitFor(s)` | unchanged: `self.wait(s)` | `Scene.wait` | Available (Manim) |
| `waitUntil("name")`, time events | [`self.cue("name", at=, after=)`](../manim-stage/cues.md) | `Scene.wait` | Available (incl. timeline dragging, ripple, undo) |
| Timing functions / easing | unchanged: `rate_func` | `manim.rate_functions` | Available (Manim) |
| `createSignal`, computed, effects | [`Signal`, `computed`, `effect`, `bind`](../manim-stage/signals.md) | `ValueTracker`, updaters | Available |
| Project variables | [`project.var()`, `project.theme()`](../manim-stage/project.md) | `config`, `camera.background_color`, `Text.set_default` | Available |
| Slides | unchanged: sections (`next_section`); shown as chapters in the [web player](../manim-stage/web-player.md) | `Scene.next_section` | Available |
| Code block, `lines()`, `word()`, ranges | [`AnimatedCode`](../manim-stage/animated-code.md), `CodeRange`, `lines()`, `word()`, `find()` | `VGroup` of token Mobjects | Available |
| Scene transitions | [`enter`/`exit`; `manim-stage compose`](../manim-stage/transitions.md) | `FadeIn`/`FadeOut`; rendered videos | Available |
| References (`createRef`) | ordinary Python attributes | — | n/a |
| Editor plugins | [Studio plugins](../manim-stage/plugins.md) (`manim_stage.plugins` entry points) | — | Available |

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

## Motion Canvas guides as lessons

Each Motion Canvas guide's main example, rebuilt in manim-stage as a runnable [feature lesson](../tutorials/feature-lessons.md) (`examples/lessons/`).

| Motion Canvas guide | Lesson | Differences |
|---|---|---|
| Signals | `01_signals.py` `RadiusSignal` | `bind` replaces node-property signals |
| Animation flow | `02_flow.py` `FlowHelpers` | Helpers return Manim `AnimationGroup`/`Succession` |
| Tweening | `02_flow.py` `Tweening` | Timing functions are Manim `rate_func`s |
| Code | `03_code.py` `CodeTour` | Moved lines slide instead of fading |
| Time Events | `04_cues.py` `TimeEvents` | Shift-drag ripples (MC: ripple by default, Shift holds) |
| Media (audio) | `05_sound.py` `Narrated`, `SoundEffects` | Many clips; narration bookmarks are cues |
| Project variables | `06_theme.py` `ThemePalette` | Typed variables plus a colour theme |
| Transitions | `08_transitions.py`, `lessons.sequence.json` | Joined after rendering by `manim-stage compose` |
| Camera | `09_camera.py` `CenterOn` | No camera rotation in `MovingCameraScene` |
| Presentation | `10_slides.py` `Slides` | Sections become web-player chapters; no pause-per-slide |
| LaTeX | `12_text.py` `Formula` | Needs a LaTeX install |
