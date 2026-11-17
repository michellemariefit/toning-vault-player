"""
Build data/vault.json from the Toning Vault workout PDFs (tools/pdf/*.pdf).

    python tools/build_workouts.py

Files: flf-1.pdf flf-2.pdf flf-1-home.pdf  tt-1..4.pdf tt-1..3-home.pdf
       ml-1..5.pdf ml-1..5-home.pdf  mb-1..5.pdf mb-1..5-home.pdf

Each PDF is one workout of up to 3 days. Every exercise cell has a photo and a name, both
linking to the YouTube demo, plus REPS / SETS / REST / TEMPO. Home PDFs add
"Home Version: <name>" under some exercises with its own link.
"""
import io, json, os, re, sys, glob
import pymupdf
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import swaps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = os.path.join(ROOT, "tools", "pdf")
IMAGES = os.path.join(ROOT, "images")
OUT = os.path.join(ROOT, "data", "vault.json")
YT = re.compile(r"(?:youtu\.be/|v=)([A-Za-z0-9_-]{11})")

# The Toning Ladder, one step per phase. Reps/sets/rest come from the workouts themselves (the Ladder PDF
# quotes different rep ranges for steps 3 and 4; the workouts win).
SERIES = [
    {"id": "flf", "step": 1, "name": "Fat Loss Foundation", "short": "Foundation", "tag": "Wake the body up",
     "files": ["flf-1", "flf-2"], "reps": "20-30 reps", "load": "Lowest weight you'll use", "restNote": "Rest 30 sec or less",
     "quote": "Start here. Lay the foundation.", "outcomes": "Build endurance · Burn fat · Wake up your muscles",
     "about": "Full body, high reps, light weight, pulses. This is the metabolic on-ramp: you're priming the whole system."},
    {"id": "tt", "step": 2, "name": "Toning Transformation", "short": "Toning", "tag": "Sculpt and shape",
     "files": [f"tt-{n}" for n in range(1, 5)], "reps": "20 reps", "load": "Slightly heavier", "restNote": "Rest 60 sec after each circuit",
     "quote": "Time to tighten and tone.", "outcomes": "Sculpt and shape muscle · Increase definition · Boost metabolism",
     "about": "Separate body parts. Lighter load, higher control. This is where the definition shows up."},
    {"id": "ml", "step": 3, "name": "Muscle Leaning", "short": "Leaning", "tag": "Build the burn",
     "files": [f"ml-{n}" for n in range(1, 6)], "reps": "12-15 reps", "load": "Heavy and challenging", "restNote": "Rest 60 to 90 sec",
     "quote": "Level up strength and leanness.", "outcomes": "Build lean muscle · Fire up fat burn · Prevent plateaus",
     "about": "Separate body parts, heavier load. You should still feel the burn, but the load is doing more of the work than the volume."},
    {"id": "mb", "step": 4, "name": "Muscle Building", "short": "Building", "tag": "Get strong",
     "files": [f"mb-{n}" for n in range(1, 6)], "reps": "8-12 reps, pyramids and drop sets", "load": "Your strongest lifts of the cycle", "restNote": "Rest 60 to 90 sec",
     "quote": "Biggest strength gains happen here.", "outcomes": "Maximize strength · Add fullness and shape · Keep metabolism high",
     "about": "Heaviest weight you can move with clean form. Lowest rep range. Small body parts in isolation. This is where the shape gets locked in."},
]
RESET = {"id": "reset", "step": 5, "name": "Reset & Supercompensation", "short": "Reset", "tag": "Recover. Climb again.",
     "reps": "20-30 reps, light", "load": "Light. Then return to Step 1.", "restNote": "",
     "quote": "Circle back stronger.", "outcomes": "Recover and refresh · Shock your body · Accelerate results",
     "about": "Lower volume: 2 or 3 sets, light weight, or a full-body Foundation day. Then start the climb again at Step 1. Phase 5 is where the results from the last 3 months show up."}


NAME_FIX = {"Hammer": "Hammer Curl", "Puhsups": "Pushups", "Jacknife": "Jackknife", "Leg Extensións": "Leg Extensions",
            "Overhead Extensión": "Overhead Extension", "Rope Overhead Extensión": "Rope Overhead Extension"}


