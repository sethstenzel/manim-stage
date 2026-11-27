"""Studio editor shell (backlog 1.3, spec F01), driven headless with pytest-qt."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from conftest import SCENES  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QAbstractButton, QComboBox, QWidget  # noqa: E402

from manim_stage.studio.app import create_window  # noqa: E402

TIMEOUT = 120_000


@pytest.fixture
def window(qtbot, tmp_path):
    win, svc = create_window(SCENES / "timing.py", "MixedRunTimes", workers=1,
                             cache_dir=tmp_path / "cache", watch=False)  # fmt: skip
    qtbot.addWidget(win)
    win.show()
    yield win
    win.close()


def wait_done(qtbot, win, scene):
    def ready():
        cur = win.service.current
        assert cur is not None and cur.scene == scene and cur.state in ("done", "error")

    qtbot.waitUntil(ready, timeout=TIMEOUT)


def test_discovers_scenes_and_renders_the_requested_one(qtbot, window):
    wait_done(qtbot, window, "MixedRunTimes")
    names = [window.scene_box.itemData(i) for i in range(window.scene_box.count())]
    assert names[:4] == ["Lesson", "Nested", "MixedRunTimes", "Broken"]
    assert window.scene_box.currentData() == "MixedRunTimes"
    assert window.playback.total == window.service.current.timeline.duration_frames
    qtbot.waitUntil(lambda: window.viewport.has_frame, timeout=TIMEOUT)
    assert "Ready" in window.status_label.text()


def test_transport_seek_step_and_shortcuts(qtbot, window):
    wait_done(qtbot, window, "MixedRunTimes")
    total = window.playback.total
    window.seek(5)
    assert window.transport.frame_box.value() == 5
    window.shortcuts["next"].trigger()
    assert window.playback.frame == 6
    window.shortcuts["end"].trigger()
    assert window.playback.frame == total - 1
    window.shortcuts["start"].trigger()
    assert window.playback.frame == 0
    window.shortcuts["fwd_1s"].trigger()
    assert window.playback.frame == round(window.playback.fps)
    # scrub bar click seeks
    bar = window.transport.scrub
    qtbot.mouseClick(bar, Qt.MouseButton.LeftButton, pos=bar.rect().center())
    assert abs(window.playback.frame - total // 2) <= 1


def test_play_advances_and_range_loops(qtbot, window):
    wait_done(qtbot, window, "MixedRunTimes")
    window.seek(2)
    window.shortcuts["range_in"].trigger()
    window.seek(6)
    window.shortcuts["range_out"].trigger()
    assert (window.playback.range.start, window.playback.range.end) == (2, 7)
    window.shortcuts["play"].trigger()
    assert window.playback.playing
    seen = set()
    qtbot.waitUntil(lambda: seen.add(window.playback.frame) or len(seen) >= 4, timeout=10_000)
    assert seen <= set(range(2, 7))
    window.shortcuts["play"].trigger()
    assert not window.playback.playing


def test_switching_scene_and_quality_rerenders(qtbot, window):
    wait_done(qtbot, window, "MixedRunTimes")
    window.scene_box.setCurrentIndex(window.scene_box.findData("Nested"))
    window._scene_chosen(0)
    wait_done(qtbot, window, "Nested")
    assert window.service.current.settings.height == 480
    window.quality_box.setCurrentIndex(window.quality_box.findData("medium_quality"))
    window.render()
    wait_done(qtbot, window, "Nested")
    assert (window.service.current.settings.width, window.service.current.settings.fps) == (
        1280, 30.0)  # fmt: skip


def test_error_shows_location_and_open_button(qtbot, window):
    wait_done(qtbot, window, "MixedRunTimes")
    window.scene_box.setCurrentIndex(window.scene_box.findData("Broken"))
    window._scene_chosen(0)
    wait_done(qtbot, window, "Broken")
    qtbot.waitUntil(lambda: window.log.error_location is not None, timeout=TIMEOUT)
    file, line = window.log.error_location
    assert Path(file).name == "timing.py"
    src = (SCENES / "timing.py").read_text(encoding="utf-8").splitlines()
    assert "raise ValueError" in src[line - 1]
    assert window.viewport.overlay_is_error and "boom" in window.viewport.overlay
    assert f"timing.py:{line}" in window.log.open_button.text()


def test_theme_toggle_and_zoom(qtbot, window):
    from PySide6.QtWidgets import QApplication

    from manim_stage.studio.ui.theme import is_dark

    app = QApplication.instance()
    before = is_dark(app)
    window.toggle_theme()
    assert is_dark(app) != before
    window.toggle_theme()
    window.viewport.set_zoom(2.0)
    assert window.viewport.current_scale() == 2.0
    window.shortcuts["fit"].trigger()
    assert window.viewport.zoom is None


def test_every_control_has_an_accessible_name(qtbot, window):
    def named(w):
        return bool(w.accessibleName() or (isinstance(w, QAbstractButton) and w.text()))

    controls = [
        w
        for w in window.findChildren(QWidget)
        if isinstance(w, (QAbstractButton, QComboBox))
        and w.isVisibleTo(window)
        and not w.objectName().startswith("qt_")  # Qt's own internals
    ]
    assert controls and not [type(w).__name__ for w in controls if not named(w)]
