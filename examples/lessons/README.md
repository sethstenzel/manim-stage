# Feature lessons

One short, runnable lesson per main manim-stage feature. Each one shows how to **use** the feature and how to **animate** with it. Most lessons rebuild an idea from the [Manim example gallery](https://docs.manim.community/en/stable/examples.html) or the [Motion Canvas guides](https://motion-canvas.io/docs/) with manim-stage's Python APIs. Ideas are described in our own words; no Motion Canvas code is copied.

Every lesson shares one theme, `.manim-stage/project.json`. Change a colour there, or in the Studio's Project tab, and every lesson follows. Walkthrough: [`docs/kb/tutorials/feature-lessons.md`](../../docs/kb/tutorials/feature-lessons.md).

| # | Lesson | Feature | Based on | Run |
|---|---|---|---|---|
| 01 | `01_signals.py` | `Signal`, `computed`, `bind` | MC *Signals*; Manim `ArgMinExample` | `manim-stage studio 01_signals.py RadiusSignal` |
| 02 | `02_flow.py` | `sequence`, `chain`, `all_of`, `delay`, `loop`, `tween` | MC *Animation flow*, *Tweening* | `manim-stage studio 02_flow.py Tweening` |
| 03 | `03_code.py` | `AnimatedCode`: highlight, select, animated edits | MC *Code* guides | `manim-stage studio 03_code.py CodeTour` |
| 04 | `04_cues.py` | named cues (`self.cue`) | MC *Time Events* | `manim-stage studio 04_cues.py TimeEvents` |
| 05 | `05_sound.py` | `self.narration` with bookmarks; `add_sound` | manim-voiceover; MC *Media* | `manim-stage studio 05_sound.py Narrated` |
| 06 | `06_theme.py` | project theme and variables | MC *Project variables* | `manim-stage studio 06_theme.py ThemePalette` |
| 07 | `07_inspector.py` | Inspector and `self.expose` | MC inspector | `manim-stage studio 07_inspector.py Orbit` |
| 08 | `08_transitions.py` | `enter`/`exit`; `manim-stage compose` | MC *Transitions* | `manim-stage compose lessons.sequence.json -q low_quality` |
| 09 | `09_camera.py` | `MovingCameraScene` + `StageMixin`; camera readout | MC *Camera*; Manim `FollowingGraphCamera` | `manim-stage studio 09_camera.py CenterOn` |
| 10 | `10_slides.py` | sections; Sections tab; web player chapters | MC *Presentation* | `manim-stage web 10_slides.py Slides -q low_quality` |
| 11 | `11_demo_params.py` | `demo.param` live controls | Manim `PointWithTrace`, `SineCurveUnitCircle` | `manim-stage studio 11_demo_params.py Lissajous` |
| 12 | `12_text.py` | `Text`, `MarkupText`, `MathTex`; Text tab | Manim text examples, `MovingFrameBox`; MC *LaTeX* | `manim-stage studio 12_text.py Typography` |
| 13 | `13_binary_search.py` | `Array`, pointers, `Trace`, `play_trace` | algorithm lessons | `manim-stage studio 13_binary_search.py BinarySearch` |

- **Plain Manim works too:** `manim -qm 01_signals.py RadiusSignal`.
- **`12_text.py Formula` needs LaTeX** (`manim-stage doctor` checks). Every other lesson uses Pango text only.
- **`05_sound.py` writes placeholder audio** (`narration_lesson.wav`, `click.wav`) on first run. Replace the narration with your own recording.
- **More examples:**
  - [`../algorithms/`](../algorithms/): every educational helper;
  - [`../third_party/`](../third_party/): complete, user-style examples;
  - [`../plugins/`](../plugins/): a Studio plugin.
