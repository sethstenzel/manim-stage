# ManimCE feature audit: F05–F12 scope (Code, reactive state, interactivity, plugins, serialization, transitions, media, theming)

Refs audited (blobless clone `C:\s3711\git\manim-stage\.upstream\manim`, read via `git show`/`git grep` only; nothing was run):

- **STABLE** = `v0.22.1` = `16ea443e` (current pin)
- **MAIN** = `8c258a00` (origin/main, 29 commits after STABLE, includes `v0.30.0a1`)

Citation format is `path:line @S` (STABLE) / `@M` (MAIN). When a line is the same at both refs, it's written `@S/M`. "Unverified" means I inferred it from reading the code and did not execute it.

Out of scope here (another agent covers them): scene timeline, caching, sections, audio, CLI, tests. They're mentioned only where they overlap F05–F12.

---

## 1. Inventory

### 1.1 `Code` mobject (`manim/mobject/text/code_mobject.py`)

- **What changed on MAIN.** Functionally nothing. The `git diff S..M` touches only imports: bs4 now imports lazily inside `__init__`, and `Paragraph` is imported at module level (commits 7b4da275, 37056b0e). Line numbers below hold at both refs unless marked.
- **Constructor.** `Code(code_file=None, code_string=None, language=None, formatter_style="vim" | type[Style], tab_width=4, add_line_numbers=True, line_numbers_from=1, background="rectangle"|"window", background_config=None, paragraph_config=None)`. Source: `code_mobject.py:172-184 @S`.
- **Class-level defaults.**
  - Both are mutable dicts and act as global theming hooks: `default_background_config` (`:156-163`) and `default_paragraph_config = {"font": "Monospace", "font_size": 24, "line_spacing": 0.5, "disable_ligatures": True}` (`:164-169`).
  - The class annotation `code: VMobject` (`:170`) is stale: `self.code` is never assigned.
- **Highlighter.**
  - Uses Pygments: `get_lexer_by_name`, or else `guess_lexer_for_filename` / `guess_lexer` (`:187-200`).
  - Pygments renders to HTML through `HtmlFormatter(style=..., noclasses=True)` (`:204-208 @S`, `:206 @M`), and BeautifulSoup parses the `<pre>` (`:210-214`).
  - Only the `color:` CSS property of each top-level `<span>` is applied, via regex `color: (#hex6|#hex3)` (`:258-270`). Pygments bold, italic, underline and token background are **dropped**.
  - Any Pygments style works by name or as a class (`get_pygments_style`, `get_styles_list`, `:351-372`).
- **Tabs.** `code_string.expandtabs(tabsize=tab_width)` runs before highlighting (`:202 @S`, `:204 @M`). Column math is therefore in expanded-space units.
- **Submobject structure.**
  - Children are added in this order: `self.background`, added last with `add_to_back` (`:349`); `self.line_numbers` as a `Paragraph`, only if `add_line_numbers` (`:292-305`); `self.code_lines` as a `Paragraph` (`:251-255`, `:317`).
  - `code.code_lines[i]` is a VGroup of glyph VMobjects for line *i*, so **lines are addressable by index**.
  - **Columns are not directly addressable.** Each glyph is first indexed by character, with whitespace placeholder `Dot`s present, while coloring (`:257-277`). Then all `Dot`s are stripped (`:315-316`). After construction, glyph index *k* in a line equals the index among the line's **non-whitespace** characters, not the column.
  - There is no stored mapping from source span to glyph, and no token objects. Token boundaries are lost after coloring.
- **Vertical-metric hack.** The suffix `" pA<n>"` is appended to the first and last lines to normalise ascender and descender (`:236-249`). Those glyphs are then popped and squashed to zero width (`:307-313`), and they take part in sizing the background rectangle (`:324-329`).
- **Fonts.**
  - The default font is the alias `"Monospace"`, which resolves differently on each platform's Pango/fontconfig. That makes it a cross-OS determinism risk (unverified per platform).
  - `register_font(font_file)` is a context manager for bundling a font: `text_mobject.py:1524 @S/M`.
  - `disable_ligatures=True` is mandatory for the char-to-glyph mapping. `Text._gen_chars` raises `ValueError` if a font's `calt` ligatures still merge glyphs (`text_mobject.py:642-670 @S/M`).
- **Unicode.**
  - Coloring indexes by Python code point (`for char in child.text`, `:272-277`). This assumes one glyph per non-space code point. Combining marks, ZWJ emoji, and anything Pango shapes into fewer glyphs will either raise or mis-colour later glyphs (unverified; there are no Unicode Code tests).
  - The Code tests (`tests/module/mobject/text/test_code_mobject.py @S`, 13 tests) cover init, styles, colours, baseline and line-height. They don't cover Unicode, tabs, or transitions.
