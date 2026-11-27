"""Studio editor shell (backlog 1.3, spec F01), driven headless with pytest-qt."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from conftest import SCENES  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QAbstractButton, QComboBox, QWidget  # noqa: E402

from manim_stage.studio.app import create_window  # noqa: E402

TIMEOUT = 120_000


def dispose(win):
    """Close and destroy a window in the GUI thread, then collect Python cycles here
    (not later on some runner thread, where finalising Qt objects aborts)."""
    import gc

    from PySide6.QtCore import QCoreApplication, QEvent

    win.close()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QCoreApplication.processEvents()
    gc.collect()


@pytest.fixture
def window(qtbot, tmp_path):
    win, svc = create_window(SCENES / "timing.py", "MixedRunTimes", workers=1,
                             cache_dir=tmp_path / "cache", watch=False)  # fmt: skip
    win.show()
    yield win
    dispose(win)


def wait_done(qtbot, win, scene):
    def ready():  # the GUI thread has handled the final status (not just the service)
        st = win.shown_state
        assert st is not None and st[1] == scene and st[2] in ("done", "error")

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


def test_timeline_shows_events_and_selection_drives_event_panel(qtbot, tmp_path):
    win, _ = create_window(
        SCENES / "timing.py", "Lesson", workers=1, cache_dir=tmp_path / "c", watch=False
    )
    win.show()
    wait_done(qtbot, win, "Lesson")
    canvas = win.timeline.canvas
    lay = canvas.layout_
    assert lay is not None and {ln.key for ln in lay.lanes} >= {"sections", "main", "audio"}
    # keyboard: focus timeline, next event, Enter seeks to it
    canvas.setFocus()
    canvas.playhead = 0
    qtbot.keyClick(canvas, Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier)
    first = lay.by_id[canvas.selected]
    assert first.start == 0
    for _ in range(3):
        qtbot.keyClick(canvas, Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier)
    box = lay.by_id[canvas.selected]
    qtbot.keyClick(canvas, Qt.Key.Key_Return)
    assert win.playback.frame == min(box.start, win.playback.total - 1)
    assert win.event_panel.box is box and box.label in win.event_panel.title.text()
    assert canvas.accessibleDescription()
    # clicking a bar selects it; the panel shows Manim details
    fade = next(
        b
        for b in lay.by_id.values()
        if b.kind == "animation" and (b.animation or {}).get("class") == "FadeIn"
    )
    rect = next(r for b, r, _ in canvas.box_rects() if b.id == fade.id)
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=rect.center().toPoint())
    assert canvas.selected == fade.id
    assert "fading" in win.event_panel.details.text().lower()
    assert win.event_panel.curve.isVisibleTo(win.event_panel)
    # zoom keeps the playhead's frame under the cursor anchor and enables scrolling
    canvas.zoom(4.0)
    assert not canvas.fit_mode
    canvas.fit()
    assert canvas.fit_mode and canvas.scroll == 0
    # selection survives a re-render (stable event IDs)
    win.render()
    qtbot.waitUntil(
        lambda: win.shown_state and win.shown_state[0] > 1 and win.shown_state[2] == "done",
        timeout=TIMEOUT,
    )
    assert canvas.selected == fade.id
    dispose(win)


def test_click_on_ruler_seeks(qtbot, window):
    wait_done(qtbot, window, "MixedRunTimes")
    canvas = window.timeline.canvas
    from manim_stage.studio.ui.timeline import LABEL_W

    x = int(canvas.x_of(window.playback.total // 2))
    qtbot.mouseClick(
        canvas, Qt.MouseButton.LeftButton, pos=__import__("PySide6.QtCore").QtCore.QPoint(x, 5)
    )
    assert abs(window.playback.frame - window.playback.total // 2) <= 1
    assert x > LABEL_W


def test_export_dialog_range_command_and_run(qtbot, window, tmp_path):
    wait_done(qtbot, window, "MixedRunTimes")
    window.scene_box.setCurrentIndex(window.scene_box.findData("Lesson"))
    window._scene_chosen(0)
    wait_done(qtbot, window, "Lesson")
    tl = window.service.current.timeline.to_dict()
    second = [e for e in tl["events"] if e["kind"] in ("play", "wait")][1]
    window.seek(second["start_frame"] + 1)
    window.shortcuts["range_in"].trigger()
    window.seek(second["end_frame"] - 2)
    window.shortcuts["range_out"].trigger()
    dlg = window.open_export()
    assert dlg is not None and dlg.ranged.isChecked()
    assert "-n 1,1" in dlg.command.text() and dlg.command.text().startswith("manim render")
    assert "animations 1–1" in dlg.range_note.text()
    dlg.quality.setCurrentIndex(dlg.quality.findData("low_quality"))
    dlg.format.setCurrentIndex(dlg.format.findData("mp4"))
    assert not dlg.transparent.isEnabled()  # mp4 has no alpha in Manim
    dlg.media_dir.setText(str(tmp_path / "media"))
    dlg.start()
    qtbot.waitUntil(lambda: dlg.result is not None, timeout=TIMEOUT)
    assert dlg.result.ok, dlg.result.error
    assert "✔ Done" in dlg.status.text() and "854×480" in dlg.status.text()
    assert dlg.open_btn.isEnabled()
    dlg.close()


def test_snapshot_and_copy_frame(qtbot, window, tmp_path):
    from PySide6.QtGui import QGuiApplication

    wait_done(qtbot, window, "MixedRunTimes")
    window.seek(10)
    window.shortcuts["copy_frame"].trigger()
    img = QGuiApplication.clipboard().image()
    assert not img.isNull() and img.width() == 854
    out = tmp_path / "snap.png"
    window.save_snapshot(str(out), quality="low_quality")
    qtbot.waitUntil(lambda: bool(window.last_snapshot_message), timeout=TIMEOUT)
    assert out.is_file() and "Saved frame 10" in window.last_snapshot_message


def _drag(widget, start, end, *, shift=False):
    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication

    mods = Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier
    left = Qt.MouseButton.LeftButton

    def send(kind, pos, button, buttons):
        p = QPointF(pos)
        ev = QMouseEvent(kind, p, widget.mapToGlobal(p), button, buttons, mods)
        QApplication.sendEvent(widget, ev)

    send(QEvent.Type.MouseButtonPress, start, left, left)
    for i in range(1, 6):
        send(QEvent.Type.MouseMove, start + (end - start) * (i / 5), Qt.MouseButton.NoButton, left)
    send(QEvent.Type.MouseButtonRelease, end, left, Qt.MouseButton.NoButton)


def test_drag_cue_saves_sidecar_rerenders_and_undoes(qtbot, tmp_path):
    from PySide6.QtCore import QPointF

    from manim_stage import cues as cs

    proj = tmp_path / "proj"
    (proj / ".manim-stage").mkdir(parents=True)
    scene = proj / "lesson.py"
    scene.write_text((SCENES / "cues.py").read_text(encoding="utf-8"), encoding="utf-8")
    side = proj / ".manim-stage" / "cues.json"
    win, _ = create_window(scene, "Narrated", workers=1, cache_dir=tmp_path / "c", watch=True)
    win.show()
    wait_done(qtbot, win, "Narrated")
    canvas = win.timeline.canvas
    fps = win.playback.fps

    def cue(name):
        return next(
            b for b in canvas.layout_.by_id.values() if b.kind == "cue" and b.meta["name"] == name
        )

    def rect(name):
        return next(r for b, r, _ in canvas.box_rects() if b.id == cue(name).id)

    def rerendered(after_seq):
        return lambda: win.shown_state[0] > after_seq and win.shown_state[2] == "done"

    # drag "intro" (target 2.0 s) 1 s later, in hold mode
    seq = win.shown_state[0]
    r = rect("intro")
    start = r.center()
    end = start + QPointF(fps * canvas.ppf, 0)
    _drag(canvas, start, end)
    assert cs.load(side).target_seconds("Narrated", "intro") == pytest.approx(3.0, abs=1 / fps)
    qtbot.waitUntil(rerendered(seq), timeout=TIMEOUT)
    assert cue("intro").start == pytest.approx(3 * fps, abs=1)
    assert cue("intro").meta["overridden"] is True
    swap_after_hold = cue("swap").start

    # undo → override removed → back to 2.0 s
    seq = win.shown_state[0]
    win.act_undo.trigger()
    assert cs.load(side).target_seconds("Narrated", "intro") is None
    qtbot.waitUntil(rerendered(seq), timeout=TIMEOUT)
    assert cue("intro").start == 2 * fps

    # redo
    seq = win.shown_state[0]
    win.act_redo.trigger()
    qtbot.waitUntil(rerendered(seq), timeout=TIMEOUT)
    assert cue("intro").start == pytest.approx(3 * fps, abs=1)
    assert cue("swap").start == swap_after_hold

    # keyboard nudge of the selected cue (+1 frame)
    canvas.select(cue("intro").id)
    canvas.setFocus()
    before = cue("intro").start
    seq = win.shown_state[0]
    qtbot.keyClick(
        canvas,
        Qt.Key.Key_Right,
        Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.ShiftModifier,
    )
    qtbot.waitUntil(rerendered(seq), timeout=TIMEOUT)
    assert cue("intro").start == before + 1

    # Event panel: reset to default
    canvas.select(cue("intro").id)
    assert win.event_panel.cue_row.isVisibleTo(win.event_panel)
    seq = win.shown_state[0]
    win.event_panel.cue_reset.click()
    qtbot.waitUntil(rerendered(seq), timeout=TIMEOUT)
    assert cue("intro").start == 2 * fps and not cue("intro").meta["overridden"]
    dispose(win)


def test_audio_lane_gets_waveforms_and_a_mix(qtbot, tmp_path, test_sound):
    import shutil

    from manim_stage import audio

    proj = tmp_path / "p"
    (proj / ".manim-stage").mkdir(parents=True)
    shutil.copy(SCENES / "audio_scene.py", proj / "lesson.py")
    shutil.copy(test_sound, proj / "voice.wav")
    audio.save(
        proj / ".manim-stage" / "audio.json",
        audio.AudioFile({"Voiced": [audio.AudioClip("n", "voice.wav", start=0.5)]}),
    )
    win, _ = create_window(
        proj / "lesson.py", "Voiced", workers=1, cache_dir=tmp_path / "c", watch=False
    )
    win.show()
    wait_done(qtbot, win, "Voiced")
    qtbot.waitUntil(lambda: bool(win.timeline.canvas.waveforms), timeout=TIMEOUT)
    sound_id = next(iter(win.timeline.canvas.waveforms))
    assert sound_id == "Voiced:sound:clip:n#0"
    assert win.audio_seq == win.service.current.seq
    assert not win.audio.available  # tests run silent (MANIM_STAGE_NO_AUDIO)
    assert not win.transport.btn_audio.isEnabled()
    assert win.audio.duration == pytest.approx(win.playback.total / win.playback.fps, abs=0.05)
    dispose(win)


def test_audio_clip_add_drag_trim_mute_undo(qtbot, tmp_path, test_sound):
    import shutil

    from PySide6.QtCore import QPointF

    from manim_stage import audio

    proj = tmp_path / "p"
    (proj / ".manim-stage").mkdir(parents=True)
    shutil.copy(SCENES / "audio_scene.py", proj / "lesson.py")
    win, _ = create_window(
        proj / "lesson.py", "Voiced", workers=1, cache_dir=tmp_path / "c", watch=True
    )
    win.show()
    wait_done(qtbot, win, "Voiced")
    canvas = win.timeline.canvas
    side = proj / ".manim-stage" / "audio.json"

    def rerendered(after):
        return lambda: win.shown_state[0] > after and win.shown_state[2] == "done"

    def clip_box():
        return next((b for b in canvas.layout_.by_id.values() if b.meta.get("clip")), None)

    # add a clip at 0.5 s (file is outside the project → copied in)
    seq = win.shown_state[0]
    win.add_audio(str(test_sound), start=0.5)
    qtbot.waitUntil(rerendered(seq), timeout=TIMEOUT)
    assert (proj / "assets" / "audio" / test_sound.name).exists()
    box = clip_box()
    assert box is not None and box.start == int(0.5 * win.playback.fps)  # sounds start at floor

    # drag the body 1 s later
    rect = next(r for b, r, _ in canvas.box_rects() if b.id == box.id)
    seq = win.shown_state[0]
    _drag(canvas, rect.center(), rect.center() + QPointF(win.playback.fps * canvas.ppf, 0))
    qtbot.waitUntil(rerendered(seq), timeout=TIMEOUT)
    assert audio.load(side).scenes["Voiced"][0].start == pytest.approx(1.5, abs=0.07)

    # mute in the Event panel: the clip stays on the timeline, but silent
    canvas.select(clip_box().id)
    assert win.event_panel.clip_box.isVisibleTo(win.event_panel)
    win.event_panel.clip_mute.setChecked(True)
    seq = win.shown_state[0]
    win.event_panel.clip_apply.click()
    qtbot.waitUntil(rerendered(seq), timeout=TIMEOUT)
    b = clip_box()
    assert b is not None and b.meta.get("silent") and b.meta["silent_reason"] == "muted"
    assert not [e for e in win.service.current.timeline.events if e.kind == "sound"]

    # undo twice → unmuted, back at 0.5 s
    for _ in range(2):
        seq = win.shown_state[0]
        win.act_undo.trigger()
        qtbot.waitUntil(rerendered(seq), timeout=TIMEOUT)
    c = audio.load(side).scenes["Voiced"][0]
    assert c.start == 0.5 and not c.mute
    dispose(win)


def test_project_panel_edits_theme_and_variables_with_undo(qtbot, tmp_path):
    import shutil

    from manim_stage import project as pj

    proj = tmp_path / "proj"
    shutil.copytree(SCENES / "themed", proj)
    (proj / ".manim-stage").mkdir()
    win, _ = create_window(
        proj / "scene_a.py", "SceneA", workers=1, cache_dir=tmp_path / "c", watch=True
    )
    win.show()
    wait_done(qtbot, win, "SceneA")
    panel = win.project_panel
    assert "accent" in panel.color_buttons and "size" in panel.var_editors
    rev0 = win.service.current.revision
    panel.color_buttons["accent"].set_value("#00ff00")
    panel.var_editors["size"][0].setValue(2.0)
    assert panel.has_changes()
    seq = win.shown_state[0]
    panel.apply_btn.click()
    qtbot.waitUntil(
        lambda: win.shown_state[0] > seq and win.shown_state[2] == "done", timeout=TIMEOUT
    )
    saved = pj.load(proj / ".manim-stage" / "project.json")
    assert saved.theme.accent == "#00ff00" and saved.variables["size"].value == 2.0
    assert win.service.current.revision != rev0
    seq = win.shown_state[0]
    win.act_undo.trigger()
    qtbot.waitUntil(
        lambda: win.shown_state[0] > seq and win.shown_state[2] == "done", timeout=TIMEOUT
    )
    assert (
        pj.load(proj / ".manim-stage" / "project.json").theme.accent == pj.DEFAULT_COLORS["accent"]
    )
    dispose(win)
