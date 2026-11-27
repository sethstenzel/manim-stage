"""Audio workspace core: decode, clip processing, mixdown, sidecar, StageScene clips, playback."""

import shutil
import subprocess
import sys

import numpy as np
import pytest
from conftest import SCENES

from manim_stage import audio
from manim_stage.audio import RATE, AudioClip, AudioFile, SoundPlacement
from manim_stage.runner import run_capture
from manim_stage.studio.audio_player import AudioPlayer


def test_decode_resamples_to_48k_stereo(test_sound):
    a = audio.decode(test_sound)  # 0.5 s mono 48 kHz tone
    assert a.shape == (24000, 2) and a.dtype == np.float32
    assert np.abs(a).max() == pytest.approx(
        8000 / 32767 * 0.7071, rel=0.02
    )  # mono → stereo at -3 dB


def test_process_trims_gains_and_fades():
    src = np.ones((RATE * 2, 2), dtype=np.float32) * 0.5
    clip = AudioClip(
        "c", "x.wav", trim_in=0.5, trim_out=1.5, gain_db=6.0206, fade_in=0.25, fade_out=0.25
    )
    out = audio.process(src, clip)
    assert len(out) == RATE  # 1 s after trimming
    assert out[0, 0] == 0.0 and out[-1, 0] < 0.01  # faded in and out
    assert out[RATE // 2, 0] == pytest.approx(1.0, abs=1e-3)  # +6 dB doubles 0.5


def test_mix_places_and_cuts(tmp_path):
    f = tmp_path / "one.wav"
    audio.write_wav(f, np.full((RATE, 2), 0.25, dtype=np.float32))
    buf = audio.mix([SoundPlacement(f, -0.5), SoundPlacement(f, 1.0, 6.0206)], duration=1.75)
    assert len(buf) == int(1.75 * RATE)
    assert buf[0, 0] == pytest.approx(0.25, abs=1e-3)  # second half of the first sound
    assert buf[int(0.75 * RATE), 0] == pytest.approx(0.0)  # gap
    assert buf[int(1.5 * RATE), 0] == pytest.approx(0.5, abs=2e-3)  # +6 dB, cut at the end


def test_peaks():
    s = np.zeros((RATE, 2), dtype=np.float32)
    s[RATE // 2] = 0.8
    pk = audio.peaks(s, 100)
    assert len(pk) == 100 and pk.max() == pytest.approx(0.8) and pk[0] == 0


def test_sidecar_roundtrip_mute_and_solo(tmp_path):
    data = AudioFile(
        {
            "S": [
                AudioClip("a", "a.wav"),
                AudioClip("b", "b.wav", mute=True),
                AudioClip("c", "c.wav"),
            ]
        }
    )
    p = audio.save(tmp_path / "audio.json", data)
    import json

    from test_schemas import validator

    validator("audio.schema.json").validate(json.loads(p.read_text(encoding="utf-8")))
    back = audio.load(p)
    assert [c.id for c in back.active("S")] == ["a", "c"]
    back.scenes["S"][2].solo = True
    assert [c.id for c in back.active("S")] == ["c"]


@pytest.fixture
def voiced_project(tmp_path, test_sound):
    proj = tmp_path / "p"
    (proj / ".manim-stage").mkdir(parents=True)
    shutil.copy(SCENES / "audio_scene.py", proj / "lesson.py")
    shutil.copy(test_sound, proj / "voice.wav")
    data = AudioFile(
        {
            "Voiced": [
                AudioClip("narration", "voice.wav", start=0.5, gain_db=-3, fade_out=0.1),
                AudioClip("muted", "voice.wav", start=1.0, mute=True),
            ]
        }
    )
    audio.save(proj / ".manim-stage" / "audio.json", data)
    return proj


def test_stage_scene_adds_active_clips_as_sounds(voiced_project):
    tl = run_capture(voiced_project / "lesson.py", "Voiced", fps=15, width=64, height=36).timeline
    sounds = [e for e in tl.events if e.kind == "sound"]
    assert len(sounds) == 1  # the muted clip is not added
    s = sounds[0]
    assert s.meta["clip"] == "narration" and s.id == "Voiced:sound:clip:narration#0"
    assert s.start_frame == 7 and s.meta["start_seconds"] == 0.5
    assert (voiced_project / ".manim-stage" / "cache" / "audio").is_dir()


def test_exported_audio_matches_the_preview_mix(voiced_project, tmp_path):
    import av

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "manim",
            "render",
            "lesson.py",
            "Voiced",
            "-ql",
            "--media_dir",
            str(tmp_path / "m"),
        ],
        cwd=voiced_project,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    out = next((tmp_path / "m").rglob("Voiced.mp4"))
    rendered = audio.decode(out)
    tl = run_capture(voiced_project / "lesson.py", "Voiced", fps=15, width=64, height=36).timeline
    preview = audio.mix(
        audio.sounds_from_timeline(tl.to_dict(), voiced_project), tl.duration_frames / 15
    )
    n = min(len(rendered), len(preview))
    a, b = rendered[:n, 0], preview[:n, 0]
    # same placement (≤ 1 frame) and level, within AAC tolerance
    lag = int(np.argmax(np.correlate(a[::16], b[::16], "full"))) - (len(b[::16]) - 1)
    assert abs(lag * 16) <= RATE / 15
    assert np.corrcoef(a, b)[0, 1] > 0.98
    assert np.sqrt(np.mean(a**2)) == pytest.approx(np.sqrt(np.mean(b**2)), rel=0.1)
    assert av  # PyAV decoded the AAC track


class FakeStream:
    def __init__(self, callback, **kw):
        self.callback, self.kw, self.started = callback, kw, False

    def start(self):
        self.started = True

    def stop(self):
        pass

    def close(self):
        pass


def test_player_plays_from_position_and_mutes():
    made = []
    player = AudioPlayer(stream_factory=lambda **kw: made.append(FakeStream(**kw)) or made[-1])
    ramp = np.linspace(0, 1, RATE, dtype=np.float32)[:, None].repeat(2, axis=1)
    player.set_mix(ramp)
    player.play(0.5)
    out = np.zeros((480, 2), dtype=np.float32)
    made[0].callback(out, 480, None, None)
    assert out[0, 0] == pytest.approx(0.5, abs=1e-4)
    assert player.position() == pytest.approx(0.51)
    assert player.drift(0.5) == pytest.approx(0.01)
    player.muted = True
    made[0].callback(out, 480, None, None)
    assert not out.any()
    player.seek(2.0)  # past the end → silence
    player.muted = False
    made[0].callback(out, 480, None, None)
    assert not out.any()
    player.stop()
    assert not player.playing


def test_player_is_unavailable_when_disabled(monkeypatch):
    monkeypatch.setenv("MANIM_STAGE_NO_AUDIO", "1")
    p = AudioPlayer()
    assert not p.available and "MANIM_STAGE_NO_AUDIO" in p.reason
    p.play(0)  # no-op