- **Code-transition support.** None. There are no diff helpers in `manim/`: `git grep difflib|SequenceMatcher` finds nothing at either ref.
- **Related reusable pieces.**
  - Carets: `TypeWithCursor` / `UntypeWithCursor` (`animation/creation.py:678,788 @S`).
  - Highlight boxes: `SurroundingRectangle` / `BackgroundRectangle` / `Underline` (`mobject/geometry/shape_matchers.py:26,83,195 @S`).
  - Emphasis: `Indicate`, `Circumscribe`, `FocusOn`, `Wiggle`, `ApplyWave` (`animation/indication.py:125,571,72,488,358 @S`).
  - Letter-by-letter typing: `AddTextLetterByLetter` (`creation.py:544`).

### 1.2 Text / MarkupText / Paragraph (per-glyph addressing)

- **`Text(SVGMobject)`.**
  - Defined at `text_mobject.py:302 @S/M`. Pango renders to an SVG cached under `text_dir`, named by a SHA-256 of the text plus settings (`_text2hash :690`, `_text2svg :835`).
  - Submobjects are glyphs only. Whitespace and newlines are stripped, so `t[i]` indexes non-whitespace glyphs, while `t2c` slice keys index the original string. This mismatch is documented at `:308-328`.
  - Tabs are replaced with `tab_width` spaces (`:528-531`). Spaces become zero-size `Dot`s only when `disable_ligatures=True` (`_gen_chars :642-670`). `self.text` ends up with spaces and newlines stripped (`:557`).
- **`Paragraph(VGroup)`.** Defined at `:114`. It builds one `Text` for all lines and slices `chars` per line, counting spaces only if `disable_ligatures` (`_gen_chars :179-217`). It centres itself at the origin (`:175`). There is per-line alignment (`_set_line_alignment`), but no line identity beyond index.
- **`MarkupText`.** Defined at `:877`. Pango markup with `_count_real_chars` (`:1422`). Glyph indexing has the same whitespace caveat.
- **`remove_invisible_chars`.** Defined at `:90`. A helper that strips `Dot` placeholders.

### 1.3 Transform-matching (`animation/transform_matching_parts.py`)

- **`TransformMatchingAbstractBase(AnimationGroup)`.**
  - Defined at `:27 @S`. It builds `key -> VGroup` maps from `get_mobject_parts` / `get_mobject_key` (`get_shape_map :144-155`).
  - Parts with equal keys are **grouped into one VGroup** (`:149-155`). Groups with the same key on both sides are matched and transformed as whole groups (`:99-102`).
  - `key_map` maps explicit source keys to target keys, and those pairs go through `FadeTransformPieces` (`:104-116`).
  - Unmatched parts can `Transform` (`transform_mismatches`), `FadeTransformPieces` (`fade_transform_mismatches`), or fall back to FadeOut/FadeIn (`:127-138`).
  - `get_mobject_parts` and `get_mobject_key` are `@staticmethod` hooks (`:166-172`), so a subclass can supply a custom key.
- **`TransformMatchingShapes`.**
  - Defined at `:175`. The key is a hash of points rounded to 3 decimals after centring and normalising height (`:227-233`), so the key ignores colour and position.
  - Parts come from `family_members_with_points()`, which **includes the Code background and line numbers**.
- **`TransformMatchingTex`.** Defined at `:237`. The key is `tex_string` (`:299-301`). It doesn't apply to `Code` or `Text`.
- **Usable for code diffs?**
  - Only as a base class. Repeated tokens with the same key become **one many-to-many group** with no positional pairing, so there is no duplicate disambiguation.
  - No ordering or LCS is used. Matching by shape hash also merges every identical glyph (all `e`s, and so on).
  - A custom subclass keyed on a stable `(line_id, token_idx)` ID can reuse the fade and transform plumbing.
- **MAIN.** A one-line import change only.

### 1.4 ValueTracker, updaters, interpolation

