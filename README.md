# manim-stage

Motion Canvas–class authoring for [Manim Community Edition](https://github.com/ManimCommunity/manim): a local Studio editor, seekable timeline, named timing cues for narration, audio workspace, and semantic code-diff animations — all as an **optional Python layer on top of Manim**, not a fork or a new renderer.

> Status: **M0 complete** ([gate report](docs/m0-gate-report.md)); next: M1 Studio MVP. Usable today: scene event capture, background runner, frame cache. Spec: [`spec.md`](spec.md) · Audit: [`docs/capability-audit.md`](docs/capability-audit.md) · Decisions: [`docs/architecture-decisions.md`](docs/architecture-decisions.md) · Plan: [`docs/backlog.md`](docs/backlog.md) · Knowledge base: [`docs/kb/`](docs/kb/README.md)

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
