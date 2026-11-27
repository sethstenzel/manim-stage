"""Camera-aware preview (MF.8)."""

from conftest import SCENES
from PIL import Image

from manim_stage import camera_info
from manim_stage.runner import run_capture

SCENE = SCENES / "cameras.py"


def cams(result):
    return {
        i: camera_info.decode(Image.open(p).text.get(camera_info.PNG_KEY))
        for i, p in result.frames.items()
    }


def test_moving_camera_state_is_stored_in_each_frame(tmp_path):
    r = run_capture(SCENE, "Pan", cache_dir=tmp_path / "c", width=64, height=36)
    states = cams(r)
    first, last = states[0], states[max(states)]
    assert first["center"] == [0.0, 0.0] and camera_info.is_default(first)
    assert last["center"][0] > 1.9 and last["width"] < first["width"] * 0.55
    assert "center (1.9" in camera_info.describe(last)
    again = run_capture(SCENE, "Pan", cache_dir=tmp_path / "c", width=64, height=36)
    assert cams(again)[max(states)] == last  # cached frames keep it


def test_three_d_and_zoomed_states(tmp_path):
    r = run_capture(SCENE, "Orbit", cache_dir=tmp_path / "c", width=64, height=36)
    states = cams(r)
    assert states[0]["camera"] == "ThreeDCamera" and states[0]["phi"] == 60.0
    assert abs(states[max(states)]["theta"] - 30.0) < 1
    assert "φ 60° θ 30°" in camera_info.describe(states[max(states)])  # rounded
    z = cams(run_capture(SCENE, "Zoom", cache_dir=tmp_path / "c", width=64, height=36))
    assert z[0]["zoomed"]["width"] > 0 and not camera_info.is_default(z[0])


def test_viewport_maps_clicks_through_the_camera_and_shows_a_readout(qtbot, tmp_path):
    from test_studio_ui import dispose, wait_done

    from manim_stage.studio.app import create_window

    win, _ = create_window(SCENE, "Pan", workers=1, cache_dir=tmp_path / "c", watch=False)
    win.show()
    wait_done(qtbot, win, "Pan")
    win.seek(win.playback.total - 1)
    qtbot.waitUntil(lambda: "center (1.9" in win.camera_label.text(), timeout=10_000)
    vp = win.viewport
    r = vp.frame_rect()
    x, y = vp.widget_to_scene(r.center().x(), r.center().y())
    cx = vp.camera["center"][0]
    assert abs(x - cx) < 0.02 and abs(y) < 0.02
    p = vp.scene_to_widget(cx, 0.0)
    assert abs(p.x() - r.center().x()) < 1 and abs(p.y() - r.center().y()) < 1
    win.seek(0)
    qtbot.waitUntil(lambda: win.camera_label.text() == "", timeout=10_000)
    assert "Scene (Camera)" in win.renderer_badge.text()
    dispose(win)


def test_renderer_badge_names_three_d_scenes(qtbot, tmp_path):
    from test_studio_ui import dispose, wait_done

    from manim_stage.studio.app import create_window

    win, _ = create_window(SCENE, "Orbit", workers=1, cache_dir=tmp_path / "c", watch=False)
    win.show()
    wait_done(qtbot, win, "Orbit")
    assert "ThreeDScene (ThreeDCamera)" in win.renderer_badge.text()
    win.seek(win.playback.total - 1)
    qtbot.waitUntil(lambda: "φ 60°" in win.camera_label.text(), timeout=10_000)
    dispose(win)
