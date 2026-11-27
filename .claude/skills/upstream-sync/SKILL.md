---
name: upstream-sync
description: Review and bring in new changes from the upstream projects (ManimCE dependency, Motion Canvas reference) pinned in upstreams.json. Use when asked to sync, update from upstream, check what's new in Manim or Motion Canvas, bump the Manim version, or before starting a new milestone.
---

# Upstream sync

Follow `docs/upstream-sync.md` exactly. Summary:

1. `git status` must be clean. Create branch `upstream/<name>-<new-ref>` (one upstream per branch/PR).
2. Run `python scripts/upstream_sync.py status`. If nothing touches watched paths and there are no new tags, report that and stop.
3. For the chosen upstream:
   - `python scripts/upstream_sync.py log <name>` and `diff <name> --stat`.
   - Read the upstream changelog / release notes for new tags (`gh release view -R <owner/repo> <tag>`).
   - Read relevant diffs: `python scripts/upstream_sync.py diff <name>` or open files under `.upstream/<name>` after `checkout <name> <ref>`.
   - Pick the target ref:
     - `manim`: latest **stable** release. Exception until 0.30.0 final (ADR-0003): a reviewed upstream `main` commit, bumped with `--label main@<shortsha>`.
     - `motion-canvas`: latest tag or a reviewed `main` commit.
4. Classify every relevant change as **Adopt / Adapt / Inspire / Ignore** (definitions in the doc).
5. Re-pin: `python scripts/upstream_sync.py bump <name> <ref> [--label ...]`. For `manim` this also rewrites the pinned commit in `pyproject.toml`.
6. Apply:
   - `manim`: `uv lock`, fix adapters in `src/manim_stage/_compat.py`, run `uv run pytest` (including golden-frame tests). If tests stay red, report the failures verbatim and revert the pin (`git checkout upstreams.json pyproject.toml uv.lock`); don't commit a red pin.
   - `motion-canvas`: create design notes/issues for Inspire items. Never copy code or assets.
   - Update `docs/capability-audit.md`, ADRs and `docs/backlog.md` where status changed.
7. Add a sync-log entry at the top of the log in `docs/upstream-sync.md`.
8. Commit, then ask the user before pushing / opening the PR (unless they already said to). If the weekly `upstream-sync` issue exists, reference it in the PR.

Report to the user: old → new pin, Adopt/Adapt/Inspire items, test results, anything needing their decision.
