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
  - The revision hashes scene file + scene name + settings + Manim build (version + git commit). Imported modules and assets are not hashed yet.
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
  - Optional extras: `[voiceover]`, `[treesitter]`, `[dev]`.
  - Editor: React + TypeScript, pinned lockfile, prebuilt assets shipped inside the wheel so end users need no Node.

## ADR-0010 — Preview service: aiohttp, one WebSocket, token + origin checks

- **Status:** Accepted (2026-11-27)
- **Context:** spec §2.8, §4, §8 `PreviewMessage`. Needs HTTP (editor assets, frame PNGs), a WebSocket (commands/events), Windows/Linux/macOS, few dependencies.
- **Decision:**
  - `aiohttp` (one package: HTTP server, WebSocket, static files; no ASGI server). Shipped in the optional `studio` extra so headless users (`cue`, `AnimatedCode`, `bake`) don't pull it.
  - Binds `127.0.0.1` only; refuses other hosts unless `--host` is given with an explicit `--allow-remote` (documented as unsafe).
  - **Host check** on every request (`127.0.0.1:<port>` / `localhost:<port>`) against DNS rebinding.
  - **Session token:** random 32-byte token printed in the editor URL; required on the WebSocket handshake (`?token=`) and as `X-Stage-Token` on every non-GET request. **Origin check** on the WebSocket and state-changing requests: must equal the server's own origin.
  - Frames are served by `GET /frames/<revision>/<index>.png` (revision regex-validated, no path joins with user input), cacheable forever (content-addressed).
  - Protocol `manim_stage.preview` v1, JSON over one WebSocket; every message has `v`, `type`; requests carry `id`. Schema in `docs/schemas/preview-message.schema.json`.
  - Revisions are monotonically increasing integers per scene. Messages tagged with an older revision are dropped by server and client. A new revision cancels (kills) the previous runner.
  - **Dependency-aware revision:** the runner reports the files of user modules it imported (outside site-packages/stdlib) plus assets passed to `add_sound`/`ImageMobject`/`SVGMobject`; the service watches all of them and the cache key includes their content hashes.

## ADR-0011 — Manim feature coverage via an introspected catalog

- **Status:** Accepted (2026-11-27)
- **Context:** owner requirement: the editor surfaces all Manim features intelligently, including features added by future upstream syncs. Hand-maintained lists go stale.
- **Decision:**
  - `manim_stage.catalog` introspects the installed Manim: public `Mobject`/`Animation` subclasses, `rate_functions`, colour constants, `Scene` subclasses (camera types), `ManimConfig` options, installed plugins. Each entry: name, module, category (from Manim's module layout: `animation.creation`, `mobject.geometry`, …), signature, first doc paragraph, renderer support, KB link.
  - Categories are derived from module paths, with a small override table for curated grouping. A test asserts every name in `manim.__all__` maps to a category or an explicit ignore list, so a sync that adds a public feature fails until it is classified (and the KB updated).
  - The editor consumes the catalog (library panel, timeline colouring, inspector, config panel). Nothing in the editor hardcodes Manim class lists.

## ADR-0012 — Editor stack

- **Status:** Accepted (2026-11-27)
- **Decision:**
  - `editor/`: React 18 + TypeScript + Vite, npm with committed `package-lock.json`. No UI component framework (small bundle, own accessible components). Vitest for unit tests.
  - Build output goes to `src/manim_stage/studio/static/` (gitignored); CI builds it before packaging; wheels include it (hatch `artifacts`).
  - The server serves a plain fallback page when the build is missing (dev checkouts without Node).
  - No Motion Canvas UI code or assets; layout ideas described in our own words only.
