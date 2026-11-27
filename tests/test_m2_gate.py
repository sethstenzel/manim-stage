"""M2 gate (spec §11): the narrated bubble-sort demo, headless reproducibility, and the
F03 acceptance scenario.

F03 accept: "replace a 30-second narration with a 35-second recording, adjust five
cues visually, rerender, and confirm animations align without manually changing five
wait() calls in Python."
"""

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from manim_stage import audio
from manim_stage import cues as cs
from manim_stage.runner import run_capture
from manim_stage.studio.cue_edit import CueInfo, edit_for_plan, plan_move

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "bubble_sort"
CUES = ["show_array", "compare", "swap", "largest_done", "optimise"]
FPS = 10


@pytest.fixture
def lesson(tmp_path):
    proj = tmp_path / "bubble_sort"
    (proj / ".manim-stage").mkdir(parents=True)
    for f in ("lesson.py", "make_audio.py"):
        shutil.copy(EXAMPLE / f, proj / f)
    sys.path.insert(0, str(proj))
    try:
        import make_audio

        audio.write_wav(proj / "narration.wav", make_audio.speech_like(30.0))
        yield proj, make_audio
    finally:
        sys.path.remove(str(proj))
        sys.modules.pop("make_audio", None)


def timeline(proj, cache=None):
    return run_capture(
        proj / "lesson.py",
        "BubbleSortLesson",
        fps=FPS,
        width=192,
        height=108,
        cache_dir=cache,
        workers=2 if cache else 1,
    )


def cue_frames(tl):
    return {e.label: e.start_frame for e in tl.timeline.events if e.kind == "cue"}


def first_play_after(tl, frame):
    return min(
        e.start_frame for e in tl.timeline.events if e.kind == "play" and e.start_frame >= frame
    )


def test_demo_timeline(lesson):
    proj, _ = lesson
    r = timeline(proj)
    assert r.timeline.duration_frames == 30 * FPS  # waits for the 30 s narration
    assert cue_frames(r) == {
        "show_array": 30,
        "compare": 60,
        "swap": 90,
        "largest_done": 150,
        "optimise": 200,
    }
    kinds = {e.kind for e in r.timeline.events}
    assert {"sound", "caption", "cue", "play", "wait"} <= kinds
    assert "self.wait(" not in (proj / "lesson.py").read_text(encoding="utf-8")


def test_headless_reproducibility(lesson, tmp_path):
    """Two independent renders of every frame are pixel-identical; the CLI export has
    the right length, audio and subtitles."""
    proj, _ = lesson
    a, b = timeline(proj, tmp_path / "c1"), timeline(proj, tmp_path / "c2")
    assert a.revision == b.revision and len(a.frames) == len(b.frames) == 30 * FPS

    def digest(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    assert all(digest(a.frames[i]) == digest(b.frames[i]) for i in a.frames)

    out = tmp_path / "media"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "manim",
            "render",
            "lesson.py",
            "BubbleSortLesson",
            "-ql",
            "--media_dir",
            str(out),
            "--disable_caching",
        ],
        cwd=proj,
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert proc.returncode == 0, proc.stderr[-3000:]
    from manim_stage.export import probe_media

    mp4 = next(out.rglob("BubbleSortLesson.mp4"))
    info = probe_media(mp4)
    assert abs(info["duration_s"] - 30.0) < 0.15 and info["audio"]
    assert list(out.rglob("BubbleSortLesson.srt"))  # narration subcaptions


def test_f03_new_take_and_five_retimed_cues(lesson):
    proj, make_audio = lesson
    source_before = (proj / "lesson.py").read_bytes()
    base = timeline(proj)

    # the narrator re-records: the new take is 35 s
    audio.write_wav(proj / "narration.wav", make_audio.speech_like(35.0, seed=11))
    # adjust five cues "visually": the same planning + undoable edits the timeline uses
    sidecar = proj / ".manim-stage" / "cues.json"
    shifts = {"show_array": 0.5, "compare": 1.0, "swap": 1.5, "largest_done": 2.5, "optimise": 4.0}
    current = timeline(proj)
    for name in CUES:
        infos = [CueInfo.from_meta(e.meta) for e in current.timeline.events if e.kind == "cue"]
        target = next(i for i in infos if i.name == name).target_frame + int(shifts[name] * FPS)
        plan = plan_move(infos, name, target, ripple=False)
        assert plan.clamped is None, plan.clamped
        edit_for_plan(sidecar, "BubbleSortLesson", plan, FPS).do(sidecar)
        current = timeline(proj)

    after = timeline(proj)
    expected = {n: f + int(shifts[n] * FPS) for n, f in cue_frames(base).items()}
    assert cue_frames(after) == expected
    # the animation right after each cue starts exactly at the cue (≤ 1 frame, spec §9)
    for name in CUES:
        assert abs(first_play_after(after, expected[name]) - expected[name]) <= 1, name
    assert after.timeline.duration_frames == 35 * FPS  # follows the new recording
    assert (proj / "lesson.py").read_bytes() == source_before  # no Python edits
    data = cs.load(sidecar)
    assert set(data.scenes["BubbleSortLesson"]) == set(CUES)

    # headless: plain `manim render` reproduces the new timing
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "manim",
            "render",
            "lesson.py",
            "BubbleSortLesson",
            "-ql",
            "--media_dir",
            str(proj / "media"),
            "--disable_caching",
        ],
        cwd=proj,
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert proc.returncode == 0, proc.stderr[-3000:]
    from manim_stage.export import probe_media

    info = probe_media(next((proj / "media").rglob("BubbleSortLesson.mp4")))
    assert abs(info["duration_s"] - 35.0) < 0.15
