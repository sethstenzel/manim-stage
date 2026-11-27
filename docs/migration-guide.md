# Migration guide

Two audiences: people with existing **Manim** projects, and people coming from **Motion Canvas**. Both end up with ordinary Manim scenes; manim-stage never replaces Manim.

## From Manim

### Step 0: nothing changes

Install manim-stage and open your existing file:

```bash
manim-stage studio my_lesson.py
```

- **Every scene previews exactly as `manim render` draws it,** tested pixel for pixel across Manim's feature families (see [Compatibility](kb/reference/compatibility.md)).
- **Plain `manim render` keeps working unchanged.**
- **manim-stage writes nothing into your files.** Sidecar data goes in `.manim-stage/` beside them.

### Step 1: adopt only what you need

Each feature is opt-in and independent.

| You want | Change | Page |
|---|---|---|
| Scrub, inspect and export | nothing | [Studio](kb/manim-stage/studio-editor.md), [Export](kb/manim-stage/export.md) |
| Chapters in a web player | `self.next_section("Name")` (Manim's own API) | [Web player](kb/manim-stage/web-player.md) |
| Re-time to narration without editing code | `class L(StageScene)`, then `self.cue("name")`; drag cues in the Studio | [Cues](kb/manim-stage/cues.md) |
| One look for many scenes | `.manim-stage/project.json` theme + `project.theme()` | [Project](kb/manim-stage/project.md) |
| Values that drive many mobjects | Replace a `ValueTracker` + `add_updater` pair with `Signal` + `bind` | [Signals](kb/manim-stage/signals.md) |
| Animated code edits | `Code` → `AnimatedCode(...).animate_to(new_source)` | [Animated code](kb/manim-stage/animated-code.md) |
| Arrays, stacks, protocols | `manim_stage.edu` | [Educational helpers](kb/manim-stage/edu.md) |

`StageScene` is a `Scene`. If you already subclass `MovingCameraScene`, `ThreeDScene`, …, mix in `StageMixin` instead: `class L(StageMixin, ThreeDScene)`.

### Before and after: updaters to signals

```python no-run
# Manim
t = ValueTracker(0)
bar = Rectangle(width=0.5, height=1)
bar.add_updater(lambda m: m.stretch_to_fit_height(max(t.get_value(), 0.01)).align_to(ORIGIN, DOWN))
self.play(t.animate.set_value(3))

# manim-stage (still a ValueTracker underneath)
t = Signal(0.0)
bar = Rectangle(width=0.5, height=1)
bind(bar, height=lambda: max(t(), 0.01), align=DOWN)
self.play(t.animate.set_value(3))
```

## From Motion Canvas

Concepts carry over with Manim names. For the full map, see [Motion Canvas equivalents](kb/reference/motion-canvas-equivalents.md); the rules behind each port are in [PORTING.md](../PORTING.md).

| Motion Canvas | manim-stage / Manim |
|---|---|
| `makeScene2D(function* (view) {...})` | `class S(StageScene): def construct(self): ...` |
| `yield* circle().scale(2, 1)` | `self.play(circle.animate.scale(2), run_time=1)` |
| `yield* all(a, b)` / `sequence(0.1, …)` / `chain(…)` | `all_of(a, b)` / `sequence(0.1, …)` / `chain(…)` |
| `yield* waitUntil('event')` | `self.cue("event")`, draggable in the Studio |
| `createSignal(0)`, `createComputed(…)` | `Signal(0)`, `computed(…)`, `bind(…)` |
| `<Code>` + `code().code(next, 1)` | `AnimatedCode(src)` + `self.play(code.animate_to(next))` |
| Project variables (`useScene().variables`) | `project.var("name", default)` |
| Editor plugins | [Studio plugins](kb/manim-stage/plugins.md) (`manim_stage.plugins` entry points) |
| Presentation mode / slides | Manim sections → [web player](kb/manim-stage/web-player.md) chapters |

### Worked translation

```ts
// Motion Canvas
export default makeScene2D(function* (view) {
  const x = createSignal(0);
  view.add(<Circle size={80} x={() => x() * 100} fill="#58C4DD" />);
  yield* waitUntil('move');
  yield* x(3, 1);
});
```

```python no-run
# manim-stage
from manim import Circle, LEFT
from manim_stage import Signal, StageScene, bind

class Move(StageScene):
    def construct(self):
        x = Signal(0.0)
        dot = Circle(radius=0.4, color="#58C4DD", fill_opacity=1)
        bind(dot, x=lambda: x() * 1.0)
        self.add(dot)
        self.cue("move")
        self.play(x.animate.set_value(3), run_time=1)
```

### What differs on purpose

- **Units.** Manim units, not pixels: the frame is about 14.2 × 8 by default.
- **Plain Python methods.** `construct` is an ordinary method, not a generator; `self.play` blocks until the animation is done.
- **Layout.** Flexbox layout isn't ported. Use Manim's `arrange`, `next_to` and `to_edge`.
- **Rendering.** Manim (Cairo) renders everything, in the preview and on export.

## Upgrading Manim

manim-stage pins a reviewed Manim commit. Upgrades follow [the upstream sync process](upstream-sync.md); the compatibility and regression suites gate each one.