def tempo_seconds(t):
    """'201' -> 3 seconds a rep. '201-101' (pulses) -> 3."""
    m = re.match(r"(\d)(\d)(\d)", t or "")
    return (int(m.group(1)) + int(m.group(2)) + int(m.group(3))) if m else 3


def minutes(day):
    """Rough length of a day: reps x tempo per set, plus rest, plus a little shuffling between exercises."""
    sec = 0
    for b in day["blocks"]:
        for e in b["exercises"]:
            nums = [int(x) for x in re.findall(r"\d+", e["reps"])]
            reps = (sum(nums) / len(nums)) if nums else 20
            if "-" in e["reps"] and len(nums) > 2: reps = sum(nums)      # pyramids and drop sets list every mini-set
            sets = 1 if len(nums) > 2 else (e["sets"] or 1)
            per = reps * tempo_seconds(e["tempo"]) + (30 if "sec" in e["reps"] else 0) + 12
            sec += sets * per + sets * e["restSeconds"]
    return int(round(sec / 60 / 5.0)) * 5 or 5


def yt(uri):
    m = YT.search(uri or "")
    return m.group(1) if m else None


STAT_LINE = re.compile(r"(?i)^([\d`\-\s]+\s*(s|sec|secs|seconds)?|per|side|p/s|top|half|-|\*|each|active|rest\s*\d+s?|sec|secs|seconds)$")
NOTE_END = re.compile(r"(?i)\s*((and\s+)?isometric\s+hold\s*(\w+\s+)?\d+s?|(and\s+)?hold\s*\d+s?|isometric|pyramid set(\s*\(.*?\))?|21[’']s|1\s*½|1\s*1/2|drop set)\s*$")


def parse_stats(tokens):
    """Tokens of the REPS / SETS / REST / TEMPO cells, parsed from the right.
    ['20-','30','2','30s','201-','101'] -> reps 20-30, sets 2, rest 30, tempo 201-101
    ['10-','10-','10','4','0','311']   -> reps 10-10-10 (pyramid), sets 4
    ['20-','19-','15','-','-','111']   -> reps 20-19-15 (drop set), sets 0"""
    t = []
    for x in " ".join(tokens).replace("p/s", "per side").replace("seconds", "sec").split(" "):
        x = x.strip()
        if x and x != "*": t.append(x)
    tempo = []
    while t and re.fullmatch(r"\d{3}-?", t[-1]):
        tempo.insert(0, t.pop())
    if not tempo and len(t) >= 3 and t[-1] == "-":
        t.pop()
    rest, active = "", False
    if t and t[-1].lower() in ("sec", "secs", "s"):
        t.pop()
    if t and re.fullmatch(r"(?i)`?\d+\s*(s|sec)?|-|rest\s*\d+s?", t[-1]):
        rest = re.sub(r"(?i)rest", "", t.pop().lstrip("`")).strip()
    if t and t[-1].lower() in ("active", "rest"):
        active = True
        while t and t[-1].lower() in ("active", "rest"): t.pop()
    sets = 0
    if t and re.fullmatch(r"\d", t[-1]):
        sets = int(t.pop())
    elif t and t[-1] == "-":
        t.pop()
    reps = " ".join(t)
    reps = re.sub(r"-\s+", "-", reps).replace(" -", "-").strip()
    rest_s = int(re.sub(r"\D", "", rest) or 0)
    out = {"reps": reps, "sets": sets, "restSeconds": rest_s, "tempo": "".join(tempo).strip("-")}
    if active: out["activeRest"] = True
    return out


def split_note(name):
    """'Pushups Isometric Hold 20s' -> ('Pushups', 'Isometric Hold 20s')"""
    notes = []
    while True:
        m = NOTE_END.search(name)
        if not m or not m.group(1) or m.start() == 0:
            break
        notes.insert(0, m.group(1).strip()); name = name[:m.start()].strip()
    return name.strip(" ,"), " ".join(notes)


