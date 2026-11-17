"""Map every Vault exercise to a row of the Vault Coach exercise matrix (tools/coach/gym.csv),
so the player can offer swaps that keep the same movement pattern and muscles.
Rules are regexes on the lowercased exercise name, first match wins."""
import csv, re, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES = [
    (r"plie", "Plie Squat"), (r"jump squat|split jump", "Jump Squat"), (r"single leg squat|split squat", "Split Squat"),
    (r"leg press|leg extensi|band squat|squat", "Squat"), (r"step.?up", "Step-Up"),
    (r"stationary lunge", "Stationary Lunge"), (r"lateral lunge", "Lateral Lunge"), (r"curtsy|bowler", "Curtsy Lunge"),
    (r"lunge", "Reverse Lunge"), (r"deadlift", "Deadlift"), (r"leg curl", "Stability Ball Leg Curl"),
    (r"hip|cable kick", "Stability Ball Hip Extension"), (r"glute bridge|bridge", "Hip Thrust"),
    (r"abduction", "Stability Ball Abductions"),
    (r"incline.*press|incline press", "Incline DB Press"), (r"decline.*press", "Decline DB Press"), (r"push.?up|puhsup", "Push-Up"),
    (r"rear delt|reverse fly|swimmer", "High Row"), (r"fly", "Cable Fly"), (r"chest press|dumbbell press|tubing press", "Dumbbell Press"),
    (r"shoulder press", "Shoulder Press"), (r"upright row", "Upright Row"), (r"lateral raise", "Lateral Raise"),
    (r"front raise|arm raise", "Front Raise"), (r"around the world", "Around the World"),
    (r"high row", "High Row"),
    (r"lat pulldown|tubing pulldown", "Lat Pulldown"), (r"straight.?arm|lying pull|lying leg pull", "Straight-Arm Pulldown"),
    (r"cable row|rope row|standing row|cable bent", "Cable Row"), (r"bent.?over|barbell row", "Bent-Over Row"), (r"dumbbell row", "Single Arm DB Row"),
    (r"hammer", "Hammer Curl"), (r"barbell curl", "Barbell Curl"), (r"twisting curl|incline dumbbell curl|incline curl", "Incline Curl"),
    (r"curl", "DB Curl"),
    (r"skull", "Skull Crusher"), (r"overhead", "Overhead Extension"), (r"kickback", "Kickback"),
    (r"pulldown|pull down|pushdown", "Rope Pulldown"),
    (r"side plank|starfish", "Side Plank"), (r"arm walk", "Arm Walks"), (r"plank", "Plank"), (r"dip", "Dips"),
    (r"jacknife|jackknife|v-up|knee tuck", "Jackknife"), (r"reverse.*crunch|reverse oblique", "Reverse Crunch"),
    (r"leg.*raise", "Hanging Leg Raise"), (r"rollout|transfer", "Stability Ball Rollout"), (r"twist|woodchop", "Woodchop"),
    (r"rolldown|roll-down", "Decline Roll-Down"), (r"extend", "Stability Ball Extend & Crunch"), (r"scoop", "Scoop with Slides"),
    (r"skier", "Skiers"), (r"bounce", "Plank"),
]


def rows():
    out = {}
    with open(os.path.join(ROOT, "tools", "coach", "gym.csv"), newline="") as f:
        for r in csv.DictReader(f):
            out[r["Primary Exercise"]] = {
                "group": r["Movement Pattern"].replace(" – ", " · ").title().replace("Db", "DB"),
                "muscles": r["Primary Muscles"], "equipment": r["Equipment"],
                "variations": [v.strip() for v in r["Approved Variations"].split("/")],
                "home": r["Default Home Swap"], "gym": r["Default Gym Swap"]}
    return out


def row_for(name):
    n = name.lower()
    for pat, key in RULES:
        if re.search(pat, n):
            return key
    return None