- **`ValueTracker(Mobject)`** (`mobject/value_tracker.py:21 @S/M`). The value is stored in `points[0,0]` (`:78-91`), and interpolation goes through `path_func` on points (`:195-203`). That's why `tracker.animate.set_value(x)` works: it is a `_MethodAnimation` Transform over points.
- **`ComplexValueTracker`** (`:207`). Stores the value in `points[0,:2]`.
- There are no vector, colour or structured trackers. Arithmetic dunders return new trackers (`:102-190`).
- **`Mobject.add_updater(fn, index=None, call_updater=False)`** (`mobject.py:1148 @S`, `:1160 @M`).
  - An updater is treated as time-based if its signature has a parameter literally named `dt`, checked with `inspect.signature` on every call (`update :1050-1086 @S`).
  - Related methods: `suspend_updating`/`resume_updating` (`:1313,1339`), `get_family_updaters` (`:1145`), `match_updaters` (`:1284`).
- **Helpers** (`animation/updaters/mobject_update_utils.py @S/M`):
  - `always` (`:41`); `f_always` (`:49`).
  - `always_redraw(func)` (`:67-110`): `mob.add_updater(lambda _: mob.become(func()))`, which rebuilds the whole mobject every frame.
  - `turn_animation_into_updater` (`:184`); `cycle_animation` (`:247`).
  - `UpdateFromFunc` / `UpdateFromAlphaFunc` (`update.py:18,43`).
  - `Variable` (`mobject/text/numbers.py:345`) pairs a label with a ValueTracker.
- **Per-frame order.** `Scene.update_to_time` (`scene/scene.py:1714-1724 @S`, `:1711-1722 @M`) runs these steps in sequence:
  1. Each animation's `update_mobjects(dt)` then `interpolate(alpha)`.
  2. `Scene.update_mobjects`: `self.mobjects` in add order, each running `Mobject.update` with the parent's updaters in list order and then submobjects recursively (`:409-418 @S`).
  3. `update_meshes`.
  4. `update_self`, the scene-level updaters, which run last (`:426-443 @S`).
- Animated mobjects have their updaters suspended by default (`Animation(suspend_mobject_updating=True)`, `animation.py:137,206 @S`).
- **No dependency tracking, invalidation, cycle detection or memoisation exists** at either ref.
- **Interpolation.**
  - `Mobject.interpolate` (`mobject.py:3243 @S`). `VMobject.interpolate_color` linearly interpolates fill, stroke and background-stroke RGBA arrays, widths and sheen (`types/vectorized_mobject.py:1965-1987 @S`). `ManimColor.interpolate` (`utils/color/core.py:632`).
  - Submobject counts are aligned with `align_submobjects` / `add_n_more_submobjects` (`mobject.py:3186,3218 @S`). This is what makes a naive `Transform(code_a, code_b)` scramble glyphs.
- **`.animate`.**
  - `_AnimationBuilder` (`mobject.py:3560 @S`, `:3573 @M`) records method calls on a `generate_target()` copy.
  - `override_animate(method)` (`mobject.py:3640 @S`, `:3654 @M`) lets a method return a custom Animation. For example, `code.animate.animate_to(...)` could build a diff animation.
  - `override_animation(AnimClass)` (`animation/animation.py:725 @S`) swaps the implementation of e.g. `Create` or `Transform` per Mobject class.

### 1.5 OpenGL interactive mode

- **`Scene.interactive_embed()`** (`scene.py:1439 @S`, `:1432 @M`).
  - Requires `OpenGLRenderer`, a window, no media output, no dry-run and no `skip_animation_preview` (`check_interactive_embed_is_valid :1419-1437 @S`).
  - It starts an IPython `InteractiveShellEmbed` on a thread. Scene methods `play/wait/add/remove` are proxied through a `Queue` of `MethodWithArgs` (`:1470-1484 @S`), and a `rerun()` helper is added.
- **`Scene.interact()`** (`:1523-1600 @S`).
  - Runs a render loop: `renderer.render`, then `update_mobjects`, `update_meshes`, `update_self` with wall-clock `dt` (`:1576-1583`). Wall-clock `dt` makes it non-deterministic.
  - **A watchdog `Observer` on `config.input_file` exists only inside `interact()`** (`:1525-1528`, `RerunSceneHandler :135-143`). There is no `--watch` CLI flag at either ref (grep "watch" in `cli/` and `_config/` finds nothing).
- **Rerun does not reload the module.**
  - At STABLE, `cli/render/commands.py:93-114` calls `scene_classes_from_file` once and then re-instantiates the **same class object** on rerun.
  - MAIN does the same: `cli/render/commands.py:111-131 @M`, with `Manager.render` returning `rerun` (`manager.py:464-474 @M`).
  - So a "file" rerun picks up `config` changes, but source edits to `construct` would not take effect unless something else reloads the module (unverified at runtime; inferred from code).
