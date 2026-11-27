"""Replays must be identical (spec §2.5): seeds are enforced, hazards are reported."""

import numpy as np
from conftest import SCENES
from PIL import Image

from manim_stage.determinism import scan_source
from manim_stage.runner import run_capture

FILE = SCENES / "nondeterministic.py"


def test_seeded_random_replays_identically_across_runs_and_workers(tmp_path):
    kw = {"fps": 10, "width": 320, "height": 180}
    a = run_capture(FILE, "Seeded", cache_dir=tmp_path / "a", **kw)
    b = run_capture(FILE, "Seeded", cache_dir=tmp_path / "b", workers=3, **kw)
    assert a.revision == b.revision
    for i, path in a.frames.items():
        assert np.array_equal(np.asarray(Image.open(path)), np.asarray(Image.open(b.frames[i])))


def test_seed_is_part_of_the_revision(tmp_path):
    kw = {"fps": 10, "width": 160, "height": 90, "cache_dir": tmp_path}
    assert (
        run_capture(FILE, "Seeded", seed=1, **kw).revision
        != run_capture(FILE, "Seeded", seed=2, **kw).revision
    )


def test_runner_reports_hazards_as_timeline_warnings():
    tl = run_capture(FILE, "WallClock", fps=10, width=160, height=90).timeline
    text = "\n".join(tl.warnings)
    lines = FILE.read_text(encoding="utf-8").splitlines()
    clock = next(i for i, ln in enumerate(lines, 1) if "time.time()" in ln)
    at_import = next(i for i, ln in enumerate(lines, 1) if ln.startswith("AT_IMPORT"))
    assert f"nondeterministic.py:{clock}: time.time() reads the wall clock" in text
    assert f"nondeterministic.py:{at_import}: random.random() runs at import" in text


def test_scan_rules():
    src = """
import random, time, os, uuid, secrets
from datetime import datetime
import numpy as np
x = random.choice([1, 2])
class K:
    y = np.random.rand()
def f():
    random.random()          # fine: inside a function, after Manim seeds
    np.random.uniform()      # fine
    time.perf_counter()
    datetime.now()
    os.urandom(4)
    uuid.uuid4()
    secrets.token_hex()
    rng = np.random.default_rng()
"""
    got = [(f.line, f.call) for f in scan_source(src)]
    assert got == [
        (5, "random.choice"),
        (7, "np.random.rand"),
        (11, "time.perf_counter"),
        (12, "datetime.now"),
        (13, "os.urandom"),
        (14, "uuid.uuid4"),
        (15, "secrets.token_hex"),
        (16, "np.random.default_rng"),
    ]
