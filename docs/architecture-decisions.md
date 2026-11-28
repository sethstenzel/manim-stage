# Architecture decisions

Record of decisions required by the spec (§3, §12.9). Status: Proposed → Accepted / Superseded.

## ADR-0001 — Standalone repository, not a GitHub fork

- **Status:** Accepted (2026-11-26)
- **Context:** The project must track two upstreams: ManimCE (engine) and Motion Canvas (UX reference). Spec §2.3 says "No hard fork by default ... a standalone Python package ... A fork is permissible only after a documented architecture decision." Spec §2.9 forbids copying Motion Canvas source.
- **Decision:** manim-stage is a standalone repo.
  - Manim is a pip dependency with a version constraint, pinned for review in `upstreams.json`.
  - Motion Canvas is a read-only reference, pinned in `upstreams.json` so audits cite exact commits.
  - Upstream changes are brought in by the review process in [`upstream-sync.md`](upstream-sync.md), not by merging upstream history.
- **Why not a fork of Manim:** a fork would make us maintain the whole engine, diverge from ManimCE on every release, and violate spec §2.1/§2.10 (Manim stays source of truth; no regressions). A GitHub fork can only track one parent, so it would not help with Motion Canvas either.
- **Why not a fork of Motion Canvas:** it is TypeScript and the spec forbids copying its code or making TypeScript the authoring API.
- **Consequences:**
  - Changes Manim must make for us go upstream as narrow PRs (spec §12.5); short-lived compatibility adapters are allowed with tests.
  - If a future need truly requires patching Manim internals, write a superseding ADR first. A temporary fork of Manim would then live in a *separate* repo, used as a pinned dependency, never merged here.
  - `.upstream/` checkouts are local, gitignored, and disposable.

## ADR-0002 — Project name `manim-stage`

- **Status:** Accepted (2026-11-26); revisit after M0 if needed.
- **Context:** The spec's working name `manim-studio` is already used on PyPI and GitHub (MathItYT/manim-studio). Spec §1 says to rename after inspection.
- **Decision:** Repo `manim-stage`, PyPI distribution `manim-stage` (free at time of writing), import package `manim_stage`. Fits the cue/timeline vocabulary. The editor can still be called "Studio" inside the product (`manim-stage studio ...`).
- **Note:** Where `spec.md` says `manim_studio` / `manim-studio`, read `manim_stage` / `manim-stage`. The spec file is kept verbatim.

## ADR-0003 — Manim baseline: target the 0.30 line, not 0.22

- **Status:** Accepted by owner (2026-11-26)
- **Context:** See [capability audit](capability-audit.md).
  - STABLE 0.22.1 lacks every timeline primitive F01/F02/F04 need. Its float clock depends on cache state and renderer.
  - MAIN (0.30 line, prerelease `v0.30.0a1`) has a deterministic frame clock, timeline capture, `Manager.evaluate` frame drawing and a sample-accurate audio mixer. They are experimental or private, with a large refactor stack still open.
- **Options:**
  1. Target 0.22, reimplement tracing/clock ourselves via monkeypatching. Large, fragile, and obsolete when 0.30 ships.
  2. **Target 0.30 (MAIN pinned by SHA until 0.30.0 final), all version-specific code in `manim_stage._compat`.**
  3. Wait for 0.30.0 final before starting M1.
- **Recommendation:** Option 2.
  - Develop against a pinned MAIN SHA.
  - Declare `manim>=0.30.0` once released; until then, document install from the pinned commit.
  - Re-pin weekly via the upstream-sync process.
  - No 0.22 support unless a user need appears (manim-stage has no users yet).
- **Consequences:**
  - The M0 proof runs on MAIN.
  - manim-voiceover needs an upstream fix for 0.30 before F04 voiceover integration.
  - `upstreams.json` will pin `manim` to a MAIN SHA (allowed: the "stable only on main" rule in upstream-sync.md is relaxed for this pre-release period and must be restored at 0.30.0).

## ADR-0004 — Runner: fresh child process per revision, JSON-lines protocol

- **Status:** Accepted (owner, 2026-11-27)
- **Context:**
  - Manim keeps process-global state: `set_default` class mutation, an SVG cache keyed without file content, a `ConvertToOpenGL` metaclass bound at class creation, and eagerly loaded plugins.
  - The OpenGL rerun path doesn't re-import user modules.
  - Scenes can't be safely copied (spec §4 replay concerns).
