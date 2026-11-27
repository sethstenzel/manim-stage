"""``manim-stage`` command line (ADR-0009, backlog 1.6).

Manim's CLI has no plugin subcommands, so manim-stage has its own entry point. It
never replaces ``manim render``: exports are plain Manim renders (see ``export``).

    manim-stage studio lesson.py [Scene]   open the Studio editor
    manim-stage scenes lesson.py           list Scene classes
    manim-stage timeline lesson.py Scene   print the scene's events (text or --json)
    manim-stage doctor                     check Manim, Qt, FFmpeg/PyAV, LaTeX, fonts
    manim-stage validate lesson.py [Scene] check named cues (exit 1 on errors)
    manim-stage bake lesson.py [Scene]     write resolved cue times to .manim-stage/cues.json
    manim-stage cache [--clear]            frame-cache size / clear it
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from . import __version__


def _add_studio(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("studio", help="open the Studio editor on a scene file")
    p.add_argument("file", type=Path, help="Python file with Manim Scene classes")
    p.add_argument("scene", nargs="?", help="Scene class to open (default: the first)")
    p.add_argument(
        "-q",
        "--quality",
        default="low_quality",
        help="Manim quality preset for the preview (default: low_quality)",
    )
    p.add_argument("--workers", type=int, default=None, help="parallel drawing processes")
    p.add_argument("--cache-dir", type=Path, default=None, help="frame cache folder")
    p.add_argument("--no-watch", action="store_true", help="don't re-render on save")
    p.set_defaults(func=cmd_studio)


def cmd_studio(args: argparse.Namespace) -> int:
    from .studio.app import run

    return run(args)


def cmd_scenes(args: argparse.Namespace) -> int:
    import subprocess

    from .runner import child_env, runner_command

    proc = subprocess.run(
        runner_command(args.file, None, list_scenes=True),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=child_env(),
        cwd=args.file.resolve().parent,
    )
    for raw in proc.stdout.splitlines():
        try:
            m = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if m.get("type") == "error":
            print(f"error: {m['message']} ({m.get('file')}:{m.get('line')})", file=sys.stderr)
            return 1
        if m.get("type") == "scenes":
            if args.json:
                print(json.dumps(m["scenes"], indent=2))
            else:
                for s in m["scenes"]:
                    print(f"{s['name']:30s} line {s['line']:<5} {', '.join(s['bases'][:1])}")
            return 0
    print(proc.stderr, file=sys.stderr)
    return 1


def cmd_timeline(args: argparse.Namespace) -> int:
    from .runner import RunnerError, run_capture

    try:
        r = run_capture(args.file, args.scene, fps=args.fps, width=160, height=90)
    except RunnerError as e:
        print(f"error: {e} ({e.file}:{e.line})", file=sys.stderr)
        return 1
    tl = r.timeline
    if args.json:
        print(json.dumps(tl.to_dict(), indent=2))
        return 0
    fps = tl.frame_rate
    print(
        f"{tl.scene}: {tl.duration_frames} frames at {fps:g} fps ({tl.duration_frames / fps:.2f} s)"
    )
    for e in tl.events:
        depth = e.track.count("/") and int(e.track.split("/")[1]) or 0
        span = f"{e.start_frame / fps:7.2f}-{e.end_frame / fps:<7.2f}s"
        where = f"{e.source.path}:{e.source.line}" if e.source else ""
        print(f"{span} {'  ' * depth}{e.kind:9s} {e.label[:60]:60s} {where}")
    for w in tl.warnings:
        print(f"warning: {w}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    from .doctor import run_checks

    results = run_checks()
    if args.json:
        print(json.dumps([r.__dict__ for r in results], indent=2))
    else:
        for r in results:
            mark = {"ok": "ok  ", "warn": "WARN", "fail": "FAIL"}[r.status]
            print(f"{mark} {r.name:22s} {r.detail}")
    return 1 if any(r.status == "fail" for r in results) else 0


def cmd_cache(args: argparse.Namespace) -> int:
    from .studio.app import default_cache_dir

    root = args.cache_dir or default_cache_dir()
    if args.clear:
        if root.exists():
            shutil.rmtree(root)
        print(f"cleared {root}")
        return 0
    size = sum(p.stat().st_size for p in root.rglob("*") if p.is_file()) if root.exists() else 0
    revs = (
        [d for d in root.iterdir() if d.is_dir() and not d.name.startswith(".")]
        if (root.exists())
        else []
    )
    print(f"{root}\n{len(revs)} revisions, {size / 1024**2:.1f} MB")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    from .cuetools import collect, format_report

    reports = collect(args.file, args.scene or None)
    print(format_report(reports))
    return 1 if any(r.error for r in reports) else 0


def cmd_bake(args: argparse.Namespace) -> int:
    from .cues import CueError
    from .cuetools import bake, format_report

    try:
        path, reports = bake(args.file, args.scene or None)
    except CueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(format_report(reports))
    print(f"wrote {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="manim-stage", description="Motion Canvas-class authoring for Manim"
    )
    parser.add_argument("--version", action="version", version=f"manim-stage {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    _add_studio(sub)
    p = sub.add_parser("scenes", help="list the Scene classes in a file")
    p.add_argument("file", type=Path)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_scenes)
    p = sub.add_parser("timeline", help="print a scene's play/wait/section/sound events")
    p.add_argument("file", type=Path)
    p.add_argument("scene")
    p.add_argument("--fps", type=float, default=15.0)
    p.add_argument("--json", action="store_true", help="timeline JSON (docs/schemas)")
    p.set_defaults(func=cmd_timeline)
    p = sub.add_parser("doctor", help="check the environment (Manim, Qt, FFmpeg, LaTeX, fonts)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_doctor)
    p = sub.add_parser("validate", help="check the named cues of StageScenes (exit 1 on errors)")
    p.add_argument("file", type=Path)
    p.add_argument("scene", nargs="*", help="scenes to check (default: every StageScene)")
    p.set_defaults(func=cmd_validate)
    p = sub.add_parser("bake", help="write resolved cue times into .manim-stage/cues.json")
    p.add_argument("file", type=Path)
    p.add_argument("scene", nargs="*", help="scenes to bake (default: every StageScene)")
    p.set_defaults(func=cmd_bake)
    p = sub.add_parser("cache", help="show or clear the preview frame cache")
    p.add_argument("--clear", action="store_true")
    p.add_argument("--cache-dir", type=Path, default=None)
    p.set_defaults(func=cmd_cache)
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # never crash on a legacy console encoding
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "file", None) is not None:
        if not args.file.is_file():
            parser.error(f"{args.file} is not a file")
        args.file = args.file.resolve()
    return int(args.func(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
