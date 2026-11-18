"""
Sharper Start / End photos from the original FMFL exercise clips.

For every exercise video id that has a PDF pair (images/<id>-start.webp and -end.webp, cut out of the
PDF composites by split_photos.py), find the matching clip in tools/clipmap.json, sample it at 3 frames
a second, and pick the two frames that look most like the PDF's start and end photos. Those frames are
saved full size as the new images/<id>-start.webp and -end.webp (the PDF versions move to -pdfstart/-pdfend).

    python tools/clip_frames.py --clips /home/user/vault-src/clips [--ids id1,id2] [--force]

tools/clip_overrides.json can pin a clip and seconds by hand: {"<id>": ["Clip name.mp4", 3.0, 5.5]}.
Writes tools/clip_frames.json with what was chosen and the match scores, for review.
"""
import argparse, io, json, os, shutil, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGES = os.path.join(ROOT, "images")
MAP = json.load(open(os.path.join(ROOT, "tools", "clipmap.json")))
OVR_PATH = os.path.join(ROOT, "tools", "clip_overrides.json")
OVR = json.load(open(OVR_PATH)) if os.path.exists(OVR_PATH) else {}
OUT_JSON = os.path.join(ROOT, "tools", "clip_frames.json")
FPS = 3
TW, TH = 96, 62           # comparison size, about the PDF crop's shape


def prep(im):
    """grayscale, center-crop to the template shape, small, blurred, zero-mean unit-var"""
    im = im.convert("L")
    w, h = im.size
    want = TW / TH
    if w / h > want:
        nw = int(h * want); im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = int(w / want); im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    a = np.asarray(im.resize((TW, TH)).filter(ImageFilter.GaussianBlur(1)), dtype=np.float32)
    a -= a.mean(); s = a.std() or 1
    return a / s


def ncc(a, b):
    return float((a * b).mean())


def sample(clip, tmp):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", clip, "-vf", f"fps={FPS},scale=192:-2", os.path.join(tmp, "f%05d.jpg")])
    if r.returncode: print("bad clip", os.path.basename(clip))
    return sorted(os.listdir(tmp))


def grab(clip, sec, out):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{sec:.3f}", "-i", clip, "-frames:v", "1", "-vf", "scale=960:-2", out], check=True)
    im = Image.open(out).convert("RGB"); im.save(out, "WEBP", quality=86)


def best_frames(clip, t_start, t_end):
    with tempfile.TemporaryDirectory() as tmp:
        frames = sample(clip, tmp)
        if not frames: return None
        raw = [Image.open(os.path.join(tmp, f)) for f in frames]
        arrs = [prep(im) for im in raw]
        ss = np.array([ncc(a, t_start) for a in arrs]); es = np.array([ncc(a, t_end) for a in arrs])
        # fades: the first second, the last two seconds, and any near-black frame are out
        dark = np.array([np.asarray(im.convert("L")).std() < 12 for im in raw])
        bad = dark.copy(); bad[:FPS] = True; bad[-2 * FPS:] = True
        ss[bad] = -9; es[bad] = -9
        # the background is the same in both photos, so score each frame by how much more it looks like
        # one pose than the other; the start frame is the most start-like, the end frame the most end-like
        # within the next five seconds (one rep or two)
        d = np.where(bad, -9, ss - es)
        i = int(np.argmax(d))
        lo, hi = i + 2, min(len(es), i + FPS * 5)
        de = np.where(bad, -9, es - ss)
        j = (lo + int(np.argmax(de[lo:hi]))) if hi > lo else int(np.argmax(de))
        if de[j] <= 0:   # nothing after the start looks more like the end: take the best end frame anywhere
            j2 = int(np.argmax(de))
            if abs(j2 - i) >= 2: j = j2
        return {"start": i / FPS, "end": j / FPS, "sStart": float(ss[i]), "sEnd": float(es[j]), "n": len(frames)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", required=True); ap.add_argument("--ids", default=""); ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    data = json.load(open(os.path.join(ROOT, "data", "vault.json")))
    ids = a.ids.split(",") if a.ids else [v for v in data["pairs"] if v in MAP]
    results = json.load(open(OUT_JSON)) if os.path.exists(OUT_JSON) else {}
    for vid in ids:
        if vid not in MAP:
            print("no clip mapped:", vid); continue
        ps = os.path.join(IMAGES, f"{vid}-pdfstart.webp"); pe = os.path.join(IMAGES, f"{vid}-pdfend.webp")
        if not os.path.exists(ps):   # keep the PDF crops as the templates
            shutil.copy(os.path.join(IMAGES, f"{vid}-start.webp"), ps); shutil.copy(os.path.join(IMAGES, f"{vid}-end.webp"), pe)
        if vid in results and not a.force and vid not in OVR:
            continue
        t_start, t_end = prep(Image.open(ps)), prep(Image.open(pe))
        if vid in OVR and OVR[vid][1] is not None:
            name, s, e = OVR[vid]; clip = os.path.join(a.clips, name)
            pick = {"clip": name, "start": s, "end": e, "sStart": None, "sEnd": None, "override": True}
        elif vid in OVR:   # clip pinned, seconds matched
            name = OVR[vid][0]; clip = os.path.join(a.clips, name)
            r = best_frames(clip, t_start, t_end); pick = {"clip": name, **r}
        else:
            pick = None
            for name in MAP[vid]:
                clip = os.path.join(a.clips, name)
                if not os.path.exists(clip): print("missing clip", name); continue
                r = best_frames(clip, t_start, t_end)
                if r and (pick is None or r["sStart"] + r["sEnd"] > pick["sStart"] + pick["sEnd"]):
                    pick = {"clip": name, **r}
            if not pick: print("no frames for", vid); continue
            clip = os.path.join(a.clips, pick["clip"])
        grab(clip, pick["start"], os.path.join(IMAGES, f"{vid}-start.webp"))
        grab(clip, pick["end"], os.path.join(IMAGES, f"{vid}-end.webp"))
        results[vid] = pick
        print(vid, pick["clip"], f"start {pick['start']:.2f}s end {pick['end']:.2f}s", "" if pick.get("override") else f"scores {pick['sStart']:.2f} {pick['sEnd']:.2f}")
        json.dump(results, open(OUT_JSON, "w"), indent=1)


if __name__ == "__main__":
    main()
