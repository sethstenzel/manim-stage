from pathlib import Path
import numpy as np
from PIL import Image
cli = {int(p.stem): p for p in Path("media/images/spike/Lesson").glob("*.png")}
print("cli frames:", len(cli), "max index", max(cli))
for f in sorted(Path("frames").glob("eval_*.png")):
    i = int(f.stem.split("_")[1])
    if i not in cli: print(i, "not in CLI png-sequence"); continue
    a = np.asarray(Image.open(f).convert("RGBA"), dtype=int); b = np.asarray(Image.open(cli[i]).convert("RGBA"), dtype=int)
    print(i, "max abs diff:", int(np.abs(a - b).max()), "differing px:", int((a != b).any(-1).sum()))
