"""Rendered web playback with chapters (spec F12, backlog 4.3).

Turns a rendered video plus its timeline into a small static site you can open from
disk or host anywhere: ``index.html`` (player, chapter list, captions), the video, and
``chapters.vtt`` / ``captions.vtt`` for other players. Nothing is executed in the
browser except the page's own player script; the scene's Python never runs there.

Chapters come from Manim sections (``self.next_section("Swap")``); without sections,
from named cues; otherwise one chapter. Captions come from ``add_subcaption`` and
narration.
"""

from __future__ import annotations

import html
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SKIP_SECTIONS = {"", "autocreated"}  # Manim's implicit first section


@dataclass
class Chapter:
    title: str
    start: float  # seconds


@dataclass
class Caption:
    start: float
    end: float
    text: str


def chapters(timeline: dict[str, Any]) -> list[Chapter]:
    """Chapter starts in seconds, from sections, else cues, else one chapter."""
    fps = float(timeline["frame_rate"])
    events = timeline.get("events", [])
    found: list[Chapter] = []
    for kind in ("section", "cue"):
        found = [
            Chapter(
                str(e.get("label") or e.get("meta", {}).get("name", "")), e["start_frame"] / fps
            )
            for e in events
            if e["kind"] == kind and (e.get("label") or "") not in SKIP_SECTIONS
        ]
        if found:
            break
    found.sort(key=lambda c: c.start)
    unique: list[Chapter] = []
    for c in found:  # one chapter per instant
        if unique and abs(unique[-1].start - c.start) < 1e-6:
            continue
        unique.append(c)
    if not unique or unique[0].start > 1e-6:
        unique.insert(0, Chapter(timeline.get("scene") or "Start", 0.0))
    return unique


def captions(timeline: dict[str, Any]) -> list[Caption]:
    fps = float(timeline["frame_rate"])
    out = [
        Caption(e["start_frame"] / fps, e["end_frame"] / fps, str(e.get("label", "")))
        for e in timeline.get("events", [])
        if e["kind"] == "caption" and e.get("label")
    ]
    return sorted(out, key=lambda c: c.start)


def _ts(seconds: float) -> str:
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def chapters_vtt(chs: list[Chapter], duration: float) -> str:
    lines = ["WEBVTT", ""]
    for i, c in enumerate(chs):
        end = chs[i + 1].start if i + 1 < len(chs) else duration
        lines += [str(i + 1), f"{_ts(c.start)} --> {_ts(max(end, c.start))}", c.title, ""]
    return "\n".join(lines)


def captions_vtt(caps: list[Caption]) -> str:
    lines = ["WEBVTT", ""]
    for i, c in enumerate(caps):
        lines += [str(i + 1), f"{_ts(c.start)} --> {_ts(c.end)}", c.text, ""]
    return "\n".join(lines)


def build(
    video: str | os.PathLike[str],
    timeline: dict[str, Any],
    out_dir: str | os.PathLike[str],
    *,
    title: str | None = None,
) -> Path:
    """Write the player site into ``out_dir`` and return the path of ``index.html``."""
    src = Path(video)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / src.name
    if src.resolve() != target.resolve():
        shutil.copy2(src, target)
    fps = float(timeline["frame_rate"])
    duration = timeline["duration_frames"] / fps
    chs, caps = chapters(timeline), captions(timeline)
    (out / "chapters.vtt").write_text(chapters_vtt(chs, duration), encoding="utf-8")
    if caps:
        (out / "captions.vtt").write_text(captions_vtt(caps), encoding="utf-8")
    data = {
        "title": title or timeline.get("scene", "manim-stage"),
        "video": src.name,
        "duration": duration,
        "chapters": [c.__dict__ for c in chs],
        "captions": [c.__dict__ for c in caps],
    }
    poster = _poster(target, out / "poster.jpg", chs[1].start if len(chs) > 1 else duration / 3)
    data["poster"] = poster.name if poster else ""
    (out / "player.json").write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    page = _PAGE.replace("__TITLE__", html.escape(data["title"]))
    page = page.replace("__VIDEO__", html.escape(src.name, quote=True))
    page = page.replace("__POSTER__", html.escape(data["poster"], quote=True))
    # embedded so captions/chapters work from file:// (browsers block <track> there)
    page = page.replace("__DATA__", json.dumps(data).replace("</", "<\\/"))
    index = out / "index.html"
    index.write_text(page, encoding="utf-8")
    return index


def _poster(video: Path, out: Path, at: float) -> Path | None:
    """A still for the player before it starts (the first frame at or after ``at`` s)."""
    try:
        import av

        with av.open(str(video)) as c:
            stream = c.streams.video[0]
            for frame in c.decode(stream):
                if frame.time is not None and frame.time + 1e-6 >= at:
                    frame.to_image().convert("RGB").save(out, quality=85)
                    return out
    except Exception:
        return None
    return None


