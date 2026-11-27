"""Camera state per rendered frame (backlog MF.8, spec §2.7).

Every Manim scene's camera has an animatable ``frame`` (``self.camera.frame``; the
old ``MovingCameraScene`` is now plain ``Scene``). ``ThreeDScene`` uses a
``ThreeDCamera`` with phi/theta/gamma/zoom/focal distance, and ``ZoomedScene`` adds a
zoomed camera. The preview runner records this state for every frame it renders,
inside the cached PNG as a text chunk, so cached frames keep it. The Studio reads it
back to:

- show a camera readout ("center (1.00, 0.50) · width 7.11", "φ 60° θ −30° …");
- map viewport clicks and inspector selection boxes through a moved camera.
"""

from __future__ import annotations

import json
import math
from typing import Any

PNG_KEY = "manim_stage.camera"


def _r(x: float) -> float:
    return round(float(x), 4)


def camera_state(scene: Any) -> dict[str, Any] | None:
    """JSON-safe camera state of ``scene`` at the current frame (None if unknown)."""
    cam = getattr(scene, "camera", None)
    if cam is None:
        return None
    st: dict[str, Any] = {"camera": type(cam).__name__}
    frame = getattr(cam, "frame", None)
    try:
        if frame is not None:
            c = frame.get_center()
            st.update(center=[_r(c[0]), _r(c[1])], width=_r(frame.width), height=_r(frame.height))
        if hasattr(cam, "get_phi"):
            st.update(
                phi=_r(math.degrees(cam.get_phi())),
                theta=_r(math.degrees(cam.get_theta())),
                gamma=_r(math.degrees(cam.get_gamma())),
                zoom=_r(cam.get_zoom()),
                focal_distance=_r(cam.get_focal_distance()),
            )
        if getattr(scene, "zoom_activated", False):
            zf = scene.zoomed_camera.frame
            zc = zf.get_center()
            st["zoomed"] = {"center": [_r(zc[0]), _r(zc[1])], "width": _r(zf.width)}
    except Exception:  # a camera we don't know: record what we have
        pass
    return st


def encode(state: dict[str, Any] | None) -> dict[str, str]:
    """PNG text chunks for ``FrameCache.put``."""
    return {PNG_KEY: json.dumps(state, separators=(",", ":"))} if state else {}


def decode(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def is_three_d(state: dict[str, Any] | None) -> bool:
    return bool(state and "phi" in state)


def is_default(state: dict[str, Any] | None, frame_width: float = 14.2222) -> bool:
    """True for an unmoved, unzoomed, flat camera (nothing worth showing)."""
    if not state:
        return True
    if is_three_d(state) or state.get("zoomed"):
        return False
    cx, cy = state.get("center", [0, 0])
    width = state.get("width", frame_width)
    return abs(cx) < 1e-3 and abs(cy) < 1e-3 and abs(width - frame_width) < 1e-2


def describe(state: dict[str, Any] | None, frame_width: float = 14.2222) -> str:
    """One-line readout for the status bar."""
    if not state:
        return ""
    parts = [state.get("camera", "Camera")]
    if is_three_d(state):
        parts.append(f"φ {state['phi']:.0f}° θ {state['theta']:.0f}° γ {state['gamma']:.0f}°")
        parts.append(f"zoom {state['zoom']:.2f}")
    elif "center" in state:
        cx, cy = state["center"]
        scale = frame_width / state["width"] if state.get("width") else 1.0
        parts.append(f"center ({cx:.2f}, {cy:.2f}) · width {state['width']:.2f} ({scale:.2f}×)")
    z = state.get("zoomed")
    if z:
        parts.append(f"zoomed: ({z['center'][0]:.2f}, {z['center'][1]:.2f}) w {z['width']:.2f}")
    return " · ".join(parts)