def parse_pdf(path):
    doc = pymupdf.open(path)
    out = []          # exercises in page order
    day = 0
    for page in doc:
        links = [(pymupdf.Rect(l["from"]), yt(l.get("uri"))) for l in page.get_links() if yt(l.get("uri"))]
        images = [(pymupdf.Rect(i["bbox"]), i["xref"]) for i in page.get_image_info(xrefs=True)
                  if i["xref"] and i["width"] < 1000]
        blocks = []
        CODE = re.compile(r"^([A-E])\s?(\d)\s?\.\s*(.*)$")
        for b in page.get_text("blocks"):
            if b[6] != 0: continue
            lines = [re.sub(r"\s+", " ", x).strip() for x in b[4].split("\n")]
            lines = [x for x in lines if x]
            if not lines: continue
            # a name glued onto a stats block from the other column: split it off
            idx = [i for i, x in enumerate(lines) if i > 0 and CODE.match(x)]
            if idx:
                i = idx[0]
                hits = page.search_for(lines[i])
                if hits:
                    blocks.append((hits[0], lines[i:]))
                    lines = lines[:i]
            blocks.append((pymupdf.Rect(b[:4]), lines))
        blocks.sort(key=lambda b: (round(b[0].y0), b[0].x0))
        col = lambda r: 0 if r.x0 < 300 else 1
        names, stats, extras, days, used = [], [], [], [], set()
        for r, lines in blocks:
            first = lines[0]
            m = CODE.match(first)
            if re.fullmatch(r"DAY \d", first):
                days.append((r.y0, int(first[-1]))); continue
            if first.startswith("EXERCISE") or first.startswith("©"): continue
            if m:
                names.append({"rect": r, "code": m.group(1) + m.group(2), "name": " ".join([m.group(3)] + lines[1:]).strip(),
                              "col": col(r), "extra": [], "home": ""})
                continue
            if all(STAT_LINE.match(x) for x in lines):
                stats.append((r, lines)); continue
            extras.append((r, lines))
        for ex in names:
            r = ex["rect"]
            # day: latest DAY header above the name on this page, else carry
            above = [d for (y, d) in days if y < r.y0]
            if above: day = above[-1]
            ex["day"] = day
            vids = [v for (lr, v) in links if lr.intersects(r)]
            ex["video"] = vids[0] if vids else None
            # stats: nearest stats block above in same column
            # stats: every stats block in this column in the band above the name
            band = [(sr, lines) for (sr, lines) in stats
                    if col(sr) == ex["col"] and sr.y0 < r.y0 and sr.y0 >= r.y0 - 95 and id(sr) not in used]
            band.sort(key=lambda b: b[0].x0)
            ex["stats"] = [x for (sr, lines) in band for x in lines]
            for sr, _ in band: used.add(id(sr))
            # extras: lines right below the name in the same column. Each one continues
            # whatever sits directly above it (the name or a Home Version line).
            last, last_rect = "name", r
            for er, lines in sorted(extras, key=lambda e: e[0].y0):
                if col(er) != ex["col"] or not (-4 <= er.y0 - last_rect.y1 < 14):
                    continue
                txt = " ".join(lines)
                parts = re.split(r"(?i)home version\s*:\s*", txt)
                if parts[0].strip():
                    gap = er.y0 - last_rect.y1
                    if last == "home" and gap < 8:
                        ex["home"] += " " + parts[0].strip()
                    else:
                        ex["name"] += " " + parts[0].strip()
                if len(parts) > 1:
                    hv = [v for (lr, v) in links if lr.intersects(er)]
                    ex["home"] = parts[1].strip(); last = "home"
                    if hv: ex["homeVideo"] = hv[0]
                last_rect = er
            # photo: nearest image above the name in same column
            ic = [(ir.y1, xref, ir) for (ir, xref) in images if col(ir) == ex["col"] and ir.y1 <= ex["rect"].y0 + 14]
            if ic:
                y1, xref, ir = max(ic, key=lambda t: t[0])
                if ex["rect"].y0 - y1 < 40 and ex["video"]:
                    outp = os.path.join(IMAGES, f"{ex['video']}-pdf.webp")
                    if not os.path.exists(outp):
                        raw = doc.extract_image(xref)["image"]
                        im = Image.open(io.BytesIO(raw)).convert("RGB")
                        im.save(outp, "WEBP", quality=84)
                    ex["photo"] = "images/" + os.path.basename(outp)
            out.append(ex)
    return out


