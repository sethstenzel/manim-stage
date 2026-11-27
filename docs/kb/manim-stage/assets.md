# Assets and environment checks

- **Status:** Available
- **Renderer:** Both
- **Since:** PR #30
- **Spec:** F10 · **Backlog:** 3.5, MF.9 · **Source:** `src/manim_stage/assets.py`, `doctor.py`, `studio/ui/assets_panel.py`
- **Motion Canvas origin:** the editor's media handling (imported images, audio and video assets). **Built on:** Manim's own path resolution (`seek_full_path_from_defaults`: the path as given, else `assets_dir` + name + the default extensions of `ImageMobject`, `SVGMobject` and `add_sound`), and Pango's font list.

## What it is

A missing image or font should fail before a ten-minute render, not halfway through it. manim-stage lists every asset your scene refers to and checks each one exists, resolving names exactly as Manim will. The Studio's **Assets** tab also shows what this machine can render: LaTeX, fonts, encoders, audio.

## Quick start

```bash
manim-stage assets lesson.py            # table; exit code 1 if something is missing
manim-stage assets lesson.py --json     # for CI
```

```python
from pathlib import Path

from manim_stage.assets import format_report, inventory

Path("pics.py").write_text('''
from manim import *

class Pics(Scene):
    def construct(self):
        self.add(ImageMobject("logo"))         # Manim also tries logo.png, .jpg etc.
        self.add_sound("click.wav")
''')
inv = inventory(["pics.py"])
print(format_report(inv))
assert {r.name for r in inv.missing} == {"logo", "click.wav"}
```

In the Studio, open the **Assets** tab and press **Check assets**:
- ✔ means found, ⚠ missing, … computed at run time. Double-click to open the file's folder.
- **Add asset…** copies a file into `assets/images|svg|audio|video|fonts|data/` and copies the matching Manim call to the clipboard, e.g. `ImageMobject("assets/images/logo.png")`.
- **Exporting** checks assets first and warns about anything missing.

## How it works

**References are found statically in the scene file:**
- the first argument of `ImageMobject`, `SVGMobject` and `self.add_sound`;
- `file=` of `self.narration`;
- `font=` of `Text`, `MarkupText`, `Paragraph`, `Code` and `AnimatedCode`, checked against Pango's fonts;
- plus the clip files of the [audio workspace](audio.md).

Names computed at run time (variables, f-strings) are listed as dynamic. The [runner](runner.md)'s dependency tracking still records what a render actually opened.

**Resolution** follows Manim: the path as written, relative to the folder you render from (the scene's folder in the Studio and `compose`), else `assets_dir` (default `./`) + name + default extensions.

## Render presets

The [Export](export.md) dialog has a **Preset** list:
- Manim's quality presets;
- 1080p30 and 4K30 (via `-r W,H --fps N`);
- transparent MOV 1080p30 (ProRes 4444 with alpha);
- GIF 480p15.

The exact `manim render` command is still shown. In code: `PRESETS["4k30"].apply(ExportSettings())`.

## Environment

The Assets tab lists the same checks as [`manim-stage doctor`](cli.md#commands):
- the Manim build and its required APIs;
- Cairo, and Pango fonts (`Text`);
- LaTeX + dvisvgm (`Tex`/`MathTex`);
- an FFmpeg encoder for each export format;
- PySide6, preview audio output, and installed Manim plugins.

## Limitations and unsupported cases

- **Imported modules aren't scanned.** References in helper modules aren't found statically, but they *are* tracked as dependencies once rendered.
- **Colour-space handling is Manim's:** sRGB with `yuv420p` for MP4/WebM, and alpha only for MOV/WebM/PNG. manim-stage reports what was written (pixel format, nominal vs average fps, so variable frame rates are flagged) and doesn't convert.

## Related

- [Export](export.md), [Audio workspace](audio.md), [CLI](cli.md), [Data formats](../reference/data-formats.md).
