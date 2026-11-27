# Upstream sync process

manim-stage depends on two upstream projects. Neither is merged into this repo; instead each is **pinned to a reviewed commit** in [`upstreams.json`](../upstreams.json), and new upstream changes are reviewed and adopted deliberately.

| Upstream | Role | What "bringing in changes" means |
|---|---|---|
| `manim` | dependency | Raise the supported Manim version, adapt our adapters to API changes, drop our code where upstream now does the job natively. |
| `motion-canvas` | reference | Read new features/behavior in docs and source, then decide whether to design an equivalent in Python. **Never copy code or assets.** |

## Tooling

`scripts/upstream_sync.py` (stdlib only) keeps blobless clones in `.upstream/<name>` (gitignored).

```bash
python scripts/upstream_sync.py status               # new tags + watched-path commits since each pin
python scripts/upstream_sync.py status manim --json  # machine-readable
python scripts/upstream_sync.py log manim            # commits since pin touching watched paths
python scripts/upstream_sync.py log manim --all-paths
python scripts/upstream_sync.py diff manim --stat    # watched-path diff since pin
python scripts/upstream_sync.py diff manim --to v0.30.0
python scripts/upstream_sync.py checkout manim       # put the pinned source in .upstream/manim for reading
python scripts/upstream_sync.py checkout manim main  # or any ref
python scripts/upstream_sync.py bump manim v0.30.0   # re-pin after review
```

`watch_paths` in `upstreams.json` lists the upstream areas that matter to us (scene lifecycle, renderers, `Code`, audio, config, CLI, plugins; Motion Canvas docs, flow/time events, signals, media, code, UI). Edit it as the project's surface grows.

## Triggers

- **Weekly CI** (`.github/workflows/upstream-watch.yml`) runs `status` and keeps one open issue labelled `upstream-sync` up to date with the report.
- **On demand:** ask Claude to "run the upstream sync" (project skill `/upstream-sync`), or run the script yourself.
- **Before starting a milestone** (spec §11), sync first so design work targets current upstream.

## Review procedure (one upstream at a time, one PR per sync)

1. **Branch:** `git switch -c upstream/<name>-<new-ref>`.
2. **Survey:** `status`, then `log <name>` and `diff <name> --stat`. Read release notes / changelog for any new tags.
3. **Classify each relevant upstream change** in the sync log (below):
   - **Adopt** – upstream now provides something we planned or built → use it, delete our duplicate.
   - **Adapt** – upstream API/behavior changed under our code → fix adapters, add regression tests.
   - **Inspire** (Motion Canvas only) – new behavior worth a Python equivalent → open a design note/issue with acceptance criteria. Describe behavior in our own words.
   - **Ignore** – irrelevant; one line saying why.
4. **Update artifacts:** `docs/capability-audit.md` rows whose Existing/Partial/Missing status changed, ADRs if a decision is affected, the backlog.
5. **Manim only – verify:** bump the version constraint in `pyproject.toml`, run our full test suite and the golden-frame regression tests against the new Manim. Prereleases (`a`, `b`, `rc`) may be tested on a branch but are not pinned on `main`.
6. **Re-pin:** `python scripts/upstream_sync.py bump <name> <ref>`.
7. **Record:** add an entry to the sync log below, open a PR containing pin + log + code changes. Never re-pin without a log entry.

## Rules

- No vendoring of upstream source; no `git subtree`/`submodule` merges of upstream history into this repo.
- Code adapted from Manim (MIT) keeps its copyright header and is listed in `NOTICE` with source path and commit.
- Motion Canvas is studied for behavior only (spec §2.9). Do not paste its code, even "temporarily".
- Contributing a narrow fix upstream to Manim is preferred over monkeypatching (spec §12.5). Track such PRs in the sync log.

## Sync log

Newest first. Each entry: date, upstream, old pin → new pin, summary of Adopt/Adapt/Inspire items with links, and upstream PRs we opened.

### 2026-11-26 — initial pins
- `manim`: pinned **v0.22.1** (`16ea443`), latest stable release.
- `motion-canvas`: pinned **v3.17.2** (`e735a99`), latest release.
- Noted for M0 audit — unreleased Manim `main` (tagged `v0.30.0a1`) already contains work overlapping this spec; re-check before designing F01/F02/F04:
  - Timeline capture and JSON export (ManimCommunity/manim#5006)
  - Scene evaluation without rendering; draw requested frames (#5005)
  - Play calls through one loop with listeners (#5004)
  - PyAV sound mixer placing audio in movie time (#5059)
  - Saved sections embedded as MP4 chapters (#5125)
- Noted — Motion Canvas docs moved to https://motion-canvas.io (spec §14 links are stale); project effectively dormant since Feb 2025.
- Noted — Motion Canvas `main` has unreleased sound waveforms (#1158), programmable sounds (#1082), audio offset editing (#1166).
