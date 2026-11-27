# Motion Canvas baseline audit (behavior reference for manim-stage)

Scope: read-only study of Motion Canvas (MC) as a **behavior/UX reference only** (spec §2.9). Everything below is described in my own words; no MC source is reproduced. Short API names and signatures are cited.

Refs used (blobless clone `C:\s3711\git\manim-stage\.upstream\motion-canvas`):

- `@v3.17.2` = `e735a995aa738ca682feb4204a39ee7db7b5d279` (latest stable)
- `@main` = `7b91435c301d530351dcf5ebb91dd139c002e405` (unreleased: programmable sounds #1082, sound waveforms #1158, audio offset editing #1166)
- Paths are repo-relative. `core/` = `packages/core/src/`, `ui/` = `packages/ui/src/`, `2d/` = `packages/2d/src/`, `vite/` = `packages/vite-plugin/src/`, `docs/` = `packages/docs/docs/`.
- "unverified" = inferred from reading the source, or not confirmed at runtime.

## 0. Project health (checked with gh API on 2026-11-26)

| Item | Finding |
|---|---|
| License | MIT for core/2d/ui/vite-plugin. On `@main`, the `@motion-canvas/ffmpeg` exporter was **relicensed to GPLv3** (commit a40d50b message) because it uses FFmpeg. |
| Last stable release | **v3.17.2, 2024-12-14**. Last tag of any kind: v3.18.0-alpha.0, 2025-02-16 (`alpha` branch, same date). |
| Commit activity since 2025-01-01 | **13 commits on main**. 12 landed in Feb 2025 (sounds, waveforms, audio-offset fixes, shortcut refactor). The only later commit is #1231, 2026-07-02, which moves the docs domain from motioncanvas.io to **motion-canvas.io**. Spec §14 URLs point at the old domain. |
| PRs/issues | Since mid-2025, PRs are being opened (#1235–#1246) but none merged apart from the domain change. 22 issues opened since 2025-06-01 and 5 closed. 181 issues open. About 20.3k stars. Not archived. |
| Verdict | **Dormant / minimal maintenance.** The feature set is effectively frozen at v3.17.2 plus the unreleased Feb-2025 audio work. Treat it as a stable reference, not a moving target. Don't expect upstream answers. |

Architecture recap (`docs/advanced/plugins/index.mdx@v3.17.2`): a Vite dev server on Node, plus a browser app. The browser app holds the **runtime** (player, scenes, the user's animation code, all executed in the browser) and the **editor** (Preact UI). Rendering also happens **in the browser**: frames are sent over the Vite websocket to Node, which writes them out. There is no headless/CLI renderer in this repo. I found no puppeteer/headless path outside e2e tests.

---

## 1. Editor

### Layout (`ui/Editor.tsx`, `ui/components/layout/Navigation.tsx` @v3.17.2)

- A left icon rail of tabs. Each tab opens a resizable left sidebar pane:
  - **Video Settings**
  - plugin tabs (for example the 2d "Scene Graph" tree)
  - **Thread Debugger**, a live tree of the running generator threads (`ui/components/sidebar/Threads.tsx`)
  - **Console**, with an error-count badge that shakes on a new error
  - **Settings**, for app-wide preferences
- The rail also has a link back to project selection, a Docs link, an "experimental features" badge, and a Timeline toggle for the bottom panel.
- The rail is followed by a vertical split: sidebar plus viewport on top, timeline at the bottom. Both splits are resizable and can be hidden. A footer shows package versions (`ui/components/footer/Versions.tsx`).
- **No scene picker.** A *project* is an ordered list of scenes that always plays as one continuous timeline. With several projects configured (`motionCanvas({project: [...]})`), a **project selection page** appears first (`ui/ProjectSelection.tsx`; `docs/getting-started/configuration.mdx`). To isolate one scene, middle-click its clip on the timeline. That sets the playback range to that scene (`ui/components/timeline/SceneTrack.tsx`).

### Viewport (`ui/components/viewport/*`)

- A canvas preview with:
  - zoom to fit (`0`), zoom in/out (`=`/`-`), pan
  - a toggleable grid (`'`)
  - mouse coordinates in scene space (an app setting), with `P` to copy them
  - an EyeDropper color picker (`I`, Chromium only)
  - plugin overlays drawn on top: selection outlines from the 2d inspector, and the grid plugin (`ui/plugin/GridPlugin`)
- While rendering, the viewport switches to a render view showing elapsed time and an ETA (`Viewport.tsx`, `core/app/TimeEstimator.ts`).

### Playback controls (`ui/components/playback/PlaybackControls.tsx`)

- Speed select: ×0.25, ×0.5, ×1, ×1.5, ×2.
- Mute toggle with a volume slider.
- Go to start, previous frame, play/pause, next frame, go to end.
- Loop toggle (on by default; `core/app/Player.ts` initial state has `loop: true`, `muted: true`).
- A readout of the actual achieved FPS, or "PAUSED".
- A snapshot button that renders the current frame at *rendering* settings into `output/still/<project>/NNNNNN.png` (`core/app/Renderer.ts renderFrame`).
- Time readouts on both sides: current time and total duration as `HH:MM:SS:FF [frame]` (`ui/components/viewport/Timestamp.tsx`).
- **How speed works:** each tick advances the frame by `speed`. At ×0.25, frames are fractional, so the generator is really sampled at sub-frame times. That gives true slow motion, not repeated frames. Changing speed forces a reload and recalculation (`Player.setSpeed`, `PlaybackManager.next`).

### Playback range and loop

- The range is a project setting `shared.range: [startSec, endSec]`. It is stored in seconds in the project `.meta`, with `null` meaning Infinity.
- Playback, looping and rendering are all clamped to the range. Scrubbing outside it flashes the range border (`ui/components/timeline/RangeSelector.tsx`, `Timeline.tsx`).

### Rendering settings (Video Settings tab; `core/app/ProjectMetadata.ts`, `docs/getting-started/rendering/index.mdx`)

There are three groups:

- **General (shared):**
  - background color (empty means transparent; cannot be animated)
  - range
  - resolution (default 1920×1080)
  - audio offset (seconds; disabled when no audio)
- **Preview:**
  - fps (default 30, with presets)
  - resolution scale (enum)
- **Rendering:**
  - fps (default 60)
  - resolution scale
  - color space (sRGB or Display-P3)
  - exporter, plus that exporter's own option sub-form

The groups render buttons next to each other: a **Render/Present** split button (a dropdown switches between the two), Abort, and an "Output Directory" button that opens the folder in the OS file manager (`vite/partials/exporter.ts` `/__open-output-path`).

### Project/app settings

- **Per-project:** the `.meta` file next to `project.ts` (see §6).
- **Per-user, app-wide:** `~/.motion-canvas/settings.json` (`vite/partials/settings.ts`; `core/app/SettingsMetadata.ts`). It holds the UI accent color, a legacy font toggle, whether coordinates are shown, and **defaults for new projects** (background, resolution).
- **UI layout state** (timeline zoom/scroll, the active tab, the chosen render/present action) is kept in browser localStorage (`ui/hooks/useStorage.ts`).

### Keyboard shortcuts (`ui/contexts/shortcuts.tsx` @v3.17.2; reorganized on @main)

Shortcuts are scoped to whichever panel the pointer is over.

| Scope | Key | Action |
|---|---|---|
| Global | Space | Toggle playback |
| Global | ← / → | Previous / next frame |
| Global | Shift+← / Shift+→ | Go to first / last frame |
| Global | M | Mute |
| Global | ↑ / ↓ | Volume ±10% |
| Global | L | Loop |
| Viewport | 0 / = / - / ' / P / I | Fit / zoom in / zoom out / grid / copy coordinates / color picker |
| Timeline | F | Scroll the view to the playhead |
| Timeline | B / N | Set range start / end to the playhead |
| Presentation | ← → Shift+← Shift+→ F | Previous / next / first / last slide, fullscreen |

`@main` adds an `EditorPlugin.shortcuts` hook so plugins can register their own shortcuts (`ui/plugin/EditorPlugin.ts@main`).

### Preview updates on file change (Vite HMR)

- Each scene is imported with a `?scene` query. The Vite plugin turns that import into a wrapper module (`vite/partials/scenes.ts`) that:
  - creates the `<scene>.meta` sidecar if it is missing
  - attaches the meta to the scene
  - **self-accepts HMR**
- When a scene file, or a module it imports, changes, the new scene description goes out through a persistent `onReplaced` dispatcher. The Player calls `scene.reload(newDescription)`:
  - only **that scene's cache** is invalidated (`core/scenes/GeneratorScene.reload`)
  - a recalculation is requested (`core/app/Player.ts` constructor subscription)
- **The playhead is preserved:** recalculation re-seeks to the previous frame (`Player.prepare`: if no seek is pending, it seeks to the current frame).
- **Errors** thrown while recalculating are logged to the Console with a resolved stack. The Console shows a source frame and a "go to source" action that calls Vite's `/__open-in-editor?file=…:line:col` (`ui/utils/sourceMaps.ts`, `ui/components/console/*`).
- There is **no cancellation** of an in-progress recalculation. Everything runs on the main thread, yielding with `setTimeout(0)` between scenes (`GeneratorScene.recalculate`).
- **Changing `project.ts` itself:** the project wrapper module does not self-accept HMR, so this probably triggers a full page reload (unverified).
- **Audio files:** HMR is delayed by 1 s, then the browser is notified with `motion-canvas:assets` (`vite/partials/assets.ts`). Files matching `bufferedAssets` (default `.wav`/`.ogg`) are served from memory, so an external audio editor can still overwrite them while in use.

### How seeking works (central to manim-stage's design)

There are **no frame caches or state checkpoints in preview.** Seeking re-runs the generator.

1. **Recalculation pass** (`PlaybackManager.recalculate`, `GeneratorScene.recalculate`). After any reload, every *uncached* scene is reset and stepped frame by frame at the preview fps, **without drawing**, until it can transition out. This pass records per scene `firstFrame`, `duration`, `lastFrame` and `transitionDuration`, plus the time events, slides and (on @main) sounds registered along the way. Scenes whose cache is still valid are skipped, and only their `firstFrame` is shifted. The scene cache holds metadata only, not pixels.
2. **Seeking** (`PlaybackManager.seek`):
   - Forward seek within the current scene: step forward.
   - Backward seek, or a jump into a later scene: pick the scene that contains the target frame (`findBestScene`, using the cached frame ranges), **reset it** (fresh generator, fresh RNG from the stored seed, new `Variables`), then step it forward without drawing to the target frame.
   - The scene boundary is the only checkpoint. The cost is O(frames from scene start), and you only see the drawn frame. Profiling labels this "seek time".
3. **Audio is the master clock at ×1:**
   - If the animation gets ahead of the audio by more than 1/50 s, the animation waits.
   - If it falls behind, it seeks forward to the audio time and drops frames.
   - At other speeds, the audio is resynced to the animation every frame (`Player.run`, `MAX_AUDIO_DESYNC`).
   - The redraw loop runs on rAF and is throttled to about fps+5.

Implication for us: MC gets fast backward seeks because JS scenes are cheap to replay and side-effect-free *by convention*. Manim scenes are not cheap to replay, so manim-stage needs the frame-cache strategy from spec §4. **MC is not proof that replay-from-start is good enough for Manim.**

---

## 2. Timeline (`ui/components/timeline/*` @v3.17.2)

### Structure, top to bottom

1. **Range selector strip:**
   - drag on empty space to create a range
   - drag the range body to move it
   - drag the handles to resize
   - double-click to reset the range to everything
   - Shift / Ctrl+Shift visually activate the range and track modes
2. **Ruler** of frame-indexed ticks (`Timestamps.tsx`). Tick density is snapped to a power of two of frames-per-pixel, with ticks at least 32 px apart. Ticks are in frames, with seconds shown via CSS/data attributes (unverified).
3. **Scene track:**
   - one clip per scene, sized to its cached duration
   - the start of a clip is shaded for its transition-in duration
   - clicking the scene name opens its source (the scene's creation stack)
   - middle-click sets the range to that scene
   - each clip contains a **slide sub-track** (`beginSlide` names, click to open source, middle-click to seek)
4. **Label (time-event) track**, one label group per scene (§3).
5. **Audio track:**
   - **v3.17.2:** a single waveform canvas for the project's one audio file. It draws peak data scaled to the visible window. Hold Shift and drag to change the audio offset, written to `shared.audioOffset` on release (`AudioTrack.tsx`).
   - **@main:** one waveform per *programmable sound* clip (§8). These respect trim, playback rate and offset (`AudioTrack.tsx@main`, `core/media/AudioResourceManager.ts@main`).
6. **Playhead** plus a hover preview line. While a label or range handle is dragged, the preview line follows the dragged time.

### Interaction

- Left-drag anywhere scrubs (a seek on every pointer move; frames are floored).
- Middle-drag pans.
- Mouse wheel zooms around the cursor. The scale runs from 0.5× up to about 128 px per frame. Shift+wheel or horizontal wheel scrolls.
- Zoom and scroll are persisted in localStorage. When the total duration changes, the scale is adjusted so the visible span stays stable.

### Where the data comes from

All of it comes from the recalculation pass (§1). The UI subscribes to:

- `scene.onCacheChanged` for clip extents
- `scene.timeEvents.onChanged` for labels
- `scene.slides.onChanged` for slides
- `scene.sounds.onChanged` for sounds (@main)
- `player.audio.onDataChanged` for peaks

There is **no per-animation or per-tween track.** Only scenes, slides, time events and audio appear. The Thread Debugger shows the live thread tree for the current frame only.

**Undo/redo:** none. A grep for undo/redo across `ui/` and `core/` finds nothing.

---

## 3. Time events (`core/scenes/timeEvents/*`, `core/flow/scheduling.ts`, `core/utils/useDuration.ts`, `ui/components/timeline/Label.tsx`, `docs/getting-started/time-events.mdx` @v3.17.2)

### API

- `waitUntil(name, after?)` is exactly `waitFor(useDuration(name))`, optionally followed by `after`.
- `useDuration(name)` registers the event at the current thread time and returns its duration in seconds. It can be used anywhere a duration is needed, for example as the duration of a tween.
- A new event defaults to **0 s duration**, so it happens immediately.

### Model (per scene)

- **Persisted:** `{name, targetTime}` in the scene's `.meta` under `timeEvents`. `targetTime` is in seconds, absolute, measured from the **scene** start (not the project start), and is an unquantized float, for example `0.98140625`.
- **At runtime**, each event carries:
  - `initialTime`: when the `waitUntil` was reached
  - `targetTime`
  - `offset`: the duration, equal to target minus initial and clamped to at least 0 in the editor
  - `stack`: a creation stack trace, used for "go to source"

### Absolute vs relative semantics, and ripple

- **When the code changes** and a recalculation runs, `preserveTiming` is true. Each event keeps its stored **absolute `targetTime`**, and its duration is recomputed as `max(0, targetTime − initialTime)`. If code before an event becomes longer, the wait shrinks, so the cue stays at the same moment in the narration. That is the property you want for audio sync.
- **When an event is dragged in the timeline**, the UI calls `timeEvents.set(name, newOffset, preserve = shiftKey)`:
  - **Without Shift (default ripple):** `preserveTiming` becomes false for the next recalculation. *Every* event's `targetTime` is rebuilt as `initialTime + offset`, so later events keep their durations and move with the change.
  - **With Shift:** later events keep their absolute `targetTime`, and their durations absorb the change.
  - After the recalculation, `preserveTiming` goes back to true.
- The ripple is a by-product of replaying the scene: lengthening one wait pushes back the `initialTime` of every later event.
- **Ripple stays inside one scene,** because times are scene-relative. Later scenes simply start later.

### Dragging UX

- During a drag, a dark trail runs from `initialTime` to the label pill, and the playhead preview follows the label.
- On release, the scene reloads and recalculates. The rest of the timeline only updates after the drop. There is no live ripple preview of later labels.
- Double-click opens the source line. Middle-click seeks to the event.
- A second marker (`labelClipTarget`) shows the *stored* `targetTime`. When it differs from the effective time (because of the clamp), you can see the ghost target.
- Dragged offsets are not snapped to frames.

### Persistence

- `MetaFile` sends a `motion-canvas:meta` websocket message, and the Vite plugin calls `fs.writeFile` with pretty-printed JSON, then acknowledges. If no ack arrives within 1 s, the browser gives up with a timeout error.
- Writes are **not atomic.** There is no temp file and rename, and no backup.
- The plugin ignores the HMR echo of its own write for 1 s (`vite/partials/meta.ts`).
- Editing the `.meta` on disk, for example through git checkout, hot-reloads into the editor (`EditableTimeEvents.handleMetaChanged`).
- The meta is written only when the events changed or the number of events changed (`handleRecalculated`).

### Identity, collisions, missing and renamed events

- **Identity** is the event name string, scoped to one scene.
- **Collision:**
  - A second `waitUntil` with the same name in the same scene run logs an *error* with a stack trace, and the second call returns duration 0.
  - There is no automatic suffixing.
  - The same name may be reused in *different* scenes.
  - Slides behave differently: a duplicate slide name only logs a *warning* (`core/scenes/Slides.ts`).
- **Missing or orphaned:** events are rewritten from the set registered during the last recalculation. An event that is no longer reached is **silently dropped from the meta** the next time the meta is written. There is no warning and no tombstone.
- **Renamed:** treated as a new event with duration 0. The old timing is lost silently, apart from git history.
- **Unreachable** events inside a branch that did not run in this pass get the same treatment as missing ones.

### Rendering path difference (potential preview/export divergence; unverified at runtime)

- During render, `ReadOnlyTimeEvents` computes the duration as `targetTime − initialTime` **without the ≥0 clamp** (`core/scenes/timeEvents/ReadOnlyTimeEvents.ts`).
- The editor keeps a stale `targetTime` that is less than `initialTime` in the meta (only the effective offset is clamped). In that case, `waitFor` gets a negative argument and sets thread time *backwards* (`core/flow/scheduling.ts waitFor`). Later tweens would then start "in the past" and jump. In the editor they are clamped.

**Lesson for F03:** validate in one place and use one resolver for preview and export.

---

## 4. Code animations

### `Code` node (current; `2d/lib/components/Code.ts`, `2d/lib/code/*`, `docs/components/code/index.mdx`)

**Content model**

- `code` is a **code signal** (`CodeSignal`). Its value is a *scope*: a list of fragments, plus a `progress` value from 0 to 1.
- A fragment is one of:
  - a plain string (unchanged text)
  - a `{before, after}` pair (changing text)
  - a nested scope or signal
- The `CODE` tagged template builds scopes that can embed other code signals. Embedded signals stay reactive, which lets you compose snippets.

**Editing API** (on `code().code`, or on any `Code.createSignal()`)

- `code(newString, duration)`: a **diff-based** transition.
- `append(code[, duration])` and `prepend(…)`. Both also work as a tagged template, for example `append(0.6)` followed by a template.
- `insert(point, code[, duration])`.
- `remove(range[, duration])`.
- `replace(range, code[, duration])`.
- `edit(duration)` as a tagged template whose holes are `insert(text)`, `remove(text)` or `replace(before, after)`. This states the change inline without positions.
- Without a duration, the edit applies immediately. Several edits wrapped in `all(...)` animate at the same time.

**Ranges**

- A `CodeRange` is a pair of 0-based points, `[line, col]` to `[line, col]`.
- Columns sit between characters, so the end is exclusive.
- Helpers: `word(line, col, len?)` and `lines(from, to?)`. Without `len`, `word` runs to the end of the line.
- Queries: `findFirstRange`, `findAllRanges`, `findLastRange`. Each takes a string or RegExp. On @main, a plain string matches exactly (#1153).
- Geometry: `getPointBBox(point)`, and `getSelectionBBox(range)`, which returns one bbox per line in node-local space. Use these to place boxes, carets or arrows yourself. Since v3.17.x the bboxes account for in-flight transitions (#1116).

**Selection highlighting**

- `selection` is a signal holding one or more ranges.
- Tweening it, for example `selection(range, duration)`, drives a `selectionProgress` from 0 to 1. Each glyph gets a per-character "selected-ness" value interpolated between the old and new selection.
- The default draw hook dims unselected glyphs by multiplying alpha down to about 0.2.
- `drawHooks.token(ctx, text, position, color, selection)` can be overridden, for example to blur.
- `DEFAULT` resets the selection to "everything selected".

**Diff algorithm** (`2d/lib/code/diff.ts`, `CodeDiffer.ts`, `CodeTokenizer.ts`, `LezerHighlighter.ts`)

- The algorithm is **patience diff** (unique common elements, then the longest increasing subsequence, recursing between anchors), run over **tokens, not lines**.
- Token source:
  - With a highlighter, the highlighter's `tokenize()` is used. `LezerHighlighter` uses the **Lezer parse tree's leaf nodes** plus the gaps between them, so diffs are **syntax-token-level**.
  - The fallback `defaultTokenize` splits on runs of whitespace and on single brackets `()[]{}`.
- Runs of deleted and inserted tokens are merged into `{before, after}` fragments. Matched tokens become unchanged fragments.
- **There is no move detection.** The result has a `moved` field that is always false, so a moved block shows as a delete plus an insert.
- No explicit override mapping is possible. To force a particular pairing, use `edit`/`replace`.
- When a token repeats, patience diff only anchors on tokens that are unique in both versions. Non-unique tokens are matched by prefix/suffix trimming inside each gap, or not matched at all.

**Transition rendering** (`2d/lib/code/CodeCursor.ts`)

- Layout is on a **monospace grid.** The cell width is the measured width of "X". Each glyph's width is rounded to whole cells.
- Unchanged fragments **slide** from their old cursor position to their new one. Positions interpolate linearly with the eased progress. Line count and width also interpolate, so the node's size animates.
- Changed fragments **cross-fade around the midpoint:**
  - the "before" text shows until progress reaches 0.5, then the "after" text
  - alpha dips to 0 at the midpoint, with the fade spanning the middle 80%
  - a small vertical slide runs proportional to the change in row count
- If a token's text is the same but its highlight color changed, the color is **lerped**.

**Timing**

- The default duration in `edit()` is 0.6 s. Signal tweens default to `easeInOutCubic`, and a custom timing function can be passed.
- An edit is a single tween of the scope's `progress`. There is no per-token stagger.

**Syntax highlighting**

- `Code.defaultHighlighter = new LezerHighlighter(parser, HighlightStyle?)`, set per project, or `highlighter` per node.
- Grammars are installed from npm (`@lezer/javascript`, `@lezer/python`, `@lezer/rust`, and so on). Dialects are supported (jsx, ts).
- Theme: a CodeMirror `HighlightStyle` (`DefaultHighlightStyle`).
- `CodeHighlighter` interface: `initialize()` (async-capable), `prepare(code) → cache`, `highlight(index, cache) → {color, skipAhead}`, `tokenize(code)`. A custom highlighter can be plugged in.

**Known limitation:** the docs admit **text jitter in Chromium**, because canvas text snaps to whole pixels, and recommend rendering in Firefox (`docs/components/code/index.mdx` "Rendering").

### `CodeBlock` (legacy, deprecated; to be removed in v4; `2d/lib/components/CodeBlock.ts`, `docs/components/code-block.mdx`)

- Highlighting comes from **starry-night** (TextMate grammars), chosen by `language`. The default language is `tsx`. You must `yield view.add(...)` so the highlighter can load.
- The common leading indentation is removed automatically when the code starts with a newline.
- Selection uses `range(l1,c1,l2,c2)`, `word`, `lines`, which can be combined by spreading. Unselected text is desaturated.
- `edit(duration, changeSelection = true)` is a tagged template with `insert`, `remove`, `edit(before, after)`.
  - Removed code goes out, the remaining code moves, inserted code comes in.
  - By default, the selection jumps to the changed parts.

---

## 5. Signals (`core/signals/*`, `docs/getting-started/signals.mdx`, `docs/getting-started/tweening.mdx`)

**Creation**

- `createSignal(valueOrFn, interpolation?)` makes a simple signal.
- Typed signals: `Vector2.createSignal`, `Color.createSignal`, `Code.createSignal`, and others.
- Every node property is a signal, declared with decorators.

**Calling a signal** (overloaded by argument count)

- `s()` returns the value.
- `s(v)` sets a value or a function. Passing a function makes the signal **computed/reactive**.
- `s(v, duration, timing?, interp?)` returns a **tween generator**. Tweens chain with `.to(v, d)`, `.back(d)`, `.wait(d)`, `.run(gen)` and `.do(fn)`.
- `DEFAULT` resets to the initial value. It also works as a tween target.
- Helper methods: `reset()`, `save()`, `isInitial()`.

**Dependency tracking** (`DependencyContext`)

- **Push-dirty, pull-recompute.**
- While a signal or computed evaluates, a global collection stack records every signal read, and it subscribes to those signals' dirty flags.
- Dependencies are **re-collected on every evaluation**, so dynamic dependencies work.
- Setting a value clears its old dependencies and raises its dirty flag. Dirtiness propagates to dependents through their subscriptions.
- Recomputation is **lazy**: it happens on the next read.
- Results are **cached**: repeated reads cost nothing.
- **Cycle detection:** if a context re-enters collection while already collecting, it throws a "circular dependency" error.

**Other primitives**

- `createComputed(fn)` is a memoized derived value. It can take arguments.
- `createComputedAsync(promiseFactory, initial?)`.
- `createEffect(fn)` re-runs **synchronously** whenever a dependency raises its dirty flag. It returns a disposer.
- `createDeferredEffect(fn)` re-runs **once per thread step** (the thread's `onDeferred` phase), and only if dirty. It returns a disposer.

**Async resources**

- Async resources such as images and fonts register promises.
- Rendering repeats up to 10 times until the promises resolve (`GeneratorScene.render`).
- Reading an async property during logic before it is ready logs an error telling you to "yield the node first".

**Tween internals** (`core/tweening/tween.ts`, `core/threading/Thread.ts`)

- Each thread has two clocks:
  - `time`: a logical clock that a wait or tween **snaps exactly** to its end time when it finishes
  - `fixed`: the accumulated frame dt
- Tweens run while the end time is ahead of `fixed`, then set `time` to exactly the end.
- Result: sequences of animations **do not drift** from per-frame rounding, and animation timing does not depend on fps. The docs say "resilient to changes in frame rate". Frames just sample the timeline.

**Interpolation**

- Numbers interpolate linearly (`map`).
- `Vector2` has lerp and arc-lerp options.
- `Color` lerps in **LCH by default** (chroma-js; `core/types/Color.ts`).
- Easing functions live in `core/tweening/timingFunctions.ts`. A `spring()` helper is in `core/tweening/spring.ts`.

**Compound signals** (`CompoundSignalContext`)

- The parent signal is assembled from child signals, for example `.x` and `.y` on a `Vector2` signal.
- Each child can be set or tweened on its own. Reading the parent combines the children's values.

**Lifecycle:** `dispose()` unsubscribes everything. Scene reset rebuilds the nodes (and so their signals), so cleanup is implicit at reset. There is no explicit per-scene disposal API for user signals (unverified).

**Diagnostics:** an exception inside a computed is logged with an `inspect` key pointing to the owning node. There is no impurity or nondeterminism detection.

---

## 6. Project variables, settings, meta files

### Project variables (`core/scenes/Variables.ts`, `docs/advanced/project-variables.mdx`)

- Declared in `makeProject({variables: {...}})`, or with the `<motion-canvas-player variables='{json}'>` attribute on the embeddable web player.
- Read with `useScene().variables.get(name, fallback)`. This returns a **getter backed by a signal**, so anything bound to it updates when the variable changes.
- `Player.setVariables()` pushes new values into all scenes.
- The signals are recreated on each scene reset.
- **There is no editor UI for variables in core**, and no schema, typing or validation. Values are arbitrary JSON.
- The renderer re-applies `project.variables` before rendering (`Renderer.reloadScenes`).

### Project settings

- Defined in `makeProject({name, scenes, plugins, audio, audioOffset (deprecated→meta), variables, experimentalFeatures, logger})` in `core/app/Project.ts`.
- `experimentalFeatures: true` unlocks APIs marked experimental, which are exempt from semver (`docs/advanced/experimental.mdx`).
- Editor plugins are experimental.

### Meta files (sidecar JSON)

- **`<scene>.meta`** sits next to each scene file and is auto-created on the first `?scene` import (`vite/partials/scenes.ts`, `vite/utils.ts createMeta`). It holds `{version: 1, timeEvents: [{name, targetTime}], seed: <uint32>}` (`core/scenes/SceneMetadata.ts`; sample `packages/examples/src/scenes/logging.meta@v3.17.2`).
- **`<project>.meta`** sits next to `project.ts`. It holds:
  - `version`
  - `shared: {background, range: [start, end|null], size: {x, y}, audioOffset}`
  - `preview: {fps, resolutionScale}`
  - `rendering: {fps, resolutionScale, colorSpace, exporter: {name, options}}` (sample `packages/examples/src/code.meta@v3.17.2`)
- **`~/.motion-canvas/settings.json`** holds user settings (§1).

**Versioning:**

- A `version` field exists (1), but **I found no migration code** (grep in `core/meta`, `core/app`).
- Unknown keys are kept as "custom fields" and written back, which gives forward compatibility (`core/meta/ObjectMetaField.set`). The example project meta still has stale top-level `fileType`/`quality` keys and `version: 0`.
- Values are typed `MetaField`s: Bool, Number (with presets and range), Enum, Color, Vector2, Range, String, Object, and Exporter. The editor renders each with a matching view (`ui/components/meta/*`). **This is MC's only "schema" mechanism.** Plugins and exporters reuse it for option forms.

---

## 7. Scene transitions and chaining (`core/transitions/*`, `core/app/PlaybackManager.ts`, `core/scenes/GeneratorScene.ts`, `docs/getting-started/transitions.mdx`)

**Chaining.** Scenes play in the order of the `scenes: [...]` array. Each scene is a generator, with these states:

| State | Meaning |
|---|---|
| Initial | inside the transition |
| AfterTransitionIn | transition finished |
| CanTransitionOut | `finishScene()` was called, or the generator ended |
| Finished | generator ended |

When the current scene reaches `CanTransitionOut`, the next scene starts **on the same frame** and the previous scene becomes `previousScene`. The previous scene **keeps being stepped**: it is frozen if it has finished, or still animating if it called `finishScene()` early. This continues until the new scene leaves its transition. Both scenes are composited, and `previousOnTop` controls which is drawn on top.

**Timing.**

- The next scene's `firstFrame` is the previous scene's frame at `CanTransitionOut`, so scenes overlap during transitions.
- `transitionDuration` is measured in the recalculation pass and drawn as shading on the scene clip.
- `@main` #1128: seeking into the middle of a transition now always shows both scenes.

**Built-ins.**

- `slideTransition(direction, duration = 0.6)`
- `zoomInTransition(area: BBox, duration)` and `zoomOutTransition(area, duration)`: zoom with a cross-fade
- `fadeTransition(duration)`: fades in the new scene's alpha over the old one
- `waitTransition(duration, previousOnTop = true)`: keeps the old scene visible, for example under an overlay

**Custom transitions.**

- `useTransition(currentCtxFn, previousCtxFn?, previousOnTop?)` registers before-render hooks that modify each scene's canvas 2D context (translate, scale, alpha), and returns an `endTransition()` function.
- Nodes must be added before the transition is yielded. Otherwise the new scene is empty during the transition.

**No shared-element or morph transitions** between scenes. Transitions only transform the context. Audio is project-level, so transitions have no audio semantics.

---

## 8. Media

**Images:** `Img` node with `src` from a Vite asset import. The browser decodes the image, so any browser-supported format works. Remote sources go through an optional CORS proxy with a MIME allowlist and a host allowlist (`docs/getting-started/configuration.mdx` `proxy`).

**Video:** `Video` node (`2d/lib/components/Video.ts`).

- Controls: `play()`, `pause()`, `seek()`, `loop`, `playbackRate`. Its internal `time` signal advances with thread time.
- **Preview** uses "fast seek": the native video plays and is resynced only when the drift exceeds 0.2 s.
- **Render** uses exact seeks: it sets `currentTime` every frame and waits for `seeked`. That makes the render deterministic.
- The video's own audio is not part of the export (unverified).
- Open issue #1244: CORS video taints the canvas during export.

**Audio (v3.17.2): one track per project.**

- Configured with `makeProject({audio: importedFile})`.
- One offset in seconds (`shared.audioOffset`), editable in Video Settings or by Shift-dragging the waveform.
- Playback uses a single `HTMLAudioElement` (`core/media/AudioManager.ts`). Peaks are decoded for the waveform (`core/media/AudioData.ts`).
- No trim, gain, fades, mute/solo or multiple tracks.
- The only scene-level sync tool is time events against that one track.

**Programmable sounds (@main only, unreleased; #1082, #1158, #1166; `core/scenes/Sounds.ts@main`).**

- Builder: `sound(file).trim(start?, end?).gain(dB).detune(cents).playbackRate(r).play(offset?)`.
  - The effective rate is `2^(cents/1200) × rate`.
- Each `.play()` registers a sound at the current playback time plus the offset. Sounds are collected per scene during recalculation, so they **follow time-event edits automatically.**
- Preview plays them through an audio element pool (`AudioManagerPool`, `AudioResourceManager`).
- The timeline shows one waveform clip per sound.
- The FFmpeg exporter builds a filter graph per sound and mixes everything with `amix`. The output length is clamped to the exact frame count (`-t frames/fps`) (`packages/ffmpeg/server/FFmpegExporterServer.ts@main`). Each sound gets, as needed:
  - `-ss` / `atrim` for trimming
  - `aresample` to the chosen sample rate
  - `volume` for gain
  - `asetrate` + `aresample` for detune/rate
  - `adelay` for its offset

---

## 9. Rendering and export (`core/app/Renderer.ts`, `core/app/ImageExporter.ts`, `packages/ffmpeg/*`, `docs/getting-started/rendering/*`)

**Same engine as preview.**

- A separate `Renderer` instance has its own `PlaybackManager` and `Stage`.
- It uses `ReadOnlyTimeEvents`: durations come straight from the cloned meta, and nothing is written back.
- Before rendering it reloads every scene from the latest HMR description, meta and variables. It then:
  1. recalculates at the **render** fps
  2. seeks to the range start
  3. steps one frame at a time, drawing each frame
- Preview and render share code but differ in fps and resolution scale (settings are separate), in video seek mode, and in the time-event resolver (see the negative-duration caveat in §3).
- "Resolution" changes the canvas size without rescaling content. "Scale" multiplies the pixel density and scales content with it.
- Rendering is stepped in the browser tab. It yields every ~1/30 s, has an abort button and shows an ETA.

**Image sequence** (built in).

- Each frame is sent as a `canvas.toDataURL(type, quality)` base64 payload over the Vite websocket. Node writes it to `output/<project>/NNNNNN.<ext>`, or to `output/<project>/<scene>/NNNNNN.<ext>` with *group by scene*.
- Formats: PNG, JPEG, WebP, depending on the browser. Quality runs from 0 to 100.
- Every frame waits for an acknowledgement (`vite/partials/exporter.ts`).

**Video (FFmpeg)** (separate package; installs ffmpeg-static).

- Frames arrive as PNG data URLs and are piped through `image2pipe` into ffmpeg with `yuv420p`. The output is a single `output/<project>.mp4`.
- Options: *fast start* (`+faststart`) and *include audio*.
- v3.17.2 audio handling:
  - `-itsoffset` set to `audioOffset − range start`, with a code comment saying the offset only works for negative values
  - `-shortest`
- `@main` audio handling: a sample-rate option, an exact `-t`, and multi-sound mixing.
- No codec, CRF, bitrate, alpha or ProRes options. Alpha output is image-sequence only.
- `@main` #1095: skips encoding when extracting frames. PR #1229, which would have added per-scene export and higher quality, was closed unmerged.

**Range export.** The range comes from `shared.range` and is converted with `ceil(sec × fps)` (`PlaybackStatus.secondsToFrames`).

**Snapshot.** Renders one still at rendering settings.

**Presentation mode** (`docs/getting-started/presentation.mdx`).

- `beginSlide(name)` pauses until Space is pressed. A slide list sits in a side panel, and keyboard navigation and fullscreen are available.
- Slide IDs are `scene:name`.

---

## 10. Plugin API (`core/plugin/Plugin.ts`, `ui/plugin/EditorPlugin.ts`, `vite/plugins.ts`, `docs/advanced/plugins/*`)

There are three layers.

**Node/Vite plugins**

- These are ordinary Vite plugins with an extra `[PLUGIN_OPTIONS]` symbol property:
  - `entryPoint`: the runtime module to inject
  - `config(pluginConfig)`: can adjust projects or the output path
  - `runtimeConfig()`: JSON or raw JS passed to the runtime plugin factory
- They can add dev-server middleware and websocket handlers, which is how the exporters reach the file system.

**Runtime plugins** (`makePlugin`)

- Hooks: `settings(projectSettings)` (rewrite config), `project(project)`, `player(player)`, `presenter`, `renderer`, `exporters(project) → ExporterClass[]`.
- **Exporter contract:**
  - The `ExporterClass` provides `id`, `displayName`, `meta(project) → MetaField` (the options form) and `create(project, settings)`.
  - The `Exporter` it creates may implement `configuration?()`, `start?()`, `handleFrame(canvas, frame, sceneFrame, sceneName, signal)` and `stop?(result)`.
  - On @main, `start(sounds, duration)` receives the sounds, and `handleFrame` also receives a 2D context.

**Editor plugins** (`makeEditorPlugin`; documented as **experimental**)

- `tabs: [{name, tabComponent, paneComponent}]`: sidebar tabs and panes, written in Preact.
- `inspectors: [{key, component}]`: an inspector pane chosen by an inspection key.
- `previewOverlay` and `presenterOverlay`: `{drawHook() → (ctx, matrix) => void, component}` for canvas overlays and pointer handling.
- `provider`: a context component.
- `shortcuts`: @main only.
- **There is no timeline-track hook.** Plugins cannot add timeline tracks.

**Loading and versioning**

- Plugins can be listed in `makeProject({plugins})`, in a scene's plugins, or as Vite `entryPoint`s. They are deduplicated by `name`.
- A string entry is dynamically imported, and a failure is logged and skipped (`core/app/bootstrap.ts`).
- **There is no plugin API version handshake.** Compatibility relies on semver of the `@motion-canvas/*` packages, and the package versions are shown in the footer.
- Plugin code runs in the same browser context with full access to the player, project and websocket.

**Custom editor:** the `editor` option of the Vite plugin can swap the entire UI package, which must provide `editor.html`, `styles.css`, and a `main.js` exporting `editor()` and `index()`.

---

## 11. Inspector (`2d/editor/*`, `core/scenes/Inspectable.ts`)

**Scene contract.** A scene that implements `Inspectable` provides:

- `inspectPosition(x, y)` for hit-testing
- `validateInspection`
- `inspectAttributes`
- `drawOverlay(element, matrix, ctx)`
- `transformMousePosition`

`Scene2D` implements all of these.

**Selecting.**

- Click in the viewport: hit-test at the clicked point, and outline the selected node (hover is drawn at half alpha).
- Or pick from the **Scene Graph** tab. The tree includes detached nodes, and on @main supports keyboard navigation (#1101).

**Node identity.** Nodes are keyed by `key`. Without an explicit key, the key is generated as `<scene>/<ClassName>[<n>]`, a per-scene, per-class counter that resets on every scene reset (`2d/lib/scenes/Scene2D.registerNode`). The selection therefore survives seeks and reloads only while creation order stays the same. A duplicate explicit key logs an error and falls back to the generated key.

**Node Inspector pane.**

- Shows the key, a **GO TO SOURCE** button (the node's creation stack), and every signal property marked `inspectable` with its *current value* (`AutoField`).
- Values refresh after each render.
- **Read-only.** There is no property editing, no persistence of edits, and no copy-as-code.
- The pane says plainly when a node does not exist at the current frame.

---

## 12. Determinism

**Random**

- `useRandom()` returns the scene's RNG. It is a **Mulberry32** PRNG (`core/scenes/Random.ts`). Methods include `nextInt`, `nextFloat`, `gauss`, the array variants, and `spawn()`.
- The seed is **stored in the scene's `.meta`**. It is generated from `Math.random()` the first time the meta is created, so the meta file has to be committed to stay reproducible.
- The RNG is recreated from that seed on every scene reset, so replay and seeking produce identical sequences.
- `useRandom(seed, fixed = true)` gives an independent RNG. With `fixed = false`, the scene seed is added to the given seed.
- `Math.random()` and `Date` are **not** intercepted. Calling them breaks replay silently, and no warning is given.

**Time**

- Animation logic only sees thread time (`useTime()`), which comes from frame stepping. There is no wall-clock time.
- Frame/second conversion uses `ceil(sec × fps)` (`core/app/PlaybackStatus.ts`).
- The logical clock snaps at the end of each wait or tween (§5), so the timeline does not depend on fps. Event `targetTime`s are floats stored without frame quantization.

**Assets.** Async loads are awaited before drawing (up to 10 render passes). Fonts depend on the browser, as do text pixel-snapping and the Chromium code jitter (§4). For video, the render path uses exact seeks.

**Preview vs export.** They share code but run as different instances, often at different fps and scale. MC has no automated parity check. The one known semantic divergence is the negative time-event case in §3 (unverified at runtime).

---

## 13. Spec feature map (F01–F12)

| Spec | MC behavior worth matching | MC limitations we can exceed |
|---|---|---|
| **F01 Studio editor** | Layout: icon rail, sidebar, viewport, timeline, all resizable. Playback controls with ×0.25–×2 speed (fractional-frame slow motion), loop, frame step, `HH:MM:SS:FF [frame]` timecode, snapshot. Panel-scoped shortcuts (Space, ←/→, Shift+←/→, M, L, 0/=/-, F, B/N). Hot reload keeps the playhead and invalidates only the edited scene. Console errors show a source frame and open in the editor. App settings kept separate from project settings. | No scene picker: the whole project is one timeline. No cancellation of stale recalculation, and everything runs on the main thread. Backward seek always replays from scene start, with no frame cache (fine for JS, too slow for Manim). No light/dark theme toggle, only an accent color (unverified). No renderer-capability indicators. |
| **F02 Timeline** | Scene clips with transition shading. Slide and event sub-tracks. Ruler with power-of-two tick density. Wheel zoom around the cursor, middle-drag pan, scrubbing. Range bar (drag, handles, double-click reset, B/N keys, middle-click a scene). Click any item to jump to source. Timeline data comes from one non-drawing pass. | No per-animation tracks (`play`/`wait`/group spans), no overlapping-animation view, no selection model, no markers other than events and slides. No undo/redo. Event IDs are names only. No track hook for plugins. |
| **F03 Named cues** | `waitUntil(name)` / `useDuration(name)` with a default of 0. Sidecar stores an **absolute, scene-relative `targetTime`**: code edits keep cues locked to narration, and only the wait absorbs the change. Drag ripples later cues; Shift-drag holds them. Dragging shows a trail from call site to cue. Double-click opens source, middle-click seeks. External edits to the sidecar hot-reload. | Missing or renamed cues are **silently dropped** from the meta. A duplicate name only logs an error and resolves to 0. Negative waits are clamped in the editor but **not in render**. Writes are not atomic, have no backup and no undo. Ripple stays within one scene. No live ripple preview during the drag. Offsets are not frame-quantized. No validation report and no bake/export step for headless rendering. No descriptions or metadata on cues. |
| **F04 Audio** | Waveform under the timeline. Shift-drag to offset. Audio is the master clock in preview (≤20 ms desync, drop frames to catch up). Buffered serving so an external audio editor can overwrite files. @main: programmable `sound().trim().gain().detune().playbackRate().play(offset)`, one waveform clip per sound, FFmpeg `amix` export with exact duration. | Stable release has **one audio track per project**: no trim, gain, fades, mute/solo or multiple tracks. Export offset handling is buggy (comment says negative values only; range handling unverified). No captions, word timings or voiceover adapter. Programmable sounds are unreleased, and the FFmpeg exporter is now GPLv3. |
| **F05 Code animation** | `Code` with a code-signal model: `append`/`prepend`/`insert`/`remove`/`replace`, and `edit` with inline insert/remove/replace markers. **Token-level patience diff** with tokens from the Lezer parse tree (whitespace/bracket fallback). Unchanged tokens slide, changed tokens cross-fade around the midpoint, highlight colors lerp. `CodeRange` and `word`/`lines`/`find*Range`. Animated selection dimming. `getSelectionBBox` for overlays. Grammars and themes are pluggable. | **No move detection** (always false). No explicit override mappings. Ambiguous repeated tokens are matched only by patience-diff anchors. Monospace-cell assumption (each glyph's width rounded to cells). No per-token stagger. No built-in caret, line-number or scroll primitives. Admitted Chromium jitter. |
| **F06 Signals** | Lazy, cached computeds with dynamic dependency re-collection and cycle detection. Calling `signal(v, d)` returns a tween, with `.to/.back/.wait` chains and `DEFAULT` reset. Compound signals (`.x`, `.y`). Two effect kinds: synchronous `createEffect` and once-per-frame `createDeferredEffect`. Logical clock snaps exactly at the end of each tween, so there is no drift. LCH color lerp. | No diagnostics for impure effects or nondeterministic reads. No explicit lifecycle scope for disposal. Errors inside a computed are logged and swallowed (it returns its previous value). |
| **F07 Variables / themes** | `useScene().variables.get(name, fallback)` returns a reactive getter. Variables are set from the project or the web player and pushed live with `setVariables`. Typed `MetaField` kinds (Number with presets and range, Enum, Color, Vector2, Bool, Range, Object) give auto-generated settings forms. Defaults for new projects live in user settings. | No schema, types or validation for variables. No editor UI for variables. No themes, presets or palettes. No migration for meta `version`. |
| **F08 Inspector** | Click to select in the viewport with hover and selection outlines. Scene-graph tree including detached nodes. Generated stable keys (`scene/Class[n]`) or explicit keys. GO TO SOURCE via the creation stack. Live values refresh after each render. Says clearly when a node is absent at this frame. Scene-agnostic `Inspectable` contract. | **Read-only.** No editing, persistence, copy-as-code or undo. Keys are fragile when creation order changes. |
| **F09 Transitions** | Scene state machine with overlap (Initial, AfterTransitionIn, CanTransitionOut, Finished). `finishScene()` starts the transition early while the old scene keeps animating. Built-in slide, zoomIn, zoomOut, fade and wait transitions. Custom transitions via `useTransition(ctxFn, prevCtxFn, previousOnTop)`. Transition length is measured and drawn on the timeline. | Transitions only transform the context: no shared-element transitions, no masks or wipes beyond what you draw yourself. Audio is not tied to scenes. |
| **F10 Media / export** | Separate preview and render fps/scale. Resolution vs scale distinction. Color space choice. Range render. Snapshot to `still/`. Image sequence (PNG/JPEG/WebP, quality, group by scene). FFmpeg MP4 with fast start. Abort button and ETA. Exact video seeks in render. | Render happens **only inside the browser tab**: no headless CLI. Frames go over a websocket as base64 PNG (slow). No codec, CRF, alpha-video or ProRes options. No asset validation. Output name is fixed (`<project>.mp4`). |
| **F11 Plugins** | Three layers: Vite/Node (server endpoints, `entryPoint`, `runtimeConfig`), runtime (`settings`/`project`/`player`/`renderer`/`presenter`/`exporters`), editor (tabs, inspectors, preview/presenter overlays, provider, shortcuts). Exporter contract: `start` / `handleFrame` / `stop`, with options described as `MetaField`s. Dedup by name. Load failures are logged and skipped. | **No version handshake.** Editor API is experimental and undocumented. No timeline-track or event-metadata hooks. Plugins run with full trust in the page and can reach the file system through the dev server. |
| **F12 Reproducibility / education** | Seeded per-scene Mulberry32 RNG with the seed stored in a sidecar and rebuilt on every reset. Thread time only. Presentation mode with `beginSlide`, a slide list, keyboard navigation and fullscreen (useful for local step-through demos). Thread Debugger. | `Math.random()` and `Date` are not guarded and give no warning. Seed comes from `Math.random()` on first meta creation (not reproducible until committed). No data-driven trace tooling. No portable chaptered playback of *rendered* video (only the live JS web player). |

### Top design takeaways for manim-stage

1. **Copy the cue semantics, fix the edges.** Store absolute scene-relative cue times in a sidecar. Ripple by default, with a modifier to hold. Add what MC lacks: one resolver shared by preview and export, explicit ≥0 validation, orphan/rename detection with tombstones, atomic writes, undo, and frame-quantized storage (spec §8).
2. **The timeline should come from a non-drawing "recalculate" pass with per-scene invalidation,** which maps well to a Manim instrumented dry run. MC proves the UX. Its replay-from-scene-start seeking does not carry over to Manim's cost model, so we keep the frame cache from spec §4.
3. **Code diff baseline:** token-level patience diff over syntax tokens, slide plus cross-fade. Beat MC with move detection, override mappings, a stagger option and a proportional-font option.
4. **Audio:** design for multiple clips from day one. MC's stable release has a single track, and its multi-sound model is unreleased.
5. **Plugin API:** add the version handshake and the timeline-track and inspector-edit hooks that MC lacks.
6. **Licensing:** core is MIT, which makes behavior study fine. Do not reuse the FFmpeg exporter, which is GPLv3 on @main.