- **`Scene.embed()`** (`:1602 @S`). A plain IPython embed that re-renders after each cell. Exiting it raises and ends the scene.
- **Input.**
  - Pyglet window via moderngl_window: `renderer/opengl_renderer_window.py:18 @S`, moved to `renderer/opengl/window.py:42 @M` (with new `window_settings.py`).
  - Mouse and key events are forwarded to `Scene.on_mouse_motion/scroll/drag/press` and `on_key_press` (`scene.py:1812-1966 @S`). Defaults: `r` resets the camera, `q` quits, orbit and pan controls.
  - User hooks: `set_key_function(char, fn)` (`:1961`) and `mouse_press_callbacks` (`:206`).
- **Optional DearPyGui panel** (`--enable_gui`, `scene.py:22-30, 1507, _configure_pygui @S`). It has rerun/continue/scene-select buttons plus user `self.widgets` dicts (`:202`). This is a primitive precedent for F12 widgets and F08 inspector.
- **Runtime introspection.**
  - Available: `scene.mobjects`, `get_top_level_mobjects` (`:474`), `get_mobject_family_members` (`:493`); `Mobject.name` (defaults to the class name, `mobject.py:119`), `z_index`, `color`, `submobjects`, `get_family`, bounds; `Mobject.get_image()` (MAIN reimplements it through `CairoRenderer`).
  - Missing: no stable object IDs (only Python `id()` and `original_id` set on deepcopy, `mobject.py:464`), no property schema, no source-location per mobject.
- **MAIN additions (overlap, owned by the timeline agent).**
  - `Manager.evaluate(capture_timeline=..., frame_times=..., on_frame=...)` (`manager.py:503 @M`) evaluates without encoding and draws only the requested frames.
  - `manim/timeline.py @M` exports JSON (schema `manim.timeline` v1, "experimental"). It records per play: kind, start, end, run_time, animation type names, and source `{path, line}` (`_run/record.py:122-186 @M`). It records **no mobject identities**.
  - A private `_RunListener` interface (`_run/loop.py:119-145 @M`).

### 1.6 Plugins

- **Discovery.**
  - `get_plugins()` loads **every** `importlib.metadata` entry point in group `manim.plugins` (`plugins/plugins_flags.py:13-18 @S/M`).
  - `manim/plugins/__init__.py:11-16` compares that against `config.plugins` (the `[CLI] plugins =` key, `_config/utils.py:678-681 @S`) and only **warns** about missing ones. It is imported from `manim/__init__.py:121 @S` / `:110 @M`, so every `import manim` loads all installed plugin entry points.
- **`manim plugins -l`** lists them (`cli/plugins/commands.py:19-44`).
- **Hooks.** None.
  - CLI subcommands are hard-wired with `main.add_command(...)` (`__main__.py:95-100 @S/M`). There is no entry-point group for commands.
  - There are no config, renderer or scene hooks.
  - Docs say plugins must be imported explicitly (removed auto-import in 0.18.1) and that the system "will probably be refactored" (`docs/source/plugins.rst @S`).
- **MAIN.** Unchanged.

### 1.7 Serialization / copy / checkpoints

- **No pickle support at either ref.** `git grep pickle|__getstate__|__reduce` in `manim/` finds nothing.
- **`Mobject.__deepcopy__`** (`mobject.py:458-465 @S`) deep-copies `__dict__`, which includes the `updaters` list.
  - Functions and lambdas are atomic under `copy.deepcopy`, so **copied updaters still close over the original mobjects**. For example, `always_redraw`'s updater calls `mob.become` on the original.
  - `Mobject.copy()` is `deepcopy` (`:1025`).
  - `OpenGLMobject.copy(shallow=False)` (`opengl_mobject.py:1517 @S`) detaches `parents` while copying.
- **`save_state()` / `restore()`** (`mobject.py:2281-2295 @S`; OpenGL `:1590-1605`). One saved deep copy per mobject, restored through `become()`.
- **`Scene.__deepcopy__`** (`scene.py:290-301 @S`, `:320 @M`) skips `manager`, `renderer` and `time_progression`.
  - The only test (`tests/module/test_manager.py:115-123 @S`) sets `scene.queue = None` first, because `Scene.queue` is a `queue.Queue` holding thread locks. A default Scene is therefore not deep-copyable.
- **Global, process-level caches that persist across runs:**
  - `SVG_HASH_TO_MOB_MAP` (`svg/svg_mobject.py:29`). Its key is `(class, svg_default, path_string_config, file_name, renderer)`; **file content and mtime are not in the key** (`hash_seed :183-195`).
  - Text SVG files are content-hashed, so they are safe.
