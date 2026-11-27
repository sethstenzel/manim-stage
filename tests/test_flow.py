"""Flow helpers, in-scene transitions and scene composition (backlog 3.4, spec F09)."""

import json
import math
import shutil

import numpy as np
import pytest
from manim import RIGHT, Circle, Create, Dot, FadeIn, Scene, Square, tempconfig

from manim_stage import audio
from manim_stage.capture import capture
from manim_stage.compose import Part, blend, compose, load_spec
from manim_stage.flow import all_of, chain, delay, enter, exit, loop, sequence, tween

CFG = {
    "frame_rate": 10,
    "dry_run": True,
    "disable_caching": True,
    "progress_bar": "none",
    "verbosity": "WARNING",
}


def spans(scene_cls):
    with tempconfig(CFG):
        tl = capture(scene_cls)
    return [
        (e.label.split("(")[0], e.start_frame, e.end_frame)
        for e in tl.events
        if e.kind == "animation"
    ], tl


def test_sequence_starts_children_at_exact_second_offsets():
    class S(Scene):
        def construct(self):
            dots = [Dot().shift(RIGHT * i) for i in range(3)]
            self.play(sequence(0.5, *(FadeIn(d, run_time=1) for d in dots)))

    with tempconfig(CFG):
        tl = capture(S)
    play = next(e for e in tl.events if e.kind == "play")
    assert play.end_frame - play.start_frame == 20  # 2 × 0.5 s + 1 s


def test_chain_delay_loop_all_durations():
    class S(Scene):
        def construct(self):
            s = Square()
            self.play(chain(Create(s, run_time=0.5), s.animate(run_time=0.5).shift(RIGHT)))
            self.play(delay(1.0, FadeIn(Circle(), run_time=0.5)))
            self.play(loop(3, lambda i: s.animate(run_time=0.2).shift(RIGHT)))
            self.play(all_of(FadeIn(Dot(), run_time=0.3), FadeIn(Dot(), run_time=0.6)))

    with tempconfig(CFG):
        tl = capture(S)
    lengths = [e.end_frame - e.start_frame for e in tl.events if e.kind == "play"]
    assert lengths == [10, 15, 6, 6]


def test_tween_drives_any_function():
    seen = []

    class S(Scene):
        def construct(self):
            self.play(tween(1.0, seen.append))

    with tempconfig(CFG):
        S().render()
    assert seen[0] == pytest.approx(0.0) and seen[-1] == pytest.approx(1.0)
    assert seen == sorted(seen)


def test_enter_and_exit_transitions():
    class S(Scene):
        def construct(self):
            self.add(Square(), Circle().shift(RIGHT * 2))
            self.play(enter(self, "slide", "left"))
            self.play(exit(self, "zoom"))
            self.play(enter(self, "fade"))

    with tempconfig(CFG):
        S().render()
    with pytest.raises(ValueError):
        enter(None, "spin")


def test_blend_styles():
    a = np.zeros((4, 8, 3), np.uint8)
    b = np.full((4, 8, 3), 200, np.uint8)
    assert blend(a, b, 0.5, "fade")[0, 0, 0] == 100
    s = blend(a, b, 0.25, "slide_left")
    assert (s[:, :6] == 0).all() and (s[:, 6:] == 200).all()
    w = blend(a, b, 0.5, "wipe_right")
    assert (w[:, :4] == 200).all() and (w[:, 4:] == 0).all()


def _video(path, colors, fps=10, size=(64, 36), tone=None):
    import av

    with av.open(str(path), "w") as c:
        vs = c.add_stream("libx264", rate=fps)
        vs.width, vs.height = size
        vs.pix_fmt = "yuv420p"
        vs.options = {"crf": "0"}
        if tone is not None:
            aus = c.add_stream("aac", rate=audio.RATE)
            aus.layout = "stereo"
        for col in colors:
            f = np.zeros((size[1], size[0], 3), np.uint8)
            f[:] = col
            for p in vs.encode(av.VideoFrame.from_ndarray(f, format="rgb24")):
                c.mux(p)
        for p in vs.encode():
            c.mux(p)
        if tone is not None:
            n = int(len(colors) / fps * audio.RATE)
            sig = np.zeros((2, n), np.float32)
            sig[:, :] = tone
            for s in range(0, n, 1024):
                af = av.AudioFrame.from_ndarray(
                    np.ascontiguousarray(sig[:, s : s + 1024]), format="fltp", layout="stereo"
                )
                af.sample_rate = audio.RATE
                af.pts = s
                for p in aus.encode(af):
                    c.mux(p)
            for p in aus.encode():
                c.mux(p)


