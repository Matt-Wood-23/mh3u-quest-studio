"""Reference tables + derived numbers for the editor (all from data/*.json).

- monster names (em-ID) and base HP
- item names (quest/save item id)
- the difficulty ("Nando") table: Nando bytes are row indexes, not percent
- Category flag labels, stage-placement legality, supply crates
"""
import json
import re
import struct
from collections import namedtuple
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def _load(name):
    with open(DATA / name, encoding="utf8") as f:
        return json.load(f)


_mon = _load("monsters.json")["monsters"]
MONSTERS = {int(k): v["name"] for k, v in _mon.items()}
BASE_HP = {int(k): v["base_hp"] for k, v in _mon.items() if v["base_hp"]}
ITEMS = _load("items_en.json")["items"]          # index == item id
_nando = _load("nando_table.json")
NANDO_ROWS = _nando["rows"]
_flags = _load("category_flags.json")
FLAG_BITS = _flags["bits"]
HP_CUT_MASK = int(_flags["hp_cut"]["mask"], 16)  # 0x00100010
HP_CUT = _flags["hp_cut"]["factor"]              # 0.55
_place = _load("em_stage_placement.json")
PLACEMENT = {int(k): set(v) for k, v in _place["placement"].items()}
MAP_TO_INTERNAL = {int(k): v for k, v in _place["quest_map_to_internal"].items()}
_supp = _load("supp_sets.json")
_supp = _supp["sets"] if "sets" in _supp else {   # older format: bare lists
    k: {"items": v, "used_by": []} for k, v in _supp.items()}
SUPP_SETS = {int(k): [(it["id"], it["qty"]) for it in v["items"]]
             for k, v in _supp.items()}
# Crate slot (0-39) of each item above. Slots matter: high-rank quests start
# with slots 0-7 only, and many crates leave some of those empty.
SUPP_SLOTS = {int(k): [it.get("slot", i) for i, it in enumerate(v["items"])]
              for k, v in _supp.items()}
SUPP_USERS = {int(k): v.get("used_by", []) for k, v in _supp.items()}
START_AREAS = {int(k): v for k, v in _load("start_areas.json")["maps"].items()}
# The game numbers areas internally; the map shows other numbers on some
# maps. Index = internal area, value = the map's number (0 = base camp).
AREA_SHOWN = {int(k): v for k, v in _load("area_labels.json")["maps"].items()}
_spawn = _load("spawn_tables.json")
SIZE_SPREAD = _spawn["size_spread"]     # [Sizeparam] -> [[weight, lo, hi]]
SPAWN_POINTS = {int(em): {int(st): recs for st, recs in per.items()}
                for em, per in _spawn["spawn_points"].items()}
_usage = _load("field_usage.json")
_inv = _load("invaders.json")
INVADER_LISTS = {int(k): v for k, v in _inv["lists"].items()}
INVADER_LIST_COUNT = _inv["count"]          # NoraSetTable 0..count-1

MAP_NAMES = {
    1: "Deserted Island", 2: "Sandy Plains", 3: "Flooded Forest",
    4: "Tundra", 5: "Volcano", 6: "Great Desert", 7: "Ruins",
    8: "Land Arena (event/grudge)", 9: "Land Arena", 10: "Event Water Arena",
    11: "Sacred Land", 12: "Water Arena", 13: "Misty Peaks", 14: "Tower",
    15: "Tainted Sea",
}

_MON_KEYS = {re.sub(r"[^a-z0-9]", "", n.lower()): i for i, n in MONSTERS.items()}


def mon_name(em_id):
    return MONSTERS.get(em_id, f"em{em_id:03d}")


def item_name(item_id):
    if 0 <= item_id < len(ITEMS):
        return ITEMS[item_id]
    return f"item#{item_id}"


def map_name(m):
    return MAP_NAMES.get(m, f"map {m}")


def area_text(quest_map, a):
    """Internal area number a, named the way the in-game map shows it."""
    if a == 0:
        return "camp"
    shown = AREA_SHOWN.get(quest_map)
    if shown is None:
        return f"area {a}"
    if a < len(shown):
        return f"area {shown[a]}"
    return f"area ? (game number {a})"


def resolve_mon_id(v):
    """em-ID (int or '0x..') or a monster name -> em-ID."""
    if isinstance(v, int):
        return v
    try:
        return int(v, 0)
    except ValueError:
        key = re.sub(r"[^a-z0-9]", "", v.lower())
        if key in _MON_KEYS:
            return _MON_KEYS[key]
        raise ValueError(f"unknown monster {v!r}") from None


# ------------------------------------------------------------ difficulty

def _f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def nando_row(i):
    return NANDO_ROWS[i] if 0 <= i < len(NANDO_ROWS) else None


Stats = namedtuple("Stats", "hp_mult atk_mult dmg_mult est_hp hp_cut")


def monster_stats(em_id, nando_hp, nando_at, nando_etc, category=0):
    """What the game does at spawn (uEnemy::setMaxHp 0x0259FB84):
    max HP = trunc(base HP x row[Nando_hp][0]), then x0.55 when the quest's
    Category has 0x10 or 0x100000. Attack = row[Nando_at][1]; damage the
    monster takes = hit damage x row[Nando_etc][2]. Returns None if any
    index is outside the table."""
    rh, ra, re_ = nando_row(nando_hp), nando_row(nando_at), nando_row(nando_etc)
    if rh is None or ra is None or re_ is None:
        return None
    cut = bool(category & HP_CUT_MASK)
    est = None
    base = BASE_HP.get(em_id)
    if base:
        est = int(_f32(_f32(float(base)) * _f32(rh[0])))
        if cut:
            est = int(_f32(_f32(float(est)) * _f32(HP_CUT)))
    return Stats(rh[0], ra[1], re_[2], est, cut)


