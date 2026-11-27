# Data formats and the time model

- **Status:** Timeline and runner messages: Available. Cues, project manifest, editable properties: Planned (draft schemas).
- **Spec:** §8 · **Source:** `docs/schemas/` · **Tests:** `tests/test_schemas.py`

## What it is

These are the JSON contracts between the runner, the editor and project files. Each file and message carries a schema name and version. Full schemas and rules: [docs/schemas/README.md](../../schemas/README.md).

| Format | Where | Status |
|---|---|---|
| Timeline (`manim_stage.timeline` v1) | runner → editor; `SceneTimeline.to_dict()` | Available |
| Runner messages (protocol `v: 1`) | runner stdout, one JSON per line | Available |
| Scene sequence (v1) | `*.sequence.json` | Available ([scene transitions](../manim-stage/transitions.md)) |
| Exposed properties (`manim_stage.properties` v1) | `.manim-stage/properties.json` | Available ([inspector](../manim-stage/inspector.md)) |
| Project (`manim_stage.project` v1) | `.manim-stage/project.json` | Available ([project theme and variables](../manim-stage/project.md)) |
| Audio clips (`manim_stage.audio` v1) | `.manim-stage/audio.json` | Available ([audio workspace](../manim-stage/audio.md)) |
| Cues (`manim_stage.cues` v1) | `.manim-stage/cues.json` | Available ([named cues](../manim-stage/cues.md)) |
| Project (`manim_stage.project` v1) | `.manim-stage/project.json` | Planned (draft) |
| Editable property | inspector | Planned (draft) |

## Quick start: validate a timeline

```python
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from manim import tempconfig

from manim_stage.capture import capture
from manim_stage.runner import load_scene_class

Path("fmt_scene.py").write_text('''
from manim import *

class S(Scene):
    def construct(self):
        self.play(FadeIn(Square()), run_time=0.3)
''')
with tempconfig({"frame_rate": 10, "pixel_width": 160, "pixel_height": 90,
                 "progress_bar": "none", "verbosity": "WARNING"}):
    doc = capture(load_scene_class(Path("fmt_scene.py"), "S")).to_dict()

import manim_stage

schema_path = Path(manim_stage.__file__).parents[2] / "docs" / "schemas" / "timeline.schema.json"
Draft202012Validator(json.loads(schema_path.read_text())).validate(doc)
print(doc["events"][0]["start_frame"], doc["events"][0]["end_frame"])  # 0 3
```

(`jsonschema` is a dev dependency, and this example runs from a source checkout.)

## The time model in five rules

1. Times are **integer frame indices**. Frame *i* covers `[i/r, (i+1)/r)`.
2. Ranges are **half-open**, `[start, end)`. Zero-length markers have `start == end`.
3. Seconds are derived (`frame / r`), never accumulated.
4. Sounds keep their exact start in seconds. Audio samples are at 48 kHz, so one frame at 30 fps is 1600 samples.
5. Cue targets are absolute frames from scene start, rescaled with rounding when the frame rate changes.

## Related

- [Event capture](../manim-stage/event-capture.md) · [Scene runner](../manim-stage/runner.md) · ADR-0005, ADR-0006
