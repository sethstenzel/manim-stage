# manim-stage — instructions for Claude

## What this is
- Optional Python layer + local editor that gives ManimCE Motion Canvas–class authoring. Full spec: `spec.md` (kept verbatim; read `manim_studio` as `manim_stage`, see ADR-0002).
- Manim = **dependency**, Motion Canvas = **behavior reference only**. Not a fork (ADR-0001 in `docs/architecture-decisions.md`).

## Hard rules (from spec §2, §12)
- Manim stays the engine and source of truth. Existing Manim scripts must render identically. New behavior is opt-in.
- Python is the authoring API **and** the editor language (PySide6, ADR-0012). The editor is a control/visualization layer, never a renderer.
- Manim terminology and concepts first (ADR-0013). Port Motion Canvas concepts as real Python APIs built on Manim primitives (e.g. `Signal` is a `ValueTracker`); every ported concept gets a KB page and a row in `docs/kb/reference/motion-canvas-equivalents.md`.
- Never copy Motion Canvas source or UI assets. Describe its behavior in your own words.
- Don't monkeypatch Manim internals without a documented, tested, short-lived adapter. Prefer narrow upstream PRs.
- Local server binds 127.0.0.1; CSRF/origin checks on state-changing endpoints.
- Work milestone by milestone (M0 → M4). Small, reviewable commits/PRs with tests and docs. Don't claim done for mockups or single-renderer features without labelling limits.
- Owner directive (2026-11-27): work autonomously through M1–M4; decide ADRs/scope yourself (record them as Accepted with rationale), merge green PRs and continue. Do not stop to ask for acceptance.

## Upstream changes
- Pins: `upstreams.json`. Process: `docs/upstream-sync.md`. Tool: `scripts/upstream_sync.py`.
- When asked to sync/update from upstream, or before starting a milestone, use the `/upstream-sync` skill.
- Read upstream source from `.upstream/<name>` (run `python scripts/upstream_sync.py checkout <name>` first). Cite upstream file paths with the pinned commit.
- Never re-pin without a sync-log entry in `docs/upstream-sync.md`.

## Key docs
- `docs/capability-audit.md` — Existing/Partial/Missing per requirement (spec §3)
- `docs/architecture-decisions.md` — ADRs
- `docs/backlog.md` — implementation backlog
- `PORTING.md` — running log of how Motion Canvas features are ported into Manim: decisions, implementations, processes. **Update it in every PR that ports, designs or changes such a feature.**
- `docs/kb/` — local knowledge base of every feature and its use. **Every feature PR and every upstream sync must update it** (pages + `whats-new.md`); KB examples are smoke-tested.

## Dev commands
- `uv sync` → venv with Manim pinned to the commit in `pyproject.toml` (`[tool.uv.sources]`)
- `uv run pytest` · `uv run ruff check .` · `uv run ruff format src tests scripts`
- All Manim-version-specific code goes in `src/manim_stage/_compat.py` (feature-detected, not version-checked).

## Environment notes
- Primary dev machine is Windows; keep scripts cross-platform (stdlib Python, no bash-only tooling).
