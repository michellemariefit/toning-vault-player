"""Split the PDF composite photos (start photo top-left, end photo bottom-right, pink arrow) into
images/<id>-start.webp and images/<id>-end.webp, so the player can show a clean Start / End pair."""
import glob, os
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGES = os.path.join(ROOT, "images")


def groups(idx):
    out = []
    for i in idx:
        if out and i - out[-1][-1] <= 1: out[-1].append(i)
        else: out.append([i])
    return out


def split(path):
    im = Image.open(path).convert("RGB")
    if im.size != (450, 252): return False
    a = np.array(im).astype(int); white = a.min(axis=2) > 225
    cg = groups([i for i, v in enumerate(white.mean(axis=0)) if v > 0.45])
    rg = groups([i for i, v in enumerate(white.mean(axis=1)) if v > 0.45])
    if len(cg) < 3 or len(rg) < 3: return False
    sl, st = cg[0][-1] + 1, rg[0][-1] + 1
    el, et, er, eb = cg[1][-1] + 1, rg[1][-1] + 1, cg[-1][0] - 1, rg[-1][0] - 1
    sb = (rg[2][0] - 1) if len(rg) >= 4 else st + 117
    start = im.crop((sl, st, el - 2, sb)); end = im.crop((el, et, er, eb))
    base = path[:-len("-pdf.webp")]
    start.save(base + "-start.webp", "WEBP", quality=86); end.save(base + "-end.webp", "WEBP", quality=86)
    return True


if __name__ == "__main__":
    n = 0
    for f in sorted(glob.glob(os.path.join(IMAGES, "*-pdf.webp"))):
        if split(f): n += 1
    print("split", n)
