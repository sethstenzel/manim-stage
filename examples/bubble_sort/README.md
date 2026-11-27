# Narrated bubble sort (manim-stage M2 demo)

A 30-second lesson built from plain Manim plus manim-stage's narration, named cues and `AnimatedCode`. Walkthrough: [`docs/kb/tutorials/narrated-bubble-sort.md`](../../docs/kb/tutorials/narrated-bubble-sort.md).

```bash
python make_audio.py                             # placeholder narration.wav (or record your own)
manim render lesson.py BubbleSortLesson -ql      # plain Manim render, with audio and subtitles
manim-stage studio lesson.py BubbleSortLesson    # preview; drag cues to re-time
```

Cue times live in `.manim-stage/cues.json` (created when you first drag a cue). Until then, the `at=` defaults in `lesson.py` apply.