# Nando2 (the "row spread") moves each difficulty row at random when the
# monster spawns: 0x020F28D8 picks a weighted offset from the table at
# 0x101F9DDC[Nando2], rolled separately for HP, attack and defense (spawn
# 0x020F32D8). A row below 0 becomes 0; Nando2 of 3 or more counts as 0. A
# game-state check (0x02261DC8, id 0x19, not decoded) can switch 1 to 2.
# In-game, Narg at Nite (HP row 44, Nando2 1) gave rows 42, 42, 43, 43 and
# 45 over five hunts.
NANDO_SPREAD = {1: [(-2, 10), (-1, 25), (0, 25), (1, 20), (2, 20)],
                2: [(-2, 20), (-1, 35), (0, 45)]}
SPREAD_TEXT = {0: "fixed", 1: "−2 to +2 rows each hunt",
               2: "−2 to 0 rows each hunt"}


def spread_offsets(spread):
    return [o for o, _ in NANDO_SPREAD.get(spread, [(0, 100)])]


def _span(lo, hi, fmt="{:g}"):
    return fmt.format(lo) if lo == hi else f"{fmt.format(lo)}–{fmt.format(hi)}"


def _pp(x):
    return f"{x:+d}".replace("-", "−")


# Sizeparam (the "size spread") picks one of 35 tables (0x101F9DE8). At spawn
# 0x020F2AAC makes a weighted pick from it, then a value in that entry's
# range: size % = Size + value. Table 0 is empty = exactly Size. Sizeparam 35
# and up reads past the table.
def size_range(size_param):
    """(low, high) in % points added to Size; None past the table."""
    if not 0 <= size_param < len(SIZE_SPREAD):
        return None
    t = SIZE_SPREAD[size_param]
    if not t:
        return (0, 0)
    return (min(lo for _, lo, _ in t), max(hi for _, _, hi in t))


def size_choice(size_param):
    r = size_range(size_param)
    if r is None:
        return f"{size_param}  past the game's table"
    if r == (0, 0):
        return f"{size_param}  exact size"
    return f"{size_param}  {_pp(r[0])} to {_pp(r[1])}%"


SIZE_CHOICES = [size_choice(p) for p in range(len(SIZE_SPREAD))]


def size_text(size, size_param):
    r = size_range(size_param)
    if r is None:
        return f"size {size}% (the size spread reads past the game's table)"
    return f"size {_span(size + r[0], size + r[1])}%"


# Starttype (the "spawn type") picks one of the monster's spawn points for
# the quest's map, from the same placement table as the stage check
# (0x101F9C80, read by 0x0216D798). Each point sets the area the monster
# starts in (its area_no).
def spawn_points(em_id, quest_map):
    """[[area, prog_type], ...] or None when there's no list."""
    st = MAP_TO_INTERNAL.get(quest_map)
    if st is None:
        return None
    return SPAWN_POINTS.get(em_id, {}).get(st)


def spawn_area_text(quest_map, a):
    """Where a monster's spawn point puts it. Area 0 is camp for hunters,
    but the one monster spawn point there (Ceadeus on the Ruins) is its
    entrance off the map: it swims into area 1 from there."""
    if a == 0:
        return ("its entrance (swims into area 1)" if quest_map == 7
                else "its entrance off the map")
    return area_text(quest_map, a)


def spawn_choice(v, points, quest_map=None):
    if points is None:
        return str(v)
    if 0 <= v < len(points):
        a = points[v][0]
        return (f"{v}  starts at {spawn_area_text(quest_map, a)}" if a == 0
                else f"{v}  starts in {area_text(quest_map, a)}")
    return f"{v}  no such spawn point"


# Stamina picks a row of the monster's own stamina table (staminaTblIdx: how
# much stamina it rolls and how long it stays tired, 0x025A6610 / 0x025C2094).
# The rows live in game data, so these are the game's own uses.
STAMINA = {0: "village quests", 1: "Port low and high rank", 2: "G rank",
           3: "arena quests"}


def stamina_choice(v):
    return f"{v}  {STAMINA.get(v, 'not used by the game')}"


def _title(tag):
    return tag.split(" ", 1)[1] if " " in tag else tag


# DemoNo / ProgNo / Ren_pattern: labelled by the quests that use each value.
DEMO_NO = {0: "none"}
for _v, _uses in _usage["demo_no"].items():
    _u = _uses[0]
    DEMO_NO[int(_v)] = (f"{_u['monsters'][0]} ({_title(_u['quest'])})"
                        if _u["monsters"] else _title(_u["quest"]))
PROG_NO = {0: "none"}
for _v, _uses in _usage["prog_no"].items():
    PROG_NO[int(_v)] = f"story step of {_title(_uses[0])}"
REN_PATTERN = {0: "none (most quests)"}
for _v, _uses in _usage["ren_pattern"].items():
    _n = sorted({u["monsters"] for u in _uses})
    _lineup = f"{_n[0]}–{_n[-1]}" if len(_n) > 1 else f"{_n[0]}"
    _how = f"{len(_uses)} quests, e.g." if len(_uses) > 1 else "as in"
    _first = min(u["quest"] for u in _uses)
    REN_PATTERN[int(_v)] = f"{_lineup} monsters ({_how} {_title(_first)})"


