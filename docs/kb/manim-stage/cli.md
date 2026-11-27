# Command line (`manim-stage`)

- **Status:** Available
- **Since:** PR #16
- **Spec:** F01 · **Backlog:** 1.6, MF.9 (doctor) · **ADRs:** ADR-0009 · **Source:** `src/manim_stage/cli.py`, `src/manim_stage/doctor.py`
- **Motion Canvas origin:** `npm run serve` (start the editor). **Built on:** Manim's CLI conventions: quality presets, `manim render` for output. Manim has no plugin subcommands, so manim-stage has its own entry point (ADR-0009).

## What it is

`manim-stage` opens the Studio editor and gives headless access to what it knows about a scene. It never replaces `manim render`, which you keep using for final output (the Studio's [export](export.md) runs it for you).

## Quick start

```bash
manim-stage studio lesson.py              # editor on the first Scene in lesson.py
manim-stage studio lesson.py Intro -q medium_quality --workers 4
manim-stage scenes lesson.py              # Scene classes, their line and Manim base class
manim-stage timeline lesson.py Intro      # every play/wait/section/sound with times and source line
manim-stage timeline lesson.py Intro --json > intro.timeline.json
manim-stage doctor                        # what this machine can render
manim-stage cache                         # preview cache size; --clear to empty it
```

The same functions are callable from Python:

```python
from pathlib import Path

from manim_stage.cli import main

Path("cli_demo.py").write_text('''
from manim import *

class Hello(Scene):
    def construct(self):
        self.play(Write(Text("Hello")), run_time=0.5)
        self.next_section("outro")
        self.wait(0.3)
''')
assert main(["scenes", "cli_demo.py"]) == 0
assert main(["timeline", "cli_demo.py", "Hello"]) == 0
```

## Commands

| Command | What it does |
|---|---|
| `studio FILE [SCENE]` | Opens the [Studio editor](studio-editor.md). Options: `-q/--quality` (Manim preset, default `low_quality`), `--workers`, `--cache-dir`, `--no-watch`. Same as `python -m manim_stage.studio`. |
| `scenes FILE [--json]` | Lists the `Scene` subclasses defined in the file, in source order, with their line and nearest Manim base (`Scene`, `MovingCameraScene`, `ThreeDScene`, …). Imports the file in a child process. |
| `timeline FILE SCENE [--fps N] [--json]` | Shows the [event capture](event-capture.md) as a table, with nesting, times and source lines. `--json` prints the [timeline schema](../reference/data-formats.md) document. Doesn't draw frames. |
| `doctor [--json]` | Checks Python, the Manim build and required APIs, Cairo, Pango fonts (`Text`), LaTeX + dvisvgm (`Tex`/`MathTex`), FFmpeg/PyAV encoders for each export format, PySide6, and installed Manim plugins. Exits 1 if something essential fails. |
| `cache [--clear] [--cache-dir DIR]` | Shows the preview frame cache's size, or empties it. |

`--version` prints the manim-stage version.

## Exit codes

`0` success · `1` the scene failed, or `doctor` found a failure · `2` bad usage, missing PySide6, or an unsupported Manim build.

## Limitations and unsupported cases

- `scenes` and `timeline` execute the file's Python, like `manim render` does. Use trusted files only.
- `bake` and `validate` for narration cues arrive with M2 (backlog 2.1).

## Related

- [Studio editor](studio-editor.md), [Export](export.md), [Scene runner](runner.md).
