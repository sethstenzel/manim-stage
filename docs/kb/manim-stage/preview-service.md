# Preview service

- **Status:** Available (engine). The editor UI that uses it is Planned (M1).
- **Renderer:** Cairo (OpenGL untested)
- **Since:** PR #10
- **Spec:** F01, §4, §8 `PreviewMessage` · **ADRs:** ADR-0004, ADR-0010 · **Source:** `src/manim_stage/studio/service.py`
- **Motion Canvas origin:** the editor's live project preview. **Built on:** Manim's `Manager.evaluate`, run in [runner](runner.md) child processes.

## What it is

`PreviewService` is the Studio's engine. Ask it to render a scene; it runs the scene in background child processes and tells you, as events, what happened: the timeline, each cached frame, log lines, errors with file and line, and completion. It has no GUI and opens no network port, so you can drive it from a script, a test or the editor.

## Quick start

```python
from pathlib import Path

from manim_stage.studio import PreviewService, RenderSettings

Path("lesson.py").write_text('''
from manim import *
from helper import COLOR

class Intro(Scene):
    def construct(self):
        self.play(Create(Circle(color=COLOR)), run_time=0.5)
        self.wait(0.2)

class Outro(Scene):
    def construct(self):
        self.play(FadeOut(Square()), run_time=0.3)
''')
Path("helper.py").write_text("COLOR = '#58C4DD'\n")

svc = PreviewService("lesson.py", cache_dir=".preview-cache",
                     settings=RenderSettings(fps=15, width=320, height=180))
svc.subscribe(lambda m: print(m.seq, m.type, m.data.get("state") or m.data.get("frame") or ""))

print([s["name"] for s in svc.discover_scenes()])      # ['Intro', 'Outro']
seq = svc.render("Intro")
svc.wait_idle(120)
rev = svc.current
print(rev.state, rev.timeline.duration_frames, len(rev.frames))   # done 11 11
print([p.name for p in svc.dependencies])                          # ['lesson.py', 'helper.py']
assert rev.state == "done" and len(rev.frames) == rev.timeline.duration_frames
svc.close()
```

## How it works

- **Revisions.** Every `render()` call gets the next integer `seq`. A new call kills the running children; messages still arriving from an older `seq` are dropped, so an outdated frame never replaces a current one.
- **Order of events** for one revision: `status: running` → `timeline` → `frame` × N (with `cached`/`total` progress) → `done` → `status: done`. On a scene exception: `error` (message, traceback, file, line) → `status: error`. Cancelled: `status: cancelled` with `reason` `superseded` or `cancelled`. `log` carries stderr lines (Manim warnings, the scene's `print`s).
- **Frames** come from the [frame cache](frame-cache.md). Re-rendering an unchanged scene redraws nothing.
- **Dependencies.** The runner records every local file the scene imported or opened (helper modules, images, SVGs, data files, sounds). Their content is part of the cache revision, so editing `helper.py` invalidates cached frames. `svc.dependencies` lists them, for file watching.
- **Where Manim writes.** Manim's own media folder (text/SVG/LaTeX caches) goes under the cache folder, one per worker, never into your project.
- **Threads.** Listeners are called on background threads. GUI code must hand events to its own thread.

Message format: `docs/schemas/preview-message.schema.json`; see [data formats](../reference/data-formats.md).

## Options

| `PreviewService(...)` / `RenderSettings(...)` | Default | Meaning |
|---|---|---|
| `cache_dir` | required | Frame cache and per-worker Manim media folders |
| `settings.fps`, `width`, `height` | 15, 854×480 | Preview frame rate and size |
| `settings.seed` | 0 | Random seed (part of the revision) |
| `settings.workers` | 1 | Child processes that share the frame drawing |
| `budget_mb` | 2048 | Frame cache size limit |
| `cwd` | the scene's folder | Working directory of the children (relative asset paths resolve here) |
| `python` | current interpreter | Interpreter for the children |

## Limitations and unsupported cases

- Files opened from C code (fonts by Pango, media by FFmpeg) are not seen; sounds added with `add_sound` are added from the timeline.
- Files read only during frame drawing (not during the timeline pass) are not tracked. In practice Manim scenes load assets while building, so this is rare.
- Rendering executes the scene's Python. Open trusted projects only.

## Related

- [Scene runner](runner.md), [Frame cache](frame-cache.md), [Event capture](event-capture.md).