def stats_text(em_id, nando_hp, nando_at, nando_etc, category=0, spread=0,
               size=None, size_param=0):
    """What the game will apply; ranges when Nando2 spreads the rows."""
    if monster_stats(em_id, nando_hp, nando_at, nando_etc, category) is None:
        return "Nando values must be 0-127 (the table has 128 rows)"
    offs = spread_offsets(spread)
    stats = [monster_stats(em_id, max(0, nando_hp + o), max(0, nando_at + o),
                           max(0, nando_etc + o), category) for o in offs]
    if any(s is None for s in stats):
        return ("with this row spread the rows can go past 127, the end of "
                "the game's table")
    hp = "HP x" + _span(min(s.hp_mult for s in stats),
                        max(s.hp_mult for s in stats))
    if stats[0].hp_cut:
        hp += " x0.55"
    if stats[0].est_hp is not None:
        hp += " = " + _span(min(s.est_hp for s in stats),
                            max(s.est_hp for s in stats), "{:,}") + " HP"
    out = (f"{hp}  ·  attack x"
           + _span(min(s.atk_mult for s in stats), max(s.atk_mult for s in stats))
           + "  ·  damage taken x"
           + _span(min(s.dmg_mult for s in stats), max(s.dmg_mult for s in stats)))
    varies = len(offs) > 1
    if size is not None:
        out += "  ·  " + size_text(size, size_param)
        r = size_range(size_param)
        varies = varies or (r is not None and r != (0, 0))
    if varies:
        out += "  (varies each hunt)"
    return out


def monster_problems(slot, m, quest_map):
    """Warnings for one monster block (a dict with Type + the block fields)."""
    em = m["Type"]
    if not em:
        return []
    who = f"monster {slot + 1}: {mon_name(em)}"
    out = []
    if m["Num"] == 0:
        out.append(f"{who} has count 0, so it won't appear")
    elif m["Size"] == 0:
        out.append(f"{who} has size 0%")
    pts = spawn_points(em, quest_map)
    if pts is not None and m["Starttype"] >= len(pts):
        out.append(f"{who} has no spawn type {m['Starttype']} on "
                   f"{map_name(quest_map)} (the game lists 0–{len(pts) - 1}), "
                   f"so it may start in the wrong place or crash the game")
    if size_range(m["Sizeparam"]) is None:
        out.append(f"{who}: size spread {m['Sizeparam']} reads past the "
                   f"game's table (0–{len(SIZE_SPREAD) - 1})")
    if m["Stamina"] not in STAMINA:
        out.append(f"{who}: stamina {m['Stamina']} isn't used by any of the "
                   f"game's quests (they use 0–3), so the monster's table "
                   f"may not have that row")
    return out


# ---------------------------------------------------------- category flags

def flag_label(bit):
    b = FLAG_BITS[bit]
    if b["name"]:
        return b["name"]
    if b["count"]:
        return f"unknown, set on {b['count']} base quests"
    return "unknown, unused by base quests"


def category_summary(cat):
    """One-liner: named bits by name, the rest as hex masks."""
    known, other = [], []
    for b in range(64):
        if cat >> b & 1:
            name = FLAG_BITS[b]["name"] if b < 32 else None
            (known if name else other).append(name or f"0x{1 << b:X}")
    parts = known + ([f"unlabeled {' '.join(other)}"] if other else [])
    return "; ".join(parts) if parts else "no flags"


# ------------------------------------------------------- stage legality

def stage_legal(em_id, quest_map):
    """True/False if known, None if there's no data for the monster/map."""
    stages = PLACEMENT.get(em_id)
    internal = MAP_TO_INTERNAL.get(quest_map)
    if stages is None or internal is None:
        return None
    return internal in stages


def legality_warnings(monsters, quest_map):
    """monsters: iterable of (slot, em_id). The RPX placement table
    (0x101F9C80) has no spawn data for these monster/map pairs; slot 0
    without data crashes the game at quest load."""
    out = []
    for slot, em_id in monsters:
        if em_id and stage_legal(em_id, quest_map) is False:
            sev = ("WILL CRASH at quest load" if slot == 0
                   else "may crash or misbehave")
            out.append(f"monster {slot + 1}: {mon_name(em_id)} has no spawn "
                       f"data for {map_name(quest_map)} — {sev}")
    return out


# --------------------------------------------------------- supply crate

# --------------------------------------------------------- quest groups
# Where a base-game quest shows up, from its quest number.
QUEST_GROUPS = ("Village", "Port", "Event", "Arena", "Moga Woods")


def quest_group(quest_no):
    if quest_no < 1000:
        return "Moga Woods"          # training and Moga Woods free roam
    if quest_no < 11000:
        return "Village"
    if quest_no < 20000:
        return "Port"
    if 20100 <= quest_no < 39000:
        return "Event"               # the game's event-quest numbers
    if 60000 <= quest_no < 62000:
        return "Arena"               # Grudge Matches and Challenge Quests
    return "Other"


def quest_rank(quest_no):
    """0 low / 1 high / 2 G rank from the quest number, None when the
    number doesn't say (Moga Woods, Grudge and Challenge quests)."""
    return next((r for lo, hi, r in _RANK_BY_NO if lo <= quest_no < hi), None)


def supp_set_items(supp_set_no):
    """[(item id, qty)] in a crate, per-hunter duplicates collapsed, or
    None when the game has no such crate."""
    items = SUPP_SETS.get(supp_set_no)
    if items is None:
        return None
    seen, order = set(), []
    for iid, qty in items:
        if (iid, qty) not in seen:
            seen.add((iid, qty))
            order.append((iid, qty))
    return order


