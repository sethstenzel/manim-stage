"""MkDocs hooks that turn the repository's Markdown into the HTML docs site.

The Markdown stays the source of truth and keeps working on GitHub. These hooks only
adapt it for the site:

- Add the repo-root documents (PORTING.md, CHANGELOG.md, spec.md) as site pages.
- Rewrite relative links: links to other docs become site links, links to code,
  examples or other repo files become GitHub links.
- Make GitHub-style lists (no blank line before them, 2-space nesting) render the same.
- Turn the KB's ``python no-run`` fences (a test marker, see test_kb_examples.py)
  into plain ``python`` fences.
- Put the package version in the footer.
"""

from __future__ import annotations

import posixpath
import re
import tomllib
from pathlib import Path

from mkdocs.structure.files import File, Files

ROOT = Path(__file__).resolve().parent.parent
REPO_URL = "https://github.com/sethstenzel/manim-stage"
# Repo-root document -> path inside the site.
ROOT_PAGES = {"PORTING.md": "porting.md", "CHANGELOG.md": "changelog.md", "spec.md": "spec.md"}
_SITE_TO_ROOT = {v: k for k, v in ROOT_PAGES.items()}

_LINK = re.compile(r"(\]\()(<?)([^)\s>]+)(>?)((?:\s+\"[^\"]*\")?\))")
_ITEM = re.compile(r"^(?:[-*+]|\d+[.)])[ \t]+")
_NO_RUN = re.compile(r"^(\s*```[\w+-]+)[ \t]+no-run[ \t]*$", re.MULTILINE)


def version() -> str:
    with open(ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)["project"]["version"]


def on_config(config, **kwargs):
    config["copyright"] = f"manim-stage {version()} · MIT licence"
    return config


def on_files(files: Files, config, **kwargs) -> Files:
    for repo_name, site_path in ROOT_PAGES.items():
        files.append(File.generated(config, site_path, abs_src_path=str(ROOT / repo_name)))
    return files


def repo_path(src_uri: str) -> str:
    """Where a site page's Markdown lives in the repository."""
    return _SITE_TO_ROOT.get(src_uri, f"docs/{src_uri}")


def _in_site(files: Files, path: str) -> bool:
    f = files.get_file_from_path(path)
    return f is not None and not f.inclusion.is_excluded()


def rewrite_link(target: str, src_uri: str, files: Files) -> str:
    """Map one relative link in the page at ``src_uri`` to a site or GitHub link."""
    if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I) or target.startswith(("#", "/")):
        return target
    path, _, anchor = target.partition("#")
    if not path:
        return target
    anchor = f"#{anchor}" if anchor else ""
    here = posixpath.dirname(src_uri)
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(repo_path(src_uri)), path))
    if resolved.startswith("../"):
        return target  # outside the repo; leave it alone

    site = None
    if resolved in ROOT_PAGES:
        site = ROOT_PAGES[resolved]
    elif resolved == "docs" or resolved.startswith("docs/"):
        rel = resolved[5:] or "."
        if (ROOT / resolved).is_dir():
            index = posixpath.normpath(posixpath.join(rel, "README.md"))
            rel = index if _in_site(files, index) else None
        if rel and _in_site(files, rel):
            site = rel
    if site is not None:
        return posixpath.relpath(site, here or ".") + anchor

    kind = "tree" if (ROOT / resolved).is_dir() else "blob"
    return f"{REPO_URL}/{kind}/main/{resolved}{anchor}"


def normalize_lists(text: str) -> str:
    """Make GitHub-style lists parse the same way in Python-Markdown.

    GitHub accepts a list straight after a paragraph line and nests with 2 spaces.
    Python-Markdown needs a blank line before the list and 4-space nesting, so add the
    blank line and double the indentation of lines inside a list.
    """
    out: list[str] = []
    in_list = False
    prev = ""
    for line in text.split("\n"):
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        if not stripped:
            out.append(line)
            prev = line
            continue
        if indent == 0:
            item = bool(_ITEM.match(line))
            if item and not in_list and prev.strip():
                out.append("")  # a list right after a paragraph line
            in_list = item
        elif in_list:
            line = " " * (indent * 2) + stripped
        out.append(line)
        prev = line
    return "\n".join(out)


def _rewrite_prose(text: str, src_uri: str, files: Files) -> str:
    text = normalize_lists(text)
    return _LINK.sub(lambda m: m[1] + m[2] + rewrite_link(m[3], src_uri, files) + m[4] + m[5], text)


def on_page_markdown(markdown: str, page, config, files: Files, **kwargs) -> str:
    markdown = _NO_RUN.sub(r"\1", markdown)
    # Adapt prose only, never fenced code blocks.
    parts = re.split(r"(^\s*(?:```|~~~).*?^\s*(?:```|~~~)[ \t]*$)", markdown, flags=re.M | re.S)
    src_uri = page.file.src_uri
    return "".join(
        part if i % 2 else _rewrite_prose(part, src_uri, files) for i, part in enumerate(parts)
    )
