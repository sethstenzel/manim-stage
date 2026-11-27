"""Knowledge base checks: every ```python block runs, every relative link resolves.

Blocks of one page run in order in a shared temporary folder (a later block may use
files an earlier one wrote). Mark fragments that must not run as ```python no-run.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

KB = Path(__file__).resolve().parent.parent / "docs" / "kb"
PAGES = sorted(p for p in KB.rglob("*.md") if not p.name.startswith("_"))
BLOCK = re.compile(r"^```python[ \t]*\n(.*?)^```", re.S | re.M)
LINK = re.compile(r"\[[^\]]*\]\(([^)#\s]+)(?:#[^)]*)?\)")


def blocks(page: Path) -> list[str]:
    return BLOCK.findall(page.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "page", [p for p in PAGES if blocks(p)], ids=lambda p: str(p.relative_to(KB))
)
def test_examples_run(page, tmp_path):
    for i, code in enumerate(blocks(page)):
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=600,
        )
        assert proc.returncode == 0, (
            f"{page.relative_to(KB)} block {i} failed:\n{proc.stdout}\n{proc.stderr}"
        )


@pytest.mark.parametrize("page", PAGES, ids=lambda p: str(p.relative_to(KB)))
def test_relative_links_resolve(page):
    for target in LINK.findall(page.read_text(encoding="utf-8")):
        if "://" in target or target.startswith("mailto:"):
            continue
        assert (page.parent / target).resolve().exists(), f"{page.name}: broken link {target}"


def test_index_lists_every_page():
    index = (KB / "README.md").read_text(encoding="utf-8")
    for page in PAGES:
        if page.parent == KB:
            continue
        rel = page.relative_to(KB).as_posix()
        assert rel in index, f"docs/kb/README.md does not link {rel}"
