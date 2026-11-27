"""Playback model: drift-free clock, buffering, loop, range, playhead preservation."""

import pytest

from manim_stage.studio.playback import Playback


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


@pytest.fixture
def pb():
    clock = Clock()
    p = Playback(clock)
    p.set_scene(10.0, 30)
    return p, clock


ALL = set(range(30))


def test_plays_by_wall_time_without_drift(pb):
    p, clock = pb
    p.play()
    for _ in range(7):  # uneven ticks
        clock.t += 0.033
        p.tick(ALL)
    clock.t = 1.0
    assert p.tick(ALL) == 10  # 1 s at 10 fps, independent of tick count


def test_speed(pb):
    p, clock = pb
    p.set_speed(2.0)
    p.play()
    clock.t = 0.5
    assert p.tick(ALL) == 10


def test_holds_at_unrendered_frame_then_resumes(pb):
    p, clock = pb
    p.play()
    clock.t = 1.0
    assert p.tick(set(range(5))) == 4 and p.buffering
    clock.t = 1.1  # frames 5.. arrive; resume from 4 smoothly, no jump to 11
    assert p.tick(ALL) == 5 and not p.buffering


def test_loop_and_stop_at_end(pb):
    p, clock = pb
    p.play()
    clock.t = 3.05
    assert p.tick(ALL) == 0 and p.playing  # looped
    p.loop = False
    p.seek(28)
    clock.t += 1.0
    assert p.tick(ALL) == 29 and not p.playing


def test_range_bounds_playback(pb):
    p, clock = pb
    p.set_range(10, 15)
    assert p.frame == 10
    p.play()
    clock.t = 0.45
    assert p.tick(ALL) == 14
    clock.t = 0.55
    assert p.tick(ALL) == 10  # wrapped to range start


def test_play_at_end_restarts(pb):
    p, _ = pb
    p.seek(29)
    p.play()
    assert p.frame == 0


def test_new_timeline_keeps_or_resets_playhead(pb):
    p, _ = pb
    p.seek(20)
    assert p.set_scene(10.0, 40) and p.frame == 20  # still valid: kept
    assert not p.set_scene(10.0, 15) and p.frame == 0  # shorter: visibly reset


def test_step_pauses_and_clamps(pb):
    p, _ = pb
    p.play()
    p.step(-5)
    assert p.frame == 0 and not p.playing
    p.step(100)
    assert p.frame == 29


@pytest.mark.parametrize("frame, code", [(0, "00:00.00"), (9, "00:00.09"), (10, "00:01.00"),
                                         (605, "01:00.05")])  # fmt: skip
def test_timecode(pb, frame, code):
    p, _ = pb
    assert p.timecode(frame) == code
