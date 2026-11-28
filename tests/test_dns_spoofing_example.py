"""The DNS spoofing explainer (examples/dns_spoofing) renders with its cues, chapters and theme."""

from pathlib import Path

from PIL import Image

from manim_stage import web
from manim_stage.runner import run_capture

FILE = Path(__file__).resolve().parent.parent / "examples" / "dns_spoofing" / "dns_spoofing.py"
CUES = [
    "lookup_starts",
    "answer_cached",
    "ttl_expired",
    "flood",
    "poisoned",
    "victim_asks",
    "cert_warning",
    "defenses",
]
SECTIONS = ["Normal lookup", "Cache poisoning", "Victim redirected", "Defenses"]


def test_dns_spoofing_renders_with_its_cues_chapters_and_theme(tmp_path):
    r = run_capture(FILE, "DnsSpoofing", fps=10, width=192, height=108, cache_dir=tmp_path / "c")
    tl = r.timeline
    assert not tl.warnings, tl.warnings
    assert len(r.frames) == tl.duration_frames > 0
    assert 40 <= tl.duration_frames / 10 <= 70
    assert [e.label for e in tl.events if e.kind == "cue"] == CUES
    assert [c.title for c in web.chapters(tl.to_dict())] == SECTIONS
    px = Image.open(r.frames[0]).convert("RGB").getpixel((2, 2))
    assert px == (0x0F, 0x17, 0x20)  # background from .manim-stage/project.json