def build(file_id, series, home):
    exs = parse_pdf(os.path.join(PDF, file_id + ".pdf"))
    days = {}
    for e in exs:
        s = parse_stats(e["stats"])
        nm = re.sub(r"\s+", " ", e["name"]).replace(" seconds", " sec").replace(" p/s", " per side").rstrip(" *")
        toks = nm.split(" ")
        tail = []
        while len(toks) > 1 and (STAT_LINE.match(toks[-1]) or toks[-1].lower() in ("top", "half")):
            tail.insert(0, toks.pop())
        if tail and len(tail) >= 2 and not e["stats"]:
            e["stats"] = tail; s = parse_stats(tail); nm = " ".join(toks)
        name, note = split_note(nm)
        name = NAME_FIX.get(name, name)
        item = {"code": e["code"], "name": name, "video": e["video"], **s}
        if note:
            item["note"] = note
        if e["home"]:
            hn, hnote = split_note(re.sub(r"\s+", " ", e["home"]))
            item["homeName"] = hn; item["homeVideo"] = e.get("homeVideo")
            if hnote and hnote != note: item["homeNote"] = hnote
        if e.get("photo"):
            item["photo"] = e["photo"]
        days.setdefault(e["day"], []).append(item)
    out_days = []
    for dn in sorted(days):
        items = sorted(days[dn], key=lambda i: (i["code"][0], int(i["code"][1])))
        blocks = []
        for it in items:
            if not blocks or blocks[-1]["label"] != it["code"][0]:
                blocks.append({"label": it["code"][0], "exercises": []})
            blocks[-1]["exercises"].append(it)
        for b in blocks:
            for it in b["exercises"]:
                it["row"] = swaps.row_for(it["name"]) or ""
                if it.get("homeName"): it["homeRow"] = swaps.row_for(it["homeName"]) or ""
        d = {"id": f"{file_id}-d{dn}", "day": dn, "blocks": blocks}
        d["minutes"] = minutes(d)
        d["n"] = sum(len(b["exercises"]) for b in blocks)
        out_days.append(d)
    return {"id": file_id, "series": series["id"], "home": home, "days": out_days}


def main():
    data = {"phases": [], "reset": RESET, "swaps": swaps.rows()}
    problems = []
    for s in SERIES:
        ws = []
        for f in s["files"]:
            for home in (False, True):
                fid = f + ("-home" if home else "")
                if not os.path.exists(os.path.join(PDF, fid + ".pdf")):
                    continue
                w = build(fid, s, home)
                n = int(f.split("-")[1])
                w["number"] = n
                w["name"] = f"{s['short']} {n}" + (" · Home" if home else "")
                w["base"] = f
                if home:
                    nxt = next(x for x in ws if x["id"] == f); nxt["homeId"] = fid
                ws.append(w)
                for d in w["days"]:
                    for b in d["blocks"]:
                        for e in b["exercises"]:
                            if not e["video"] or not e.get("sets") or not e.get("photo"):
                                problems.append((fid, d["day"], e["code"], e["name"], e["video"], e.get("sets"), e.get("photo")))
        data["phases"].append({**{k: v for k, v in s.items() if k != "files"}, "workouts": ws})
    # start/end pairs made by tools/split_photos.py
    pairs = {os.path.basename(f)[:-len("-start.webp")] for f in glob.glob(os.path.join(IMAGES, "*-start.webp"))}
    data["pairs"] = sorted(pairs)
    for p in data["phases"]:
        for w in p["workouts"]:
            for d in w["days"]:
                for b in d["blocks"]:
                    for e in b["exercises"]:
                        if e.get("video") in pairs:
                            e["startPhoto"] = f"images/{e['video']}-start.webp"; e["endPhoto"] = f"images/{e['video']}-end.webp"
    json.dump(data, open(OUT, "w"), indent=1)
    print("wrote", OUT)
    for p in problems: print("PROBLEM", p)


if __name__ == "__main__":
    main()