def supp_set_summary(supp_set_no):
    """Start-of-quest supply crate (quest/support/suppNNN.supp)."""
    if supp_set_no == 0:
        return "(no supply crate)"
    order = supp_set_items(supp_set_no)
    if order is None:
        return f"(no supp{supp_set_no:03d}.supp in the game)"
    return ", ".join(f"{item_name(i)} x{q}" for i, q in order) or "(empty)"


# Items in over 80% of crates (First-aid Med, Ration, Map, Torch, ...): the
# picker leaves them out so each entry shows what sets that crate apart.
_CRATE_BASICS = None


def _crate_basics():
    global _CRATE_BASICS
    if _CRATE_BASICS is None:
        crates = [{i for i, _ in v} for v in SUPP_SETS.values() if v]
        count = {}
        for c in crates:
            for i in c:
                count[i] = count.get(i, 0) + 1
        _CRATE_BASICS = {i for i, n in count.items() if n > 0.8 * len(crates)}
    return _CRATE_BASICS


def supp_set_label(n, shown=4):
    """One line for the crate picker: the quests that use the crate, then
    the items that set it apart from the usual basics."""
    if n == 0:
        return "no supply crate"
    items = SUPP_SETS.get(n)
    if items is None:
        return "no such crate in the game"
    if not items:
        return "empty crate"
    users = [u.split(" ", 1)[1] if u.startswith("#") else u
             for u in SUPP_USERS.get(n, [])]
    who = (users[0] + (f" +{len(users) - 1}" if len(users) > 1 else "")
           if users else "no base quest")
    extra, seen = [], set()
    for i, q in items:
        if i not in _crate_basics() and i not in seen:
            seen.add(i)
            extra.append(item_name(i) + (f" x{q}" if q > 1 else ""))
    what = ", ".join(extra[:shown]) + (f" +{len(extra) - shown} more"
                                       if len(extra) > shown else "")
    return f"{who} · {what or 'basics only'}"


# How the crate reaches the hunters (game code, US v1.3; EU identical;
# checked in-game). At the start (0x0216BAE0) the box gets crate
# slots 0-39, slots 0-7, or nothing, from the quest's rank and SuppTimeFlag.
# Slots, not items: many crates leave some of slots 0-7 empty (Field Trip's
# set 155 starts with just Map and Torch). The rank comes from the quest
# NUMBER (0x0216BA84), or "arena" when HagiNo is 3. Later deliveries:
# SuppTimeFlag 1 on the timed schedule below, off when HagiNo is 0
# (0x0216D140); SuppTimeFlag 2 after 2 minutes; and, with any flag, once
# SuppEnemyNum x SuppEnemyType are hunted (0x02175F6C).
#
# Timed schedule: table 0x101C5154[time limit // 5] (0x0216BC68), entries
# (minutes left on the clock, chance out of 128). At each the game rolls once
# (0x0216D604); the first hit delivers the rest. Every vanilla quest with a
# timed delivery is 50 minutes long (schedule 10: 3, 6, 9, 12, 15 minutes in,
# the last one certain). Other lengths can end without a delivery, and
# schedules 0, 1 and 12 are empty. 13+ reads past the table.
SUPPLY_SCHEDULES = [
    [], [],
    [(8, 32), (6, 48), (4, 16)],
    [(13, 8), (10, 32), (7, 48), (4, 16)],
    [(18, 8), (15, 32), (12, 32), (9, 32), (6, 16)],
    [(22, 4), (19, 16), (16, 32), (13, 32), (10, 32), (7, 16), (4, 8)],
    [(27, 2), (24, 8), (21, 6), (18, 32), (15, 32), (12, 32), (9, 16), (6, 8)],
    [(31, 2), (28, 4), (25, 8), (22, 16), (19, 16), (16, 32), (13, 32),
     (10, 32), (7, 16), (4, 8)],
    [(36, 2), (33, 2), (30, 4), (27, 8), (24, 8), (21, 16), (18, 32),
     (15, 32), (12, 32), (9, 16), (6, 8)],
    [(42, 2), (39, 2), (36, 4), (33, 4), (30, 8), (27, 8), (24, 16),
     (21, 32), (18, 32), (15, 32), (12, 16), (9, 16), (6, 8)],
    [(47, 8), (44, 16), (41, 32), (38, 64), (35, 128)],
    [(52, 2), (49, 2), (46, 4), (43, 4), (40, 8), (37, 8), (34, 16),
     (31, 16), (28, 16), (25, 32), (22, 32), (19, 32), (16, 16), (13, 16),
     (10, 16), (7, 8), (4, 8)],
    [],
]


def supply_schedule(time_min):
    """([(minute into the quest, chance %)], chance % it never comes), or
    None when the time limit reads past the game's table."""
    i = time_min // 5
    if i >= len(SUPPLY_SCHEDULES):
        return None
    rolls, never = [], 1.0
    for left, c in SUPPLY_SCHEDULES[i]:
        rolls.append((max(0, time_min - left), 100 * c / 128))
        never *= 1 - c / 128
    return rolls, 100 * never


def _pct(x):
    return f"{int(x + 0.5)}%" if x >= 1 or x == 0 else "<1%"


SUPP_TIME = {0: "Full crate at the start",
             1: "By rank; the rest later, on a random timer",
             2: "First 8 slots; the rest after 2 minutes",
             3: "By rank; the rest only from the hunt delivery"}
