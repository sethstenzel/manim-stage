# Manim: sound and sections

- **Status in Manim:** stable API. The 0.30 line (our pin) replaced the audio mixer and added MP4 chapters.
- **Used by:** [Event capture](../manim-stage/event-capture.md) (sound/section events). The planned audio workspace (F04) and cues (F03) build on these.

## What it is

- `self.add_sound(file, time_offset=0, gain=None, gain_to_background=None)` places an audio file at the current scene time plus `time_offset`.
- `self.next_section(name, type=..., skip_animations=False)` starts a section.
- `manim render --save_sections` writes one video per section plus a JSON index. On the 0.30 line with PyAV ≥ 16, the sections are also embedded as **MP4 chapters**.

## Quick start

```python
import math
import struct
import wave

from manim import FadeIn, Manager, Scene, Square, tempconfig

with wave.open("tone.wav", "wb") as w:  # 0.25 s, 440 Hz
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000)
    w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / 48000)))
                           for i in range(12000)))


class Narrated(Scene):
    def construct(self):
        self.next_section("intro")
        self.add_sound("tone.wav", time_offset=0.1)
        self.play(FadeIn(Square()), run_time=0.5)


with tempconfig({"frame_rate": 15, "progress_bar": "none", "verbosity": "WARNING"}):
    m = Manager(Narrated())
    m.evaluate(capture_timeline=True)
    sound = next(e for e in m.timeline.to_dict()["entries"] if e["kind"] == "sound")
print(sound["start"], sound["duration"])  # 0.1 0.25
```

## Things to know

**0.30 mixer (PyAV):**
- Places audio sample-accurately at 48 kHz in **movie time**.
- This is correct when plays are cached, skipped with `-n`, or in skipped sections. On 0.22 the audio could drift in those cases.

**Not available in Manim:** trim (in-point), fades, mute/solo or volume envelopes. Only `gain` and `gain_to_background`. A negative start trims the head only. The planned audio workspace (F04) pre-processes clips for these.

**Section index:** the `--save_sections` JSON index has no start times. Get section times from the timeline instead ([event capture](../manim-stage/event-capture.md)).

**Chapters** are written only with `--save_sections` and PyAV ≥ 16. Manim's own floor is `av>=15`, so with older PyAV they are silently missing.

## Related

- `docs/audit/manim-core.md` §1.5–1.6 · [Event capture](../manim-stage/event-capture.md)