def test_compose_three_scenes_two_transitions_frame_exact(tmp_path):
    """F09 accept (composition core): 3 scenes, 2 transitions, exact durations, no
    dropped/duplicated frames, audio at the right offsets."""
    import av

    vids = []
    for i, (col, n) in enumerate((((200, 0, 0), 20), ((0, 200, 0), 30), ((0, 0, 200), 25))):
        v = tmp_path / f"s{i}.mp4"
        _video(v, [col] * n, tone=0.1 * (i + 1))
        vids.append(v)
    parts = [
        Part(tmp_path / "a.py", "A", video=vids[0]),
        Part(tmp_path / "b.py", "B", "fade", 0.5, video=vids[1]),
        Part(tmp_path / "c.py", "C", "slide_left", 0.3, video=vids[2]),
    ]
    r = compose(parts, tmp_path / "out.mp4")
    assert r.overlaps == [0, 5, 3] and r.offsets == [0, 15, 42]
    assert r.frames == 20 + 30 + 25 - 5 - 3
    with av.open(str(r.output)) as c:
        frames = [f.to_ndarray(format="rgb24") for f in c.decode(video=0)]
    assert len(frames) == r.frames
    px = [tuple(int(v) for v in f[18, 32]) for f in frames]
    assert px[0][0] > 190 and px[14][0] > 190  # A alone until the fade
    mid = px[17]
    assert 40 < mid[0] < 160 and 40 < mid[1] < 160  # cross-fade
    assert px[25][1] > 190  # B alone
    assert px[-1][2] > 190  # C at the end
    a = audio.decode(r.output)
    level = lambda t: float(np.abs(a[int(t * audio.RATE)][0]))  # noqa: E731
    assert level(0.5) == pytest.approx(0.1, abs=0.03)  # A
    assert level(2.5) == pytest.approx(0.2, abs=0.03)  # B
    assert level(6.5) == pytest.approx(0.3, abs=0.04)  # C


def test_spec_file_and_validation(tmp_path):
    spec = tmp_path / "lesson.sequence.json"
    spec.write_text(
        json.dumps(
            {
                "output": "lesson.mp4",
                "quality": "low_quality",
                "scenes": [
                    {"file": "a.py", "scene": "A"},
                    {"file": "b.py", "scene": "B", "transition": "wipe_up", "duration": 0.4},
                ],
            }
        )
    )
    parts, opts = load_spec(spec)
    assert [p.transition for p in parts] == ["cut", "wipe_up"] and opts["quality"] == "low_quality"
    spec.write_text(json.dumps({"scenes": [{"file": "a.py", "scene": "A", "transition": "fade"}]}))
    with pytest.raises(ValueError, match="first scene"):
        load_spec(spec)
    assert shutil.which  # keep import used


def test_three_real_scenes_two_transitions_with_audio(tmp_path, test_sound):
    """F09 accept: three scenes linked by two transitions render with stable durations,
    no dropped/duplicated frames, and audio where each scene put it."""
    from conftest import SCENES

    from manim_stage.cli import main
    from manim_stage.export import probe_media

    proj = tmp_path / "p"
    shutil.copytree(SCENES / "sequence", proj)
    spec = proj / "lesson.sequence.json"
    spec.write_text(
        json.dumps(
            {
                "output": "lesson.mp4",
                "quality": "low_quality",
                "scenes": [
                    {"file": "parts.py", "scene": "One"},
                    {"file": "parts.py", "scene": "Two", "transition": "fade", "duration": 0.4},
                    {
                        "file": "parts.py",
                        "scene": "Three",
                        "transition": "slide_left",
                        "duration": 0.6,
                    },
                ],
            }
        )
    )
    assert main(["compose", str(spec)]) == 0
    info = probe_media(proj / "lesson.mp4")
    fps = 15
    n = [math.ceil(1.5 * fps - 1e-9), 2 * fps, math.ceil(1.5 * fps - 1e-9)]  # Manim's frames
    ov = [round(0.4 * fps), round(0.6 * fps)]
    expected = sum(n) - sum(ov)
    assert abs(info["duration_s"] * fps - expected) < 0.5  # no dropped/duplicated frames
    two_start = (n[0] - ov[0]) / fps
    # beeps: One's at 0.5 s; Two's 1.0 s into Two
    a = audio.decode(proj / "lesson.mp4")[:, 0]
    loud = np.abs(a) > 0.05
    onsets = [i / audio.RATE for i in range(1, len(loud)) if loud[i] and not loud[i - 1]]
    firsts = [onsets[0]] + [t for p, t in zip(onsets, onsets[1:], strict=False) if t - p > 0.3]
    assert abs(firsts[0] - 0.5) < 1 / fps + 0.03
    assert abs(firsts[1] - (two_start + 1.0)) < 1 / fps + 0.03