HAGI = {0: "Low rank: no timed delivery", 1: "High rank", 2: "G rank",
        3: "Arena: full crate, no deliveries", 4: "Multi-monster hunts"}
_RANK_BY_NO = [(1000, 1600, 0), (1600, 2000, 1), (2000, 2600, 0),
               (2600, 11000, 1), (11000, 11300, 0), (11300, 11600, 1),
               (11600, 12000, 2), (12000, 12300, 0), (12300, 12600, 1),
               (12600, 12900, 2), (20100, 20200, 0), (20200, 20300, 1),
               (20300, 39000, 2)]
RANK_NAMES = ("low rank", "high rank", "G rank", "arena")


def supply_rank(quest_no):
    """0 low / 1 high / 2 G rank, as the crate code reads a quest number."""
    return next((r for lo, hi, r in _RANK_BY_NO if lo <= quest_no < hi), 0)


def _items_text(pairs):
    seen, order = set(), []
    for iid, qty in pairs:          # collapse the per-hunter duplicates
        if (iid, qty) not in seen:
            seen.add((iid, qty))
            order.append((iid, qty))
    return ", ".join(f"{item_name(i)} x{q}" for i, q in order)


def supply_plan(quest_no, set_no, flag, hagi, enemy_type, enemy_num,
                time_min=50):
    """(lines, problems): what the box holds at the start and what comes
    later, as the game code reads these fields."""
    if set_no == 0:
        return ["No supply crate."], []
    items = SUPP_SETS.get(set_no)
    if items is None:
        return [], [f"there is no supp{set_no:03d}.supp in the game"]
    slots = SUPP_SLOTS.get(set_no, list(range(len(items))))
    r = 3 if hagi == 3 else supply_rank(quest_no)
    if flag == 2:
        start = 8
    elif r in (0, 3):
        start = 40
    elif r == 1:
        start = 40 if flag == 0 else 8
    else:
        start = 40 if flag == 0 else 0
    first = [it for it, sl in zip(items, slots) if sl < start]
    held_back = len(first) < len(items)
    lines = [f"Quest {quest_no} counts as {RANK_NAMES[r]}"
             + (" (HagiNo 3)." if r == 3 else " (from its number).")]
    if not held_back:
        lines.append("At the start: the whole crate.")
    elif first:
        lines.append(f"At the start: {_items_text(first)} only (crate slots "
                     f"1–8).")
    else:
        lines.append("At the start: nothing.")
    later, problems = [], []
    if r != 3:
        if flag == 1 and hagi & 0xFF:
            sched = supply_schedule(time_min)
            if sched is None:
                problems.append(f"with a {time_min}-minute time limit the "
                                f"delivery timer reads past the end of the "
                                f"game's schedule table")
            elif not sched[0]:
                if held_back:
                    problems.append(f"with a {time_min}-minute time limit the "
                                    f"game has no delivery schedule, so the "
                                    f"timed delivery never comes")
            else:
                rolls, never = sched
                mins = ", ".join(str(m) for m, _ in rolls[:-1])
                mins = (f"{mins} or {rolls[-1][0]}" if mins
                        else str(rolls[-1][0]))
                odds = " / ".join(_pct(c) for _, c in rolls)
                txt = (f"on a random timer, {mins} minutes in (chance at "
                       f"each: {odds})")
                if never > 0:
                    txt += f"; in {_pct(never)} of runs it never comes"
                    if held_back:
                        problems.append(
                            f"with a {time_min}-minute time limit the timed "
                            f"delivery never comes in {_pct(never)} of runs "
                            f"(only 50-minute quests are certain to get it)")
                later.append(txt)
        if flag == 2:
            later.append("after 2 minutes")
    if enemy_num and enemy_type:
        later.append(f"after {enemy_num} {mon_name(enemy_type)} "
                     f"{'is' if enemy_num == 1 else 'are'} hunted")
    if later:
        lines.append(("The rest arrives " if held_back else "Deliveries: ")
                     + "; also ".join(later) + ".")
    if held_back and not later:
        problems.append("the rest of the supply crate is never delivered")
    if enemy_num and not enemy_type:
        problems.append("the hunt delivery has a count but no monster")
    return lines, problems


START_PARAM = {0: "Base camp", 1: "Random area (main hunting maps)",
               2: "Fixed area (Ruins, Sacred Land, Tainted Sea)"}
_START_KIND = {1: "random start", 2: "fixed start area"}
ENEMY_LV = {0: "Low rank (village)", 1: "Low rank (hub)",
            2: "High rank (village)", 3: "High rank (hub)", 4: "G rank"}


def start_text(quest_map, start_param):
    """'camp 20%, area 1 15%, …' for this map and StartParam."""
    per = START_AREAS.get(quest_map)
    if not per or not 0 <= start_param < len(per):
        return "base camp (the game has no list for this value)"
    pairs = per[start_param]
    if len(pairs) == 1:
        a = pairs[0][0]
        return ("always base camp" if a == 0
                else f"always {area_text(quest_map, a)}")
    return ", ".join(f"{area_text(quest_map, a)} {w}%" for a, w in pairs)


def _start_maps(start_param):
    """Maps where this StartParam starts the hunters away from base camp."""
    return [m for m, per in sorted(START_AREAS.items())
            if 0 <= start_param < len(per) and per[start_param] != [[0, 100]]]


