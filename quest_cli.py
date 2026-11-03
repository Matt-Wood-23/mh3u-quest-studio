#!/usr/bin/env python3
"""MH3U Quest Studio — command line.

Uses the same game folder + workspace as the GUI (studio_config.json).

  quest_cli.py list   [--star N] [--map N] [--mon NAME] [--edited]
  quest_cli.py show   QUEST_NO
  quest_cli.py edit   QUEST_NO [options]           (saved to the workspace)
  quest_cli.py revert QUEST_NO
  quest_cli.py status
  quest_cli.py install                             (into the game folder)
  quest_cli.py restore                             (put originals back)
  quest_cli.py export QUEST_NO FILE / import QUEST_NO FILE
  quest_cli.py verify                              (parser self-test)

Examples:
  quest_cli.py edit 2906 --name "My Hunt" --time 25 \\
      --mon "1:Type=Great Jaggi,Num=2,Nando_hp=40"
  quest_cli.py edit 2906 --copy-mon 2:1206          (clone a monster block)
  quest_cli.py edit 2906 --reward1 "9:3:0,311:2:25"  (id:amount:chance)
  quest_cli.py edit 60000 --category 0x08010001      (flags, hex)
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    sys.stdout.reconfigure(errors="replace")
except AttributeError:
    pass

from questlib import gamedata as GD          # noqa: E402
from questlib import project as P            # noqa: E402
from questlib.quest_format import (Quest, MON_FIELDS, MON_SLOTS, LANGS,  # noqa: E402
                                   STRING_FIELDS, NANDO_FIELDS, NANDO_MAX,
                                   identity_rewrite)

SCALARS = {  # option -> quest_format field
    "time": "time_min", "star": "star", "map": "map", "quest_no": "quest_no",
    "contract": "contract", "money": "reward_money", "penalty": "penalty",
    "hrp": "main_hrp", "failure_hrp": "failure_hrp",
    "crate": "supp_set_no", "demo": "demo_no",
    "supp_time_flag": "supp_time_flag", "start_param": "start_param",
    "ren_pattern": "ren_pattern", "rannyu_limite": "rannyu_limite",
    "special_flag": "special_flag", "special_cond": "special_cond",
    "special_cond2": "special_cond2", "category": "category",
    "clr_pattern": "clr_pattern",
    "obj1_type": "obj1_param", "obj1_id": "obj1_id", "obj1_num": "obj1_num",
    "obj2_type": "obj2_param", "obj2_id": "obj2_id", "obj2_num": "obj2_num",
}


def project():
    cfg = P.Config(HERE / "studio_config.json")
    if not cfg.game_dirs:
        raise SystemExit("no game folder set: run quest_studio.py once (or "
                         "write studio_config.json) first")
    ws = Path(cfg.workspace) if cfg.workspace else HERE / "workspace"
    return P.Project(cfg.game_dirs, cfg.region, ws)


def locate(pr, quest_no):
    for pack in P.PACKS:
        leaf = pr.find_leaf(pack, quest_no)
        if leaf:
            return pack, leaf
    raise SystemExit(f"quest {quest_no} not found")


def show(q):
    g = q.get
    print(f"#{g('quest_no'):05d}  {g('star')}*  {GD.map_name(g('map'))}  "
          f"{g('time_min')} min")
    for f in STRING_FIELDS:
        print(f"  {f:>13}: {q.get_string(f)!r}")
    for i, m in enumerate(q.monsters):
        if m["Type"]:
            rest = " ".join(f"{k}={v}" for k, v in m.items() if k != "Type")
            print(f"  monster {i + 1}: {GD.mon_name(m['Type'])} ({m['Type']})  "
                  f"{rest}")
            print(f"             {GD.stats_text(m['Type'], m['Nando_hp'], m['Nando_at'], m['Nando_etc'], g('category'))}")
    for col, recs in ((1, q.reward1), (2, q.reward2)):
        txt = ", ".join(f"{GD.item_name(i)} x{n}" + (f" ({p}%)" if p else "")
                        for i, n, p in recs)
        print(f"  rewards {col}: {txt or '-'}")
    print(f"  objective: {q.objective_text(GD.mon_name, GD.item_name)}")
    print(f"  money: fee {g('contract')}z  reward {g('reward_money')}z  "
          f"penalty {g('penalty')}z  HRP {g('main_hrp')}/{g('failure_hrp')}")
    print(f"  crate (set {g('supp_set_no')}): "
          f"{GD.supp_set_summary(g('supp_set_no'))}")
    print(f"  category 0x{g('category'):X}: {GD.category_summary(g('category'))}")
    c1, c2 = g("special_cond"), g("special_cond2")
    print(f"  who can join: rules {c1} ({GD.cond_name(c1)}), {c2} "
          f"({GD.cond_name(c2)}); board text {g('special_flag')}: "
          f"{GD.req_text(g('special_flag'))}")
    for p in GD.requirement_problems(g("special_flag"), c1, c2):
        print(f"WARNING: {p}")


def cmd_list(a):
    pr = project()
    mon = GD.resolve_mon_id(a.mon) if a.mon else None
    for pack in P.PACKS:
        mods = set(pr.modified(pack))
        for leaf, _ in pr.quest_entries(pack):
            if a.edited and leaf not in mods:
                continue
            q = Quest(pr.load(pack, leaf))
            if a.star is not None and q.get("star") != a.star:
                continue
            if a.map is not None and q.get("map") != a.map:
                continue
            if mon is not None and mon not in [m["Type"] for m in q.monsters]:
                continue
            mons = ", ".join(GD.mon_name(m["Type"]) for m in q.monsters
                             if m["Type"])
            print(f"{leaf[2:]}{'*' if leaf in mods else ' '} {q.get('star')}* "
                  f"{GD.map_name(q.get('map')):<18} "
                  f"{q.get_string('name'):<42} {mons}")


def cmd_show(a):
    pr = project()
    show(Quest(pr.load(*locate(pr, a.quest_no))))


def parse_mon(spec):
    slot_s, _, rest = spec.partition(":")
    slot = int(slot_s) - 1
    if not 0 <= slot < MON_SLOTS:
        raise SystemExit(f"monster slot must be 1..{MON_SLOTS}")
    fields = {}
    for kv in filter(None, rest.split(",")):
        k, _, v = kv.partition("=")
        k = next((f for f in MON_FIELDS if f.lower() == k.strip().lower()),
                 None)
        if k is None:
            raise SystemExit(f"unknown monster field in {kv!r}; fields: "
                             f"{', '.join(MON_FIELDS)}")
        fields[k] = GD.resolve_mon_id(v.strip()) if k == "Type" else int(v, 0)
        hi = NANDO_MAX if k in NANDO_FIELDS else 255
        if not 0 <= fields[k] <= hi:
            raise SystemExit(f"{k}={fields[k]} outside 0..{hi}")
    return slot, fields


def parse_rewards(spec):
    out = []
    for part in filter(None, spec.split(",")):
        bits = part.split(":")
        if len(bits) != 3:
            raise SystemExit(f"reward {part!r} must be id:amount:chance")
        out.append(tuple(int(b, 0) for b in bits))
    return out


def cmd_edit(a):
    pr = project()
    pack, leaf = locate(pr, a.quest_no)
    q = Quest(pr.load(pack, leaf))
    langs = range(len(LANGS)) if a.lang == "all" else [LANGS.index(a.lang)]
    for f in STRING_FIELDS:
        v = getattr(a, f)
        if v is not None:
            q.set_string(f, v.replace("\\n", "\r\n"), langs=langs)
    for opt, field in SCALARS.items():
        v = getattr(a, opt)
        if v is not None:
            if field in ("special_cond", "special_cond2") and not \
                    0 <= v < GD.COND_COUNT:
                raise SystemExit(f"--{opt.replace('_', '-')} must be "
                                 f"0..{GD.COND_COUNT - 1}")
            q.set(field, v)
    for spec in a.copy_mon or []:
        parts = spec.split(":")
        if len(parts) not in (2, 3):
            raise SystemExit("--copy-mon is SLOT:QUEST[:SRCSLOT]")
        slot, src_no = int(parts[0]) - 1, int(parts[1])
        src_slot = int(parts[2]) - 1 if len(parts) == 3 else 0
        sp, sl = locate(pr, src_no)
        block = Quest(pr.pristine_data(sp, sl)).monsters[src_slot]
        if not block["Type"]:
            raise SystemExit(f"quest {src_no} monster {src_slot + 1} is empty")
        q.set_monster(slot, **block)
    for spec in a.mon or []:
        slot, fields = parse_mon(spec)
        q.set_monster(slot, **fields)
    for slot in a.clear_mon or []:
        q.clear_monster(slot - 1)
    if a.reward1 is not None:
        q.set_reward_table(1, parse_rewards(a.reward1))
    if a.reward2 is not None:
        q.set_reward_table(2, parse_rewards(a.reward2))
    pr.save(pack, leaf, q.to_bytes())
    show(q)
    for w in GD.legality_warnings([(i, m["Type"]) for i, m in
                                   enumerate(q.monsters)], q.get("map")):
        print(f"WARNING: {w}")
    print(f"saved {leaf} to the workspace; run 'install' to put it in the game")


def cmd_revert(a):
    pr = project()
    pr.revert(*locate(pr, a.quest_no))
    print("reverted (run 'install' to apply)")


def cmd_status(a):
    pr = project()
    for pack in P.PACKS:
        mods = pr.modified(pack)
        print(f"{pack}: {len(mods)} edited ({pr.pack_status(pack)})"
              + (f": {' '.join(m[2:] for m in mods)}" if mods else ""))
        for t, s in pr.install_state(pack):
            print(f"    {s:<10} {t}")


def cmd_install(a):
    pr = project()
    for pack in P.PACKS:
        done = pr.install(pack) if pr.modified(pack) else pr.restore(pack)
        for t in done:
            print(f"{pack}: wrote {t}")
    print("restart MH3U to load the quests")


def cmd_restore(a):
    pr = project()
    for pack in P.PACKS:
        for t in pr.restore(pack):
            print(f"{pack}: restored {t}")


def cmd_export(a):
    pr = project()
    Path(a.file).write_bytes(pr.load(*locate(pr, a.quest_no)))
    print(f"wrote {a.file}")


def cmd_import(a):
    pr = project()
    pack, leaf = locate(pr, a.quest_no)
    data = Path(a.file).read_bytes()
    Quest(data)
    pr.save(pack, leaf, data)
    print(f"imported {a.file} as {leaf} (run 'install' to apply)")


def cmd_verify(a):
    pr = project()
    ok = bad = 0
    for pack in P.PACKS:
        for leaf, _ in pr.quest_entries(pack):
            d = pr.pristine_data(pack, leaf)
            if identity_rewrite(d) == d:
                ok += 1
            else:
                bad += 1
                print(f"MISMATCH {pack}/{leaf}")
    print(f"round-trip: {ok}/{ok + bad} quests byte-identical")
    if bad:
        raise SystemExit(1)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list")
    p.add_argument("--star", type=int)
    p.add_argument("--map", type=int)
    p.add_argument("--mon")
    p.add_argument("--edited", action="store_true")
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("show")
    p.add_argument("quest_no", type=int)
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("edit")
    p.add_argument("quest_no", type=int)
    p.add_argument("--lang", default="all", choices=["all"] + LANGS)
    for f in STRING_FIELDS:
        p.add_argument(f"--{f.replace('_', '-')}", dest=f)
    for opt in SCALARS:
        p.add_argument(f"--{opt.replace('_', '-')}", dest=opt,
                       type=lambda s: int(s, 0))
    p.add_argument("--mon", action="append", metavar="SLOT:Field=v,...",
                   help=f"slot 1-5; fields {', '.join(MON_FIELDS)}")
    p.add_argument("--copy-mon", action="append", metavar="SLOT:QUEST[:SRC]")
    p.add_argument("--clear-mon", action="append", type=int, metavar="SLOT")
    p.add_argument("--reward1", metavar="id:amount:chance,...")
    p.add_argument("--reward2", metavar="id:amount:chance,...")
    p.set_defaults(fn=cmd_edit)

    for name, fn in (("revert", cmd_revert),):
        p = sub.add_parser(name)
        p.add_argument("quest_no", type=int)
        p.set_defaults(fn=fn)
    for name, fn in (("status", cmd_status), ("install", cmd_install),
                     ("restore", cmd_restore), ("verify", cmd_verify)):
        sub.add_parser(name).set_defaults(fn=fn)
    for name, fn in (("export", cmd_export), ("import", cmd_import)):
        p = sub.add_parser(name)
        p.add_argument("quest_no", type=int)
        p.add_argument("file")
        p.set_defaults(fn=fn)

    a = ap.parse_args()
    try:
        a.fn(a)
    except (P.ProjectError, ValueError) as e:
        raise SystemExit(f"error: {e}")


if __name__ == "__main__":
    main()
