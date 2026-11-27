# manim-stage

Motion Canvas–class authoring for [Manim Community Edition](https://github.com/ManimCommunity/manim): a local Studio editor, seekable timeline, named timing cues for narration, audio workspace, and semantic code-diff animations — all as an **optional Python layer on top of Manim**, not a fork or a new renderer.

> Status: **pre-M0**. Nothing is implemented yet. The full product spec is in [`spec.md`](spec.md). The first task is the baseline audit (spec §3, milestone M0).

## Relationship to upstream projects

| Project | Role | How it is used |
|---|---|---|
| [ManimCommunity/manim](https://github.com/ManimCommunity/manim) | **Dependency** | Installed from PyPI. Engine, scene model and renderer stay authoritative. Not vendored, not forked. |
| [motion-canvas/motion-canvas](https://github.com/motion-canvas/motion-canvas) | **Reference** | Behavior and UX reference only. No source or UI assets are copied. |

Both are pinned to reviewed commits in [`upstreams.json`](upstreams.json). See [`docs/upstream-sync.md`](docs/upstream-sync.md) for how new upstream changes are reviewed and brought in, and [ADR-0001](docs/architecture-decisions.md) for why this is a standalone repo rather than a GitHub fork.

```bash
python scripts/upstream_sync.py status     # what changed upstream since our pins
```

## License

MIT — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
