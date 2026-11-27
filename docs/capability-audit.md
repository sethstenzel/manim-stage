# Capability audit (M0, spec §3)

- **Date:** 2026-11-26
- **Refs audited:**
  - ManimCE **STABLE** = `v0.22.1` (`16ea443`).
  - ManimCE **MAIN** = `8c258a0` (origin/main; prerelease `v0.30.0a1` = `5bf7b78` is a sibling release commit, not on main's ancestry).
  - Motion Canvas `v3.17.2` (`e735a99`) and main (`7b91435`).
- **Method:** source reading (`git show`/`git grep` at pinned SHAs), PR descriptions, ecosystem repo/PyPI metadata. Tests were **not executed** for this audit; executable proof is the second M0 PR (see [backlog](backlog.md)).
- **Evidence** with `path:line @ref` citations is in [`docs/audit/`](audit/):
  - [manim-core.md](audit/manim-core.md): scene execution, timeline, cache, sections, audio, CLI, tests
  - [manim-features.md](audit/manim-features.md): `Code`, reactive state, interactive mode, plugins, serialization, transitions, media, theming
  - [ecosystem.md](audit/ecosystem.md): manim-voiceover, editors, presenters, code-diff libraries, audio tooling
  - [motion-canvas.md](audit/motion-canvas.md): reference behavior (described in our own words; no MC code copied)

Status key: **E** Existing · **P** Partial · **M** Missing · **I** Integration only · **NF** Not feasible (with existing APIs).

## Headline findings

1. **Manim MAIN already ships much of the hardest P1 groundwork** (merged 2026-11-11/12), but as experimental or private APIs:
   - deterministic frame-quantized clock;
   - timeline capture + JSON export (`--timeline-output`, `Manager.evaluate(capture_timeline=True)`);
   - `Manager.evaluate(frame_times, on_frame)`, which renders arbitrary frames pixel-identical to a render without encoding;
   - sample-accurate PyAV audio mixer in movie time;
   - MP4 chapters from sections.
2. **STABLE is a poor base for timing work.** Its float clock depends on cache state and renderer, and sounds are misplaced in `-n`/skipped renders (derived from code). → ADR-0003.
3. **MAIN is mid-refactor.** Open maintainer PRs #5173–#5178 rewrite `_run/*`, `manager.py`, `scene.py` and the renderers. Pin by SHA and isolate behind one adapter module.
4. **No reusable ManimCE editor exists.**
   - `manim_editor` is dead.
   - Other projects are standalone apps.
   - manim-voiceover and manim-slides **break on 0.30**.
   - Nothing in the ecosystem does code diffs or reactive signals.
5. **Spec API collision:** `Scene.wait_until(stop_condition, max_time)` already exists. The cue API must use another name (ADR-0006).
6. **Motion Canvas is effectively dormant.**
   - Last release Dec 2024, a handful of commits since.
   - Docs moved to **motion-canvas.io** (spec §14 links are stale).
   - Its FFmpeg exporter on main is now **GPLv3**: don't reuse it.

## Requirement matrix

| Req | Item | STABLE | MAIN | Evidence → plan |
|---|---|---|---|---|
| F01 | Editor, scene picker, playback | M | M | No editor in Manim or maintained ecosystem → build (ADR-0004). |
| F01 | Live preview | P | P | OpenGL-only `--live-preview`, wall-clock paced, forward-only. MAIN adds `Manager.evaluate` frame drawing. → runner uses `evaluate`. |
| F01 | Hot reload on file change | P | P | OpenGL `interact()` watchdog rerun does not re-import the module (unverified at runtime). Cairo has none. → fresh child process per revision (ADR-0004). |
| F01 | Tracebacks with file/line | P | P | Python tracebacks available. Runner must structure them. |
| F01 | Renderer capability indicators | P | P | `RendererCapabilities(live_preview)` exists at both refs → surface in UI. |
| F02 | Trace play/wait/section/sound | M | P | MAIN timeline v1 records top-level play/wait/section/caption/sound with frame-aligned start/end and source file:line. → ingest via adapter (ADR-0005). |
| F02 | Nested group/lag child timings | M | M | Not in timeline. Computable from `_Play.animations[*].anims_with_timings` via private listener → isolated shim. |
| F02 | Stable event IDs | M | M | List order + source line only. Lines repeat in loops. Wrappers hijack the source frame. → our own ID scheme (ADR-0005). |
| F02 | Frame indices / rational time (§8) | M | P | MAIN: integer frame counter, `ceil(d·r−1e-9)` frame counts. Timeline stores float seconds only. → our schema stores frame indices. |
| F02 | Jump-to-source | M | P | `source.path/line` per play on MAIN. |
| F03 | Named cues + sidecar overrides | M | M | Primitives only (`wait`, `pause`, `wait_until(callable)`). manim-voiceover bookmarks are text-position based, with no manual times (its issue #113). → build (ADR-0006). |
| F03 | Cue validation, ripple, undo | M | M | Build. MC model (absolute scene-relative targets, ripple-on-drag) adopted with fixes for its silent-drop/non-atomic edges. |
| F04 | Audio placement + mixdown | P | P+ | STABLE: pydub ms overlay, misaligned in partial renders. MAIN: PyAV 48 kHz sample-accurate, movie-time correct, section videos carry audio. |
| F04 | Trim / fade / mute / solo / multi-clip | M | M | Not in `add_sound`. → pre-process temp assets via PyAV, or upstream. |
| F04 | Waveform UI | M | M | Editor uses wavesurfer.js (BSD-3) with server-computed peaks (PyAV). |
| F04 | Voiceover integration | I | I* | manim-voiceover works on 0.22 but **breaks on 0.30** (`_original_skipping_status`). → adapter + upstream fix. |
| F05 | Syntax highlighting, line numbers | E | E | `Code` uses Pygments (colour only: bold/italic dropped). |
| F05 | Line/column/token addressing | P | P | Lines addressable (`code_lines[i]`). Columns are not: whitespace glyphs are stripped, token boundaries discarded. |
| F05 | Code-version transitions / diff | M | M | No helper. `TransformMatching*` merges same-key parts, so unsuitable as-is. → `AnimatedCode` built on Pygments tokens + in-house patience diff (ADR-0008). |
| F05 | Stable unchanged-line positioning | M | M | `Paragraph` re-centres and the background sizes to content → explicit anchoring. |
| F05 | Unicode / ligatures / fonts | P | P | One-glyph-per-code-point assumption. Ligature fonts raise. "Monospace" alias resolves per OS → bundle a font. |
| F06 | Trackers, updaters, `.animate` | E | E | `ValueTracker`, `ComplexValueTracker`, fixed updater order. |
| F06 | Signals/computed/effects, dependency graph, cycles | M | M | Build as a thin layer whose storage is `ValueTracker`. |
| F07 | Config cascade, quality presets, class defaults | P | P | `manim.cfg`, `set_default`, `register_font`. `ManimConfig` rejects unknown keys. No theme object. → Studio project file + typed store. |
| F08 | Mobject tree / bounds / colours introspection | P | P | Primitives exist. No stable object IDs, picking API, property schema or persistence. → opt-in `expose()` registry. |
| F09 | In-scene composition | E | E | `AnimationGroup`/`Succession`/`LaggedStart`, camera frame (any Scene on MAIN). |
| F09 | Cross-scene transitions | M | M | Build at file level (PyAV crossfade) or via staged last/first frames. |
| F09 | Masks / wipes | NF | NF | No clipping API in either renderer → occluder emulation, or upstream work. |
| F10 | Output formats, transparency, codecs | E | E | mp4/webm/mov/gif/png/png-sequence, codec/pixel-format options. |
| F10 | Range export | P | P | By play index (`-n a,b`) and `--save_sections`. No time ranges → map via timeline. |
| F10 | Asset validation before render | M | M | Failures only at construction → Studio validator. |
| F10 | Video/GIF input | M | M | No video mobject. Animated GIFs load first frame only. |
| F11 | Python plugin discovery | I | I | `manim.plugins` entry points loaded eagerly on `import manim`. No hooks. CLI subcommands hard-wired → own console script + `manim_stage.plugins` group. |
| F11 | Editor plugin API with version handshake | M | M | Build (MC has none either). |
| F12 | Graph/tree/table layouts | P | P | `Graph`/`DiGraph` tree layout, `Table`, `Matrix`, `Variable`. |
| F12 | Call-stack/array/list layouts, trace-driven animation | M | M | Build (P3). |
| §4 | Seek P1 (cached frames) | I | I | MAIN: n-th play entry ↔ `partial_movie_files[n]`. Better: own frame store fed by `evaluate(on_frame)` (ADR-0007). |
| §4 | Seek P2 (re-render after edits) | P | P | `evaluate` replays from t=0 once per fresh Scene, runs to end. MAIN cache key includes start time, so a retime invalidates all later plays. |
| §4 | Seek P3 (live scrubbing) | NF | NF | No scene snapshot/restore. Copies alias updater closures. Scene not deep-copyable. |
| §2.5 | Determinism | P | P | `config.seed` defaults to `None` → Studio enforces a seed. Timeline hashes only the scene file. |

## Corrections to the spec's hypothesis matrix (§6)

- **"Seekable timeline – partial movie cache"**: viable only on MAIN. Prefer `Manager.evaluate(on_frame)` frame capture over reusing partial movie files.
- **"Editable waitUntil – voiceover plugin"**: the voiceover plugin has no manual timing and breaks on 0.30. Cues are new work; voiceover is an adapter.
- **"Animated code diffs – `Code`"**: `Code` cannot address columns or keep line positions stable. `AnimatedCode` is a new mobject that reuses Pygments, not a `Code` subclass.
- **"Media management – Manim raster/video"**: Manim has no video input at either ref.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| MAIN refactor stack (#5173–#5178) changes `_run`, `Manager`, renderers | Adapter breakage | Single `manim_stage._compat` module. Pin SHA. Weekly upstream-watch. Upstream a public listener API. |
| Timeline v1 is experimental, "no deprecation period" | Schema churn | Never expose it. Map into our versioned `SceneEvent`. |
| Each preview/seek = full scene execution (`evaluate` runs to end) | Latency on long scenes | Frame cache + per-scene invalidation. Measure in M0 proof. Propose early-stop upstream. |
| Wrappers become the recorded source location | Wrong jump-to-source | Capture user call-site ourselves (first frame outside `manim` and `manim_stage`). |
| Cache key includes start time (MAIN) | Retimes re-render everything after the change | Accept for P1. Explore time-independent keys upstream for P2. |
| Cross-OS font metrics | Non-deterministic code layout | Bundle a pinned monospace font. Golden tests per OS. |
| Third-party `manim.plugins` run on `import manim` | Code executes in runner | Document in trust boundary (spec §2.8). |
