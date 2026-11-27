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
   - Pick the target ref: latest **stable** release for `manim` (no a/b/rc on main), latest tag or reviewed `main` commit for `motion-canvas`.
4. Classify every relevant change as **Adopt / Adapt / Inspire / Ignore** (definitions in the doc).
5. Apply:
   - `manim`: update `pyproject.toml` constraint, fix adapters, run the full test suite + golden-frame tests. Report failures verbatim; do not re-pin on red tests.
   - `motion-canvas`: create design notes/issues for Inspire items. Never copy code or assets.
   - Update `docs/capability-audit.md`, ADRs and `docs/backlog.md` where status changed.
6. `python scripts/upstream_sync.py bump <name> <ref>`.
7. Add a sync-log entry at the top of the log in `docs/upstream-sync.md`.
8. Commit, then ask the user before pushing / opening the PR (unless they already said to). If the weekly `upstream-sync` issue exists, reference it in the PR.

Report to the user: old → new pin, Adopt/Adapt/Inspire items, test results, anything needing their decision.