def start_warning(quest_map, start_param):
    """Why this StartParam does nothing on this map (the hunters still start
    at base camp), or None when it works here or is 0."""
    if start_param == 0 or quest_map in _start_maps(start_param):
        return None
    where = [map_name(m) for m in _start_maps(start_param)]
    if not where:
        return "No map uses this value, so it's the same as 0."
    kind = _START_KIND.get(start_param, "start list for this value")
    text = (f"{map_name(quest_map)} has no {kind}, so this is the same as 0"
            if quest_map in START_AREAS else "this is the same as 0")
    text += (". It only changes the start on "
             + (", ".join(where[:-1]) + " and " + where[-1]
                if len(where) > 1 else where[0]))
    return text + "."


# ------------------------------------------------- who can join a quest
# SpecialFlag only picks the line the quest board shows (the game's Quest
# message 42 + flag; 28 and up shows nothing). SpecialCondition and
# SpecialCondition2 are the rules the game checks, when the quest is started
# and when someone joins online: both index a 24-entry table (0x101C55F0).

Req = namedtuple("Req", "hr players naked")
NO_REQ = Req(None, 4, False)
COND_COUNT = 24

REQ_TEXT = (
    ["None."]
    + [f"Must be HR {n} or higher to initiate/join." for n in range(1, 9)]
    + [f"Must be HR {hr} or higher to join. Max participants: {p}"
       for p in (1, 2, 4) for hr in (3, 6, 8)]
    + ["Must remove all armor and talismans to initiate/join.",
       "Must be HR 3 or higher to join. No armor or talismans.",
       "Must be HR 6 or higher to join. No armor or talismans."]
    + ["Must bring Cha-Cha & Kayamba."] * 2
    + ["Must bring Cha-Cha, Kayamba & Unfortunate Mask (on Kayamba)."] * 2
    + [f"No HR restrictions. Max participants: {p}" for p in (1, 2, 4)])

# What each line claims, to compare against the rules. The Cha-Cha lines
# claim nothing these rules can check (the game enforces those elsewhere).
REQ_CLAIMS = (
    [NO_REQ, NO_REQ] + [Req(n, 4, False) for n in range(2, 9)]
    + [Req(hr, p, False) for p in (1, 2, 4) for hr in (3, 6, 8)]
    + [Req(None, 4, True), Req(3, 4, True), Req(6, 4, True)]
    + [NO_REQ] * 4
    + [Req(None, p, False) for p in (1, 2, 4)])
assert len(REQ_TEXT) == len(REQ_CLAIMS) == 28
_NO_AUTO_TEXT = {1, 21, 22, 23, 24}   # never picked automatically


def req_text(flag):
    if 0 <= flag < len(REQ_TEXT):
        return REQ_TEXT[flag]
    return "(nothing shown)"


def cond_name(v):
    if v == 0:
        return "No rule"
    if 1 <= v <= 11:
        return "Online players can't join"
    if v == 12:
        return "No armor or talismans"
    if 13 <= v <= 15:
        return f"Max {v - 12} player" + ("s" if v > 13 else "")
    if 16 <= v < COND_COUNT:
        return f"HR {v - 14} or higher"
    return "past the end of the game's table"


def rules_of(conds):
    """The combined effect of the two rule values."""
    hr = max((c - 14 for c in conds if 16 <= c < COND_COUNT), default=None)
    players = min((c - 12 for c in conds if 13 <= c <= 15), default=4)
    return Req(hr, players, 12 in conds)


def describe_req(req):
    parts = []
    if req.hr:
        parts.append(f"HR {req.hr}+")
    if req.players < 4:
        parts.append(f"max {req.players} player" +
                     ("s" if req.players > 1 else ""))
    if req.naked:
        parts.append("no armor or talismans")
    return ", ".join(parts) or "no limits"


def text_for_rules(conds, current):
    """The board-text value for these rules: current if it already matches,
    else the first matching line, else None (no line describes them)."""
    want = rules_of(conds)
    if 0 <= current < len(REQ_CLAIMS) and REQ_CLAIMS[current] == want:
        return current
    return next((f for f, r in enumerate(REQ_CLAIMS)
                 if r == want and f not in _NO_AUTO_TEXT), None)


def requirement_problems(flag, cond1, cond2):
    """Plain-English problems with a quest's text/rules (empty = fine)."""
    out = []
    for i, c in enumerate((cond1, cond2), 1):
        if c >= COND_COUNT:
            out.append(f"rule {i} = {c} is past the end of the game's table "
                       f"(0–{COND_COUNT - 1}), so the game reads unrelated data")
        elif 1 <= c <= 11:
            out.append(f"rule {i} = {c}: nobody will be able to join this "
                       f"quest online")
    want = rules_of((cond1, cond2))
    if not 0 <= flag < len(REQ_CLAIMS):
        if want != NO_REQ:
            out.append(f"the board shows no requirement text, but the rules "
                       f"are: {describe_req(want)}")
    elif REQ_CLAIMS[flag] != want:
        out.append(f"the board says “{REQ_TEXT[flag]}” but the rules "
                   f"are: {describe_req(want)}")
    return out


