# Changelog

All notable changes. Detailed, dated notes live in [`docs/kb/whats-new.md`](docs/kb/whats-new.md); the decision log is in [`PORTING.md`](PORTING.md).

## [0.1.0] — 2026-11-27

First release. Manim stays the renderer and the source of truth; manim-stage adds an editor and opt-in authoring features. It's pinned to Manim `main@8c258a0` (the 0.30 line).

### M1 — Studio
- **Studio editor** (PySide6), with a viewport rendered by Manim. Frames are cached on disk, so scrubbing is instant.
- **Live reload** of the scene and every file it uses.
- **Seekable timeline:** plays, waits, sections, sounds and captions, with rate-function curves and lag staircases.
- **Event panel** that jumps to the source line; **Export dialog**; `manim-stage` CLI.

### M2 — Teaching workflow
- **Named cues** (`self.cue`). Drag them on the timeline to re-time a scene without editing Python.
- **Audio clips** with waveforms; **narration** adapter (manim-voiceover concepts); `AnimatedCode` with diff-based `animate_to`.
- **Gate:** narrated bubble-sort example; renders are reproducible.

### M3 — Composition and customisation
- **Signals:** `Signal` (a `ValueTracker`), `computed`, `bind`, `effect`.
- **Project theme and typed variables**, with a Project tab.
- **Inspector and `expose()`:** preview, save, undo, copy as Python.
- **Flow helpers and scene transitions;** `manim-stage compose` joins scenes.
- **Assets inventory, render presets,** and an Assets/environment tab.
- **Gate:** themed three-scene lesson with deterministic exports.

### M4 — Ecosystem and polish
- **Studio plugin SDK** (entry points, API-version handshake, timeline lanes, panels, inspector rows, commands, exporters).
- **Educational helpers:** `Array`, `LinkedList`, `Tree`, `CallStack`, `SequenceDiagram`, `label_edges`, `tree_layout`, and data-driven traces.
- **Demo parameters** (editor-time sliders) and a **web player** with chapters and captions.
- **Manim-aware editor:**
  - a Library tab, a catalog of every Manim feature;
  - a Config tab (`manim.cfg`) and a Sections tab;
  - camera-aware preview;
  - a Text and LaTeX tab.
- **Compatibility suite:** ten unmodified Manim feature scenes are pixel-identical between preview and `manim render`.
- **Three third-party-style examples.**
- **Performance:** PNG encoding overlaps drawing; the first full 1080p30 preview is 36% faster with one worker.
- **Packaging:** the wheel is smoke-tested on Windows, Linux and macOS; a tag-driven release workflow.
