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
