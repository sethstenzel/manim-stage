# Scene runner

- **Status:** Available
- **Renderer:** Cairo (OpenGL untested)
- **Since:** PR #2 (cache and workers: PR #4)
- **Spec:** F01, §2.8 · **ADRs:** ADR-0004 · **Source:** `src/manim_stage/runner.py`

## What it is

The runner runs a scene file in a **fresh Python child process**. It reports progress as JSON lines: timeline, frames, done or error. The Studio uses it so that a crashing or hanging scene never takes the editor down, and so that every edit starts from clean Manim state.

## Quick start

```python
from pathlib import Path

from manim_stage.runner import RunnerError, run_capture

Path("runner_demo.py").write_text('''
from manim import *

class Ok(Scene):
    def construct(self):
        self.play(FadeIn(Square()), run_time=0.4)

class Broken(Scene):
    def construct(self):
        self.play(FadeIn(Square()), run_time=0.2)
        raise ValueError("oops")
''')

result = run_capture("runner_demo.py", "Ok", fps=15, width=320, height=180)
print(result.manim_version, result.timeline.duration_frames, result.timings)

try:
    run_capture("runner_demo.py", "Broken", fps=15, width=320, height=180)
except RunnerError as err:
    print("error:", err, "at", err.file, "line", err.line)
    assert err.line == 11
```

## How it works

**The child** is `python -m manim_stage.runner FILE SCENE [options]`. It:
1. imports Manim, then sends `hello`;
2. applies the render settings with `tempconfig`;
3. imports the scene file as a new module (the file's folder is put on `sys.path`, like Manim does);
4. captures the timeline and sends it **before** drawing any frames;
5. with a cache, draws missing frames and sends one `frame` message per frame;
6. sends `done` with timings.

Anything the scene or Manim prints goes to **stderr**, so stdout carries only the protocol.

**Protocol v1** has one JSON object per line, each with `"v": 1`:

| `type` | Fields |
|---|---|
| `hello` | `manim_version`, `pid` |
| `timeline` | `revision`, `timeline` (see [event capture](event-capture.md)) |
| `frame` | `frame` (index), `path` (PNG in the cache) |
| `done` | `elapsed_s`, `timings` (`import`, `timeline`, `frames`, `total`, seconds since start), `frames_drawn` |
| `error` | `message`, `traceback`, `file`, `line` (innermost frame in the scene file if any) |

**The parent**, `run_capture(...)`, runs the child(ren), parses the messages and returns a `RunResult`, or raises `RunnerError` with `.file`, `.line` and `.traceback`.

## Options

| `run_capture` argument | CLI flag | Default | Meaning |
|---|---|---|---|
| `fps` | `--fps` | 15 | Frame rate |
| `width`, `height` | `--width`, `--height` | 854×480 | Pixel size |
| `cache_dir` | `--cache-dir` | none | Cache every frame here; see [frame cache](frame-cache.md) |
| `budget_mb` | `--budget-mb` | 2048 | Frame cache size limit |
| `workers` | `--shard i/n` | 1 | Split frame drawing across *n* children |
| — | `--media-dir` | Manim default (`./media`) | Manim's media folder (text/SVG caches); set per worker automatically |
| `timeout` | — | 300 s | Kill the child after this long |
| `python` | — | current interpreter | Interpreter for the child |

## Limitations and unsupported cases

- **Trust boundary:** the runner **executes the scene file**. Only run trusted local projects. Python sandboxing is out of scope (spec §2.8). Installed `manim.plugins` entry points also run, because `import manim` loads them.
- **Output order:** results are returned when the child exits. Streaming them to the editor while the child runs comes with the preview service (M1).
- **Cancellation** is by `timeout` only for now. Explicit cancel/restart comes with the preview service (M1).
- **Media folder:** without `--media-dir`, Manim writes its text/SVG cache into `./media` of the current directory, as `manim render` does.

## Related

- [Event capture](event-capture.md) · [Frame cache](frame-cache.md) · ADR-0004 in `docs/architecture-decisions.md`
