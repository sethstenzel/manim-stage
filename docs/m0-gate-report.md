# M0 gate report

- **Date:** 2026-11-26
- **Spec gate (§11 M0):** "documented, executable architecture proof and baseline tests. Stop and propose revised scope if deterministic replay cannot be made safe."
- **Verdict: GO for M1**, on the Cairo renderer, with the limits below.

## What M0 delivered

| Item | Evidence |
|---|---|
| Pinned Manim (`main@8c258a0`, ADR-0003 accepted) and Motion Canvas reference (`v3.17.2`) | `upstreams.json`, `docs/upstream-sync.md` |
| Capability audit: every requirement rated at Manim 0.22.1 and main | `docs/capability-audit.md`, `docs/audit/*` |
| ADRs 0001–0009 | `docs/architecture-decisions.md` |
| Runner records event metadata from **unmodified** scenes without changing rendering | `manim_stage.capture`/`runner`; `tests/test_capture.py`, `tests/test_runner.py` |
| Seek by cached frame | `manim_stage.framecache`; `tests/test_parity.py` |
| Rendering unchanged with manim-stage installed; golden frames on Win/Linux/macOS | `tests/test_regression.py` |
| Versioned data contracts and time model | `docs/schemas/`; `tests/test_schemas.py` |
| Deterministic replay: seeds enforced, hazards reported | `manim_stage.determinism`; `tests/test_determinism.py` |
| Local knowledge base, examples tested | `docs/kb/`; `tests/test_kb_examples.py` |
| CI: Windows, Linux, macOS × Python 3.11–3.13; 79 tests | `.github/workflows/ci.yml` |

## Measurements (spec §9)

Reference machine: Windows 11, 16 logical CPUs. Full table in `docs/benchmarks.md`.

| Target | Result | Status |
|---|---|---|
| First cached preview, 10 s 1080p ≤ 10 s | 8.0 s with 4 workers (17.9 s with 1). The timeline is shown after 1–2.5 s. | Met (needs ≥ 4 workers) |
| Scrub median ≤ 100 ms (720p) | 6.4 ms server-side | Met |
| Bounded cache, LRU | byte budget, protects current revision, concurrent-safe | Met |
| Cue sync ≤ 1 frame | Time model is frame-exact and sounds are kept to the sample. Not yet testable, because cues are M2. | Pending (M2) |
| Preview vs export agreement | **Pixel-identical** on all three OSes | Met |

## Is deterministic replay safe?

**Yes, for the scene classes below.** The runner replays a scene several times: once for the timeline, once per drawing worker, and again after every edit.

- **Clock:** Manim's 0.30 clock is frame-quantized and steps every frame identically, including `dt`-driven updaters, even when nothing is drawn.
- **Seed:** the runner always sets a seed (default 0, part of the revision). Manim seeds `random` and `numpy.random` from it in `Scene.__init__`.
- **Tests:** a scene full of `random`/`numpy.random` calls gives identical frames with 1 and 3 workers. Sharded drawing (every replay draws different frames) matches single-process drawing pixel for pixel.

### Supported vs unsupported scene classes

| Scene uses… | Status | What happens |
|---|---|---|
| Standard Manim animations, groups, updaters, `ValueTracker`, sections, sounds | **Supported** | Exact |
| `random` / `numpy.random` inside `construct` | **Supported** | Seeded; exact |
| `Text` (Pango) | **Supported** | Exact on one machine. Glyphs differ across OSes, as they do for Manim itself. |
| Wall-clock reads (`time.time`, `datetime.now`, …) | Unsupported | Warning in timeline (`file:line`). Replays may differ. |
| OS entropy (`os.urandom`, `uuid4`, `secrets`, `default_rng()` without a seed) | Unsupported | Warning. Replays may differ. |
| `random`/`numpy.random` at module level (runs before Manim seeds) | Unsupported | Warning |
| Reading external mutable state during `construct` (files, network) | Unsupported | Not detected. Document. |
| Imported helper modules / assets that change | Partial | The cache revision hashes only the scene file. Edits elsewhere can serve stale frames until dependency tracking lands (M1). |
| OpenGL renderer | **Not supported in M1** | Untested; `Manager.evaluate` rejects GPU meshes (audit). The UI must label it unsupported. |
| Interactive scenes (`interactive_embed`, mouse/key callbacks) | Unsupported | Wall-clock driven, not replayable |
| Custom `Animation` with non-standard `interpolate` timing | Partial | Outer span exact; nested spans may be approximate |
| LaTeX-heavy scenes | Unmeasured | Correctness unaffected; preview latency unknown (no LaTeX in CI) |
| Live scrubbing without a frame cache (seek P3) | Not feasible | No scene snapshot/restore in Manim |

## Risks carried into M1

1. **Manim main is mid-refactor** (open PRs #5173–#5178). All private access is in `_compat.py`, so breakage stays in one file. The weekly upstream watch flags changes.
2. **Imported modules aren't part of the cache revision.** Dependency tracking (import hook recording loaded module files) is the first M1 runner task.
3. **Per-revision cost is a full replay.** Fine for lesson-length scenes (0.4 s timeline pass for 10 s). Long scenes need a measurement before promising latency.
4. **The browser-side protocol, security and editor are all new** (M1).

## Upstream contributions identified

These are listed in `docs/backlog.md`:
- a public run-loop listener API;
- `evaluate()` early stop;
- timeline frame indices and nested children;
- section start times;
- a concurrency-safe `media_dir` text cache;
- manim-voiceover 0.30 compatibility and manual bookmark times.

## Recommended next steps

1. **Owner:** accept ADRs 0004–0009 (runner model, event IDs, cue API, frame cache, AnimatedCode, packaging), or ask for changes. M0 implemented and tested 0004, 0005 and 0007.
2. **First M1 PR:** backlog 1.1, the preview service skeleton:
   - 127.0.0.1 only, host/origin checks, CSRF token;
   - versioned WebSocket protocol wrapping the runner;
   - revision discard and cancel/restart;
   - dependency-aware revisions.
