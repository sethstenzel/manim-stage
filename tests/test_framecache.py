import os
import time

import pytest
from PIL import Image

from manim_stage.framecache import FrameCache, revision_key

REV_A = "a" * 32
REV_B = "b" * 32


def img(color=(255, 0, 0, 255)):
    return Image.new("RGBA", (64, 36), color)


def test_put_get_round_trip(tmp_path):
    cache = FrameCache(tmp_path)
    p = cache.put(REV_A, 3, img())
    assert cache.get(REV_A, 3) == p
    assert Image.open(p).getpixel((0, 0)) == (255, 0, 0, 255)
    assert cache.get(REV_A, 4) is None
    assert cache.frames(REV_A) == [3]
    assert not list(p.parent.glob(".tmp-*"))  # atomic write leaves no temp files


@pytest.mark.parametrize("bad", ["../x", "a/b", "", "ZZ" * 16, "a" * 8])
def test_revision_ids_are_validated(tmp_path, bad):
    with pytest.raises(ValueError):
        FrameCache(tmp_path).path(bad, 0)


def test_negative_frame_rejected(tmp_path):
    with pytest.raises(ValueError):
        FrameCache(tmp_path).path(REV_A, -1)


def test_trim_evicts_least_recently_used_and_protects_current(tmp_path):
    cache = FrameCache(tmp_path)
    paths = [cache.put(REV_A, i, img()) for i in range(4)] + [cache.put(REV_B, 0, img())]
    size = paths[0].stat().st_size
    now = time.time()
    for i, p in enumerate(paths):  # deterministic ages: older index = older use
        os.utime(p, (now - 100 + i, now - 100 + i))
    cache.get(REV_A, 0)  # touched -> most recent
    cache.budget_bytes = size * 3
    cache.trim(keep=REV_B)
    assert cache.frames(REV_B) == [0]  # protected
    assert cache.frames(REV_A) == [0, 3]  # 1 and 2 were least recently used


def test_trim_removes_empty_revision_dirs(tmp_path):
    cache = FrameCache(tmp_path, budget_bytes=0)
    cache.put(REV_A, 0, img())
    cache.trim()
    assert not (tmp_path / REV_A).exists()


def test_revision_key_changes_with_inputs(tmp_path):
    f = tmp_path / "s.py"
    f.write_text("x = 1")
    base = revision_key(f, "S", {"fps": 15}, manim_version="m1")
    assert base == revision_key(f, "S", {"fps": 15}, manim_version="m1")
    assert base != revision_key(f, "T", {"fps": 15}, manim_version="m1")
    assert base != revision_key(f, "S", {"fps": 30}, manim_version="m1")
    assert base != revision_key(f, "S", {"fps": 15}, manim_version="m2")
    f.write_text("x = 2")
    assert base != revision_key(f, "S", {"fps": 15}, manim_version="m1")


def test_trim_is_safe_while_another_writer_puts(tmp_path):
    """Regression: trim used to stat other writers' temp files mid-rename."""
    import threading

    cache = FrameCache(tmp_path, budget_bytes=10**9)
    errors = []

    def writer():
        try:
            for i in range(200):
                cache.put(REV_A, i, img())
        except Exception as e:  # pragma: no cover - failure path
            errors.append(e)

    t = threading.Thread(target=writer)
    t.start()
    while t.is_alive():
        cache.trim(keep=REV_B)
        cache.size_bytes()
    t.join()
    assert not errors
    assert cache.frames(REV_A) == list(range(200))
