"""The HTML docs site (ADR-0014): hook behaviour and a strict build of the real docs."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("mkdocs")
from mkdocs.config.defaults import MkDocsConfig  # noqa: E402
from mkdocs.structure.files import File, Files  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("docs_hooks", ROOT / "scripts" / "docs_hooks.py")
hooks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hooks)


@pytest.fixture
def files():
    cfg = MkDocsConfig()
    cfg.load_dict({"site_name": "t", "docs_dir": str(ROOT / "docs")})
    cfg.validate()
    cfg.plugins._current_plugin = None  # normally set while MkDocs runs a hook
    names = ["index.md", "migration-guide.md", "kb/README.md", "kb/manim-stage/cues.md"]
    fs = Files([File(n, cfg.docs_dir, "site", True) for n in names])
    return hooks.on_files(fs, cfg)


def test_links_between_docs_stay_relative(files):
    assert hooks.rewrite_link("kb/README.md#x", "migration-guide.md", files) == "kb/README.md#x"
    assert hooks.rewrite_link("../migration-guide.md", "kb/README.md", files) == (
        "../migration-guide.md"
    )


def test_repo_root_docs_become_pages(files):
    assert hooks.rewrite_link("../PORTING.md", "migration-guide.md", files) == "porting.md"
    assert hooks.rewrite_link("../../PORTING.md", "kb/README.md", files) == "../porting.md"
    # From a root page, links into docs/ drop the docs/ prefix.
    assert hooks.rewrite_link("docs/kb/README.md", "changelog.md", files) == "kb/README.md"


def test_code_and_examples_link_to_github(files):
    url = hooks.REPO_URL
    assert hooks.rewrite_link("../upstreams.json", "upstream-sync.md", files) == (
        f"{url}/blob/main/upstreams.json"
    )
    assert hooks.rewrite_link("../../examples/third_party/", "kb/README.md", files) == (
        f"{url}/tree/main/examples/third_party"
    )
    # A docs file that isn't part of the site (here: not in `files`) goes to GitHub too.
    assert hooks.rewrite_link("_template.md", "kb/README.md", files) == (
        f"{url}/blob/main/docs/kb/_template.md"
    )


def test_external_and_anchor_links_unchanged(files):
    for link in ["https://example.com/a.md", "#quick-start", "mailto:x@example.com"]:
        assert hooks.rewrite_link(link, "kb/README.md", files) == link


def test_github_style_lists_are_normalized():
    src = "Intro:\n- a\n  - a1\n  - a2\n- b\n\nPara\n  not a list\n"
    assert hooks.normalize_lists(src) == (
        "Intro:\n\n- a\n    - a1\n    - a2\n- b\n\nPara\n  not a list\n"
    )


def test_no_run_marker_stripped_and_code_untouched(files):
    class Page:
        file = files.get_file_from_path("kb/manim-stage/cues.md")

    md = "See [x](../../../PORTING.md).\n\n```python no-run\nx = '[a](../../PORTING.md)'\n```\n"
    out = hooks.on_page_markdown(md, Page(), None, files)
    assert "```python\n" in out and "no-run" not in out
    assert "[x](../../porting.md)" in out
    assert "x = '[a](../../PORTING.md)'" in out  # code blocks are never rewritten


def test_site_builds_strict(tmp_path):
    """Broken links or anchors, or a docs page missing from nav, fail here and in CI."""
    result = subprocess.run(
        [sys.executable, "-m", "mkdocs", "build", "--strict", "--site-dir", str(tmp_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "NO_MKDOCS_2_WARNING": "1"},
    )
    assert result.returncode == 0, result.stderr[-3000:]
    assert (tmp_path / "index.html").exists()
    assert (tmp_path / "porting" / "index.html").exists()
