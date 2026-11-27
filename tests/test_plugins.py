"""Studio plugin SDK (backlog 4.1, spec F11)."""

import sys
from pathlib import Path

import pytest
from conftest import SCENES

from manim_stage import plugins as pl

PLUGIN_DIR = Path(__file__).resolve().parent.parent / "examples" / "plugins" / "stage_beats"


@pytest.fixture
def beats(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    monkeypatch.setenv(
        "MANIM_STAGE_PLUGINS", "stage_beats:plugin, stage_beats:old_plugin, missing_mod:nope"
    )
    yield
    sys.modules.pop("stage_beats", None)


def test_discovery_and_handshake(beats):
    found = {p.name: p for p in pl.discover()}
    assert found["beats"].enabled and set(found["beats"].hooks) == set(pl.HOOKS)
    assert not found["old"].enabled and "API 99" in found["old"].reason
    bad = next(p for p in found.values() if p.source.endswith("missing_mod:nope"))
    assert not bad.enabled and "failed to load" in bad.reason


def test_failing_hook_disables_only_that_plugin():
    class Boom:
        name, api_version = "boom", 1

        def timeline_events(self, tl, api):
            raise RuntimeError("bang")

    lp = pl._check(pl.LoadedPlugin("boom", "test", Boom()))
    logs = []
    assert pl.plugin_events([lp], {"scene": "S", "events": []}, None, log=logs.append) == []
    assert not lp.enabled and "timeline_events" in lp.reason and "bang" in logs[0]


def test_sample_plugin_adds_a_track_and_panel_without_core_changes(beats, qtbot, tmp_path):
    """F11 accept."""
    from PySide6.QtCore import Qt
    from test_studio_ui import dispose, wait_done

    from manim_stage.studio.app import create_window

    win, _ = create_window(
        SCENES / "timing.py", "Lesson", workers=1, cache_dir=tmp_path / "c", watch=False
    )
    win.show()
    wait_done(qtbot, win, "Lesson")
    lanes = [ln.key for ln in win.timeline.canvas.layout_.lanes]
    assert "plugin:beats" in lanes
    beats_boxes = [b for b in win.timeline.canvas.layout_.by_id.values() if b.kind == "plugin"]
    assert beats_boxes and beats_boxes[0].label == "beat 1"
    titles = [d.windowTitle() for d in win.plugin_docks]
    assert titles == ["Beats"]
    assert win.plugins_panel.tree.topLevelItemCount() == 3
    # a plugin command (Next beat) moves the playhead
    win.seek(0)
    win.shortcuts["plugin:beats:Next beat"].trigger()
    assert win.playback.frame == round(win.playback.fps)
    # inspector rows from the plugin
    win.inspector_panel.node = {"id": "0", "class": "Square", "module": "m", "children": []}
    win._plugin_inspector_rows(win.inspector_panel.node)
    from PySide6.QtWidgets import QLabel

    labels = [w.text() for w in win.inspector_panel.props_host.findChildren(QLabel)]
    assert "children" in labels
    assert [lab for lab, _ in win.plugin_exporters()] == ["Beat count"]
    assert Qt  # noqa: B018
    dispose(win)


def test_cli_lists_plugins(beats, capsys):
    from manim_stage.cli import main

    assert main(["plugins"]) == 0
    out = capsys.readouterr().out
    assert "ok   beats" in out and "OFF  old" in out and "API 99" in out
