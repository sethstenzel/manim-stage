# manim-stage knowledge base

A local, offline reference for **every manim-stage feature and how to use it**. It also covers the Manim features we build on, and the Motion Canvas behaviour we mirror. It works without a network connection, and its examples are tested.

- **New this update:** [whats-new.md](whats-new.md)
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
| [Frame cache and preview frames](manim-stage/frame-cache.md) | Cache every frame for scrubbing; parallel drawing | Available | Cairo | F01, §4 P1 |
| Studio editor | Python (PySide6) desktop editor: viewport, playback, timeline, Manim library | Planned (M1) | — | F01, F02 |
| Named cues (`self.cue`) | Narration-aligned timing with editable sidecar | Planned (M2) | — | F03 |
| Audio workspace | Waveforms, offset/trim/fade, voiceover adapter | Planned (M2) | — | F04 |
| `AnimatedCode` | Token-level code-diff animations | Planned (M2) | — | F05 |

### Manim features we build on (pinned `main@8c258a0`)

| Page | What | Status in Manim |
|---|---|---|
| [Evaluate and timeline export](manim/evaluate-and-timeline.md) | `Manager.evaluate`, `--timeline-output`, frame-quantized time | Experimental (0.30 line) |
| [Sound and sections](manim/sound-and-sections.md) | `add_sound`, `next_section`, `--save_sections`, MP4 chapters | Stable API; 0.30 mixer |

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
| See when each member of a `LaggedStart` runs | [Event capture → nested animations](manim-stage/event-capture.md#nested-animations) |
| Run a scene safely in the background and get errors with line numbers | [Scene runner](manim-stage/runner.md) |
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
