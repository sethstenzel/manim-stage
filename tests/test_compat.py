from manim_stage import _compat


def test_pinned_manim_has_required_capabilities():
    caps = _compat.require_supported()
    assert caps.evaluate and caps.timeline_capture and caps.frame_callbacks


def test_missing_reports_names():
    caps = _compat.ManimCapabilities(
        "x", evaluate=True, timeline_capture=False, frame_callbacks=False
    )
    assert caps.missing() == ["timeline_capture", "frame_callbacks"]
