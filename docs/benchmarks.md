# Benchmarks

Measurements against spec §9 targets. Re-run after any runner, cache or Manim change and
add a dated section; keep old sections for comparison.

```bash
uv run python benchmarks/preview_latency.py --json benchmarks/results-<date>-<machine>.json
uv run python benchmarks/profile_frames.py 1920 1080 30   # draw vs PNG cost per frame
```

## 2026-11-26 — Windows 11 reference machine

- **Machine:** Windows 11 (10.0.26100), Intel 64 Family 6 Model 158 (16 logical CPUs), Python 3.13.5.
- **Manim:** `main@8c258a0`. **manim-stage:** backlog 0.6 branch.
- **Scene:** `benchmarks/reference_scene.py`: 10.6 s teaching scene with `Text`, bars, swaps and `LaggedStart`. No LaTeX.
- **Raw results:** `benchmarks/results-2026-11-26-win11.json`.

| Case | Workers | Timeline ready | All frames cached (cold) | Warm rerun (cache hit) | Seek median / p95 | PNG/frame |
|---|---|---|---|---|---|---|
| 720p30 | 1 | 2.5 s | 11.6 s | 1.4 s | 6.4 / 8.7 ms | 47 kB |
| 1080p30 | 1 | 1.1 s | 17.9 s | 1.3 s | 8.5 / 11.0 ms | 95 kB |
| 1080p30 | 4 | 2.2 s | **8.0 s** | 1.4 s | 8.6 / 11.6 ms | 95 kB |
| 1080p30 | 8 | 2.6 s | **6.8 s** | 1.4 s | 8.5 / 11.0 ms | 95 kB |

- **Timeline ready:** seconds from child start until the timeline message. The editor can show structure from this point.
- **Seek:** cache lookup + PNG decode for a random frame, server side. The browser transfer is not included.

### Against spec §9

| Target | Result | Verdict |
|---|---|---|
| First usable cached preview, simple 10 s 1080p scene ≤ 10 s | 17.9 s with 1 worker; **8.0 s with 4**, 6.8 s with 8. The timeline is shown after ~1–2.5 s, and frames stream in from then on. | **Met with ≥4 workers.** Default to `min(4, cpus/2)` workers. |
| Scrub median ≤ 100 ms on cached frames at 720p | 6.4 ms (720p), 8.5 ms (1080p) | **Met** with a large margin (excluding browser transfer). |
| Bounded cache with LRU eviction | `FrameCache.trim` evicts by budget and protects the current revision; tested | Met. Disk budget only; there is no in-memory cache yet. |

### Where the time goes (1080p30, single worker, `profile_frames.py`)

- About 25 ms/frame drawing (Cairo), 17 ms/frame PNG encode, and about 13 ms/frame other overhead (array→PIL, file write, protocol message). Timeline-only evaluation is 0.4 s.
- PNG `compress_level` 1 vs 6 barely differs (16.6 vs 17.2 ms), so encoding cost is filtering, not compression.
- Parallel speed-up is sub-linear: each worker replays the scene (0.4 s) and pays Python start-up + `import manim` (~0.75 s).

### Findings that changed the design

1. **Manim's `media_dir` is not safe for concurrent runners.** `Text` caches SVGs in `media_dir/texts` without locking, and a parallel run left a 0-byte SVG that broke every later run (`ParseError: no element found`). Fix: each shard gets its own `media_dir` (`<cache>/.media/shard-<i>`). Worth reporting upstream.
2. **Cache trim must tolerate concurrent writers.** Trim stat'ed another worker's temp file mid-rename. Fixed: only committed frames are considered, vanished files are tolerated, and there's a regression test.
3. The first run of a scene that uses `Text` is slower (Pango → SVG generation); later runs reuse `media_dir/texts`.

### Next optimisations (not needed for the targets; revisit in M1)

- Encode previews as WebP/JPEG or uncompressed BMP to cut ~17 ms/frame. Golden parity tests keep PNG.
- A persistent warm worker pool, to avoid re-import per revision. This conflicts with ADR-0004's fresh-process rule, so a pool would need per-revision fork/spawn hygiene.
- Draw visible-range frames first (seek-priority ordering).