# --------------------------------------------------------------- invaders
# The Nora block (6 bytes after the monster blocks), as the game uses it
# (checked in-game):
# - Quest start (0x0216C798): rand%100 < NoraSetPer arms invasions for this
#   run, and NoraPerType becomes the per-attempt chance. Any NoraSetPer > 0
#   also shows the area as unstable (0x0216E56C). NoraPekko skips this roll.
# - The timer (0x0216EC34) waits until the field allows: no more than one
#   monster in the quest's monster list (sQuest+0xB050 -> +0x8644+0x2268), so
#   it starts again only once an invader is gone. Then every 2 minutes it
#   rolls the per-attempt chance. A hit picks a candidate by weight
#   (0x0216E868), skipping any the player's progress hasn't reached, and
#   lowers the chance by 20. A pick that is already one of the quest's
#   monsters is dropped (except on quests 11882 and 20318).
# - On a quest with a Qurupeco the game keeps one invader waiting in the
#   monster list from the quest start, and the Qurupeco's call brings it in,
#   whatever NoraPekko says. The waiting invader also blocks the timer, so on
#   those quests NoraPekko makes no visible difference. Without a Qurupeco,
#   NoraPekko just means no invaders.
# - At most NoraSetMax invaders, and never more than 3.
# - Nothing in the game reads NoraSetType.

INVADER_HARD_MAX = 3
QURUPECOS = {3, 51}                 # Qurupeco, Crimson Qurupeco


def invader_list(n):
    return INVADER_LISTS.get(n, {}).get("candidates", [])


def invader_used_by(n):
    return INVADER_LISTS.get(n, {}).get("used_by", [])


def invader_list_label(n):
    """'Arzuros 70%, Pink Rathian 30%' for the list picker."""
    if n == 0:
        return "none"
    if not 0 <= n < INVADER_LIST_COUNT:
        return "past the end of the game's table"
    return (", ".join(f"{mon_name(c['em'])} {c['weight']}%"
                      for c in invader_list(n)) or "empty")


def invader_lines(n, category=0):
    """Two lines per candidate: chance, star gate and size, then strength."""
    out = []
    for c in invader_list(n):
        out.append(f"{mon_name(c['em'])}: {c['weight']}% of picks · needs "
                   f"★{c['min_star']} unlocked · "
                   f"{size_text(c['Size'], c.get('Sizeparam', 0))}")
        out.append("      " + stats_text(c["em"], c["Nando_hp"], c["Nando_at"],
                                         c["Nando_etc"], category,
                                         c.get("Nando2", 0)))
    return out


def invader_problems(per, per_type, set_max, table, pekko, quest_map,
                     main_ems):
    """Plain-English problems with a quest's invader settings (empty =
    fine). main_ems: the em-IDs in the quest's monster slots."""
    if not per and not pekko:
        return []                   # stable: the other fields do nothing
    out = []
    cands = invader_list(table)
    if not 0 <= table < INVADER_LIST_COUNT:
        out.append(f"invader list {table} is past the end of the game's "
                   f"table (0–{INVADER_LIST_COUNT - 1}), so the game reads "
                   f"unrelated data")
    elif not cands:
        out.append(f"invader list {table} is empty, so no invader can appear")
    if set_max == 0:
        out.append("max invaders is 0, so no invader can appear")
    if per and not pekko and per_type == 0:
        out.append("the chance per attempt is 0%, so no invader can appear")
    if pekko and not QURUPECOS & set(main_ems):
        out.append("the 2-minute timer is skipped (NoraPekko) and the quest "
                   "has no Qurupeco to call invaders, so none can appear")
    if pekko and not per:
        out.append("NoraPekko is on with a start chance of 0; the game's own "
                   "Qurupeco quests all use 100 (0 is untested)")
    total = len(main_ems) + min(set_max, INVADER_HARD_MAX)
    if cands and total > 5:
        out.append(f"{len(main_ems)} quest monsters + up to "
                   f"{min(set_max, INVADER_HARD_MAX)} invaders is more than "
                   f"the 5 monster slots; the game's own quests never go past "
                   f"5 (may crash)")
    for c in cands:
        name = mon_name(c["em"])
        if stage_legal(c["em"], quest_map) is False:
            out.append(f"invader {name} has no spawn data for "
                       f"{map_name(quest_map)} — may crash when it arrives")
        if c["em"] in main_ems:
            out.append(f"invader {name} is already one of the quest's "
                       f"monsters, so the game drops it when it's picked")
    return out


# ------------------------------------------------------------ quest text
# Checked in-game (US): the game never wraps or scrolls quest
# text. A description line runs past the box's right edge, and lines past 7
# spill off the panel. The quest info header fits a 40-character name (the
# board list cuts names at about 23 with "…", the game's own included). The
# game's own text stays within 29 characters for names and 7 lines of at most
# 39 for descriptions, in all 5 languages.
NAME_MAX = 40
DESC_LINES = 7
DESC_LINE_MAX = 39
TEXT_LANGS = ("en", "fr", "de", "it", "es")


def text_problems(q):
    """Quest text the game will show badly. Language slots with the same
    problem are reported once."""
    found = {}                      # message -> [languages]
    for i, lg in enumerate(TEXT_LANGS):
        name = q.get_string("name", lang=i)
        if len(name) > NAME_MAX:
            found.setdefault(f"name{{}} is {len(name)} characters; the quest "
                             f"info fits about {NAME_MAX}", []).append(lg)
        lines = q.get_string("description", lang=i).split("\r\n")
        if len(lines) > DESC_LINES:
            found.setdefault(f"description{{}} has {len(lines)} lines; the "
                             f"box shows {DESC_LINES} and the rest spills off "
                             f"the panel", []).append(lg)
        long_ = [n for n, ln in enumerate(lines, 1) if len(ln) > DESC_LINE_MAX]
        if long_:
            found.setdefault(
                f"description{{}} line {', '.join(map(str, long_))} "
                f"{'is' if len(long_) == 1 else 'are'} over {DESC_LINE_MAX} "
                f"characters; the game doesn't wrap, so long lines can run "
                f"past the box", []).append(lg)
    return [msg.format("" if len(lgs) == len(TEXT_LANGS)
                       else f" [{', '.join(lgs)}]")
            for msg, lgs in found.items()]