- **Decision:**
  - The preview service (long-lived, binds 127.0.0.1) spawns a **fresh Python child process per scene revision**. No `importlib.reload`.
  - The child talks to the service over stdio using **versioned JSON-lines messages** (idea borrowed from Manimble; our own schema = spec §8 `PreviewMessage`).
  - Frames are written to a bounded on-disk cache and referenced by path/ID, not streamed inline.
  - The service supports cancel (kill child) and restart; outdated revisions are discarded by revision number.
- **Consequences:** Python start-up and `import manim` cost per revision (MAIN's lazy imports, #5124, help). Measure in the M0 proof.

## ADR-0005 — Scene events: ingest Manim's timeline, own the schema and IDs

- **Status:** Accepted (owner, 2026-11-27)
- **Decision:**
  - Our public contract is `SceneEvent` (spec §8), versioned by us.
  - On MAIN it is populated from `Manager.evaluate(capture_timeline=True)` plus one private-listener shim (in `_compat`) for nested `AnimationGroup`/`LaggedStart` child ranges.
  - Times are stored as **integer frame indices** at the scene's frame rate, plus derived seconds. Ranges are half-open `[start, end)`.
  - **Event IDs:**
    - `"{scene}:{kind}:{source_path}:{line}#{occurrence}"`, where occurrence counts repeats of the same call site in execution order (loops).
    - An optional explicit `id=` on Studio APIs overrides it.
    - Collisions are resolved deterministically by occurrence index.
    - IDs that disappear after an edit are reported as orphans, never silently dropped.
  - The user call site is captured by Studio: the first stack frame outside `manim` and `manim_stage`. Manim's recorded `source` is not used when a Studio wrapper is involved.

## ADR-0006 — Cue API and semantics

- **Status:** Accepted (owner, 2026-11-27)
- **Context:** `Scene.wait_until(stop_condition, max_time)` already exists, so the spec's `self.wait_until("name")` would overload it. Motion Canvas stores absolute scene-relative cue times. Its weak edges: silent drops, negative waits clamped only in the editor, non-atomic writes.
- **Decision:**
  - API: `self.cue("explain_swap", at=None, after=None, description=None)` on `StageScene`. It waits until the cue time; with no override it uses `at=` (absolute seconds from scene start) or `after=` (duration from the call), and with neither it waits 0.
  - Sidecar `.manim-stage/cues.json` stores per-scene **absolute frame-indexed** overrides. Absolute is the default, because narration-locked cues survive code edits. Ripple is an editor gesture that rewrites downstream absolute targets; it is not a runtime mode.
  - **One resolver** shared by preview and headless render.
  - **Validation errors (fail render):** a target before the cue's call time (negative wait), duplicate names in one scene, non-monotonic order.
  - **Validation warnings:** orphaned overrides (cue removed or renamed) are kept as tombstones until dismissed.
  - Writes are atomic (temp + rename) with a backup on schema migration.
  - `manim-stage bake` writes resolved times so CLI renders without Studio are reproducible. The sidecar is also read by plain `manim render` when the scene subclasses `StageScene`.

## ADR-0007 — Seek: own frame store fed by `Manager.evaluate`

- **Status:** Accepted (owner, 2026-11-27)
- **Decision:**
  - **P1:** the runner evaluates the scene once with `on_frame`, writing preview-resolution frames into a content-addressed, LRU-bounded disk cache keyed by (scene revision, frame index, resolution). The editor scrubs cached frames.
  - Partial movie files are not used for preview.
  - **P2:** re-evaluate from t=0 in a fresh child on edits, with per-scene invalidation.
  - **P3:** deferred; not feasible with current Manim (no state snapshot/restore).
  - Scenes using wall-clock time, unseeded randomness or `dt`-dependent updaters get a "replay may differ" warning.
- **Update 2026-11-26 (backlog 0.6, see `docs/benchmarks.md`):**
  - Implemented as `manim_stage.framecache.FrameCache` plus `runner --cache-dir`.
  - The timeline is sent before frames.
  - Frames already cached for the revision are not redrawn.
  - The revision hashes scene file + scene name + settings + Manim build (version + git commit). Since backlog 1.1 it also hashes every local module and asset the scene opened (ADR-0010).
  - **Parallel drawing:** `run_capture(workers=N)` runs N children. Each replays the scene and draws every N-th frame. Needed to meet the 10 s/1080p target (8.0 s with 4 workers vs 17.9 s with 1).
  - Concurrent children must not share Manim's `media_dir` (unlocked Text/SVG caches), so each shard gets its own.
  - Cached frames are pixel-identical to the CLI `png-sequence` render; tested.

## ADR-0008 — Code animation engine

- **Status:** Accepted (owner, 2026-11-27)
- **Decision:**
  - New `AnimatedCode` mobject (does not subclass `Code` internals; `manim.Code` untouched).
  - Tokens come from Pygments lexers and styles (keeping bold/italic).
  - One mobject per token with stable token IDs.
  - Explicit grid anchoring so unchanged lines keep position.
  - Bundled pinned monospace font.
  - Diff: in-house patience diff at line level, then token level, with Myers/`difflib` fallback.
  - Move detection and explicit override mappings (beyond MC).
  - Optional extras: `tree-sitter` per-language grammar wheels (MIT) for syntax-aware matching. **Excluded:** `patiencediff` (GPL), `tree-sitter-language-pack` (runtime downloads).

## ADR-0009 — Packaging and entry points

- **Status:** Accepted (owner, 2026-11-27)
- **Decision:**
  - Distribution `manim-stage`, import `manim_stage`, console script `manim-stage` (`manim-stage studio lesson.py Scene`, `manim-stage bake`, `manim-stage validate`). Manim's CLI has no subcommand plugin hook.
  - Editor-extension entry-point group `manim_stage.plugins` with a version handshake.
  - Optional extras: `[studio]`, `[voiceover]`, `[treesitter]`.
  - Editor: Python + PySide6 in the `studio` extra (ADR-0012 supersedes the React/TS plan).

## ADR-0010 — Studio core: in-process Python service, no network listener by default

- **Status:** Accepted (2026-11-27). Supersedes the first draft of this ADR (aiohttp WebSocket server), after the owner's direction that the editor is implemented in Python as one cohesive application.
- **Context:** spec §4 asks for a preview service between runner and editor, and §2.8 for 127.0.0.1 binding with CSRF/origin protection. With a Python editor in the same process, a network service adds attack surface for no benefit.
- **Decision:**
  - `manim_stage.studio.service.PreviewService`: a pure-Python, GUI-independent controller (threads + queues, no Qt imports). It owns runner child processes (ADR-0004), revisions, cancellation, file watching and the frame cache, and publishes typed `PreviewMessage` events (spec §8) to subscribers. Unit-tested headless.
  - The editor subscribes in-process. **No socket is opened by default**, so the §2.8 trust boundary is just "loading a scene executes local Python"; documented in the KB.
  - Revisions are monotonically increasing integers per scene. A new revision cancels (kills) the previous runner; messages tagged with an older revision are dropped.
  - **Dependency-aware revision:** the runner reports the user modules it imported (outside site-packages/stdlib) and assets Manim loaded (sounds, images, SVGs); the service watches all of them and the cache key includes their content hashes.
  - If a network transport is ever added (e.g. F12 web playback, remote control), it must bind 127.0.0.1, check Host/Origin and require a session token; it is a separate ADR.

## ADR-0011 — Manim feature coverage via an introspected catalog

- **Status:** Accepted (2026-11-27)
- **Context:** owner requirement: the editor surfaces all Manim features intelligently, including features added by future upstream syncs. Hand-maintained lists go stale.
- **Decision:**
  - `manim_stage.catalog` introspects the installed Manim: public `Mobject`/`Animation` subclasses, `rate_functions`, colour constants, `Scene` subclasses (camera types), `ManimConfig` options, installed plugins. Each entry: name, module, category (from Manim's module layout: `animation.creation`, `mobject.geometry`, …), signature, first doc paragraph, renderer support, KB link.
  - Categories are derived from module paths, with a small override table for curated grouping. A test asserts every name in `manim.__all__` maps to a category or an explicit ignore list, so a sync that adds a public feature fails until it is classified (and the KB updated).
  - The editor consumes the catalog (library panel, timeline colouring, inspector, config panel). Nothing in the editor hardcodes Manim class lists.

## ADR-0012 — Editor stack: Python + Qt (PySide6)

- **Status:** Accepted (2026-11-27). Supersedes the first draft (React/TypeScript). Owner direction: implement the best of Motion Canvas **in Python, including the editor**, as one cohesive application.
- **Decision:**
  - Desktop editor written in Python with **PySide6** (Qt for Python, LGPLv3, used as an unmodified dynamic dependency; noted in `NOTICE`). Cross-platform (Windows/Linux/macOS), no Node or browser required. Spec F01's "browser-based (preferred)" is a preference; Python-only wins on cohesion.
  - Shipped in the optional `studio` extra: `pip install manim-stage[studio]`. Headless features (cues, `AnimatedCode`, `bake`) don't need Qt.
  - Layering: `studio.service` (no Qt) ← `studio.models` (Qt models/adapters) ← `studio.widgets` (viewport, timeline, panels). Widgets never render scenes; they display runner frames (spec §4: the editor is not a second renderer).
  - Timeline and viewport are custom `QWidget`/`QPainter` widgets. Accessibility: accessible names on every control, full keyboard navigation, non-colour signals, honours system text scaling.
  - Tests: `pytest` with `QT_QPA_PLATFORM=offscreen` on all CI OSes; widget logic kept in plain-Python helpers where possible.
  - No Motion Canvas UI code or assets; layout ideas described in our own words only.

## ADR-0013 — Port Motion Canvas concepts into Manim's model

- **Status:** Accepted (2026-11-27). Owner direction: keep Manim's abstractions, terminology and methodology; port the best Motion Canvas concepts so they fit Manim, keeping those concepts available as APIs.
- **Decision:**
  - Manim's model is the foundation: `Scene`/`construct`, `Mobject` families, `Animation` + `play`/`wait`, `run_time`/`rate_func`/`lag_ratio`, `ValueTracker` + updaters, sections, `config`, renderer, camera. Nothing replaces these.
  - Each useful Motion Canvas concept is **ported as a real, documented Python API** in `manim_stage`, built on those Manim primitives, named in `snake_case` Python style, and interoperable with plain Manim:
    - time events / `waitUntil` → `self.cue("name", ...)`: a named, editable `wait` (ADR-0006);
    - signals / `createSignal` / computed → `Signal` (a `ValueTracker` subclass, so `.animate`, `get_value`, updaters still work) and `computed(...)` returning a derived read-only `Signal`; `effect(...)` registers an updater;
    - `all` / `sequence` / `chain` / `delay` / `loop` → `all_of`, `sequence`, `chain`, `delay`, `loop` helpers that return `AnimationGroup` / `LaggedStart` / `Succession` / `Wait`-based animations;
    - `tween(duration, fn)` → `tween(run_time, fn)` returning an `Animation` (driven by `rate_func`);
    - code ranges, `lines()`, `word()`, `findFirstRange` → `AnimatedCode` with `CodeRange`, `lines()`, `word()`, `find()`;
    - references / `makeRef` → ordinary Python attributes (no port needed; documented);
    - project variables `useScene().variables` → `stage.variables` read from the project sidecar, layered on `config`;
    - scene transitions (`slideTransition`, `fadeTransition`, `zoomInTransition`) → `slide_transition`, `fade_transition`, `zoom_transition`, built as Manim `Animation`s;
    - nodes / layout (flexbox) → Mobject families plus Manim's `arrange`/`next_to`; a flex-style `Layout` helper only if needed (M3).
  - The editor uses Manim's words in the UI (Mobject, Animation, Section, rate_func, …).
  - Every ported concept has a KB page with the MC concept it comes from, the Manim primitive it is built on, and a tested example. The mapping table lives in `docs/kb/reference/motion-canvas-equivalents.md`.

## ADR-0014 — HTML docs site built from the repository Markdown

- **Status:** Accepted (2026-11-27). Owner direction: the docs must be an HTML site, regenerated with every update, bug fix and release.
- **Decision:**
  - **Tool:** MkDocs with Material, configured in `mkdocs.yml`. It's Python, so it fits the stack, and it reads the existing Markdown unchanged.
  - **Source stays Markdown:** the files keep working on GitHub and in the offline KB.
  - **Hooks adapt the Markdown for the site** (`scripts/docs_hooks.py`):
    - the repo-root `PORTING.md`, `CHANGELOG.md` and `spec.md` become pages;
    - links to code and examples go to GitHub;
    - the `no-run` test marker is stripped;
    - the footer shows the version.
  - **Built and published automatically:**
    - every PR runs a strict build, so a broken link or anchor, or a page missing from `nav`, fails CI;
    - every push to `main` deploys to GitHub Pages;
    - every release attaches the built site as a zip, so each version's docs are kept.
- **Rationale:**
  - one source of truth;
  - broken docs are caught in review;
  - no extra steps for maintainers.
- **Known risk:** Material for MkDocs reaches end of life on 2027-05-05. Its successor, Zensical, reads `mkdocs.yml`; migrate before then. The hooks are small and would need porting.
