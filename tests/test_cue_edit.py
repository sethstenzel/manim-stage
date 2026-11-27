"""Cue dragging rules, persistence and undo (backlog 2.2)."""

import pytest

from manim_stage import cues as cs
from manim_stage.studio.cue_edit import CueInfo, edit_for_plan, edit_reset, plan_move

# a reached at 10 → target 20; b reached 30 → 45 (waits 15); c reached 50 → 50 (waits 0)
CUES = [
    CueInfo("a", 10, 20, 20, False),
    CueInfo("b", 30, 45, 45, False),
    CueInfo("c", 50, 50, 50, False),
]


def test_hold_moves_only_this_cue_and_its_segment():
    plan = plan_move(CUES, "a", 25, ripple=False)
    assert plan.targets == {"a": 25} and plan.delta == 5
    assert (plan.shift_from, plan.shift_until) == (20, 45)  # up to the next cue
    assert plan.clamped is None


def test_hold_is_limited_by_the_next_cues_wait():
    plan = plan_move(CUES, "a", 60, ripple=False)
    assert plan.target == 35 and "push past cue 'b'" in plan.clamped  # b waits 15


def test_cannot_move_before_the_cue_is_reached():
    plan = plan_move(CUES, "b", 5, ripple=False)
    assert plan.target == 30 and "earlier" in plan.clamped


def test_ripple_moves_every_later_cue():
    plan = plan_move(CUES, "a", 60, ripple=True)
    assert plan.targets == {"a": 60, "b": 85, "c": 90}
    assert plan.shift_until is None and plan.clamped is None


def test_last_cue_has_no_upper_limit_in_hold_mode():
    assert plan_move(CUES, "c", 500, ripple=False).target == 500


def test_edit_do_undo_roundtrip(tmp_path):
    side = tmp_path / ".manim-stage" / "cues.json"
    f = cs.CueFile(frame_rate=60)
    f.set_target("S", "b", 3.0)  # existing override
    cs.save(side, f)
    plan = plan_move(CUES, "a", 60, ripple=True)
    edit = edit_for_plan(side, "S", plan, fps=15)
    assert edit.before == {"a": None, "b": 3.0, "c": None}
    edit.do(side)
    data = cs.load(side)
    assert data.target_seconds("S", "a") == 4.0 and data.target_seconds("S", "c") == 6.0
    edit.undo(side)
    data = cs.load(side)
    assert data.target_seconds("S", "a") is None and data.target_seconds("S", "b") == 3.0
    assert "c" not in data.scenes["S"]


def test_reset_removes_the_override(tmp_path):
    side = tmp_path / "cues.json"
    f = cs.CueFile()
    f.set_target("S", "a", 2.0)
    cs.save(side, f)
    edit = edit_reset(side, "S", "a")
    edit.do(side)
    assert cs.load(side).target_seconds("S", "a") is None
    edit.undo(side)
    assert cs.load(side).target_seconds("S", "a") == pytest.approx(2.0)


def test_new_sidecars_use_60_fps():
    assert cs.CueFile().frame_rate == 60.0