# ------------------------------------------------------------ arena gear
# Gear sets use the save file's (equipment type, id) pairs: 1 chest, 2 arms,
# 3 waist, 4 legs, 5 head, 6 talisman, 7-19 weapons (12 unused).
_eq = _load("equipment_en.json")
EQUIP_TYPES = {int(k): v for k, v in _eq["types"].items()}
EQUIP_NAMES = {int(k): v for k, v in _eq["names"].items()}
CHARM_SKILLS = _eq["charm_skills"]
WEAPON_TYPES = sorted(t for t in EQUIP_TYPES if t >= 7)
BOWGUN_TYPES = (11, 13)          # these load shots from the ammo pouch
ARENA_KINDS = ((60000, 61000, "Grudge Match"), (61000, 62000, "Challenge"))
# The Arena Clerk's lists are fixed tables of quest numbers in the game code
# (0x10026FF4): Grudge Match 60000-60011, Challenge Quest 61000-61009. The
# Challenge list reads its quests from the quest4 event pack when it opens.
GRUDGE_LISTED = range(60000, 60012)
CHALLENGE_LISTED = range(61000, 61010)
CHALLENGE_PACK = "quest4"
ARENA_B_RANK = 1800              # the game adds a fixed B rank of 30:00


def equip_name(etype, eid):
    if not eid:
        return "(none)"
    names = EQUIP_NAMES.get(etype)
    if names is None:
        return f"type {etype} #{eid}"
    return names[eid] if 0 <= eid < len(names) else f"#{eid}"


def equip_choices(etype):
    """[(id, name)] for a picker: the game's DUMMY slots and its display
    copies of DLC names are left out."""
    out = [(0, "(none)")]
    for i, n in enumerate(EQUIP_NAMES.get(etype, [])):
        if i and n not in ("DUMMY", "") and "(dup of" not in n \
                and not n.startswith("(None"):
            out.append((i, n))
    return out


def charm_skill_name(i):
    if not i:
        return "(none)"
    return CHARM_SKILLS[i] if 0 <= i < len(CHARM_SKILLS) else f"skill #{i}"


def arena_kind(quest_no):
    for lo, hi, name in ARENA_KINDS:
        if lo <= quest_no < hi:
            return name
    return None


def clock(seconds):
    return f"{seconds // 60}:{seconds % 60:02d}"


def arena_set_summary(gear):
    t, i = gear["equip"][0]
    return (f"{EQUIP_TYPES.get(t, 'no weapon')}: {equip_name(t, i)}"
            if i else "no weapon")


def arena_pack_problem(quest_no, pack):
    """Challenge Quests only list from the quest4 event pack; Grudge Matches
    always come from the base game, so a pack copy never lists."""
    if not pack:
        return []
    if quest_no in GRUDGE_LISTED:
        return [f"Grudge Matches (60000–60011) always come from the base "
                f"game files, so #{quest_no} in {pack} won't show up in the "
                f"game"]
    if quest_no in CHALLENGE_LISTED and pack.lower() != CHALLENGE_PACK:
        return [f"Challenge Quests are read from the {CHALLENGE_PACK} pack, "
                f"so #{quest_no} in {pack} won't show up in the game"]
    return []


def arena_problems(q, pack=None):
    """Gear-set checks for the save dialog. `pack` is the event pack's file
    name, or None for a base-game quest."""
    out = []
    no = q.get("quest_no")
    if not q.arena_sets:
        return out
    out += arena_pack_problem(no, pack)
    kind = arena_kind(no)
    filled = [i for i, g in enumerate(q.arena_sets)
              if any(v for p in g["equip"] for v in p)]
    if filled and not kind:
        out.append(f"gear sets are filled in, but only Grudge Match "
                   f"(60000-60999) and Challenge (61000-61999) quests hand "
                   f"them out; #{no} is neither")
    if not kind:
        return out
    if no not in GRUDGE_LISTED and no not in CHALLENGE_LISTED:
        out.append(f"the Arena Clerk only lists Grudge Matches 60000-60011 "
                   f"and Challenge Quests 61000-61009, so #{no} won't show "
                   f"up in the game")
    for i, g in enumerate(q.arena_sets, 1):
        t, wid = g["equip"][0]
        if not wid:
            out.append(f"gear set {i} has no weapon")
        elif t in BOWGUN_TYPES and not any(n for _, n in g["ammo"]):
            out.append(f"gear set {i} is a bowgun with an empty ammo pouch")
        stacks = {}
        for item, num in g["pouch"]:
            if item and num:
                stacks[item] = stacks.get(item, 0) + 1
        dup = [item_name(it) for it, c in stacks.items() if c > 1]
        if dup:
            out.append(f"gear set {i} has {', '.join(dup)} in more than one "
                       f"pouch slot; the game merges them into one stack, "
                       f"capped at what the pouch can hold")
    s, a = q.get("arena_time_s"), q.get("arena_time_a")
    if s and a and s >= a:
        out.append(f"S rank time {clock(s)} isn't faster than A rank "
                   f"{clock(a)}")
    if a and a > q.get("time_min") * 60:
        out.append(f"A rank time {clock(a)} is longer than the "
                   f"{q.get('time_min')}-minute time limit")
    return out
