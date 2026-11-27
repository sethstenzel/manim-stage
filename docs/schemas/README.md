# Data and protocol contracts (spec §8)

JSON Schema 2020-12. Every document carries `schema` + `version` (or `v` for protocol messages). Readers reject versions they don't know. Writers never change a version's meaning: a breaking change is a new version plus a migration (see [Persistence rules](#persistence-rules)).

| Schema | Spec §8 name | Status | Produced / read by |
|---|---|---|---|
| [timeline.schema.json](timeline.schema.json) | `SceneEvent` (+ timeline wrapper) | **Implemented** | `manim_stage.capture` → editor |
| [runner-message.schema.json](runner-message.schema.json) | `PreviewMessage` (runner half) | **Implemented** | `python -m manim_stage.runner` stdout |
| [cues.schema.json](cues.schema.json) | `Cue` | Draft (backlog 2.1) | `.manim-stage/cues.json` |
| [project.schema.json](project.schema.json) | `ProjectManifest` | Draft (M1) | `.manim-stage/project.json` |
| [editable-property.schema.json](editable-property.schema.json) | `EditableProperty` | Draft (M3) | inspector |

`tests/test_schemas.py` validates real runner output and the [examples](examples/) against these schemas.

## Time model

- **Unit:** integer **frame index** at the scene's frame rate *r*. Frame *i* shows the scene at time `i / r` and covers `[i/r, (i+1)/r)`. This matches Manim's 0.30 clock.
- **Ranges:** half-open `[start_frame, end_frame)`. A zero-length marker (a section) has `start_frame == end_frame`. Duration in frames is `end - start`.
- **Seconds** are derived: `frame / r`. They are never accumulated: no `t += dt`. Floats appear only at the edges:
  - **seconds → frame** for a point in time: `floor(t*r + 1e-9)`;
  - **seconds → frame** for a span end: `ceil(t*r - 1e-9)`. This is Manim's `frame_count`.
- **Sounds** may start between frames. Their exact start is kept in seconds (`meta.start_seconds`) and their frame is `floor`. Audio sample position at 48 kHz (Manim's mixer): `round(seconds * 48000)`. One frame at 30 fps is 1600 samples.
- **Cue targets** are absolute frame indices from scene start, stored with the frame rate they were authored at. At another rate they are rescaled with `round(target * r_new / r_old)`, which is accurate to one frame (spec §9).
- **Non-integer frame rates** (e.g. 29.97) are carried as floats. Frame indices remain exact integers.

## IDs

- **Event IDs:** `scene:kind:path:line#occurrence`; nested animations append `/index` (ADR-0005). They are deterministic for the same source. They change when lines move. Stable IDs across edits are planned with F03.
- **Revision IDs:** hex hashes of scene file + scene name + settings + Manim build (`manim_stage.framecache.revision_key`). They are validated with `^[0-9a-f]{16,64}$` before use in paths.

## Persistence rules

These apply to every file manim-stage writes in a project.

- **Atomic writes:** write a temp file in the same folder, then rename it over the target.
- **Before migrating a file to a new schema version:** copy it to `<name>.v<old>.bak`. Migrations are pure functions `vN → vN+1`, tested on example files.
- **Corrupt or unknown-version files are never overwritten.** The editor reports them and offers to restore the backup.
- **Paths are project-relative POSIX.** Absolute paths, drive letters, backslashes and `..` segments are rejected (`project.schema.json` `RelPath`).
- **No secrets** (tokens, API keys) in any project file.