- **Updaters with `dt` are path-dependent.** Seeking to time *t* requires replaying every frame from the last checkpoint.

### 1.8 Scene transitions / choreography / camera

- **No scene-to-scene transitions exist** at either ref. There is no multi-scene composition and no clip masks.
  - `grep -i transition` finds only docstrings.
  - Cairo and OpenGL have no clipping API; `grep clip|mask` finds only numeric clip and `coor_mask`.
  - Boolean ops (`mobject/geometry/boolean_ops.py`) can emulate shape masks for VMobjects only.
- **In-scene primitives:**
  - Transforms: `Transform` (`transform.py:58`), `ReplacementTransform` (`:253`), `TransformFromCopy` (`:307`), `FadeTransform` (`:812`), `FadeTransformPieces` (`:919`), `Restore` (`:598`).
  - Grouping: `AnimationGroup` (`composition.py:30`), `Succession` (`:198`), `LaggedStart` (`:297`), `LaggedStartMap` (`:351`).
  - Other: `FadeIn`/`FadeOut` with `shift` and `target_position` (`fading.py:98,146`); `Scene.replace` (`scene.py:611 @S`).
- **Camera.**
  - STABLE: `MovingCameraScene` with `MovingCamera` (`scene/moving_camera_scene.py:104 @S`, `camera/moving_camera.py:27`), where `self.camera.frame.animate...` and `auto_zoom` (`moving_camera.py:170`) are available. Also `ZoomedScene` and `MultiCamera` (`camera/multi_camera.py:18`).
  - **MAIN: every Scene's camera has an animatable `frame` and `auto_zoom`** (`renderer/cairo/camera.py:107,210-227 @M`). `MovingCameraScene` is `@deprecated(replacement="Scene")` (`moving_camera_scene.py:96-100 @M`), and the `manim/camera/` package is deleted.
  - `ImageMobjectFromCamera` is reworked into a renderer-drawn live view of another camera that shares the camera on deepcopy (`types/image_mobject.py:312-344 @M`), which makes picture-in-picture possible.

### 1.9 Media

- **`ImageMobject`** (`types/image_mobject.py:133 @S`, `:134 @M`) takes a path or an array. It loads with `PIL.Image.open(path).convert(image_mode)` (`:198-201 @S`). An animated GIF therefore yields only the first frame (unverified; this is standard PIL behaviour). There is also `OpenGLImageMobject` (`opengl/opengl_image_mobject.py:44`).
- **`SVGMobject`** (`svg/svg_mobject.py:36`) uses svgelements.
  - `id_to_vgroup_dict` (`:130,211`) makes SVG element IDs addressable.
  - `generate_mobject` **writes a modified temporary SVG next to the source asset** (`{stem}_{suffix}`, `:203 @S`). That is a side effect in asset directories.
- **No video input mobject** at either ref (grep `VideoMobject` or `class .*Video` finds only `VideoEncoderSpec`).
- **Asset resolution.** `seek_full_path_from_defaults(file, default_dir, exts)` tries the path as given, then `assets_dir/file{,ext}`. It raises `OSError` listing the candidates (`utils/file_ops.py:69-84 @S`).
  - Raster images: `.jpg .jpeg .png .gif .ico` (`utils/images.py:27-32`). SVG: `utils/images.py:35-40`. Sound: `utils/sounds.py:20`.
  - `assets_dir` is set in `default.cfg:71-72` (`./`) and resolved against the working directory (`scene.py:247-258 @S`).
- **Output** (CLI is owned by the other agent; listed for F10):
  - `--format auto|none|png|png-sequence|gif|mp4|webm|mov` (`cli/render/render_options.py:152-170 @S`).
  - `-t/--transparent`: MP4 rejects alpha (`_config/output.py:63-66`); MOV uses `qtrle/argb`; WebM uses `libvpx-vp9/yuva420p` (`_config/video_encoder.py:113-124`). Alpha pixel formats are validated (`:172-176`).
  - `--video-codec`, `--pixel-format`, `--encoder-option K=V`, `--fps`, `-r W,H`.
  - Quality presets come from `QUALITIES` in `constants.py:206-243`: k = 2160p60, p = 1440p60, h = 1080p60, m = 720p30, l = 480p15.
  - MAIN adds MP4 chapters from sections (ab7f9527) and a PyAV audio mixer (`scene/audio_mixer.py @M`).

### 1.10 Config theming

