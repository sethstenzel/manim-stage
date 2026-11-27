# Motion Canvas equivalents

How Motion Canvas features map to manim-stage. Behaviour is described in our own words; no Motion Canvas code or assets are used (spec §2.9).

- **Motion Canvas reference:** pinned `v3.17.2`. Docs: https://motion-canvas.io/docs/ (moved from motioncanvas.io).
- **Project health:** effectively dormant since Feb 2025.
- **Detail:** `docs/audit/motion-canvas.md`.

| Motion Canvas | What it does there | manim-stage | Status |
|---|---|---|---|
| Editor (viewport, playback, settings) | Browser editor running the animation in the page | Studio editor; Python/Manim renders, browser only displays | Planned (M1) |
| Timeline | Scenes, slides, time events and audio waveform; one non-drawing pass computes it | [Event capture](../manim-stage/event-capture.md) gives the data. Adds per-animation and nested tracks MC lacks | Data: Available. UI: Planned (M1) |
| Seeking | Replays the scene from its start in JS; no frame cache | [Frame cache](../manim-stage/frame-cache.md): pre-rendered frames, ~9 ms seek | Available |
| `waitUntil` / time events | Named events; absolute scene-relative times in a `.meta` sidecar; drag ripples later events | `self.cue(...)` with `cues.json` (ADR-0006). Adds validation, orphan detection, atomic writes, undo, headless bake | Planned (M2) |
| Audio | One audio track per project, offset only (multi-sound unreleased) | Multi-clip audio workspace: offset/trim/gain/fade; voiceover adapter | Planned (M2) |
| Code animations | Token-level patience diff; unchanged tokens slide, changed ones cross-fade | `AnimatedCode`. Adds move detection, override mappings, stagger | Planned (M2) |
| Signals | Lazy computed values with dependency tracking | Signals layered on `ValueTracker` | Planned (M3) |
| Project variables | Reactive variables, untyped, no editor UI | Typed, validated project variables and themes | Planned (M3) |
| Inspector | Read-only node inspection | Opt-in inspector with editing persisted to a sidecar | Planned (M3) |
| Transitions | Slide/fade/zoom between scenes | File-level transitions between scenes | Planned (M3) |
| Rendering | In the browser tab only; image sequence or FFmpeg | Manim CLI stays the renderer; headless and reproducible | Available (Manim) |
| Plugins | Three layers, no version handshake | Versioned editor plugin API with handshake | Planned (M4) |
