# manim-stage knowledge base

A local, offline reference for **every manim-stage feature and how to use it**. It also covers the Manim features we build on, and the Motion Canvas behaviour we mirror. It works without a network connection, and its examples are tested.

- **New this update:** [whats-new.md](whats-new.md)
- **How Motion Canvas features were ported (decisions, implementation, process):** [`PORTING.md`](../../PORTING.md)
- **Writing or updating a page:** [_template.md](_template.md) and the rules at the bottom of this page.

**Status legend:**
- **Available**: works on `main` and is tested.
- **Partial**: works with listed limitations.
- **Planned**: designed, not built. Never describe a Planned feature as working.

**Renderer labels:**
- **Cairo**: tested with the Cairo renderer, which is the default.
- **OpenGL**: tested with the OpenGL renderer.
- **Both**: tested with both.

## By feature

### manim-stage

| Page | What | Status | Renderer | Spec |
|---|---|---|---|---|
| [Event capture](manim-stage/event-capture.md) | Turn a scene into frame-exact timeline events | Available | Cairo | F02 |
| [Scene runner](manim-stage/runner.md) | Run a scene in a child process; JSON-lines protocol; errors with file/line | Available | Cairo | F01 |
| [Preview service](manim-stage/preview-service.md) | Render a scene in the background; revisions, cancel, events, dependency tracking | Available | Cairo | F01, §8 |
| [Frame cache and preview frames](manim-stage/frame-cache.md) | Cache every frame for scrubbing; parallel drawing | Available | Cairo | F01, §4 P1 |
| [Studio editor](manim-stage/studio-editor.md) | Python (PySide6) desktop editor: scene picker, viewport, playback, live reload, errors | Partial (export: Planned) | Cairo | F01 |
| [Command line](manim-stage/cli.md) | `manim-stage studio / scenes / timeline / doctor / cache` | Available | — | F01 |
| [Assets and environment checks](manim-stage/assets.md) | List/check images, SVGs, sounds, fonts the way Manim resolves them; Add asset…; environment (LaTeX, fonts, encoders) | Available | Both | F10 |
| [Export and snapshots](manim-stage/export.md) | Render via `manim render` (quality, format, range, transparency, sections) with progress, cancel and result check; save/copy frames | Available | Cairo | F01, F10 |
| [Timeline](manim-stage/timeline.md) | Lanes of play/wait/section/sound and group members; Manim categories, rate curves, jump to source | Available | Cairo | F02 |
| [Named cues (`self.cue`)](manim-stage/cues.md) | Named, adjustable waits for narration; drag on the timeline (hold/ripple, undo); `cues.json`; validate/bake | Available | Both | F03 |
| [Flow helpers and scene transitions](manim-stage/transitions.md) | `all_of`/`sequence`/`chain`/`delay`/`loop`/`tween`; enter/exit; `manim-stage compose` joins scenes with fade/slide/wipe, frame-exact with audio | Available | Cairo | F09 |
| [Inspector and exposed properties](manim-stage/inspector.md) | Mobject tree at the playhead; click to pick; `self.expose()` → preview/save/undo/copy-as-Python edits | Available | Cairo | F08 |
| [Project theme and variables](manim-stage/project.md) | `project.json`: semantic theme colours, fonts, code style; typed `project.var(...)`; Studio Project panel | Available | Both | F07 |
| [Signals, computed, bindings](manim-stage/signals.md) | `Signal` (a ValueTracker for numbers, lists, arrays, colours), cached `computed`, `bind`/`effect` updaters; cycle/purity diagnostics | Available | Both | F06 |
| [Narration (voiceover adapter)](manim-stage/narration.md) | `with self.narration(...)`: recorded voiceover + subcaption + bookmarks as draggable cues; word timings; manim-voiceover cache import | Available | Both | F04, F03 |
| [Audio workspace](manim-stage/audio.md) | Import, drag, trim, gain, fade, mute/solo audio clips (undoable); waveforms; preview playback = render mix | Available | Both | F04 |
| [`AnimatedCode`](manim-stage/animated-code.md) | Syntax-highlighted code as token mobjects; ranges; highlight; selection boxes; animated edits (token diff, moves, overrides) | Available | Cairo | F05 |

### Manim features we build on (pinned `main@8c258a0`)

| Page | What | Status in Manim |
|---|---|---|
| [Evaluate and timeline export](manim/evaluate-and-timeline.md) | `Manager.evaluate`, `--timeline-output`, frame-quantized time | Experimental (0.30 line) |
| [Sound and sections](manim/sound-and-sections.md) | `add_sound`, `next_section`, `--save_sections`, MP4 chapters | Stable API; 0.30 mixer |

### Tutorials

| Page | What |
|---|---|
| [Themed multi-scene lesson](tutorials/multi-scene-lesson.md) | Three scenes, one theme, signals, inspector edit, composed with transitions; restyle without code edits |
| [Narrated bubble sort](tutorials/narrated-bubble-sort.md) | End-to-end lesson: narration, cues, AnimatedCode; re-time to a new take without touching Python |

### Reference

| Page | What |
|---|---|
| [Motion Canvas equivalents](reference/motion-canvas-equivalents.md) | Motion Canvas feature → manim-stage status; MC → Manim terminology |
| [Data formats and the time model](reference/data-formats.md) | JSON contracts (timeline, runner messages, cues, project) and frame/time rules |
| [Upstream sync](workflow/upstream-sync.md) | How new Manim / Motion Canvas changes are brought in |
| [Regression tests and golden frames](workflow/regression-tests.md) | Proving manim-stage never changes Manim output; catching upstream rendering changes |

