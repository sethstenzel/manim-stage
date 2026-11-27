# M0 audit: ManimCE scene execution and timeline (STABLE vs MAIN)

Scope: scene execution, the timeline, caching, sections, audio, CLI/config and the test infrastructure. This is a read-only audit made with `git show` and `git grep` on a blobless clone. Nothing was executed. Where a behavior is inferred from reading the code rather than observed in a run, the text says "(derived from code)".

Ref notation:
- `@S` = STABLE `v0.22.1` = `16ea443e2a5f1d79db0a721161411ce916d6e733` (committed 2026-10-27)
- `@M` = MAIN `8c258a0082dc760d9a93671bbdfaca3cc53a6f91` (committed 2026-11-26)

Paths are relative to the repo root.

---

## 1. Inventory facts

### 1.1 Version, Python floor, dependencies
- **Version and Python floor.** `pyproject.toml:3` has `version = "0.22.1"` at both @S and @M. MAIN's pyproject was **not** bumped. `v0.30.0a1` (`5bf7b787`, 2026-11-22) is a release commit whose parent `9aa10de8` is on main. That commit is **not an ancestor** of @M (`git merge-base --is-ancestor` returns 1), and @M is 4 commits past the merge base. At @M, `manim/_version.py` reads the installed distribution version and falls back to `0.0.0+unknown`. Python floor: `requires-python = ">=3.11"` at `pyproject.toml:23` (@S and @M).
- **Dependency differences.** @S `pyproject.toml:24-52` includes `pydub>=0.22.0` (:40) and `audioop-lts` (:25, py≥3.13). @M `pyproject.toml:24-50` **drops pydub and audioop-lts** (PR #5059). Both have `av>=15.0`, `pycairo`, `moderngl<6`, `moderngl-window`, `watchdog`, `click`, `cloup`, `srt`, `tqdm`. Optional extras are `gui` (dearpygui), `jupyterlab` and `typst`.
- **PyAV version for chapters.** MP4 chapters need PyAV ≥16 (`hasattr(OutputContainer,"set_chapters")`, `manim/scene/scene_file_writer.py:45 @M`), but the floor stays at `av>=15.0`. On PyAV 15, chapters are silently omitted.

### 1.2 Renderer architecture, selection, Manager, camera
- **Renderer selection** happens in `Scene.__init__`. If `config.renderer == OPENGL`, it creates `OpenGLRenderer()`; otherwise `CairoRenderer(camera_class=…)` (`manim/scene/scene.py:210-225 @S`, `:223-238 @M`). Renderers declare `RendererCapabilities(live_preview: bool)`:
  - `manim/renderer/protocol.py:11-14 @S`, `:44-48 @M`.
  - Cairo: `live_preview=False` (`manim/renderer/cairo_renderer.py:40 @S`, `manim/renderer/cairo/renderer.py:40 @M`).
  - OpenGL: `live_preview=True` (`manim/renderer/opengl_renderer.py:544 @S`, `manim/renderer/opengl/renderer.py:101 @M`).
- **STABLE Manager.** `manim/manager.py:31 @S` exists, but its docstring says it is a forwarding facade: "Renderer, camera, clock, and output ownership still remain on the scene and renderer" (`:53-57`). `Manager.play` calls `self.renderer.play(scene,…)` (`:259-261`). Each renderer owns its own play loop:
  - Cairo: `cairo_renderer.py:70-137 @S`, which drives `Scene.play_internal` (`scene.py:1384-1417 @S`).
  - OpenGL: `opengl_renderer.py:881-936 @S`, decorated with `@handle_caching_play`.
- **MAIN Manager** (`manim/manager.py:111 @M`) owns the lifecycle state machine (`_State`, `:61-85`), the clock (`_ExecutionState`, `manim/renderer/_execution.py:19-41 @M`), the run loop, the file writer, the log handler and rollback.
  - `render(preview, *, capture_timeline=None)` is at `:416-490`.
  - `evaluate(*, capture_timeline, frame_times, on_frame)` is at `:503-587`.
  - A Manager renders or evaluates **once** (`:589-602`).
  - The renderer is reduced to drawing hooks: `_start_animation`, `_prepare_animation`, `render`, `get_frame`, `_present_frame`, `_present_frozen_frame` and `_animation_cache_identity` (`manim/renderer/protocol.py:76-98 @M`). Renderers have a lifecycle `RendererState` (`:17-41`).
  - A Cairo renderer is bound to one Scene: it raises "already bound to a Scene" (`renderer/cairo/renderer.py:97-100 @M`).
- **Camera.** At @S, cameras live in `manim/camera/*.py`. At @M (PR #4989), `manim/camera/` **no longer exists**. Cameras moved to `manim/renderer/cairo/camera.py` and are lazily re-exported (`manim/renderer/cairo/__init__.py`). The OpenGL camera is `manim/renderer/opengl/camera.py`. Open PR #5176 moves the cameras back to `manim.camera` (see §4).
- **Frame rendering path, MAIN.** `_RunLoop._step` calls `scene.update_to_time(offset)` once per frame, then calls listeners. `_Frame.draw()` and `pixels()` draw lazily, at most once per frame for all listeners (`manim/_run/loop.py:73-116, 308-335 @M`). Drawers:
  - `_TargetDrawer` draws into the renderer target for a render (`:165-192`).
  - `_SceneImageDrawer` draws with a temporary renderer for evaluate (`:195-207`).
- **OpenGL preview pacing.** The OpenGL preview is paced by wall-clock time (`renderer/opengl/renderer.py:671-746 @M`; `opengl_renderer.py:925-928, 986-990 @S`).

### 1.3 Scene lifecycle and play timing
- **Lifecycle.**
  - @S: `setup → construct → tear_down → post_construct` (`manager.py:127-185 @S`).
  - @M: `Manager._run` runs `setup()`, `construct()` (catching `EndSceneEarlyException`), `tear_down()`, `loop.finish()`, then optionally exports the timeline (`manager.py:604-626 @M`). `post_construct` runs after (`:655-687`).
- **Play run time.** `Scene.get_run_time` = `max(a.run_time for a in animations)`, then `validate_run_time`. That raises for ≤0 and clamps values below 1/fps up to one frame with a warning (`scene.py:1141-1186 @S`, `:1164-1209 @M`). The play kwargs `run_time`, `rate_func`, `lag_ratio` and so on are applied with `setattr` to every top-level animation (`compile_animations`, `scene.py:996-1038 @S`).
- **AnimationGroup / LaggedStart / Succession** are identical at @S and @M; the only diff is imports (`manim/animation/composition.py`).
  - Default `rate_func=linear` and `lag_ratio=0` (`:54-81`).
  - Child timings: `start[i] = Σ run_time[:i] * lag_ratio` and `end = start + run_time`. The group run time is `max(end)` unless `run_time` is given explicitly (`init_run_time` and `build_animations_with_timings`, `:123-160`). If `run_time` is overridden, the child timings are **rescaled**, not recomputed (`interpolate`, `:162-196`: `anim_group_time = rate_func(alpha) * max_end_time`).
  - `Succession` uses `lag_ratio=1` (`:235`). `LaggedStart` uses `DEFAULT_LAGGED_START_LAG_RATIO` (`:342-348`).
  - The per-submobject `lag_ratio` inside a single Animation is handled in `Animation.get_sub_alpha` (`manim/animation/animation.py:364-391 @M`).
- **Frame stepping, STABLE.** Frame times come from `np.arange(0, run_time, 1/config.frame_rate)`. That is a float range. When `renderer.skip_animations` is set, the times are just `[run_time]`, one step (`scene.py:1125-1129 @S`). `update_to_time(t)` passes `dt = t - last_t` to updaters and `alpha = t/run_time` to `interpolate` (`:1714-1724 @S`).
- **Frame stepping, MAIN.** `frame_count(d, r) = max(0, ceil(d*r - 1e-9))` (`manim/_run/frames.py:11-20 @M`). Frames sit at offsets `index/rate` (`loop.py:324-331`).
  - A play that is not observed (not drawn, no updaters, no stop condition) jumps to its last frame in one step but still advances the clock by the full frame count (`loop.py:315-323, 337-353`).
  - Frozen waits repeat one frame `frame_count` times (`loop.py:288-293`).
  - Calling `play()`/`wait()` re-entrantly, for example from an updater, now raises `RuntimeError` (`loop.py:244-256`; documented at `scene.py:1241-1242 @M`).
- **Time accounting, STABLE (float, depends on renderer and cache):**
  - Cairo, drawn frames: `self.time += num_frames * dt` for each frame (`cairo_renderer.py:207-211 @S`).
  - Cairo, skipped or cached plays: `self.time += scene.duration` (`:86, :110`).
  - Cairo, frozen wait: `int(duration/dt)` frames, a truncation (`:213-225`).
  - OpenGL: `self.time += scene.duration` always (`opengl_renderer.py:935 @S`). Frozen repeat is `int(frame_rate*duration)` (`:920-923`).
  - **Consequence (derived from code):** at @S, `Scene.time` (`scene.py:286-288`) differs between a fresh render (frame-quantized, float-accumulated) and a cached or skipped play (exact requested `run_time`), and between Cairo and OpenGL.
- **Time accounting, MAIN.** `time = time_offset + frame / frame_rate`, where `frame` is an **integer frame counter** (`renderer/_execution.py:25-41 @M`). Assigning `time` only changes `time_offset`. PR #5004 states the breaking change: "`scene.time` moves in whole frames instead of adding up run times: after `self.wait(0.5)` and a 0.5 s play at 15 fps it is 16/15 s instead of 1 s", and "Frozen waits round their frame count up". Skipped and cached plays step through every frame, so the state and the clock do not depend on the cache (`loop.py:210-216`; `manager.py:138-140`).
- **skip_animations / from_animation_number / upto_animation_number.**
  - @S: `CairoRenderer.update_skipping_status` (`cairo_renderer.py:261-283`) checks the section's `skip_animations`, still output, and `from_animation_number`. Going past `upto_animation_number` raises `EndSceneEarlyException`.
  - @M: `_OutputSelection.includes` and `start_play` (`manim/_run/selection.py:36-58 @M`).
  - The CLI flag is `-n start[,end]` / `--from_animation_number` (`cli/render/render_options.py:137-144 @M`).
- **Random seed.** `Scene.__init__` calls `random.seed(self.random_seed)` and `np.random.seed(...)`, where `random_seed` defaults to `config.seed` (`scene.py:188, 278-279 @S`; `:201, 298-299 @M`). `config.seed` has **no default** in `default.cfg`; `getint("seed")` returns `None` (`_config/utils.py:620-630 @M`). So with no `--seed` (`cli/render/global_options.py:129 @M`), Python and numpy are seeded from OS entropy: **nondeterministic by default**.

### 1.4 Partial movie files and the hashing cache
- **One partial movie file per play/wait.** `add_partial_movie_file(hash|None)` appends to `writer.partial_movie_files` and to the current `Section.partial_movie_files`. Skipped plays keep a `None` placeholder, "to preserve index alignment" (`scene_file_writer.py:350-371 @S`, `:392-413 @M`). File path: `output_plan.segment_path(cache_key)` (`_config/output_plan.py:83 @M`). The cache hit test is `path.exists()` (`scene_file_writer.py:691-710 @S`).
- **Cache key: `get_hash_from_play_call`.** It is a sha256 over backend, encoder fingerprint, camera JSON, sorted animation JSON, current-mobjects JSON and `renderer_state` (`utils/hashing.py:416-491 @S`, `:472-545 @M`).
  - @S Cairo passes `renderer_state=()` (`cairo_renderer.py:93-103 @S`). **Scene time is not in the key.**
  - @M passes `renderer_state={"drawing":…, "execution":{"clock":"sample-v3","time": manager.time,"frame_rate":…}}` (`manim/_run/cache.py:18, 52-81 @M`). **Scene time is in the key**: a play at a different start time misses the cache.
  - @M leaves out values filled in on first draw, via `_derived_attribute_names` (`hashing.py:101-142 @M`). Waits with a `stop_condition` are never cached (`cache.py:42`).
- **Cache eviction and flags.** LRU by atime with `max_files_cached = 100` (`utils/caching.py:35-66`; `_config/default.cfg:131`). `--disable_caching` produces keys `uncached_{index:05}`.
- **Assembly.** Partial files are concatenated with PyAV's `concat` demuxer (`combine_files`, `scene_file_writer.py:747… @S`, `:761-912 @M`).

### 1.5 Sections
- **API.** `Scene.next_section(name, section_type=DefaultSectionType.NORMAL, skip_animations=False)` (`scene.py:378 @S`, `:439 @M`; `manager.py:275-292 @S`, `:911-928 @M`). `DefaultSectionType` has a single member, `NORMAL="default.normal"`; third parties can define their own types (`scene/section.py:14-33`).
- **Output.** `--save_sections` writes one video per non-skipped section plus a JSON index (`combine_to_section_videos`, `scene_file_writer.py:966-984 @S`, `:992-1015 @M`). Each index entry is `{name, type, video}` plus `get_video_metadata` (`section.py:83-103`). The index does not include section start times.
- **MAIN additions.**
  - `Section.movie_start` (`section.py:54-79 @M`).
  - Section videos carry their slice of the audio mix (`scene_file_writer.py:997-1009 @M`).
  - **MP4 chapters**, one per non-empty section, written only with `--save_sections` and only on PyAV ≥16 (`_chapters`, `:965-990`; `set_chapters` at `:807-819`, millisecond time base). PR #5125: "Without `--save_sections`, output is unchanged."

### 1.6 Audio
- **STABLE (pydub).** `Manager.add_sound` returns immediately if `skip_animations` is set, so the sound is **dropped** (`manager.py:339-341 @S`). Otherwise it calls `writer.add_sound(file, self.time + time_offset, gain, **kwargs)`.
  - Non-WAV input is converted to WAV with PyAV, then loaded with pydub (`scene_file_writer.py:425-466 @S`).
  - Mixing is pydub `overlay` at `position=int(1000*time)` (**millisecond** truncation), with optional `gain_during_overlay=gain_to_background` (`:382-423`).
  - At the end, the WAV is exported, converted to AAC or Ogg, and muxed with PyAV (`:886-958`).
  - Sound is placed in **scene time**, while the movie leaves out skipped plays. So with `-n` or skipped sections, later sounds are offset by the skipped duration (derived from code). Because the clock is computed differently for cached and drawn plays (§1.3), this offset can also vary between runs.
- **MAIN (PyAV mixer, PR #5059).** `Manager.add_sound` probes the file **in every run**: it raises `OSError` or `ValueError` (`manager.py:951-985 @M`; `scene/audio_mixer.py:63-83`). It creates a `_Sound(file, path, start, gain, gain_to_background)` marker, which goes to the run loop and its listeners.
  - `_SoundMix` decodes to int16 stereo at `SAMPLE_RATE = 48_000` (`audio_mixer.py:24, 126-164`).
  - Sounds are placed at `round(seconds*48000)` (`:181-182`), so placement is **sample-accurate**. Scene time maps to **movie time** through the shown intervals: `_movie_time` (`:185-194`); `_Encoder.play_finished` calls `writer.add_movie_interval(start,end)` for every play in the output, cached ones included (`_run/listeners.py:65 @M`; `scene_file_writer.py:476-493`).
  - Gains are in dB. `gain_to_background` is ducking applied to sounds added earlier (`:250-275`).
  - Output: the audio is encoded block by block during the concat: AAC for MP4, PCM for MOV, Vorbis or Opus for WebM (`scene_file_writer.py:51-106`). The audio track is cut to the video length. Parts before 0 or after the scene end are cut with warnings (`:1041-1087`).
- **Missing at both refs:** source trim (in-point), fade, mute, solo and volume envelopes.

### 1.7 Timeline capture and JSON export (MAIN only; PR #5006, merged 2026-11-11)
- **How to enable.**
  - Python: `Manager(scene).evaluate(capture_timeline=True)` or `.render(capture_timeline=True)`, then `manager.timeline` (`manager.py:416-501 @M`). There is also `manager.capture_timeline = True` (`:180-186`).
  - CLI: `manim render FILE SCENE --timeline-output PATH`, optionally with `--dry_run`. It requires exactly one scene and refuses to overwrite the input file (`cli/render/commands.py:75-128 @M`).
  - `Timeline` is exported in `manim.__init__` (`from .timeline import *`).
- **Data model** (`manim/timeline.py:15-147 @M`; formatting in `manim/_run/record.py:62-256 @M`). It is a frozen dataclass wrapping a JSON string.
  - Top-level fields: `schema="manim.timeline"`, `version=1`, `mode` (`evaluate`|`render`), `scene` (class qualname), `backend` (renderer class name), `frame_rate` (float), `duration`, `ended_early`, `source` (`{path: filename, sha256}` of the scene class file, hashed when the run starts), and `entries[]`.
  - `from_json` validates `schema` and `version`. `to_json` is deterministic. `write()` is atomic (temp file, fsync, replace).
  - The docs call the format and API experimental: "may change without a deprecation period" (`timeline.py:33-35`; `docs/source/guides/timeline.rst`).
- **Entries, in chronological call order** (`record.py:161-234`):
  - `play`/`wait`: `{start, end, run_time (requested), frozen, animations:[{type, run_time}], skipped, source}`. `end` is frame-quantized; in the control data, `run_time=0.3` at 4 fps gives `end-start=0.5` (`tests/control_data/timeline-v1.json @M`).
  - `section`: `{start, name, type, skip_animations}`.
  - `caption`: `{start, end, content}`.
  - `sound`: `{start, duration (from file headers), file, gain, gain_to_background}`.
- **Not recorded:**
  - IDs of any kind.
  - Explicit frame indices. Times are floats; frame = start × frame_rate only when `time_offset == 0`.
  - Nested animation children and their timings (LaggedStart children, for example).
  - Mobject identities, cache keys, partial movie paths, updaters.
  - User markers or cues.
- **Source location.** `_location()` walks the stack from the innermost frame and returns the **first frame outside the installed `manim` package**. `path` is relative to the scene file's directory, or `null` if outside it. Calls from `exec()`/`<…>` code give `null` (`record.py:122-145`). Loop iterations repeat the same line; the control data has two entries with `line 15`. Failed plays are removed from the record (`record.py:195-202`). Capture fails if time goes backwards or is non-finite (`:147-159`).
- **Missing example.** The PR #5006 description mentions `examples/timeline_reader.py` (HTML view), but **no such file exists at @M** (`git ls-tree` finds no timeline files except the docs, `manim/timeline.py` and the tests).

### 1.8 Evaluate without rendering and requested frames (PR #5005)
- **What evaluate does.** `Manager.evaluate(capture_timeline=False, frame_times=(), on_frame=None)` runs `setup`/`construct`/`tear_down` through the same loop with `_OutputSelection.everything` and `_SceneImageDrawer`. There is no file writer, log, media, cache or `-n` (`manager.py:503-587 @M`; `_run/mode.py:62-87`).
- **Requested frames.** Each requested time is mapped to the frame whose start is ≤ that time. `RenderedFrame(image: PIL RGBA, requested_time, time, frame_index)` is delivered in increasing time order, at most once per frame (`_run/listeners.py:132-176 @M`; `manager.py:88-108`). The test `test_frames_match_the_rendered_frames` asserts pixel identity with rendered frames for both backends (`tests/test_scene_rendering/test_evaluation_frames.py:51 @M`).
- **Arbitrary frame index:** yes, indirectly, by passing `time = index/frame_rate`.
- **Limits** (from the evaluate docstring and `docs/source/guides/evaluation.rst @M`):
  - Only **forward in a single pass from scene start**, and it runs to the **end of the scene** after the last requested frame. Stopping early is only possible by raising inside `on_frame`, which ends the evaluation as an error (`test_an_error_in_on_frame_ends_the_evaluation`).
  - A Scene can be evaluated **once** and must be unused (`manager.py:555-559`). A new instance is needed for every seek.
  - GPU meshes are rejected (`_MeshGuard`, `listeners.py:113-130`).
  - Section, caption and sound calls have no effect, but sound files are still probed.
- **No checkpoint, snapshot or restore API.**

### 1.9 Run loop listeners (PR #5004)
- **Interface.** `_RunListener` has `play_started(_Play)`, `frame(_Frame)`, `play_finished`, `play_failed`, `marker(_Section|_Caption|_Sound)` and `run_finished(ended_early)` (`manim/_run/loop.py:119-144 @M`).
  - `_Play` exposes `index`, `first_frame` (integer frame index), `run_time`, `animations` (live Animation objects), `frozen`, `in_output`, `cache_key` and `cached` (`:31-56`).
  - `_Frame` exposes `index`, `repeat`, `offset`, `draw()`, `pixels()` and `image()` (`:73-116`).
- **Contract:** listeners "must not change the scene's mobjects, call back into the loop, or decide anything for other listeners" (`:119-126`).
- **Not public.**
  - All names are underscore-private, and `_run/__init__.py` has an empty `__all__`.
  - Listener lists are hard-coded: `_render_loop()` builds `[_Encoder, _Preview, _Progress]` (`manager.py:822-831`), and `evaluate()` builds `[_MeshGuard, _Progress, _FrameRequests?]` inline (`:567-577`).
  - There is no registration API and no entry point. The only practical hook is to subclass `Manager` and override the private `_use_loop(loop)`, which both run paths call (`:833-838`), to append to `loop.listeners`. That is fragile.
- **Usefulness.** Through a listener, the exact integer `first_frame` and the live `AnimationGroup.anims_with_timings` are available, which is enough to compute nested-child frame ranges for F02.

### 1.10 CLI, plugins, config
- **Subcommands are hard-coded.** `manim/__main__.py:95-100` (same at @S and @M) calls `main.add_command` for checkhealth, cache, cfg, plugins, init and render, with `DefaultGroup default="render"`. **There is no entry-point hook for third-party CLI subcommands.**
- **Plugins.** The `importlib.metadata` entry-point group `"manim.plugins"` (`plugins/plugins_flags.py:29-34`) is loaded **at `import manim`**: `plugins/__init__.py:11-16` calls `get_plugins()`, which calls `entry_point.load()` for every installed plugin, and warns about the `config.plugins` entries that are missing.
- **Config.** `ManimConfig` reads layered `manim.cfg` files: library `default.cfg`, user-wide (`%APPDATA%/Manim/manim.cfg` on Windows) and folder `./manim.cfg` (`_config/utils.py:45-118 @M`). `tempconfig({...})` gives a scoped override. Defaults: `frame_rate = 60` (`default.cfg:126 @M`), `config.frame_rate` is a float (`utils.py:1192-1198`). @M raises if `frame_rate` changes after Scene construction (`manager.py:410-414`).
- **CLI flag differences.** The only `render` flag added between @S and @M is `--timeline-output`. Output formats are `none|auto|mp4|webm|mov|gif|png|png-sequence` (`_config/output.py:11-21`, identical at both refs). `--dry_run`, `--transparent`, `--video-codec`, `--pixel-format` and `--encoder-option` exist at both refs.
- **File-change rerun.** OpenGL `Scene.interact()` starts a watchdog `Observer` on `config.input_file` and raises `RerunSceneException` when the file changes (`scene.py:135-143, 1523-1547 @S`; `:148-156, 1522-1560 @M`). The CLI rerun loop reuses `scene_classes` loaded once before the loop (`cli/render/commands.py:94,103 @S`; `:111,116-130 @M`). It **appears not to re-import the module**, so code edits would not be picked up. This is unverified at runtime.
- **Lazy imports.** PR #5124 adds `manim/utils/importing.py` `lazy_import` (`@M`). The PR body reports `manim --version` going from 1.39 s to 0.56 s.

### 1.11 Test infrastructure
- **Configuration and size.** pytest options are `-n auto --dist=loadfile` with coverage, and a `slow` marker (`pyproject.toml:118-120 @M`, same at @S). The tree has 456 files under `tests/` at @S and 494 at @M.
- **Graphical tests.** The `@frames_comparison` decorator (`manim/utils/testing/frames_comparison.py:36` at both refs) compares rendered frames against `.npz` control data under `tests/test_graphical_units/control_data/` (235 files @S, 239 @M). `--set_test` regenerates, `--show_diff` visualizes, `--skip_slow` (`tests/conftest.py:32-58 @M`).
- **Video tests** compare metadata JSON in `tests/control_data/videos_data/*.json` (`tests/utils/video_tester.py`).
- **@M-only tests:**
  - `tests/module/test_run_loop.py`
  - `test_timeline.py`
  - `test_timeline_capture_errors.py`
  - `test_manager_evaluation.py`
  - `tests/module/scene/test_audio_mixer.py`
  - `test_sound.py`
  - `tests/test_scene_rendering/test_timeline_cli.py`
  - `test_evaluation_frames.py`
  - `test_manager_cache_clock.py`
  - `test_audio_assembly.py`
  - `test_sound_and_reuse.py`
- **Timeline control data:** `tests/control_data/timeline_scene.py` and `timeline-v1.json`.
- **No timeline test exercises AnimationGroup, LaggedStart or Succession** (grep of `test_timeline.py @M`).

---

## 2. Requirement status matrix

Status values: Existing / Partial / Missing / Integration only / Not feasible.

| Requirement | STABLE `v0.22.1` | MAIN `8c258a0` | Evidence |
|---|---|---|---|
| **F01 hot-reload / preview** | **Partial**. OpenGL-only live window (`--live-preview`). OpenGL `interact()` reruns on file change through watchdog, but the module appears not to be re-imported (unverified). Cairo has no live preview. No seek, scrub or step. | **Partial**. Same as STABLE, plus `Manager.evaluate(frame_times,on_frame)` (draws chosen frames, pixel-identical to a render, no media) and `Scene.get_image()`. Still no hot reload for Cairo and no seek. Our runner must re-import and re-evaluate. | `protocol.py:11-14 @S`; `scene.py:1523-1547 @S`; `cli/render/commands.py:94-113 @S`; `manager.py:503-587 @M`; `listeners.py:132-176 @M` |
| **F02 event tracing & time ranges** | **Missing**. No tracing. Section JSON and SRT only after the render. `Scene.time` is inconsistent between cached and drawn plays and between renderers, so ranges reconstructed by monkeypatching `play` would be unreliable. | **Partial**. Timeline v1 records top-level play, wait, section, caption and sound calls with frame-quantized start/end, requested run_time, frozen/skipped flags and source file:line. Missing: nested group or lag children, frame indices, cue markers, object tracks. Experimental format. Child ranges can be computed from `_Play.animations[*].anims_with_timings` through a private listener. | `_run/record.py:161-234 @M`; `timeline.py:72-87 @M`; `composition.py:123-160`; `cairo_renderer.py:86,110,207-211 @S` |
| **F02 stable event IDs** | **Missing** | **Missing**. Only list order plus `source{path,line}`. The line repeats in loops. The innermost frame outside the manim package is reported, so helpers (including **our own `manim_studio` wrappers**) become the "source". The file hash covers only the scene file. `Mobject.uid` exists only in open PR #5173 and is per-process. | `record.py:122-145 @M`; `tests/control_data/timeline-v1.json` (line 15 twice) |
| **F03 cue-like timing primitives** | **Partial** (primitives only). `wait(duration, stop_condition, frozen_frame)`, `pause`, `wait_until(stop_condition: Callable, max_time=60)`, subcaption offsets. No named cues, no sidecar overrides. **Name collision:** the spec's suggested `self.wait_until("cue")` overloads the existing `Scene.wait_until(callable)`. | **Partial**. Same primitives, but scene time is frame-quantized and deterministic (better for cue math). Cache key includes start time, so retiming any cue invalidates every later partial movie. | `scene.py:1242-1310 @S`, `:1272-1341 @M`; `_run/cache.py:72-79 @M` |
| **F04 audio placement / mixdown** | **Partial**. `add_sound(file, time_offset, gain, gain_to_background via kwargs)`. pydub overlay at ms resolution. Placed in scene time. Dropped while skipping. Misaligned in `-n` or skipped-section renders (derived from code). No trim, fade, mute or solo. | **Partial (solid base)**. PyAV mixer at 48 kHz stereo, sample-accurate placement, movie-time mapping (correct for `-n`, skipped sections and cache), section videos carry audio, cut warnings. Timeline sound entries include duration. No trim (in-point), fade, mute, solo or envelopes; a negative start trims only the head. Adapter needed (Integration). | `manager.py:316-341 @S`; `scene_file_writer.py:382-466 @S`; `audio_mixer.py:24-275 @M`; `scene_file_writer.py:416-493 @M` |
| **F10 range/segment export & output formats** | **Partial**. Ranges only by play index (`-n a,b`). Per-section videos plus JSON index (`--save_sections`). Formats mp4, webm, mov, gif, png, png-sequence, transparency, codec and pixel-format options. No time-range export. Audio and subcaptions in partial renders are offset (derived from code). | **Partial**. Same, plus audio and subcaptions in movie time for ranges and sections, and MP4 chapters (PyAV ≥16, `--save_sections` only). Time-range export is still missing; it must be mapped to play indices using the timeline. | `render_options.py:137-161`; `output.py:11-21`; `scene_file_writer.py:965-1039 @M` |
| **§4 seek P1** (cached / pre-rendered frames) | **Integration only**. Per-play partial movies, keyed by hash, in play order with `None` placeholders. Play start times are unreliable (cache-dependent clock), and there is no public index of play to file to time. | **Integration only (feasible)**. The n-th play/wait timeline entry corresponds to `file_writer.partial_movie_files[n]`, from the same play-index order (`listeners.py:39-46`). Cache keys and paths are not in the timeline (private access needed). The alternative is our own frame store fed by a listener or a `png-sequence` render. | `scene_file_writer.py:350-371 @S`; `listeners.py:39-66 @M`; `loop.py:31-56 @M` |
| **§4 seek P2** (incremental re-render, seek after edits) | **Partial / risky**. The hash cache skips unchanged plays, but cached plays jump in one step (`times=[run_time]`), so updater state can diverge from a full render (derived from code). | **Partial**. `evaluate(frame_times)` gives correct arbitrary-time frames by re-running from t=0, once per fresh Scene instance, running to the end. No checkpoints. Cache reuse holds only if a play's start time is unchanged. Cached and skipped plays still step every frame (correct, but costs Python time). | `scene.py:1125-1129 @S`; `manager.py:503-587 @M`; `cache.py:72-79 @M` |
| **§4 seek P3** (live OpenGL scrubbing) | **Not feasible** with existing APIs: no scene-state snapshot or restore, and the preview is wall-clock paced and forward-only. | **Not feasible** with existing APIs, for the same reasons. Open PR #5173 adds immutable render snapshots for drawing; whether they help restore scene state is **unverified**. | `opengl_renderer.py:925-928 @S`; `renderer/opengl/renderer.py:671-746 @M` |
| **§8 time representation** | **Missing**. Float accumulation (`time += num_frames*dt`), float `np.arange` frame times, truncating `int()` for frozen frames, a clock that differs between cached and drawn plays and between Cairo and OpenGL. | **Partial**. Integer frame counter plus float offset. `ceil(d*r - 1e-9)` frame counts. Documented frame-start sampling: frame i covers `[i/r, (i+1)/r)`. `RenderedFrame.frame_index` is an integer. But `frame_rate` is a float and the timeline stores float seconds with no frame fields. Audio uses `round(s*48000)`. Rational times and frame indices must still be added in our schema. | `cairo_renderer.py:207-225 @S`; `_execution.py:25-41 @M`; `frames.py:11-20 @M`; `listeners.py:150-176 @M` |

Test evidence for the MAIN claims: `test_timeline.py:62` (evaluate entries), `:120` (render gives the same entries with skipped marks), `:139` (format control file); `test_evaluation_frames.py:51` (pixel identity), `:95` (frames and timeline from one evaluation); `test_manager_cache_clock.py`, `test_audio_assembly.py`, `test_sound_and_reuse.py` (all `@M`). None of these were executed for this audit.

---

## 3. Risks and surprises
1. **MAIN is mid-refactor.** A maintainer stack of open PRs touches the files we would build on:
   - #5173 render snapshots, read-only mobject arrays.
   - #5174 removes all `OpenGL*` mobject classes, about 11k lines.
   - #5175 surfaces become lit meshes.
   - #5176 moves cameras to `manim.camera`.
   - #5177: renderers become `render(nodes, config) -> Frame`, and `Scene(renderer=…)` takes a name or factory, not an instance.
   - #5178 paints, materials, lights.

   #5177 changes `manim/_run/{cache,listeners,loop,mode,state}.py`, `manager.py`, `scene.py` and `docs/source/guides/timeline.rst`. All of these are still open as of 2026-11-27.
2. **Version and tag confusion.** @M's pyproject still says `0.22.1`. `v0.30.0a1` is a sibling release commit, not on main's ancestry. Pin by commit SHA; do not rely on the version string.
3. **STABLE and MAIN timing semantics differ.** MAIN quantizes `scene.time` to frames (16/15 s instead of 1 s), rounds frozen waits up, raises on `play()` from an updater, and runs per-frame updaters for `-n` and cache hits (slower). Event times computed against STABLE will not match MAIN.
4. **STABLE's clock depends on cache state and renderer** (derived from code). That makes STABLE a poor base for F02/F04 alignment: a sound or cue placed after a cached play shifts compared with a fresh render.
5. **MAIN's cache key includes absolute start time.** Every cue retime or narration change invalidates all later partial movies, which limits P2 incremental re-render. STABLE excludes time, but its cached plays are not stepped, which risks state divergence.
6. **Our wrappers would hijack timeline `source` locations.** The innermost frame outside the manim package is recorded. If `manim_studio` calls `self.play` from its own package, the timeline's source points to our file, or to `null` when it sits outside the scene directory. Wrappers need to work around this. Options: route calls so user frames are innermost, or post-process using our own stack capture. Which works best is unverified.
7. **Default runs are nondeterministic.** `config.seed` defaults to `None`, so constraint §2.5 needs `--seed` or a project setting enforced by us. The timeline hashes only the scene file, not imported modules, assets or config.
8. **`evaluate()` constraints.**
   - One run per Scene instance.
   - Construct and evaluate under the same `frame_rate`.
   - Runs to the end of the scene, even after the last requested frame.
   - GPU meshes are rejected.
   - The file writer is unavailable.

   Every seek or preview request therefore costs a full scene execution (Python work only).
9. **No public listener or registration API.** Hooking in means subclassing `Manager` or monkeypatching private `_use_loop` or `_render_loop`. #5177 is actively rewriting these.
10. **No CLI subcommand plugin hook.** `manim studio …` cannot be registered through the `manim.plugins` entry points (subcommands are hard-coded). Also, `manim.plugins` entry points are imported eagerly on `import manim`. A separate `manim-studio` console script is the safe route.
11. **Chapters depend on the PyAV version** (≥16) while the floor is 15. Chapters are silently absent on PyAV 15 and are written only with `--save_sections`.
12. **The section index JSON has no start times.** On MAIN, `Section.movie_start` exists internally but is not serialized into the index. Section start times are available from the timeline instead.
13. **The PR-described `examples/timeline_reader.py` is absent at @M.** No reference UI ships.
14. **File-change rerun appears not to re-import user code** (unverified at runtime) and works only on OpenGL. F01 hot reload must be ours: a fresh subprocess or a module reload.

## 4. MAIN APIs to build on, and how stable they look
| API | Public? | Maturity / churn | Recommendation |
|---|---|---|---|
| `Manager.evaluate(capture_timeline, frame_times, on_frame)` and `RenderedFrame` (`manager.py:88-108, 503-587`) | Public, documented (`guides/evaluation.rst`), tested | Merged 2026-11-11, labeled "breaking changes, refactor". Open PR #5177 edits `test_manager_evaluation.py` and `manager.py`, so its exact signature is at risk. | **Build on it** for P1/P2 preview frames and fast timeline capture, behind an adapter. |
| `Timeline` JSON v1 (`manim/timeline.py`), `--timeline-output` | Public, but explicitly **experimental, no deprecation period** | About 2 weeks old. The guide is touched by #5177. Version field plus schema check exist. | **Ingest it** in an adapter that maps to our versioned `SceneEvent`. Do not expose it directly as our contract. Add IDs, frame indices and nested children ourselves. |
| `_RunListener`, `_Play`, `_Frame` (`manim/_run/loop.py`) | **Private** | Rewritten by #5004 (2026-11) and again changed by open #5174 and #5177 | Use only through one isolated shim, for exact frames and nested-group timings. Propose a public listener registration upstream (§2.3). |
| `Scene.add_sound(file, time_offset, gain, gain_to_background)` | Public | Signature changed in #5059 (`**kwargs` became an explicit `gain_to_background`) | **Build on it** for F04 placement. Trim and fade must be done by pre-processing a temp asset, or upstreamed. |
| `next_section` + `--save_sections` + chapters | Public | Stable API; MAIN adds movie-time placement and chapters | Use for F10 segment export. Derive time ranges from the timeline. |
| `file_writer.partial_movie_files`, `add_movie_interval`, `_SoundMix` | Semi-public or private | `add_movie_interval` is new in #5059 | Read-only use for the P1 frame-cache mapping, if at all. Prefer our own frame store fed by `on_frame` or a listener. |
| `RendererCapabilities(live_preview)` | Public dataclass | Present at both refs | Use for the F01 renderer capability indicators. |

**Bottom line:** STABLE lacks every timeline primitive the spec needs and has a cache-dependent float clock. MAIN supplies most of the hard parts (deterministic frame clock, timeline capture, frame-exact evaluation, movie-time audio, chapters), but as experimental or private APIs, with a large refactor stack still open. Whether to pin MAIN by SHA behind an adapter or wait for the refactor to land is a decision for the architecture ADR.
