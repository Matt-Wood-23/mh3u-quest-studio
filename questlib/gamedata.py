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
SUPP_SETS = {int(k): [(it["id"], it["qty"]) for it in v]
             for k, v in _load("supp_sets.json").items()}

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


def stats_text(em_id, nando_hp, nando_at, nando_etc, category=0):
    s = monster_stats(em_id, nando_hp, nando_at, nando_etc, category)
    if s is None:
        return "Nando values must be 0-127 (the table has 128 rows)"
    hp = f"HP x{s.hp_mult:g}"
    if s.hp_cut:
        hp += " x0.55"
    if s.est_hp is not None:
        hp += f" = {s.est_hp:,} HP"
    return (f"{hp}  ·  attack x{s.atk_mult:g}  ·  "
            f"damage taken x{s.dmg_mult:g}")


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

def supp_set_summary(item_set_no):
    """Start-of-quest supply crate (quest/support/suppNNN.supp)."""
    if item_set_no == 0:
        return "(no supply crate)"
    items = SUPP_SETS.get(item_set_no)
    if items is None:
        return f"(no supp{item_set_no:03d}.supp in the game)"
    seen, order = set(), []
    for iid, qty in items:          # collapse the per-hunter duplicates
        if (iid, qty) not in seen:
            seen.add((iid, qty))
            order.append((iid, qty))
    return ", ".join(f"{item_name(i)} x{q}" for i, q in order) or "(empty)"