## By task

| I want to… | Go to |
|---|---|
| Get the timing of every `play`/`wait` in a scene | [Event capture](manim-stage/event-capture.md) |
| Know which Manim animation, rate function and Mobject an event is | [Event capture → animation metadata](manim-stage/event-capture.md#animation-metadata) |
| See when each member of a `LaggedStart` runs | [Event capture → nested animations](manim-stage/event-capture.md#nested-animations) |
| Run a scene safely in the background and get errors with line numbers | [Scene runner](manim-stage/runner.md) |
| Find which line produced a moment in the video | [Timeline](manim-stage/timeline.md#quick-start) |
| See a LaggedStart's staircase and each animation's rate_func | [Timeline → how it works](manim-stage/timeline.md#how-it-works) |
| Find missing images, sounds or fonts before rendering | [Assets](manim-stage/assets.md#quick-start) |
| Export 4K or a transparent video | [Assets → render presets](manim-stage/assets.md#render-presets) |
| Export an MP4/GIF/PNGs, or just part of a scene | [Export](manim-stage/export.md) |
| Save a full-quality still of the current frame | [Export → Save frame](manim-stage/export.md#quick-start) |
| Check what my machine can render (LaTeX, fonts, codecs) | [CLI → doctor](manim-stage/cli.md#commands) |
| Print a scene's timing without opening the editor | [CLI → timeline](manim-stage/cli.md#quick-start) |
| Make animations wait for the narration without hand-tuned waits | [Named cues](manim-stage/cues.md#quick-start) |
| Time animations Motion Canvas-style (sequence, chain, delay, tween) | [Flow helpers](manim-stage/transitions.md#quick-start-flow-helpers) |
| Join scenes into one video with transitions | [Scene transitions](manim-stage/transitions.md#quick-start-joining-scenes) |
| See what an object on screen is (class, bounds, colours) | [Inspector](manim-stage/inspector.md#quick-start) |
| Tweak a colour visually and keep it reproducible | [Inspector → exposed properties](manim-stage/inspector.md#how-it-works) |
| Change the look of every scene at once (accent colour, fonts) | [Project theme](manim-stage/project.md) |
| Drive several mobjects from one piece of state | [Signals](manim-stage/signals.md#quick-start) |
| Build a multi-scene lesson with one look | [Tutorial: themed multi-scene lesson](tutorials/multi-scene-lesson.md) |
| Build a narrated lesson end to end | [Tutorial: narrated bubble sort](tutorials/narrated-bubble-sort.md) |
| Animate a code edit | [AnimatedCode → animated edits](manim-stage/animated-code.md#animated-edits) |
| Show code and highlight lines or words | [AnimatedCode](manim-stage/animated-code.md#quick-start) |
| Narrate with a recording and wait for words in it | [Narration](manim-stage/narration.md#quick-start) |
| Reuse audio from manim-voiceover | [Narration → reusing manim-voiceover output](manim-stage/narration.md#how-it-works) |
| Add narration or music without changing my code | [Audio workspace](manim-stage/audio.md#quick-start) |
| Hear the scene while previewing | [Audio workspace → playback](manim-stage/audio.md#how-it-works) |
| Retime animations to a new narration take | [Named cues → editing in the Studio](manim-stage/cues.md#editing-cues-in-the-studio) |
| Check or pin my cue timings | [Named cues → command line](manim-stage/cues.md#command-line) |
| Preview a scene while I edit it | [Studio editor](manim-stage/studio-editor.md#quick-start) |
| Learn the editor's keyboard shortcuts | [Studio editor → shortcuts](manim-stage/studio-editor.md#keyboard-shortcuts) |
| Drive previews from code (render, cancel, listen for frames/errors) | [Preview service](manim-stage/preview-service.md) |
| Re-render automatically when I save | [Preview service → live reload](manim-stage/preview-service.md#live-reload) |
| Know which files a scene depends on | [Preview service → dependencies](manim-stage/preview-service.md#how-it-works) |
| Pre-render frames for fast scrubbing | [Frame cache](manim-stage/frame-cache.md) |
| Render frames faster on a multi-core machine | [Frame cache → parallel drawing](manim-stage/frame-cache.md#parallel-drawing) |
| Understand why durations round up | [Evaluate and timeline export → frame quantization](manim/evaluate-and-timeline.md#frame-quantization) |
| Check a Manim upgrade didn't change rendering | [Regression tests](workflow/regression-tests.md#after-a-manim-upgrade) |
| Read or validate timeline / runner JSON | [Data formats](reference/data-formats.md) |
| Know what changed since the last update | [whats-new.md](whats-new.md) |

## Update rules (definition of done)

1. **Every feature PR** adds or updates its page(s), updates the tables above, and adds a `whats-new.md` entry.
2. **Every upstream sync** (`/upstream-sync`) records new, changed or removed upstream features we use or mirror, in the relevant page and in `whats-new.md`.
3. **Every fenced `python` block is executed by `tests/test_kb_examples.py`.** Mark fragments that must not run (e.g. Planned APIs) as `python no-run`. Examples must be self-contained and fast: low resolution, short scenes.
4. Pages state status, renderer support and limitations honestly. Link the spec feature ID, ADRs and source files.
