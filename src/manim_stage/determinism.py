"""Static checks for scene code that cannot be replayed deterministically (spec §2.5, §4).

The runner replays a scene several times: once for the timeline, once per drawing
worker, again after every edit. Manim seeds ``random`` and ``numpy.random`` in
``Scene.__init__`` from ``config.seed`` (the runner always sets one), so seeded
randomness inside ``construct`` is fine. These are not:

- wall-clock reads (``time.time``, ``datetime.now``, ...),
- OS entropy (``os.urandom``, ``uuid.uuid4``, ``secrets``, ``random.SystemRandom``),
- ``random`` / ``numpy.random`` calls at module level, which run at import, before
  Manim seeds anything.

This is a best-effort scan of the scene file only (not imported modules); it reports
warnings, it does not block rendering.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

_CLOCK = {
    "time.time", "time.time_ns", "time.perf_counter", "time.perf_counter_ns",
    "time.monotonic", "time.monotonic_ns", "time.process_time",
    "datetime.now", "datetime.utcnow", "datetime.today", "date.today",
    "datetime.datetime.now", "datetime.datetime.utcnow", "datetime.date.today",
}  # fmt: skip
_ENTROPY = {
    "os.urandom", "uuid.uuid1", "uuid.uuid4", "random.SystemRandom",
    "secrets.token_bytes", "secrets.token_hex", "secrets.randbelow", "secrets.choice",
    "np.random.default_rng", "numpy.random.default_rng",
}  # fmt: skip
_SEEDABLE = {"np.random.default_rng", "numpy.random.default_rng"}  # unseeded only if no args
_RANDOM_PREFIXES = ("random.", "np.random.", "numpy.random.")


@dataclass(frozen=True)
class Finding:
    line: int
    call: str
    reason: str

    def message(self, file: str) -> str:
        return f"{file}:{self.line}: {self.call}() {self.reason}; replays may differ."


def _dotted(node: ast.AST) -> str | None:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def _module_level_calls(tree: ast.Module) -> set[int]:
    """ids of Call nodes that execute at import time (not inside a def or class body
    that is only run later; class bodies do run at import, so they count)."""
    found: set[int] = set()

    def visit(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            if isinstance(child, ast.Call):
                found.add(id(child))
            visit(child)

    visit(tree)
    return found


def scan_source(source: str) -> list[Finding]:
    tree = ast.parse(source)
    at_import = _module_level_calls(tree)
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _dotted(node.func)
        if not name:
            continue
        if name in _CLOCK:
            findings.append(Finding(node.lineno, name, "reads the wall clock"))
        elif name in _SEEDABLE and (node.args or node.keywords):
            continue  # seeded, e.g. np.random.default_rng(7): reproducible
        elif name in _ENTROPY or name.startswith("secrets."):
            findings.append(Finding(node.lineno, name, "uses unseeded OS entropy"))
        elif name.startswith(_RANDOM_PREFIXES) and id(node) in at_import:
            findings.append(
                Finding(node.lineno, name, "runs at import, before Manim seeds the RNG")
            )
    return sorted(findings, key=lambda f: f.line)


def scan_file(path: str | Path) -> list[str]:
    path = Path(path)
    try:
        findings = scan_source(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []  # the import itself will report the syntax error
    return [f.message(path.name) for f in findings]