_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="manim-stage">
<title>__TITLE__</title>
<style>
  :root { color-scheme: dark; --bg:#111418; --panel:#1b2027; --fg:#e6e9ee; --muted:#9aa3ad;
          --accent:#58c4dd; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--fg);
         font: 15px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
  main { display:grid; grid-template-columns: minmax(0,1fr) 280px; gap:16px;
         max-width:1280px; margin:0 auto; padding:16px; }
  @media (max-width: 860px) { main { grid-template-columns: 1fr; } }
  h1 { font-size:18px; margin:0 0 10px; font-weight:600; }
  video { width:100%; background:#000; border-radius:6px; display:block; }
  .bar { position:relative; height:8px; background:var(--panel); border-radius:4px;
         margin-top:8px; cursor:pointer; }
  .bar .fill { position:absolute; inset:0 auto 0 0; background:var(--accent);
               border-radius:4px; width:0; }
  .bar .tick { position:absolute; top:-3px; width:2px; height:14px; background:var(--fg);
               opacity:.6; }
  .nav { display:flex; gap:8px; margin-top:10px; align-items:center; }
  button { background:var(--panel); color:var(--fg); border:1px solid #2c333d;
           border-radius:5px; padding:5px 10px; font:inherit; cursor:pointer; }
  button:hover, button:focus-visible { border-color:var(--accent); outline:none; }
  #now { color:var(--muted); margin-left:auto; font-variant-numeric: tabular-nums; }
  aside { background:var(--panel); border-radius:6px; padding:10px; align-self:start; }
  aside h2 { font-size:13px; text-transform:uppercase; letter-spacing:.06em;
             color:var(--muted); margin:2px 4px 8px; }
  ol { list-style:none; margin:0; padding:0; }
  li button { width:100%; text-align:left; display:flex; gap:8px; border-color:transparent;
              background:transparent; }
  li button .t { color:var(--muted); font-variant-numeric: tabular-nums; }
  li button[aria-current="true"] { background:#24303c; border-color:var(--accent); }
</style>
</head>
<body>
<main>
  <section>
    <h1>__TITLE__</h1>
    <video id="v" controls preload="metadata" src="__VIDEO__" poster="__POSTER__"></video>
    <div class="bar" id="bar" role="presentation"><div class="fill" id="fill"></div></div>
    <div class="nav">
      <button id="prev" aria-label="Previous chapter">&#9664; Prev</button>
      <button id="next" aria-label="Next chapter">Next &#9654;</button>
      <span id="now" aria-live="polite"></span>
    </div>
  </section>
  <aside aria-label="Chapters">
    <h2>Chapters</h2>
    <ol id="list"></ol>
  </aside>
</main>
<script id="data" type="application/json">__DATA__</script>
<script>
(() => {
  const data = JSON.parse(document.getElementById("data").textContent);
  const v = document.getElementById("v"), list = document.getElementById("list");
  const bar = document.getElementById("bar"), fill = document.getElementById("fill");
  const now = document.getElementById("now");
  const chs = data.chapters, dur = () => v.duration || data.duration;
  const fmt = s => {
    if (data.duration < 60) return Math.max(0, s).toFixed(1) + "s";  // short clips: tenths
    s = Math.max(0, Math.floor(s));
    return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
  };
  const buttons = chs.map((c, i) => {
    const li = document.createElement("li"), b = document.createElement("button");
    b.innerHTML = '<span class="t"></span><span class="n"></span>';
    b.querySelector(".t").textContent = fmt(c.start);
    b.querySelector(".n").textContent = c.title;
    b.onclick = () => { v.currentTime = c.start; v.play(); };
    li.appendChild(b); list.appendChild(li);
    const tick = document.createElement("div");
    tick.className = "tick"; tick.style.left = (100 * c.start / data.duration) + "%";
    tick.title = c.title; if (i) bar.appendChild(tick);
    return b;
  });
  const current = () => {
    let k = 0;
    chs.forEach((c, i) => { if (v.currentTime + 0.05 >= c.start) k = i; });
    return k;
  };
  const update = () => {
    const k = current();
    buttons.forEach((b, i) => b.setAttribute("aria-current", i === k ? "true" : "false"));
    fill.style.width = (100 * v.currentTime / dur()) + "%";
    now.textContent = chs[k].title + " · " + fmt(v.currentTime) + " / " + fmt(dur());
  };
  document.getElementById("prev").onclick = () => {
    const k = current(); const back = v.currentTime - chs[k].start > 1.5 ? k : k - 1;
    v.currentTime = chs[Math.max(0, back)].start; };
  document.getElementById("next").onclick = () => {
    const k = current(); if (k + 1 < chs.length) v.currentTime = chs[k + 1].start; };
  bar.onclick = e => { const r = bar.getBoundingClientRect();
                       v.currentTime = dur() * (e.clientX - r.left) / r.width; };
  if (data.captions.length && window.VTTCue) {
    const track = v.addTextTrack("captions", "Captions", "en");
    data.captions.forEach(c => track.addCue(new VTTCue(c.start, c.end, c.text)));
    track.mode = "showing";
  }
  const chTrack = v.addTextTrack("chapters", "Chapters", "en");
  chs.forEach((c, i) => chTrack.addCue(new VTTCue(c.start, i + 1 < chs.length ?
                                                  chs[i + 1].start : data.duration, c.title)));
  v.addEventListener("timeupdate", update);
  v.addEventListener("loadedmetadata", update);
  document.addEventListener("keydown", e => {
    if (e.target.tagName === "INPUT") return;
    if (e.key === "]") document.getElementById("next").click();
    if (e.key === "[") document.getElementById("prev").click();
  });
  update();
})();
</script>
</body>
</html>
"""


def slice_timeline(timeline: dict[str, Any], start: int, end: int) -> dict[str, Any]:
    """The part of a timeline between two frames, re-based to start at 0 (range exports)."""
    events = []
    for e in timeline.get("events", []):
        if e["end_frame"] < start or e["start_frame"] > end:
            continue
        events.append(
            {
                **e,
                "start_frame": max(0, e["start_frame"] - start),
                "end_frame": min(end, e["end_frame"]) - start,
            }
        )
    return {**timeline, "events": events, "duration_frames": max(0, end - start)}
