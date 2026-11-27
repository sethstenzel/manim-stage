# Installing and releasing

## Install a release

Releases are GitHub Releases with a wheel and an sdist. manim-stage needs Manim at the reviewed commit in `upstreams.json` (the 0.30 line, not on PyPI yet), so install both:

```bash
uv venv
uv pip install "manim_stage-0.1.0-py3-none-any.whl[studio]" \
  "manim @ git+https://github.com/ManimCommunity/manim@8c258a0082dc760d9a93671bbdfaca3cc53a6f91"
manim-stage doctor
```

- **Drop `[studio]`** for headless use (CLI, cues, signals, helpers) without Qt.
- **System libraries for Cairo/Pango** are needed as for Manim itself:
  - Linux: `libcairo2-dev libpango1.0-dev`;
  - macOS: `brew install cairo pango`;
  - Windows: wheels include them.
- **LaTeX is optional.** It's only needed for `MathTex`/`Tex`.

From source: `git clone … && uv sync && uv run manim-stage studio examples/bubble_sort/lesson.py`.

## Release process (maintainers)

1. Update `version` in `pyproject.toml` and `__version__` in `src/manim_stage/__init__.py`, then run `uv lock`.
2. Add a `## [x.y.z] — date` section to `CHANGELOG.md`. The release notes are taken from it.
3. Merge to `main` with green CI. The `package` job builds the wheel and smoke-installs it on Windows, Linux and macOS.
4. Tag and push: `git tag vX.Y.Z && git push origin vX.Y.Z`. The `release` workflow then:
   - checks that the tag matches the version;
   - builds and checks the wheel;
   - smoke-tests it on all three OSes;
   - creates the GitHub Release with the files.

**PyPI:** not yet. PyPI metadata can't pin a git commit of Manim. Once Manim 0.30 is on PyPI:
- set `manim>=0.30` in `dependencies`;
- remove `[tool.uv.sources]`;
- add a trusted-publishing job (`pypa/gh-action-pypi-publish`) to `release.yml`.