- **Scene-level options.** `config.background_color` and `background_opacity` (`default.cfg:48-52`), plus frame and pixel size and `tex_template` (`:142-144`).
- **There is no visual theme system.** `[CLI_CTX] theme` (`default.cfg:168`) is for CLI help colours only.
- **`Mobject.set_default(**kw)`** (`mobject.py:262-311 @S/M`). It replaces `cls.__init__` with a `partialmethod`, which mutates class state for the whole process. Calling it with no args restores the original. There is an OpenGL twin at `opengl_mobject.py:313` and an `Animation.set_default` at `animation/animation.py:503` (default `run_time`, `rate_func`).
  - Caveat: explicit kwargs win over `partialmethod` defaults. `Text.set_default(font=...)` therefore does **not** reach `Code`, because Code passes `font="Monospace"` explicitly through `default_paragraph_config`. Code must be themed through `Code.default_paragraph_config` / `default_background_config` or `formatter_style`.
- **Config file cascade.** Library, then user (`%APPDATA%\Manim\manim.cfg` / `~/.config/manim`), then folder `manim.cfg` or `--config_file` (`_config/utils.py:46-86, 119-129`).
  - `ManimConfig` accepts only known properties: `__setitem__` goes through a property `fset` (`:349-350`), so arbitrary lesson variables can't live in `config`.
  - The raw `configparser` is reachable as `manim._config.parser` (`_config/__init__.py:24`), which is private.
- **`ConvertToOpenGL` metaclass** (`mobject/opengl/opengl_compatibility.py:17-46 @S/M`). It swaps `Mobject`/`VMobject` bases **at class-definition time**, based on `config.renderer`. A `manim_stage` subclass of `Code` defined at import, before the renderer is configured, gets the wrong base classes.

---

## 2. Requirement status

| Req | STABLE (v0.22.1) | MAIN (8c258a00) | Evidence / notes |
|---|---|---|---|
| **F05** Semantic code animation | **Partial** | **Partial** (no change) | Existing: Pygments highlighting, any style, line numbers, background, tab expansion, per-line VGroups (`code_mobject.py:172-349`); carets via `TypeWithCursor`; boxes via `SurroundingRectangle`; emphasis animations; key-based matching base (`transform_matching_parts.py:27-172`). Missing: column/span addressing (whitespace glyphs stripped, `:315-316`), token identity, diff engine, insert/delete/move transitions, duplicate-token disambiguation (same-key parts merged, `:144-155`), scrolling/auto-fit, `CodeRange`/`highlight_lines`/`animate_to`. Unicode: one-glyph-per-code-point assumption, untested. |
| **F06** Reactive signals | **Partial** | **Partial** | Existing: `ValueTracker`/`ComplexValueTracker` (`value_tracker.py:21,207`), updaters with fixed order (`scene.py:1714-1724 @S`), `always_redraw`/`f_always`, `.animate`, `override_animate`, colour/point interpolation (`vectorized_mobject.py:1965`). Missing: dependency graph, `computed`/`effect`, invalidation, cycle detection, disposal, vector/colour trackers, recompute avoidance (`always_redraw` rebuilds every frame). |
| **F07** Variables / themes / presets | **Partial** | **Partial** | Existing: `manim.cfg` cascade, `background_color`, quality presets, `Mobject.set_default`/`Animation.set_default`, `Code.default_*_config`, `register_font`, `tex_template`. Missing: theme or semantic palette object, typed lesson variables (`ManimConfig` rejects unknown keys), editor-exposed parameters, named animation templates. `set_default` is process-global and can't reach Code fonts. |
| **F08** Inspector / property editing | **Partial** (introspection primitives only) | **Partial** (+ timeline source lines per play, `Manager.evaluate(frame_times)`) | Existing: mobject tree (`scene.mobjects`, `get_family`), `name`, `z_index`, colours, bounds, `get_image()`, OpenGL mouse/key callbacks, DearPyGui widgets (`--enable_gui`). Missing: stable object IDs, property schemas, picking (hit-testing) API, per-mobject source location, undo/redo, persistence. Timeline records source per *play*, not per object (`_run/record.py:122-186 @M`). |
| **F09** Scene transitions | **Partial** (in-scene only) | **Partial** (camera frame on every Scene) | Existing: `AnimationGroup`/`Succession`/`LaggedStart`, `ReplacementTransform`/`FadeTransform(Pieces)`, `FadeIn/Out(shift=…)`, camera frame animation (`MovingCameraScene @S`; any `Scene` `@M`), `MultiCamera`/`ImageMobjectFromCamera`. Missing: cross-scene cuts/fades/wipes/slides, scene concatenation, clip masks (no clipping API in either renderer), shared-element mapping. |
| **F10** Media / presets (assets and presets part) | **Partial** | **Partial** (+ MP4 chapters, PyAV mixer) | Existing: `ImageMobject` (raster), `SVGMobject` (with element IDs), `assets_dir` resolution raising on missing (`file_ops.py:69-84`), formats png/png-sequence/gif/mp4/webm/mov, transparency with codec checks, codec/pixel-format/encoder options, `QUALITIES` presets. Missing: video input, animated GIF input, a validation pass before render (failures only at construction), font assets in config, asset manifest. |
| **F11** Python plugin bridging | **Integration only** | **Integration only** | Existing: `manim.plugins` entry-point group discovered and loaded on `import manim` (`plugins_flags.py:13-18`), `config.plugins` (warn-only), `manim plugins -l`. No hook surface (CLI commands hard-wired, `__main__.py:95-100`). Studio can enumerate the same entry points and define its own group (e.g. `manim_stage.plugins`). |
| **F12** Educational tooling / interactivity | **Partial** | **Partial** | Existing: `Graph`/`DiGraph` with tree and partite layouts (`mobject/graph.py:430-440,1278,1598`), `Table` family, `Matrix`, `Variable`/`DecimalNumber`, OpenGL `interactive_embed` + key/mouse hooks, DearPyGui widgets. Missing: call-stack, array and linked-list layouts, trace-driven animation, sequence diagrams, step/speed controls separate from linear export, web playback. |

