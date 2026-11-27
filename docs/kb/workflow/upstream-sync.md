# Upstream sync

- **Status:** Available
- **Source:** `scripts/upstream_sync.py`, `upstreams.json` · **Process:** `docs/upstream-sync.md` · **Claude:** `/upstream-sync`

## What it is

manim-stage depends on Manim and studies Motion Canvas. Both are pinned to reviewed commits, and new upstream changes are brought in deliberately, one upstream per PR. A weekly GitHub Action keeps one issue labelled `upstream-sync` updated with what's new.

## Quick start

```bash
python scripts/upstream_sync.py status            # new tags + commits touching the paths we watch
python scripts/upstream_sync.py log manim         # those commits
python scripts/upstream_sync.py diff manim --stat
python scripts/upstream_sync.py checkout manim    # pinned source in .upstream/manim, for reading
python scripts/upstream_sync.py bump manim <ref> --label main@<sha>   # re-pin after review
```

For `manim`, `bump` also rewrites the pinned commit in `pyproject.toml`. Then run `uv lock` and `uv run pytest`.

## Every sync must

1. Classify each relevant change as Adopt / Adapt / Inspire / Ignore.
2. Fix adapters only in `src/manim_stage/_compat.py`. Never commit a pin with failing tests.
3. Update `docs/capability-audit.md`, the ADRs and the backlog where status changed.
4. **Update this knowledge base:** pages for new, changed or removed upstream features we use or mirror, plus an entry in [whats-new.md](../whats-new.md).
5. Add an entry to the sync log in `docs/upstream-sync.md`.

## Related

- `docs/upstream-sync.md` · ADR-0001 (why not a fork) · ADR-0003 (Manim 0.30 pin)
