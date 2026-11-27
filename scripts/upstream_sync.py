#!/usr/bin/env python3
"""Track and review changes in the upstream projects manim-stage builds on.

Upstreams are listed in ``upstreams.json`` at the repo root, each pinned to a
reviewed commit. Local checkouts live in ``.upstream/<name>`` (gitignored).

Commands:
  status [NAME...] [--json] [--no-fetch]
      Fetch each upstream and report new release tags and the commits since
      the pin that touch the watched paths.
  log NAME [--to REF] [--all-paths]
      Print the commit log from the pin to REF (default: tip of branch).
  diff NAME [--to REF] [--stat]
      Print the diff of watched paths from the pin to REF.
  checkout NAME [REF]
      Check out REF (default: the pinned commit) in .upstream/NAME for reading.
  bump NAME REF [--label TEXT]
      Re-pin NAME to REF after the changes up to it have been reviewed.

Standard library only; needs git on PATH.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "upstreams.json"
CHECKOUTS = ROOT / ".upstream"


def git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and result.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed in {repo}:\n{result.stderr.strip()}")
    return result.stdout.strip()


def load_config() -> dict:
    with CONFIG.open(encoding="utf-8") as f:
        return json.load(f)


def save_config(config: dict) -> None:
    # Atomic write so an interrupted bump never leaves a half-written file.
    fd, tmp = tempfile.mkstemp(dir=ROOT, prefix=".upstreams.", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        json.dump(config, f, indent=2)
        f.write("\n")
    os.replace(tmp, CONFIG)


def get_upstream(config: dict, name: str) -> dict:
    try:
        return config["upstreams"][name]
    except KeyError:
        names = ", ".join(config["upstreams"])
        sys.exit(f"Unknown upstream {name!r}. Known: {names}")


def ensure_checkout(name: str, up: dict, fetch: bool = True) -> Path:
    path = CHECKOUTS / name
    if not (path / ".git").exists():
        CHECKOUTS.mkdir(exist_ok=True)
        print(f"Cloning {up['repo']} into {path} ...", file=sys.stderr)
        # Blobless clone: full history for log/diff, file contents on demand.
        subprocess.run(
            ["git", "clone", "--filter=blob:none", "--no-checkout", up["repo"], str(path)],
            check=True,
        )
        git(path, "checkout", "--detach", up["pinned"]["commit"])
    elif fetch:
        git(path, "fetch", "--tags", "--prune", "--quiet", "origin")
    return path


def resolve(path: Path, ref: str) -> str:
    for candidate in (ref, f"origin/{ref}", f"refs/tags/{ref}"):
        sha = git(path, "rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}", check=False)
        if sha:
            return sha
    sys.exit(f"Cannot resolve {ref!r} in {path}")


def tip(path: Path, up: dict) -> str:
    return resolve(path, f"origin/{up['branch']}")


def new_tags(path: Path, pin: str) -> list[str]:
    """Tags newer than the pin: descendants of it, plus any tag created after the
    pinned commit (release commits are sometimes cut off-branch, e.g. manim v0.30.0a1)."""
    pinned = set(git(path, "tag", "--points-at", pin).splitlines())
    descendants = set(git(path, "tag", "--contains", pin).splitlines())
    pin_time = int(git(path, "show", "-s", "--format=%ct", pin))
    out = []
    refs = git(path, "for-each-ref", "--sort=-creatordate",
               "--format=%(refname:short) %(creatordate:unix)", "refs/tags")
    for line in refs.splitlines():
        name, _, ts = line.rpartition(" ")
        if name and name not in pinned and (name in descendants or int(ts) > pin_time):
            out.append(name)
    return out


def commits(path: Path, start: str, end: str, paths: list[str] | None) -> list[str]:
    args = ["log", "--no-merges", "--format=%h %as %s", f"{start}..{end}"]
    if paths:
        args += ["--", *paths]
    out = git(path, *args)
    return out.splitlines() if out else []


def cmd_status(args: argparse.Namespace) -> int:
    config = load_config()
    names = args.names or list(config["upstreams"])
    report = {}
    for name in names:
        up = get_upstream(config, name)
        path = ensure_checkout(name, up, fetch=not args.no_fetch)
        pin = up["pinned"]["commit"]
        head = tip(path, up)
        report[name] = {
            "role": up["role"],
            "pinned_ref": up["pinned"]["ref"],
            "pinned_commit": pin,
            "branch": up["branch"],
            "branch_tip": head,
            "new_tags": new_tags(path, pin),
            "commits_total": len(commits(path, pin, head, None)),
            "commits_watched": commits(path, pin, head, up["watch_paths"]),
        }

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    for name, r in report.items():
        print(f"== {name} ({r['role']}) pinned at {r['pinned_ref']} ({r['pinned_commit'][:9]})")
        print(f"   {r['branch']} tip: {r['branch_tip'][:9]}")
        tags = r["new_tags"]
        print(f"   New tags since pin: {', '.join(tags[:10]) if tags else 'none'}"
              + (f" (+{len(tags) - 10} more)" if len(tags) > 10 else ""))
        print(f"   Commits since pin: {r['commits_total']} total, "
              f"{len(r['commits_watched'])} touching watched paths")
        for line in r["commits_watched"][:25]:
            print(f"     {line}")
        if len(r["commits_watched"]) > 25:
            print(f"     ... run `log {name}` for the rest")
        print()
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    config = load_config()
    up = get_upstream(config, args.name)
    path = ensure_checkout(args.name, up)
    end = resolve(path, args.to) if args.to else tip(path, up)
    paths = None if args.all_paths else up["watch_paths"]
    for line in commits(path, up["pinned"]["commit"], end, paths):
        print(line)
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    config = load_config()
    up = get_upstream(config, args.name)
    path = ensure_checkout(args.name, up)
    end = resolve(path, args.to) if args.to else tip(path, up)
    extra = ["--stat"] if args.stat else []
    print(git(path, "diff", *extra, up["pinned"]["commit"], end, "--", *up["watch_paths"]))
    return 0


def cmd_checkout(args: argparse.Namespace) -> int:
    config = load_config()
    up = get_upstream(config, args.name)
    path = ensure_checkout(args.name, up)
    sha = resolve(path, args.ref) if args.ref else up["pinned"]["commit"]
    git(path, "checkout", "--quiet", "--detach", sha)
    print(f"{path} now at {sha}")
    return 0


def cmd_bump(args: argparse.Namespace) -> int:
    config = load_config()
    up = get_upstream(config, args.name)
    path = ensure_checkout(args.name, up)
    sha = resolve(path, args.ref)
    old = up["pinned"]
    ancestor = subprocess.run(
        ["git", "-C", str(path), "merge-base", "--is-ancestor", old["commit"], sha]
    ).returncode == 0
    if not ancestor:
        print(f"warning: {args.ref} is not a descendant of the current pin", file=sys.stderr)
    label = args.label or args.ref
    up["pinned"] = {"ref": label, "commit": sha}
    save_config(config)
    print(f"{args.name}: {old['ref']} ({old['commit'][:9]}) -> {label} ({sha[:9]})")
    if up["role"] == "dependency":
        print("Reminder: update the version constraint in pyproject.toml (once it exists) "
              "and run the full test suite against the new version.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd")

    p = sub.add_parser("status")
    p.add_argument("names", nargs="*")
    p.add_argument("--json", action="store_true")
    p.add_argument("--no-fetch", action="store_true")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("log")
    p.add_argument("name")
    p.add_argument("--to")
    p.add_argument("--all-paths", action="store_true")
    p.set_defaults(func=cmd_log)

    p = sub.add_parser("diff")
    p.add_argument("name")
    p.add_argument("--to")
    p.add_argument("--stat", action="store_true")
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("checkout")
    p.add_argument("name")
    p.add_argument("ref", nargs="?")
    p.set_defaults(func=cmd_checkout)

    p = sub.add_parser("bump")
    p.add_argument("name")
    p.add_argument("ref")
    p.add_argument("--label", help="name to record instead of REF, e.g. main@<sha>")
    p.set_defaults(func=cmd_bump)

    args = parser.parse_args()
    if not args.cmd:
        args = parser.parse_args(["status"])
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