No requirement in scope is **Not feasible**. Clip masks for wipes would need upstream renderer work (Cairo `clip()` or OpenGL stencil), so mark wipe and mask transitions as "Not feasible without upstream change" if strict.

---

## 3. Risks and surprises

1. **Code line and column identity is fragile.**
   - Glyph index is not column index, because whitespace is removed (`code_mobject.py:315-316`). Pygments token boundaries are discarded.
   - The `" pA<n>"` alignment glyphs are popped from the first and last lines. Their presence depends on `line_numbers_from`.
   - `Paragraph` re-centres (`text_mobject.py:175`), and `Code` sizes its background to content. Two `Code` instances of different sizes therefore put an unchanged line at different absolute positions.
   - "Stable unchanged-line positioning" needs explicit anchoring, e.g. aligning the top-left of `code_lines` with fixed line pitch, or building lines independently.
2. **Monospace and determinism.**
   - The `"Monospace"` alias resolves per OS through Pango/fontconfig. Glyph advances and line heights may differ between Windows, Linux and macOS (unverified).
   - Bundle a font with `register_font` and pin it in project config.
3. **Ligatures and Unicode.**
   - The char-to-glyph mapping requires `disable_ligatures=True`, and fonts with `calt` (Fira Code etc.) raise `ValueError` (`text_mobject.py:655-667`).
   - Combining marks, emoji and RTL text are untested. Coloring assumes one glyph per code point.
4. **Pygments styling loss.** Bold, italic, underline and token background colours are silently dropped (regex on `color:` only, `code_mobject.py:264-270`).
5. **TransformMatching semantics don't fit code diffs.**
   - Same-key parts are merged into one group and transformed many-to-many. There is no positional ordering or LCS.
   - The `TransformMatchingShapes` key ignores colour, so all identical glyphs collide.
   - `family_members_with_points` drags in the background and line numbers.
6. **Updater copies alias the originals.** `deepcopy` and `copy` keep updater closures pointing at source objects, so checkpoints made by copying are unsafe for updater-driven state.
7. **A Scene is not deep-copyable by default** (`queue.Queue`). There's no pickle support. Checkpoints must be "replay from a fresh scene", or Studio-owned state snapshots.
8. **`dt` updaters and wall-clock interactive loops** (`scene.py:1576-1583`) are nondeterministic or path-dependent. The interactive preview is not equivalent to the render.
9. **The file-watch rerun doesn't re-import the scene module** (`cli/render/commands.py:93-114 @S`, `:111-131 @M`). Live-reload must be built by Studio's runner as a fresh process or a `module_ops` re-import.
10. **Global process caches.**
    - `SVG_HASH_TO_MOB_MAP` ignores file content, so a long-lived runner serves stale SVGs after edits.
    - `SVGMobject` writes temporary files into asset folders.
    - `set_default` mutates classes globally.
    - Together these argue for a fresh child process per render or preview revision.
