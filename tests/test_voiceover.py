"""Narration / voiceover adapter (backlog 2.4)."""

import json

import numpy as np
import pytest
from conftest import SCENES

from manim_stage import audio
from manim_stage import cues as cs
from manim_stage.runner import run_capture
from manim_stage.voiceover import (
    bookmark_times,
    find_cached,
    load_voiceover_cache,
    load_words,
    strip_bookmarks,
)

TEXT = "Here is our array. <bookmark mark='swap'/> Now we swap the first two."


def test_strip_bookmarks():
    clean, marks = strip_bookmarks(TEXT)
    assert clean == "Here is our array. Now we swap the first two."
    assert clean[marks["swap"] :].startswith("Now")


def test_bookmark_time_sources():
    clean, marks = strip_bookmarks(TEXT)
    linear = bookmark_times(TEXT, 4.0)["swap"]
    assert linear == pytest.approx(4.0 * marks["swap"] / len(clean))
    words = [
        ("Here", 0.0, 0.2),
        ("is", 0.2, 0.3),
        ("our", 0.3, 0.5),
        ("array.", 0.5, 1.0),
        ("Now", 1.4, 1.6),
        ("we", 1.6, 1.7),
    ]
    assert bookmark_times(TEXT, 4.0, words=words)["swap"] == 1.4
    assert bookmark_times(TEXT, 4.0, bookmarks={"swap": 2.5})["swap"] == 2.5


def test_load_words_formats(tmp_path):
    a = tmp_path / "a.json"
    a.write_text(json.dumps([{"word": "hi", "start": 0, "end": 0.2}]))
    b = tmp_path / "b.json"
    b.write_text(json.dumps({"segments": [{"words": [{"text": " yo", "start": 1, "end": 1.5}]}]}))
    assert load_words(a) == [("hi", 0.0, 0.2)]
    assert load_words(b) == [("yo", 1.0, 1.5)]


def test_manim_voiceover_cache_import(tmp_path):
    (tmp_path / "hello.mp3").write_bytes(b"")
    cache = tmp_path / "cache.json"
    cache.write_text(
        json.dumps(
            [
                {
                    "input_text": "Hello <bookmark mark='A'/> world",
                    "input_data": {"input_text": "Hello world", "service": "gtts"},
                    "original_audio": "hello.mp3",
                    "final_audio": "hello.mp3",
                    "word_boundaries": [
                        {"audio_offset": 0, "text": "Hello"},
                        {"audio_offset": 6_000_000, "text": "world"},
                    ],
                }
            ]
        )
    )
    entries = load_voiceover_cache(cache)
    assert entries[0].audio == tmp_path / "hello.mp3"
    assert entries[0].words == [("Hello", 0.0, 0.6), ("world", 0.6, 0.6)]
    assert find_cached(entries, "Hello   world") is entries[0]
    assert find_cached(entries, "Bye") is None


@pytest.fixture
def narration_file(tmp_path, monkeypatch):
    f = tmp_path / "narration.wav"
    t = np.arange(2 * audio.RATE) / audio.RATE
    audio.write_wav(f, (np.sin(2 * np.pi * 200 * t)[:, None].repeat(2, 1) * 0.2).astype("f4"))
    monkeypatch.setenv("MANIM_STAGE_TEST_NARRATION", str(f))
    return f


def test_narration_plays_captions_bookmarks_and_waits(narration_file):
    tl = run_capture(SCENES / "narration.py", "Narrated", fps=10, width=64, height=36).timeline
    snd = next(e for e in tl.events if e.kind == "sound")
    assert snd.meta["narration"] == "intro" and snd.start_frame == 5 and snd.label == "intro"
    cap = next(e for e in tl.events if e.kind == "caption")
    assert cap.label == "Here is our array. Now we swap the first two."
    assert cap.meta["narration"] == "intro"
    cue = next(e for e in tl.events if e.kind == "cue")
    assert cue.label == "intro.swap"
    clean, marks = strip_bookmarks(TEXT)
    expected = 5 + round(2.0 * marks["swap"] / len(clean) * 10)
    assert abs(cue.start_frame - expected) <= 1
    assert tl.duration_frames == 25  # 0.5 s + the 2 s narration (waits for it to end)


def test_bookmark_is_a_draggable_cue(narration_file, tmp_path, monkeypatch):
    side = tmp_path / "cues.json"
    f = cs.CueFile(frame_rate=10)
    f.set_target("Narrated", "intro.swap", 2.0)
    cs.save(side, f)
    monkeypatch.setenv("MANIM_STAGE_CUES", str(side))
    tl = run_capture(SCENES / "narration.py", "Narrated", fps=10, width=64, height=36).timeline
    cue = next(e for e in tl.events if e.kind == "cue")
    assert cue.start_frame == 20 and cue.meta["overridden"]
    plays = [e for e in tl.events if e.kind == "play"]
    assert plays[-1].start_frame == 20  # the animation after the bookmark moved


def test_unknown_bookmark_is_an_error(narration_file, tmp_path):
    scene = tmp_path / "bad.py"
    scene.write_text(
        "from manim import *\nfrom manim_stage import StageScene\nimport os\n"
        "class Bad(StageScene):\n    def construct(self):\n"
        "        with self.narration('n', file=os.environ['MANIM_STAGE_TEST_NARRATION'],"
        " text='hi') as n:\n            n.wait_until('missing')\n",
        encoding="utf-8",
    )
    from manim_stage.runner import RunnerError

    with pytest.raises(RunnerError, match="no bookmark 'missing'"):
        run_capture(scene, "Bad", fps=10, width=64, height=36)
