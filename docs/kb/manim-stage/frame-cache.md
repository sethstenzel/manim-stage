# Frame cache and preview frames

- **Status:** Available
- **Renderer:** Cairo (OpenGL untested)
- **Since:** PR #4
- **Spec:** F01, §4 seek P1, §9 · **ADRs:** ADR-0007 · **Source:** `src/manim_stage/framecache.py`, `src/manim_stage/runner.py`

## What it is

The frame cache pre-renders every frame of a scene into an on-disk cache so the editor can scrub instantly. Cached frames are **pixel-identical** to what `manim render --format png-sequence` produces; this is tested on Windows, Linux and macOS. Reading a cached frame takes about 6–9 ms (see `docs/benchmarks.md`).

## Quick start

```python
import tempfile
from pathlib import Path

from manim_stage.framecache import FrameCache
from manim_stage.runner import run_capture

Path("cache_demo.py").write_text('''
from manim import *

class Demo(Scene):
    def construct(self):
        self.play(FadeIn(Square()), Create(Circle()), run_time=0.6)
''')

cache_dir = tempfile.mkdtemp()
first = run_capture("cache_demo.py", "Demo", fps=15, width=320, height=180, cache_dir=cache_dir)
print(first.frames_drawn, "frames drawn; revision", first.revision)

again = run_capture("cache_demo.py", "Demo", fps=15, width=320, height=180, cache_dir=cache_dir)
assert again.frames_drawn == 0  # nothing changed, every frame came from the cache

cache = FrameCache(cache_dir)
print("frame 4 is at", cache.get(first.revision, 4))
```

## How it works

- **Revision:** a hash of the scene file's bytes, the scene name, the render settings (fps, size, …) and the Manim build (version + git commit). Edit the file or change a setting and you get a new revision, with new frames.
- **Layout:** `<cache_dir>/<revision>/<frame:06d>.png`. Writes are atomic: temp file, then rename. An interrupted run never leaves a half-written frame.
- **Reuse:** the runner skips frames already cached for the revision. On a full cache hit, a rerun takes about 1.4 s (process start + timeline pass).
- **Eviction:**
  - `trim()` deletes the least recently used frames until the cache fits `budget_bytes`.
  - Reading a frame with `get()` marks it as recently used.
  - The revision being rendered is protected.
  - Trim is safe while other runners are writing.
- **Order:** the runner sends the timeline first, then draws the frames.

### Parallel drawing

`run_capture(..., cache_dir=..., workers=N)` starts *N* children. Each replays the scene from the start, which is cheap without drawing, and draws every *N*-th frame. Measured on a 16-thread machine with a 10 s 1080p30 scene:

| Workers | 1 | 4 | 8 |
|---|---|---|---|
| All frames cached | 17.9 s | 8.0 s | 6.8 s |

Each worker gets its own Manim `media_dir` (`<cache_dir>/.media/shard-<i>`). Manim's text/SVG cache is not safe to share between processes running at the same time.

```python
import tempfile

from manim_stage.runner import run_capture

result = run_capture("cache_demo.py", "Demo", fps=15, width=320, height=180,
                     cache_dir=tempfile.mkdtemp(), workers=2)
assert sorted(result.frames) == list(range(result.timeline.duration_frames))
```

## Options

| `FrameCache` | Default | Meaning |
|---|---|---|
| `root` | — | Cache folder |
| `budget_bytes` | 2 GiB | Size limit enforced by `trim()` |
| `put(rev, i, image, compress_level=1)` | — | Store a PIL image atomically |
| `get(rev, i)` | — | Path or `None`; touches the frame for LRU |
| `frames(rev)` | — | Cached frame indices |
| `trim(keep=rev)` | — | Evict LRU frames to fit the budget |

`revision_key(file, scene, settings, manim_version=..., extra=[...])`: pass extra bytes, such as the contents of imported modules or assets, to make them part of the revision.

## Limitations and unsupported cases

- **Imported modules and assets:** the runner hashes every local file the scene imported or opened into the revision (see [preview service → dependencies](preview-service.md#how-it-works)). Files opened from C code (fonts) are not tracked.
- **Frames are PNG**, about 95 kB per frame at 1080p. There is no in-memory cache yet.
- **Not covered:** scenes using wall-clock time, unseeded randomness or `dt`-dependent updaters may not replay identically. A warning for these is planned (ADR-0007).
- **No live scrubbing:** scrubbing uses cached frames only. True live scrubbing (seek P3) is not feasible with current Manim.

## Related

- [Scene runner](runner.md) · [Event capture](event-capture.md) · `docs/benchmarks.md`
