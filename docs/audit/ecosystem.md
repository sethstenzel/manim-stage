# manim-stage M0: ecosystem audit

Audit date: 2026-11-26. Read-only research. Sources: `gh api` repo/commit/release metadata, PyPI/npm JSON, and shallow clones in
`scratchpad/m0/clones/` (manim-voiceover, manim_editor, manim-slides, manim-sideview, manimate, MathItYT/manim-studio,
code-video-generator, manim-notebook, Manimble, manim-presentation, Manim-live-preview, manim v0.22.1, manim v0.30.0a1).
"Source-inferred" means read from code, not run. "Unverified" means I could not confirm it.

Baseline: ManimCE stable **v0.22.1** (2026-10-27, Python >=3.11, `av>=15.0`, Pygments-based `Code`). Prerelease **v0.30.0a1**
(2026-11-22) changes things that matter to every project below
([release notes](https://github.com/ManimCommunity/manim/releases/tag/v0.30.0a1)):
- Renderer state moved into `manim/renderer/_execution.py`. `renderer._original_skipping_status` is gone.
- Module paths `manim.renderer.opengl_renderer` and `manim.renderer.cairo_renderer` were removed, with no aliases.
- `scene.time` now advances in whole frames, and waits round up.
- pydub and `audioop-lts` are no longer dependencies; PyAV mixes the audio.
- New: `Manager.evaluate()`, which runs a scene without rendering it.
- New: **`--timeline-output` / `Manager.timeline`**, an experimental JSON export of plays, waits, sections, captions and sounds
  with source lines ([docs/source/guides/timeline.rst](https://github.com/ManimCommunity/manim/blob/v0.30.0a1/docs/source/guides/timeline.rst)).
- New: section chapters embedded in MP4.

---

## Summary table

| Project | License | Last activity | Manim compat | Spec overlap | Verdict |
|---|---|---|---|---|---|
| manim-voiceover | MIT | commit 2026-06-15; v0.4.0 2026-06-14; open PRs to 2026-11-17 | Lock tests 0.20.1; works on 0.22 (source-inferred); **breaks on 0.30.0a1** (`_original_skipping_status`) | F03, F04 (TTS, bookmarks, captions, cache) | **Integrate via adapter** (optional dep), and contribute upstream fixes |
| ManimCommunity/manim_editor | MIT | commit 2024-07-17; v0.3.8 2021-12-19 | PyPI pins manim 0.13.x; dead | F01 (section player), F10 | **Borrow ideas only** (section-index reading) |
| manim-slides | MIT | commit 2026-09-17; PyPI 5.7.0 2026-09-14 | `manim>=0.19`, lock 0.19.1; **import breaks on 0.30.0a1** | F01/F09 (presenting), F02 (slide markers) | **Integrate via adapter** (read/export only); not a core dep |
| manim-presentation | GPL-3.0 | commit 2022-12-15 | stale; README points to manim-slides | presenting | **Avoid** |
| Manimble (pachterlab) | BSD-2-Clause | commit 2026-11-26 (daily) | pins manim 0.21.0 + manim-slides 5.7.0 | F01, F08 (canvas edit to AST patch), engine protocol | **Borrow ideas only** |
| manim-sideview | MIT (repo); package.json has no license field | commit 2026-09-09; v0.4.3 | CLI-based, so version-agnostic | F01 (VS Code preview) | **Borrow ideas only** / coexist |
| Manim Notebook | MIT | commit 2025-04-14; v1.0.1 | **ManimGL only** | F01 (ManimGL comparison) | **Borrow ideas only** |
| kevcen/manimate | MIT | commit 2024-07-30; no release | manim==0.15.2, PySide6 6.3 | F08 (WYSIWYG) | **Avoid** (ideas at most) |
| MathItYT/manim-studio | **No LICENSE file** (README says MIT) | commit 2024-03-23; PyPI 0.7.4 | manim ^0.18 (<0.19), py<3.13 | F01/F08 (Qt GUI) | **Avoid**; **it owns the PyPI name `manim-studio`** |
| Manim-Motion (BlommeJan) | no LICENSE file (badge says MIT) | commit 2026-04-06 | Docker, Vue 2.7 | F01/F08 | **Avoid** (ideas only) |
| manim built-in `%%manim` magic / krassowski/jupyter-manim | MIT | built-in / last commit 2022-01-02 | built-in in 0.22 and 0.30 | Jupyter preview | Built-in: note only; jupyter-manim: **Avoid** |
| sleuth-io/code-video-generator | Apache-2.0 | commit 2021-09-20; v0.5.0 | manim>=0.10 (old API) | F05 (line highlight only) | **Borrow ideas only** |
| CodeVideoRenderer (ExploreMaths) | MIT | commit 2026-06-20; PyPI 1.2.3 | manim>=0.18 | F05 (typing animation, camera follow) | **Borrow ideas only** |
| manim-code-blocks (2 repos) | MIT | 2024-02 / 2025-05 | old | F05 | **Avoid** |
| reactive-manim | MIT | commit 2026-08-31; PyPI 0.0.5 | targets 0.18.1; **overrides `MathTex`** | F05/F06 ideas (identity-keyed auto-transforms) | **Borrow ideas only** |
| Pygments | BSD-2-Clause | 2.21.0, 2026-08-17 | used by manim `Code` | F05 lexing/styles | **Reuse as dependency** (already transitive) |
| py-tree-sitter + per-language grammar wheels | MIT | 0.27.0, 2026-11-23 | n/a | F05 structural matching | **Reuse as optional dependency** |
| tree-sitter-language-pack | MIT | 1.28.0, 2026-11-26 | n/a | F05 | **Avoid** (downloads native parsers at runtime) |
| tree-sitter-languages (grantjenks) | Apache-2.0 (PyPI) | release 2024-02 | n/a | F05 | **Avoid** (unmaintained) |
| difflib (stdlib) | PSF | n/a | n/a | F05 baseline | **Reuse** as fallback only |
| patiencediff | **GPL-2.0-or-later** | 1.0.2, 2026-10-20 | n/a | F05 | **Avoid** (license); implement patience/histogram in-house |
| diff-match-patch | Apache-2.0 | 20241021 | n/a | F05 intra-line char diff | Optional (Integrate) |
| rapidfuzz | MIT | 3.14.6, 2026-08-30 | n/a | F05 fuzzy line pairing | Optional (Integrate) |
| wavesurfer.js | BSD-3-Clause | 8.1.1, 2026-11-24 | n/a | F04 waveform UI | **Reuse as dependency** (editor) |
| peaks.js (BBC) | LGPL-3.0 | 4.0.0 | n/a | F04 | **Avoid** (LGPL in bundled JS) |
| audiowaveform (BBC) | GPL-3.0 | 2025-08 | n/a | F04 peaks | **Avoid** |
| PyAV | BSD-3-Clause (bundled FFmpeg license unverified) | 19.0.2 (py>=3.12) / 18.1.1 (py>=3.11) | **already a manim dep** (`av>=15.0`) | F04/F10 decode, peaks, mixdown | **Reuse as dependency** |
| python-soundfile | BSD-3-Clause | 0.14.0, 2026-06-06 | n/a | F04 decode | Not needed (PyAV covers it) |
| ManimGL (3b1b) | MIT | commit 2026-09-09; v1.7.2 2024-12-13 | different engine | interactive embed/checkpoints | **Comparison only** |

---

## 1. manim-voiceover (key for F03/F04)

- Repo: https://github.com/ManimCommunity/manim-voiceover. PyPI `manim-voiceover`. Docs: https://voiceover.manim.community
- License **MIT**. 328 stars, 61 open issues+PRs (API count).
- Last commit 2026-06-15. Latest release **v0.4.0, 2026-06-14** (PyPI same day).
- Maintenance comes in bursts from a single maintainer (Onur Solmaz). There were no commits from 2024-09-29 to 2026-05-28, then a
  refactor burst in 2026-06 (src layout, Pydantic cache models, Gemini service, uv, mutation testing).
  `docs-unchecked/2026-06-15-code-smells.md` is a self-audit listing about 45 known smells.
- Python **>=3.11** (classifiers 3.11–3.13).
- Dependencies: `manim` (unpinned), `sox`, `python-dotenv`, `mutagen`, `pydub<0.26`, `pip>=26.1.2`, `pydantic>=2.10,<3`, `python-slugify`.
  It also uses `scipy.interpolate`, which comes in only through manim.
- Extras: azure, gtts, openai, pyttsx3, elevenlabs, gemini, recorder (PyAudio+pynput), translate (deepl),
  transcribe (`openai-whisper`, `stable-ts`).
- Registered as a Manim plugin: entry point `manim.plugins: manim_voiceover`.
- CI: Ubuntu, Python 3.12, against **manim 0.20.1** (uv.lock). It is not tested on Windows or macOS, and not on manim 0.22.

### Architecture (source: `src/manim_voiceover/voiceover_scene.py`, `tracker.py`, `services/base.py`)
- **Subclasses `Scene`**: `class VoiceoverScene(Scene)`. It does not monkeypatch.
- It reaches renderer internals in two places:
  - `self.renderer.skip_animations = self.renderer._original_skipping_status` runs on every voiceover.
  - Timing reads `scene.renderer.time`.
- `set_speech_service(service, create_subcaption=True)`.
- `with self.voiceover(text="... <bookmark mark='A'/> ...") as tracker:` works like this:
  1. `SpeechService._wrap_generate_from_text` runs. It normalises whitespace, calls the provider's `generate_from_text`, optionally
     transcribes with Whisper, applies `global_speed` through sox `tempo`, and appends the entry to `cache.json`.
  2. A `VoiceoverTracker` is built.
  3. `self.add_sound(final_audio)` is called at the current `renderer.time`.
  4. Subcaptions are added through `add_subcaption`, chunked by character count and weighted by length.
  5. On exit, `wait_for_voiceover()` calls `safe_wait(remaining)`.
- **Timing**:
  - `tracker.duration` comes from **mutagen** metadata (`modify_audio.get_duration`). Only `.wav` is handled specially; *anything
    else is parsed as MP3*.
  - `start_t = renderer.time` and `end_t = start_t + duration`.
  - `get_remaining_duration()` is `end_t - renderer.time`.
  - `safe_wait(d)` waits only if `d > 1/frame_rate`.
  - Times are float seconds with no frame quantisation.
  - Under 0.30's whole-frame clock, waits round up, so drift behaviour is unverified.
- **Bookmarks**:
  - Regex `<bookmark mark='X'/>` in the text. Each mark's character offset in the bookmark-free text is mapped to audio time by
    `scipy.interpolate.interp1d` over the word boundaries (`text_offset` to `audio_offset / 10_000_000`, Azure 100-ns ticks).
  - It is scaled by `len(transcribed_text) / len(input_text)` when Whisper text differs.
  - `wait_until_bookmark(mark)` calls `safe_wait(tracker.time_until_bookmark(mark))`. `time_until_bookmark(mark, buff=0, limit=None)`
    is public, so it can be used as `run_time=`.
  - Without word boundaries it raises, telling you to enable Whisper.
  - If there are fewer than 2 boundaries, it falls back to a linear text-to-time map.
- **Word boundaries by service**:
  - **Azure**: native, through the SDK `synthesis_word_boundary` event (reads SDK private `__dict__`).
  - **OpenAI, ElevenLabs, Recorder**: default `transcription_model="base"` (local Whisper through stable-ts).
  - **gTTS, pyttsx3, Gemini**: none, unless transcription is enabled.
- **Cache**:
  - Lives in `config.media_dir/voiceovers/`.
  - `cache.json` is a JSON list of entries `{input_text, input_data, original_audio, final_audio, word_boundaries?, transcribed_text?}`.
  - The lookup key is `input_data`: the text **without bookmarks** plus the service config. So moving a bookmark does not
    re-synthesise.
  - Audio is named `slug(text)[:50]-sha256(json.dumps(input_data))[:8].mp3`.
  - Writes append without atomicity or locking. Open PR #144 adds locking and atomic replace. `json.dumps` runs without `sort_keys`.
- **Recorded audio**:
  - `RecorderService` records from the microphone during render.
  - `_StitcherService` (private, buggy: issues #88, #80; fix PR #126 open since 2026-04) splits one long recording on silence into
    per-voiceover chunks.
  - There is **no public "use this existing file" service**. Issue #100 asks for pre-recorded tracks.
- **No manual bookmark timing**: issue #113 is open. Bookmarks need TTS boundaries or Whisper.
- Open PR #143 (2026-10-10) adds `time_offset`, `gain` and timeline scheduling to `voiceover()`. Not merged.

### Compatibility
- **v0.22.1**: `_original_skipping_status` and `renderer.time` exist in both `cairo_renderer.py:55` and `opengl_renderer.py:564`.
  Should work (source-inferred, not run).
- **v0.30.0a1**: `_original_skipping_status` **no longer exists** (renderer uses `_RendererExecutionView`). Every `voiceover()` call
  will raise `AttributeError` (source-inferred).
- Also on 0.30: manim dropped `audioop-lts`. manim-voiceover imports `pydub` at module import (`helper.py`) but does not declare
  `audioop-lts`, so `import manim_voiceover` on Python >=3.13 with manim 0.30 likely fails (unverified).
- `add_sound(path)` and `add_subcaption` keep their call signatures on 0.30.

### Overlap with spec
| Spec | Covered by manim-voiceover? |
|---|---|
| F04 TTS / recording / transcription | **Yes**. The spec says not to reimplement these; use them through an adapter |
| F03 named cues | Partial. Bookmarks are named, text-anchored cues *inside one voiceover*; no sidecar overrides, no editor, no ripple |
| F04 waveform / offset / trim / gain / fade | No (gain and offset only in unmerged PR #143) |
| Word timings for display | Yes: `tracker.data["word_boundaries"]` and `cache.json` hold per-word `audio_offset` |
| Captions | Yes, through Manim subcaptions (`.srt` next to the video) |

**Verdict: Integrate via adapter.** Keep it an *optional* dependency.
- Read `cache.json` and tracker data to show voiceover segments and word timings on the timeline.
- Allow a `StudioScene` that is also a `VoiceoverScene`, through mixin compatibility testing.
- Do not depend on its internals for cue timing.
- Upstream candidates:
  - a 0.30 compatibility fix (`_original_skipping_status`);
  - a public pre-recorded-file service (#100);
  - manual or sidecar bookmark times (#113), which could be fed from manim-stage `cues.json`;
  - the atomic-cache fix (#144).
- Risks:
  - single maintainer;
  - Ubuntu-only CI;
  - runtime `pip` dependency with interactive install prompts in library code;
  - mutagen MP3-only duration.

---

## 2. Editors, presenters, previewers

### ManimCommunity/manim_editor
- https://github.com/ManimCommunity/manim_editor. MIT, 365 stars, 23 open issues.
- Last commit 2024-07-17 (readthedocs config). Last release **v0.3.8, 2021-12-19**.
- PyPI pins `manim>=0.13.1,<0.14.0`. Python ^3.7.
- Flask + waitress web app.
- Architecture: scans the CWD for section-index JSON written by `manim --save_sections` and builds projects and presentations from the
  per-section videos (`editor/manim_loader.py`, `section_index.schema.json`). It is why Manim has `next_section` and `--save_sections`.
- Overlap: F01 (browser player over pre-rendered sections), F10 (export).
- **Verdict: Borrow ideas only.** Abandoned, and pinned to manim 0.13. The section-index reading pattern is still the right P1 cache
  primitive. It is now superseded by the 0.30 timeline JSON.

### jeertmans/manim-slides
- https://github.com/jeertmans/manim-slides. MIT, **1004 stars**, 56 open issues.
- Last commit 2026-09-17. PyPI **5.7.0, 2026-09-14** (GitHub release v5.6.0, 2026-04-15).
- Python >=3.10 (classifiers to 3.14). Extras: `manim>=0.19`, `manimgl>=1.7.2`.
- CI covers Windows, macOS and Ubuntu. uv.lock tests **manim 0.19.1**.
- Architecture:
  - `Slide(BaseSlide, Scene)` **subclass**. `next_slide(loop=, auto_next=, notes=, ...)` records animation-index ranges.
  - After render it reads `renderer.file_writer.partial_movie_files`, concatenates them per slide, generates reversed clips, and
    writes `slides/<Scene>.json` (pydantic `PresentationConfig`: slides with file, rev_file, notes, loop flags).
  - Has a Qt presenter (qtpy) and converts to HTML (reveal.js), PDF and PPTX.
  - Includes an IPython magic.
- Compatibility:
  - `manim_slides/slide/manim.py` does `from manim.renderer.opengl_renderer import OpenGLRenderer` and reads `camera.pixel_width`.
    Both are removed in 0.30.0a1, so **import fails on 0.30** (source-inferred).
  - Works on 0.19–0.22 (unverified on 0.22.1).
  - Manimble pins manim 0.21.0 "for manim-slides" (reason unverified).
- Overlap: F09 / F12 stretch (portable playback with chapters), F02 slide markers. Open issue #258 asks for slide-plus-voiceover pairing.
- **Verdict: Integrate via adapter (optional).**
  - Coexist: a scene can be both a `Slide` and instrumented.
  - Read `slides/*.json` to show slide boundaries as timeline markers.
  - Optionally offer "export to manim-slides".
  - Do not make it a core dependency (Qt, and its own render pipeline).

### galatolofederico/manim-presentation
- https://github.com/galatolofederico/manim-presentation. **GPL-3.0**, 173 stars.
- Last commit 2022-12-15. PyPI 0.2.1 (2021-06-28).
- README: "For an actively developed fork please check out manim-slides".
- **Verdict: Avoid** (stale, GPL).

### pachterlab/Manimble
- https://github.com/pachterlab/Manimble. **BSD-2-Clause**, 131 stars.
- Created 2026-10-07. Release v0.4.9 2026-11-26, with near-daily commits.
- A native macOS (Swift) slide editor, with a Windows client in preview (Microsoft Store). Linux is planned.
- Shared Python engine (`engine/manimble`, Python 3.11+):
  - The front end spawns `python -m manimble.rpc` and speaks **JSON lines over stdin/stdout**, with request id, result or error, and
    pushed events ([docs/developers/protocol.md](https://github.com/pachterlab/Manimble/blob/main/docs/developers/protocol.md)).
  - `worker.py` runs scenes with animations skipped and records objects, creating call sites and layout calls by **monkeypatching**
    `Mobject.add`, `Group.__init__` and `_AnimationBuilder.__getattr__`, and wrapping scene methods with `setattr`.
  - `srcedit.py` (~2400 lines) turns canvas edits into minimal AST source patches, with render-verify and rollback, undo, and
    optimistic edits.
- Pins manim==0.21.0 and manim-slides==5.7.0.
- Overlap: F01 (runner/protocol), F08 (inspector, canvas-to-source), F10.
- **Verdict: Borrow ideas only.**
  - Good prior art for the runner protocol, call-site tracing and AST code actions (spec F02/F08: "explicit, reviewable code action").
  - Not reusable as a library (app-coupled, monkeypatch-heavy, slide-centric, macOS-first).
  - Its BSD-2 license would allow borrowing code with attribution.

### Rickaym/manim-sideview (VS Code)
- https://github.com/Rickaym/manim-sideview. MIT (repo LICENSE; `package.json` has no `license` field). 187 stars, 14 open issues.
- v0.4.3, 2026-09-09. VS Code ^1.68. Marketplace + Open VSX.
- Architecture:
  - Spawns the `manim` CLI.
  - Finds the output by parsing the last `File ready at` log line (`src/mediaResolution.ts`) or by probing the filesystem.
  - Plays the result in a webview. Re-renders on save (`onDidSaveTextDocument`).
  - Has a per-file "job" config and a Mobject snippet gallery.
  - No timeline and no seek beyond the video player.
- **Verdict: Borrow ideas only / coexist.**
  - Could later host a manim-stage webview or link to it.
  - Shows that log-scraping is fragile; prefer the 0.30 timeline JSON or our runner manifest.

### Manim Notebook (VS Code)
- https://github.com/Manim-Notebook/manim-notebook. MIT (LICENSE.txt), 49 stars.
- v1.0.1, 2025-04-14 (last commit). VS Code ^1.93.
- **ManimGL only** ("NOT Manim CE"). `##` comment cells are sent into a ManimGL `embed()` IPython session (`checkpoint_paste`).
- **Verdict: Borrow ideas only** (UX for cell-based incremental preview).
- Related: tan-o/vscode-manim-notebook (GPL-3.0, CE notebook, 0 stars): Avoid. Alamin-H-M/manim-slides-preview (MIT, 5 stars): ignore.

### kevcen/manimate
- https://github.com/kevcen/manimate. MIT, 140 stars.
- Last commit 2024-07-30. No release or PyPI.
- `requirements.txt`: manim==0.15.2, PySide6==6.3.0, moderngl 5.6.4.
- A WYSIWYG Qt editor (keyframe "states", automatic interpolation, export to Python code). Student project.
- **Verdict: Avoid** (dead, ancient pins). Keyframe-to-code export is an idea at most.

### MathItYT/manim-studio (name collision)
- https://github.com/MathItYT/manim-studio. 93 stars, 5 open issues.
- **No LICENSE file**: the GitHub API license endpoint returns 404, even though the README says MIT. Treat as all-rights-reserved.
- Last commit 2024-03-23. GitHub release 0.6.8 (2023-12-21). **PyPI `manim-studio` 0.7.4 (2024-03-23)**.
- Pins `manim>=0.18,<0.19`, `pyqt6`, Python >=3.9,<3.13.
- PyQt6 GUI: live Cairo preview via `scene.renderer.get_frame()`, mobject picker, a "live cell" for code injection, and "Generate
  Python File". Registers a `manim.plugins` entry point named `manim_studio`.
- The author is now active on `manimgl`, `wgpu-py` and `manimgx` forks, not this.
- **Verdict: Avoid.**
- **Naming impact**:
  - The PyPI distribution `manim-studio` and the plugin/import name `manim_studio` are taken.
  - The spec's working name `manim_studio` would clash on install and in the `manim.plugins` entry point.
  - `manim-stage`, `manim_stage` and `manimstage` all return 404 on PyPI, so they are available as of 2026-11-26.

### Other editors found (all Borrow ideas / Avoid)
- **BlommeJan/Manim-Motion** (46 stars). Browser "Figma-like" editor (Vue 2.7, Node 20, Docker) with a code-only mode. Last commit
  2026-04-06. No LICENSE file. Avoid.
- **diegormirhan/manim-editor** (3 stars, Rust desktop). Avoid.
- **wenhaoquestion/Manim-live-preview** (11 stars). Single upload 2025-08-26, no release. Avoid.
- **FavioVazquez/showtime** (MIT, 347 stars, created 2026-09). An agent-driven "local video studio"; not a Manim authoring layer.
  Ignore.

### Jupyter
- ManimCE has a built-in `%%manim` cell magic (`manim/utils/ipython_magic.py`, present in v0.22.1 and v0.30.0a1).
- krassowski/jupyter-manim (MIT, 198 stars, last commit 2022-01-02, PyPI 1.3 from 2020) is superseded. Avoid.
- AkashKarnatak/manim_notebook (last commit 2020): Avoid.

### ManimGL interactive features (comparison only)
- 3b1b/manim: MIT. v1.7.2 (2024-12-13). Last commit 2026-09-09.
- `Scene.embed()` opens an IPython shell bound to the live OpenGL window (`manimlib/scene/scene_embed.py`).
- `checkpoint_paste()` caches scene state per comment-header checkpoint, so re-running a cell resumes from the checkpoint
  rather than from t=0.
- `reload_scene()` and `auto_reload()` support live reload.
- `save_state`, `restore_state`, `undo`, `redo` and `SceneState` live in `scene.py:661–881`.
- `InteractiveScene` adds mouse selection and dragging.
- This is the closest prior art for spec P2/P3 "checkpoints" and live OpenGL scrubbing. ManimCE has OpenGL `interactive_embed`
  instead; that belongs to the core audit.

---

## 3. Code animation (F05)

### Existing Manim plugins
- **manim `Code`**:
  - v0.22.1 `manim/mobject/text/code_mobject.py` runs Pygments `HtmlFormatter`, parses the HTML with BeautifulSoup, and builds
    `Paragraph` glyph VGroups. Same in 0.30.0a1 (import order only).
  - No diff or transition API; users fall back to `TransformMatchingShapes` / `ReplacementTransform`.
- **sleuth-io/code-video-generator**:
  - https://github.com/sleuth-io/code-video-generator. Apache-2.0, 253 stars.
  - Last code commit 2021-09-20, v0.5.0. Deps: manim>=0.10, librosa, pyglet, ffmpeg-python.
  - `CodeScene(MovingCameraScene)`, `PartialCode(Code)`, `HighlightLines` / `HighlightLine` transforms, comment-driven walkthrough,
    background music beat alignment.
  - No inter-version diff. Borrow ideas only.
- **ExploreMaths/CodeVideoRenderer**:
  - https://github.com/ExploreMaths/CodeVideoRenderer. MIT, 59 stars.
  - Last commit 2026-06-20. PyPI 1.2.3 (2026-05-04). manim>=0.18, moviepy.
  - Simulated typing with a camera that follows the cursor; Cairo and OpenGL.
  - No structural diff. Borrow ideas only (caret and typing effects).
- **manim-code-blocks**: CasualCodersProjects (MIT, 6 stars, 2024-02) and WhitePaper233 (MIT, 3 stars, PyPI 1.0.13 2022-11,
  `tokenize-all`). Avoid.
- **reactive-manim** (philip-murray):
  - https://github.com/philip-murray/reactive-manim. MIT, 78 stars.
  - Last commit 2026-08-31. PyPI 0.0.5. Targets ManimCE 0.18.1.
  - Math-expression components (`Term`, `Parentheses`, ...) that animate automatically by **component identity** when state changes.
  - **Overrides `MathTex` on import.**
  - It is not a signal library, despite the name. Its identity-keyed automatic transform is a useful model for stable token IDs in
    F05. Borrow ideas only.
- **Not found**: no maintained ManimCE plugin for Motion-Canvas-style code diff (insert, delete, move with stable token identity).
  Searched GitHub for "manim code diff/transform/animation", `TransformMatchingCode` and the `manim-plugin` topic.
  - The only `TransformMatchingCode` found is in **maloyan/manim-web** (TypeScript port of Manim, MIT, 527 stars,
    `src/animation/transform/TransformMatchingCode.ts`). It could be a behaviour reference; it is TS, not reusable in Python.
  - **No reactive/signal library for ManimCE found** (F06): searched "manim reactive", "manim signal", "manim valuetracker".

### Syntax highlighting and parsing
- **Pygments**:
  - https://github.com/pygments/pygments. BSD-2-Clause. 2.21.0 (2026-08-17), Python >=3.9, pure Python.
  - Already required by manim `Code`. Covers every language in spec F05.
  - Gives a flat token stream (type, value) only, which is enough for highlighting and for token-level diff keys.
  - **Reuse** (transitive dependency).
- **py-tree-sitter**:
  - https://github.com/tree-sitter/py-tree-sitter. MIT. **0.27.0 (2026-11-23)**, Python >=3.11.
  - 40 wheels, including win_amd64 and win_arm64.
- **Per-language grammar wheels** (all MIT, all with win_amd64 wheels):
  | Grammar | Version | Date |
  |---|---|---|
  | `tree-sitter-python` | 0.25.0 | 2025-09 |
  | `-javascript` | 0.25.0 | |
  | `-typescript` | 0.23.2 | 2024-11 |
  | `-rust` | 0.24.2 | 2026-03 |
  | `-c` | 0.24.2 | |
  | `-cpp` | 0.23.4 | |
  | `-go` | 0.25.0 | |
  | `-bash` | 0.25.1 | |
  | `tree-sitter-sql` (DerekStride) | 0.3.13 | 2026-11 |

  This covers every F05 language. **Reuse as an optional extra** for syntax-aware matching (stable node identities), keeping
  Pygments for colours.
- **tree-sitter-language-pack** (now `xberg-io/tree-sitter-language-pack`, MIT, 1.28.0 2026-11-26):
  - Since its 2026-03 Rust rewrite, native packages **ship no grammars and download a per-platform parser bundle from GitHub on
    first use**, then `dlopen` them (ADR
    [0001](https://github.com/xberg-io/tree-sitter-language-pack/blob/main/adrs/0001-native-packages-download-parser-bundles-at-runtime.md)).
    The wheel is about 2.2 MB.
  - This conflicts with offline, deterministic, secure rendering. **Avoid**.
- **tree-sitter-languages** (grantjenks): last release 1.10.2, 2024-02. Incompatible with modern tree-sitter (unverified). **Avoid**.

### Diff
- **difflib** (stdlib): `SequenceMatcher` uses Ratcliff/Obershelp, not Myers. `autojunk` makes it misbehave on more than 200
  lines with repeated tokens. Fine as a fallback.
  `cydifflib` (MIT, rapidfuzz org, 1.2.0) is a faster drop-in.
- **patiencediff** (breezy-team): **GPL-2.0-or-later**, 1.0.2 (2026-10-20), C extension with Windows wheels. **Avoid** (copyleft).
- **Recommendation**: implement patience (unique-line anchors) or histogram diff plus Myers fallback in-house. It is about
  150 lines and well documented. Then pair the remaining lines with `rapidfuzz` (MIT, 3.14.6, Windows wheels) similarity, and do
  intra-line char/token diff with `diff-match-patch` (Apache-2.0, pure Python, 20241021) or our own token-level Myers.
- `myers` (MIT, 2020) and `patience` (2014, license UNKNOWN) on PyPI are stale. Avoid.

---

## 4. Audio tooling (F04)

- **wavesurfer.js**:
  - https://github.com/katspaugh/wavesurfer.js. **BSD-3-Clause**, 10.5k stars. **8.1.1 (2026-11-24)** on npm. No runtime
    dependencies, TypeScript types included.
  - Plugins in core: regions, timeline, zoom, minimap, envelope (gain/fade), hover, spectrogram, record.
  - Supports **pre-decoded peaks** for large files and streaming (README recommends it).
  - **Reuse as an editor dependency.** Compute peaks in Python and serve them as JSON.
  - Avoid its `record` plugin (the spec says no microphone recording in core).
- **peaks.js** (BBC): LGPL-3.0, 4.0.0. Avoid.
- **audiowaveform** (BBC): GPL-3.0 CLI. Avoid; compute peaks with PyAV and numpy instead.
- **PyAV**:
  - https://github.com/PyAV-Org/PyAV. BSD-3-Clause. **19.0.2 needs Python >=3.12**; 18.1.1 (2026-11-21) supports 3.11.
  - Wheels bundle FFmpeg for Windows, macOS and Linux. The FFmpeg build license (LGPL vs GPL) is unverified.
  - **Already a manim dependency (`av>=15.0`)**, and manim 0.30 mixes audio with PyAV.
  - **Reuse** for decode (WAV/MP3/AAC/...), resampling, peak extraction, exact sample-accurate durations (better than mutagen's
    MP3 estimate) and mixdown checks. Adds nothing to the install.
- **python-soundfile**: BSD-3-Clause, 0.14.0 (2026-06-06). Wheels bundle libsndfile (MP3 since 1.1). Redundant with PyAV.
  **Not needed.**

---

## 5. Decision-relevant notes for ADRs

1. **Manim 0.30 already ships a timeline manifest.** `Manager.evaluate(capture_timeline=True)` and `--timeline-output` give
   play, wait, section, caption and sound entries with start/end, run_time, animation types and `source.line`, plus a source sha256.
   It is deterministic JSON, marked experimental. F02 should adapt to this, not duplicate it. It needs a shim for 0.22, which has no
   such API.
2. Every editor or presenter project that hooks renderer internals (manim-voiceover, manim-slides, Manimble) **breaks or is
   unverified on 0.30**. manim-stage must isolate Manim-version-specific hooks behind a compat layer with CI on both 0.22.x and 0.30.x.
3. manim-voiceover is the only maintained narration tool and is endorsed by Manim's docs (`guides/add_voiceovers.rst`).
   - Its gaps match spec F03/F04 directly: manual bookmark times (#113), pre-recorded tracks (#100), offset/gain (PR #143).
   - Contributing upstream is cheaper than wrapping around it.
4. No reusable browser editor exists for ManimCE. manim_editor is dead; Manimble, Manim-Motion and manimate are apps with their own
   models. Build the editor and borrow Manimble's JSON-lines runner protocol and AST code-action approach.
5. No ManimCE code-diff or signals plugin exists. F05 and F06 are genuinely missing from the ecosystem.
6. Licences to keep out: GPL (patiencediff, manim-presentation, audiowaveform), LGPL (peaks.js), and no-licence repos
   (MathItYT/manim-studio, Manim-Motion).
7. **Package name**: do not publish as `manim-studio` or `manim_studio` (taken on PyPI, including the plugin entry-point name).
   `manim-stage` is free.