11. **`ConvertToOpenGL` binds base classes at class creation.** Studio subclasses must be defined after `config.renderer` is set, or created lazily per renderer.
12. **MAIN churn.**
    - `manim/camera/` was removed, renderer modules moved (`renderer/cairo/*`, `renderer/opengl/*`), and `MovingCameraScene` is deprecated.
    - The timeline JSON and `_run` listeners are explicitly experimental or private.
    - Pinning v0.22.1 while targeting MAIN APIs (`Manager.evaluate`, timeline) needs a compatibility shim.
13. **Plugin loading side effects.** `import manim` loads every installed `manim.plugins` entry point (`plugins/__init__.py:11-12`). A Studio runner importing manim executes third-party plugin code. That falls within the documented trust boundary, but should be stated.

---

## 4. Recommended extension points

- **F05 `AnimatedCode`.**
  - Don't subclass `Code` internals. Reuse Pygments (lexer and style) directly to get the token stream: `lexer.get_tokens`, `style.style_for_token`.
  - Build per-line, per-token mobjects with explicit IDs: one `Text` per token, or one `Text` per line plus a column map computed by counting non-space chars.
  - Expose `Code`-compatible attributes (`background`, `line_numbers`, `code_lines`) and keep `manim.Code` untouched. Optionally add `AnimatedCode.from_code(Code)` with a documented column map.
  - Implement the diff with Python `difflib` or patience at line level, then token level. Drive the animation through a subclass of `TransformMatchingAbstractBase` whose `get_mobject_key` returns a stable token ID, or through a custom `AnimationGroup` of `Transform` / `FadeIn` / `FadeOut`.
  - Hook `code.animate.animate_to(...)` through `override_animate` (`mobject.py:3640 @S`).
  - Reuse `TypeWithCursor`, `SurroundingRectangle` and `Indicate`/`Circumscribe` for carets, selection and emphasis.
  - Pin the font with `register_font`.
- **F06.**
  - Make signals thin wrappers whose storage is a `ValueTracker` (or a points-backed tracker subclass for vector and colour values), so `.animate.set_value` and Transform interpolation keep working.
  - Run the dependency graph as a single scene updater added with `Scene.add_updater`. Scene updaters run last (`scene.py:426-443`); alternatively, add one updater on a sentinel mobject at the front of `scene.mobjects` to run before other mobject updaters.
  - Evaluate in topological order with cycle detection, and remove the updater on scene teardown.
- **F07.**
  - Use a Studio project file such as `.manim-stage/project.json`. Apply it before scene import through `tempconfig` / `config.update` for known keys, `Mobject.set_default`/`Animation.set_default` for class defaults, and `Code.default_paragraph_config` / custom Pygments `Style` for code. Restore everything afterwards, or use a fresh process.
  - Keep lesson variables in Studio's own typed store, not `ManimConfig`.
- **F08.**
  - Opt-in `studio.expose(mobj, id=..., props=...)` registry. Inspect through `get_family()`, bounds, colours and `z_index`. Get thumbnails from `Mobject.get_image()`, or MAIN `Manager.evaluate(frame_times=…, on_frame=…)`.
  - On OpenGL, use `mouse_press_callbacks` / `set_key_function` for viewport picking.
  - Attach source IDs by capturing the call-site stack at `expose()`, mirroring MAIN `_run/record.py:122-140`.
- **F09.**
  - Build composition helpers on `AnimationGroup` / `Succession` / `LaggedStart`, plus camera-frame moves: `MovingCameraScene` at STABLE, `scene.camera.frame` at MAIN.
  - Do cross-scene transitions at the file level with FFmpeg/PyAV crossfades between rendered scene outputs, or with an in-scene "transition scene" that stages the last and first frames as `ImageMobject`s.
  - Emulate wipes with occluding rectangles. True masks need an upstream renderer change.
- **F10.**
  - Use a Studio asset validator that reuses `seek_full_path_from_defaults` semantics before render.
  - Map presets to the existing `--format/-q/-r/--fps/-t/--video-codec/--pixel-format` options.
  - Video input would be a Studio `VideoMobject` that decodes frames with PyAV, which is already a dependency on MAIN through the audio mixer, into `ImageMobject` pixel arrays. It is new work, and the render cost needs measuring.
- **F11.** Read `importlib.metadata.entry_points(group="manim.plugins")` to list Python plugins, and define a separate `manim_stage.plugins` group with a version handshake for editor extensions.
- **F12.**
  - Build on `Graph`/`DiGraph` (tree layout), `Table`, `Variable` and `ValueTracker`.
  - Implement local interactive controls in the Studio editor, driving re-render with parameters. Keep OpenGL `interactive_embed` as an optional power-user path only, because it is wall-clock driven and doesn't produce the export.
