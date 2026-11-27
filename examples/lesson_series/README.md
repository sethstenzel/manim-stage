# Themed lesson series (manim-stage M3 demo)

Three scenes (`Intro`, `Bars`, `Outro`) styled entirely by `.manim-stage/project.json` and joined by `lesson.sequence.json`. Walkthrough: [`docs/kb/tutorials/multi-scene-lesson.md`](../../docs/kb/tutorials/multi-scene-lesson.md).

```bash
manim-stage compose lesson.sequence.json -q low_quality   # → lesson.mp4
manim-stage studio lesson.py Bars                         # edit the theme in the Project tab
```
