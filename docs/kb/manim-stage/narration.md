# Narration (voiceover adapter)

- **Status:** Available
- **Renderer:** Both (audio and timing)
- **Since:** PR #22
- **Spec:** F04, F03 · **Backlog:** 2.4 · **ADRs:** ADR-0013 · **Source:** `src/manim_stage/voiceover.py`, `scene.py` (`StageMixin.narration`)
- **Origin:** the [manim-voiceover](https://voiceover.manim.community) plugin's `with self.voiceover(...) as tracker` and `<bookmark/>` concepts (Manim ecosystem; Motion Canvas has no equivalent). **Built on:** Manim's `add_sound`, `add_subcaption` and `wait`, plus [named cues](cues.md).

## What it is

`self.narration(...)` plays a **recorded** narration while you animate, shows its text as a subcaption, and waits for it to finish. `<bookmark mark='x'/>` tags in the text become **named cues** that you can wait for in code and drag on the timeline. It is manim-voiceover's workflow, but for recordings you already have (your voice, a TTS service you ran elsewhere, or manim-voiceover's own cache), and it runs on Manim 0.30.

manim-stage deliberately does no text-to-speech, speech recognition or microphone recording (spec F04). Bring the audio, and optionally word timings.

## Quick start

```python
from pathlib import Path

import numpy as np

from manim_stage import audio
from manim_stage.capture import capture

t = np.arange(2 * 48000) / 48000
audio.write_wav("intro.wav", (np.sin(2 * np.pi * 200 * t)[:, None].repeat(2, 1) * 0.2).astype("f4"))

Path("narrated.py").write_text('''
from manim import *
from manim_stage import StageScene

class Lesson(StageScene):
    def construct(self):
        bars = VGroup(*[Rectangle(height=h, width=0.5) for h in (3, 1, 2)]).arrange(RIGHT)
        self.play(Create(bars), run_time=0.5)
        with self.narration("intro", file="intro.wav",
                            text="Here is our array. <bookmark mark='swap'/> Now we swap.") as n:
            self.play(Indicate(bars[0]), run_time=0.4)
            n.wait_until("swap")
            self.play(Swap(bars[0], bars[1]), run_time=0.4)
''')

import importlib.util
spec = importlib.util.spec_from_file_location("narrated", "narrated.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
with __import__("manim").tempconfig({"frame_rate": 10, "dry_run": True}):
    tl = capture(mod.Lesson)
for e in tl.events:
    if e.kind in ("sound", "caption", "cue"):
        print(e.kind, e.label, e.start_frame / 10)
# sound intro 0.5 / caption Here is our array. Now we swap. 0.5 / cue intro.swap 1.5…
```

## How it works

`with self.narration(name, *, file=None, text=None, bookmarks=None, words=None, voiceover_cache=None, gain=None, captions=True, wait=True) as n:`

1. Adds the recording at the current time with Manim's `add_sound` (optional `gain` in dB).
2. Adds the text, without bookmark tags, as a Manim subcaption for the narration's length. It appears on the Captions lane and in the `.srt` file Manim writes next to the video.
3. Works out each bookmark's time from the narration start, using the first of these that applies:
   - an explicit `bookmarks={"swap": 2.1}`;
   - **word timings** (`words=[("Here", 0.0, 0.2), …]` or a transcript JSON: Whisper, stable-ts, WhisperX or a plain word list): the start of the first word after the tag;
   - a linear estimate from the tag's position in the text (as manim-voiceover does without word timings).
4. On leaving the block, waits for whatever is left of the narration (`wait=False` to skip).

`n.wait_until("swap")` is `self.cue("intro.swap", at=<bookmark time>)`. So a bookmark:
- shows on the **Cues** lane;
- can be **dragged**, and the override goes to `cues.json`;
- gets the same validation (no negative waits).

Re-time a sentence by dragging, without touching the text or the recording.

The `n` handle also offers manim-voiceover's tracker methods: `n.duration`, `n.get_remaining_duration()`, `n.time_until_bookmark("swap")` (useful as a `run_time`), `n.start`, `n.end`.

**Reusing manim-voiceover output:** `voiceover_cache="media/voiceovers/cache.json"` finds the entry whose text matches (ignoring bookmarks and whitespace). It uses that entry's audio file and its word boundaries (`audio_offset` in 100 ns ticks). TTS you generated with manim-voiceover elsewhere becomes recorded narration here.

**On the timeline:**
- the narration's sound is labelled with its name;
- the Event panel lists its bookmarks;
- the caption carries the word timings.

## Options

| Argument | Meaning |
|---|---|
| `file` | Recording (WAV, MP3, OGG, FLAC, … via PyAV); relative to the working directory |
| `text` | Subcaption text; may contain `<bookmark mark='x'/>` |
| `bookmarks` | Explicit bookmark times, seconds from the narration start |
| `words` | Word timings or a transcript JSON path |
| `voiceover_cache` | A manim-voiceover `cache.json` to take audio and word timings from |
| `gain` | dB, passed to `add_sound` |
| `captions` | Add the subcaption (default on) |
| `wait` | Wait for the narration to end when the block exits (default on) |

## Limitations and unsupported cases

- **No TTS, transcription or recording in manim-stage** (by design). Use manim-voiceover, a TTS service or any recorder to make the audio, and Whisper, stable-ts or WhisperX for word timings.
- **manim-voiceover itself** doesn't run on the Manim 0.30 line yet. The fixes are listed as upstream contributions in the backlog.
- **One caption per narration.** Splitting long narrations into several subcaptions is not done yet.

## Related

- [Named cues](cues.md), [Audio workspace](audio.md), [Timeline](timeline.md).
