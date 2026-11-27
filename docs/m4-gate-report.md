# M4 gate report: ecosystem and polish

- **Date:** 2026-11-27
- **Spec gate (§11 M4):** "three third-party-style examples, cross-platform release packaging, compatibility test suite."
- **Verdict: PASSED.** Release 0.1.0 is ready to tag.

## Gate evidence

| Requirement | Evidence |
|---|---|
| Three third-party-style examples | `examples/third_party/`: BFS (trace, `Graph` + `tree_layout`, `label_edges`, `Array` queue, cues), damped pendulum (`Signal`/`computed`/`bind`, `demo.param`, theme), HTTP request (`SequenceDiagram` + `AnimatedCode`). Public API only. `tests/test_third_party_examples.py` renders each and checks its cues, chapters and theme. |
| Cross-platform release packaging | CI `package` job: builds the wheel, checks its contents, installs it into a clean venv with the pinned Manim and `[studio]`, and runs the CLI and an editor import on **Windows, Linux and macOS**. `.github/workflows/release.yml`: on a `v*` tag it does the same, then attaches the wheel and sdist to a GitHub Release. Process in `docs/release.md`. |
| Compatibility test suite | `tests/test_compat_suite.py`: ten unmodified Manim scenes, one per feature family (geometry and boolean ops, typography, graphing, updaters, composition, images, sections, moving camera, zoomed, 3D). Each preview is pixel-identical to `manim render`, and `StageMixin` opt-in changes no pixels. Plus `test_parity.py`, `test_regression.py` (golden frames), `test_determinism.py`. Summary: `docs/kb/reference/compatibility.md`. CI matrix: 3 OS × Python 3.11–3.13. |

## M4 scope (spec §11: "editor plugin SDK, performance optimizations, advanced educational helpers, comprehensive docs and migration guides")

| Backlog | Delivered | KB |
|---|---|---|
| 4.1 | Studio plugin SDK v1 (entry points, API-version handshake, lanes/panels/inspector rows/commands/exporters, failure isolation); sample plugin passes the F11 acceptance test | [plugins](kb/manim-stage/plugins.md) |
| 4.2 | `manim_stage.edu`: `Array`, `LinkedList`, `Tree`, `CallStack`, `SequenceDiagram`, `tree_layout`, `label_edges`, traces | [edu](kb/manim-stage/edu.md) |
| 4.3 | Demo parameters (editor-time) vs linear export; static web player with chapters and captions | [demo](kb/manim-stage/demo-params.md), [web](kb/manim-stage/web-player.md) |
| 4.4 | Performance pass (−36% cold 1080p30 with one worker); migration guide; examples; packaging; compatibility suite | [benchmarks](benchmarks.md), [migration](migration-guide.md) |
| MF.1/4 | Introspected catalog of every Manim feature, Library tab | [library](kb/manim-stage/library.md) |
| MF.6/7 | `manim.cfg` Config tab; Sections tab | [config](kb/manim-stage/config.md), [sections](kb/manim-stage/sections.md) |
| MF.8 | Camera-aware preview | [camera](kb/manim-stage/camera.md) |
| MF.10 | Text and LaTeX helpers | [text-latex](kb/manim-stage/text-latex.md) |

## Spec §13, definition of done for a first release

| Item | Status |
|---|---|
| Open an existing Manim lesson | `manim-stage studio file.py`, with no changes to the file |
| View and scrub a synchronized timeline | Timeline, Event panel, frame cache (seek ≤ 27 ms p95 at 1080p) |
| Animate source-code changes cleanly | `AnimatedCode.animate_to` (patience diff) |
| Align narration with named, draggable cues | `self.cue`, drag on the timeline, `cues.json` |
| Render the same lesson from the headless CLI | `manim render` / `manim-stage compose`; exports deterministic |
| Keep current Manim scene and renderer compatibility | Compatibility suite and golden frames. The preview is always Cairo, and the renderer badge says so. |

## Issues found and fixed during M4

1. **`SequenceDiagram`** placed new messages at their pre-transform position after `scale`/`shift`. Rows are now computed from the current geometry.
2. **The frame cache on Windows:** concurrent `put`/`trim` could raise `PermissionError`. Replaces are now retried, and trim skips frames that are being replaced.
3. **Demo override file:** an mtime cache missed rewrites within the timestamp resolution, so the file is now read on every call.
4. **Renderer badge race:** the timeline could arrive before the scene list. The badge now also updates when the list arrives.
5. **Wide panels** (Text, Sections, Library status line) could squeeze the viewport. These panels now scroll or wrap.

## Known limitations carried forward

- **PyPI:** not published until Manim 0.30 is on PyPI (`docs/release.md`).
- **LaTeX** isn't installed in CI. The `MathTex` preview path in the Text tab runs only where LaTeX exists.
- **The OpenGL renderer** isn't used for previews; exports can use it.
- **No warm runner pool.** Each revision spawns a child, about 1.2 s of `import manim`.
- **Web player:** composed multi-scene sequences have no chapter source yet.

## Next

- Tag `v0.1.0` to publish the GitHub Release (maintainer action; see `docs/release.md`).
- After Manim 0.30 ships: move the dependency to PyPI and publish.
