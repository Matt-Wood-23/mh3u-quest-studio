#!/usr/bin/env python3
"""MH3U base-game quest record (type 0x1BBFD18E, 'QTDS' magic, LE) —
offset-tracking parser + in-place editor library.

Format: facts/04_quest_schema.md. The same record format is used by the
base-game quests in quest00/01.arc (US and EU, 413/413 byte-identical
round-trip each) and by the DLC event quests in the quest1-4 save packs.
Every field's byte offset is recorded so records can be EDITED:

- scalars / monster blocks / reward records: patched in place (fixed size)
- strings (u32 len + utf8, 5 languages): spliced — record length changes,
  which is safe because the loader parses sequentially (offsets already
  float with string lengths) and the ARC entry is re-sized on repack.

After any splice the record is re-parsed so all offsets stay valid.
"""
import struct

NLANG = 5
LANGS = ["en", "fr", "de", "it", "es"]

STRING_FIELDS = ["name", "objective", "sub_objective", "failure",
                 "client", "description"]

MON_FIELDS = ("Type", "Settype", "Starttype", "Num", "Nando_hp", "Nando_at",
              "Nando_etc", "Nando2", "Size", "Sizeparam", "Stamina")
MON_SLOTS = 5
MON_SIZE = 11

# Nando_hp/at/etc are ROW INDEXES into the RPX difficulty table (128 rows at
# 0x101F9E74), not percentages. 127 is the last row; higher values read past
# the table into unrelated data.
NANDO_FIELDS = ("Nando_hp", "Nando_at", "Nando_etc")
NANDO_MAX = 127

REWARD_SLOTS = 32          # per table; two tables (Reward1, Reward2)
REWARD_REGION = REWARD_SLOTS * 4 * 2   # 256 bytes, fixed capacity

# Clr_Pattern (how objective records A/B combine — DTI rQuestData names)
CLR_PATTERNS = {0: "single", 1: "A and B", 2: "A or B"}

# low u16 of ClrParam — objective record type (corpus-observed)
OBJ_TYPES = {
    0x0000: "(none)",       # hunt-all-main-monsters default
    0x0001: "Hunt",         # id = em-ID
    0x0002: "Deliver",      # id = item (1-based items.txt line)
    0x0081: "Capture",      # id = em-ID
    0x0101: "Slay",         # id = em-ID
    0x8101: "Slay small",   # id = em-ID (small monsters share the enum)
    0x0404: "Repel",        # siege: Lagiacrus/Ceadeus intro quests
    0x2515: "Repel siege",  # Jhen Mohran family (paired with a Slay B-record)
    0x4014: "Repel siege",  # Ceadeus "slay or repel"
    0x2000: "Siege dmg?",   # B-record on Jhen quests (num ~1000-1300)
}


class QuestFormatError(ValueError):
    pass


class Quest:
    def __init__(self, data):
        self.data = bytearray(data)
        self._parse()

    # ------------------------------------------------------------- parse

    def _parse(self):
        d = self.data
        if bytes(d[:4]) != b"QTDS":
            raise QuestFormatError(f"bad magic {bytes(d[:4])!r}")
        self._scalar = {}   # name -> (offset, struct fmt)
        self._str_off = {}  # field -> [offset of u32 len prefix] * NLANG
        self.val = {}       # parsed values (display convenience)
        pos = 4

        def u(fmt):
            nonlocal pos
            (v,) = struct.unpack_from(fmt, d, pos)
            pos += struct.calcsize(fmt)
            return v

        def scalar(name, fmt):
            nonlocal pos
            self._scalar[name] = (pos, fmt)
            self.val[name] = u(fmt)

        def strs(name):
            nonlocal pos
            offs, vals = [], []
            for _ in range(NLANG):
                offs.append(pos)
                n = u("<I")
                vals.append(bytes(d[pos:pos + n]))
                pos += n
            self._str_off[name] = offs
            self.val[name] = vals

        if u("<I") != NLANG:
            raise QuestFormatError("language count != 5")
        strs("name")
        scalar("quest_no", "<H")
        strs("objective")
        scalar("star", "B")
        scalar("map", "B")
        strs("sub_objective")
        scalar("time_min", "<H")
        strs("failure")
        # The header mirrors rQuestData's DTI order exactly (failure ptrs end
        # at +0x1AB, then these three u16s, then client/description ptrs).
        scalar("special_flag", "<H")    # DTI SpecialFlag u16 (+0x1AC)
        scalar("special_cond", "<H")    # DTI SpecialCondition (+0x1AE)
        scalar("special_cond2", "<H")   # DTI SpecialCondition2 (+0x1B0)
        strs("client")
        strs("description")
        scalar("main_zako1", "B")
        scalar("main_zako2", "B")
        # DTI Category u64 (+0x1E0; game code tests bits of the low word at
        # +0x1E4). Bits 0x10 / 0x100000 = monster HP x0.55. Verified against
        # a live dump: file 05 00 01 01 00 00 00 00 -> live 0x0000000001010005.
        scalar("category", "<Q")

        self._mon_off = []
        self.monsters = []
        for _ in range(MON_SLOTS):
            self._mon_off.append(pos)
            self.monsters.append(dict(zip(MON_FIELDS, d[pos:pos + MON_SIZE])))
            pos += MON_SIZE

        # Nora block = invaders (DTI names, 6 x u8): SetPer != 0 = unstable,
        # SetMax = max invaders, SetTable = invader list 0x101EBE5C[n]
        scalar("nora_set_per", "B")
        scalar("nora_per_type", "B")
        scalar("nora_set_type", "B")
        scalar("nora_set_max", "B")
        scalar("nora_set_table", "B")
        scalar("nora_pekko", "B")

        # Reward region: FIXED 256 bytes = Reward1 (32 x 4B slots) then
        # Reward2 (32 x 4B). Slot = [item u16][num u8][per u8]; each table's
        # live list ends at the first id==0 slot (bytes after that may be
        # stale build leftovers — preserved, never re-serialized).
        self._rewards_start = pos
        if pos + REWARD_REGION + 94 > len(d):
            raise QuestFormatError(
                f"record too short for reward+tail cluster "
                f"({len(d)} bytes, tail starts {pos})")
        self.reward1 = self._parse_reward_table(pos)
        self.reward2 = self._parse_reward_table(pos + REWARD_SLOTS * 4)
        pos += REWARD_REGION

        # money / settings / zako / objective cluster: fixed offsets from
        # here on. Names and widths follow the game's own reader (0x02076D10)
        # and writer (0x02077354), which store into the DTI fields below.
        self._money_off = pos
        scalar("contract", "<i")        # Contract (fee)
        scalar("reward_money", "<i")    # Reward (zenny)
        scalar("penalty", "<i")         # Penalty (== ceil(reward/3))
        scalar("main_hrp", "<i")        # MainHRPoint
        scalar("failure_hrp", "<i")     # FailureHRPoint
        scalar("hagi_no", "B")          # HagiNo (0-4)
        scalar("prog_no", "B")          # ProgNo (0 except 14 quests)
        scalar("enemy_lv", "B")         # EnemyLv (0-4)
        scalar("demo_no", "B")          # DemoNo: intro cutscene, 0 = none
        scalar("item_set_no", "<H")     # ItemSetNo (0 in every base quest)
        scalar("supp_set_no", "<H")     # SuppSetNo: start crate suppNNN.supp
        scalar("supp_time_flag", "<H")  # SuppTimeFlag (0-3)
        scalar("supp_enemy_type", "<H") # SuppEnemyType
        scalar("supp_enemy_num", "<H")  # SuppEnemyNum
        scalar("start_param", "<H")     # StartParam (0-2)
        scalar("ren_pattern", "<H")     # Ren_pattern (0-8)
        scalar("rannyu_limite", "<H")   # Rannyu_limite (0 in every base quest)
        scalar("zako_ptr", "<I")        # ZakoDataPtr (0 / 0x908)
        scalar("zako_nando_hp", "<I")   # live 608
        scalar("zako_nando_at", "<I")   # live 612
        scalar("zako_nando_etc", "<I")  # live 616
        scalar("zako_param1", "<H")     # live 620
        scalar("zako_id1", "<H")        # live 622
        scalar("zako_num1", "<H")       # live 624
        scalar("zako_param2", "<H")     # live 626
        scalar("zako_id2", "<H")        # live 628
        scalar("zako_num2", "<H")       # live 630
        scalar("zako_ptr2", "<I")       # written from ZakoDataPtr again
        scalar("enemy_box_type", "<I")  # EnemyBoxType (2-4)
        # objective records (DTI: Clr_Pattern, ClrParam/Id/Num A+B)
        scalar("clr_pattern", "<H")     # live 636: see CLR_PATTERNS
        scalar("obj1_param", "<I")      # live 640: low u16 = type, OBJ_TYPES
        scalar("obj1_id", "<H")         # live 644: em-ID / item id per type
        scalar("obj1_num", "<h")        # live 646
        scalar("obj2_param", "<I")      # live 648
        scalar("obj2_id", "<H")         # live 652
        scalar("obj2_num", "<h")        # live 654
        self._rest_off = pos            # trailing flag block(s), unparsed

    def _parse_reward_table(self, start):
        recs = []
        for i in range(REWARD_SLOTS):
            iid, num, per = struct.unpack_from("<HBB", self.data,
                                               start + i * 4)
            if iid == 0 or iid == 5 and num == 0 and per == 0:
                break
            recs.append((iid, num, per))
        return recs

    # ----------------------------------------------------------- getters

    def get(self, name):
        off, fmt = self._scalar[name]
        return struct.unpack_from(fmt, self.data, off)[0]

    def get_string(self, field, lang=0, decode=True):
        raw = self.val[field][lang]
        return raw.decode("utf8", "replace") if decode else raw

    def to_bytes(self):
        return bytes(self.data)

    @property
    def rewards(self):
        """Both tables, Reward1 first (legacy accessor)."""
        return self.reward1 + self.reward2

    # ----------------------------------------------------------- setters

    def set(self, name, value):
        off, fmt = self._scalar[name]
        struct.pack_into(fmt, self.data, off, value)
        self.val[name] = value

    def set_string(self, field, text, langs=range(NLANG)):
        """text: str or bytes. Splices the length-prefixed string(s), then
        re-parses so all offsets stay valid."""
        enc = text if isinstance(text, bytes) else text.encode("utf8")
        new = struct.pack("<I", len(enc)) + enc
        for lang in sorted(langs, reverse=True):  # back-to-front keeps offsets valid
            off = self._str_off[field][lang]
            old_len = struct.unpack_from("<I", self.data, off)[0]
            self.data[off:off + 4 + old_len] = new
        self._parse()

    def set_monster(self, slot, **fields):
        off = self._mon_off[slot]
        for k, v in fields.items():
            if k not in MON_FIELDS:
                raise QuestFormatError(f"unknown monster field {k!r}")
            if not 0 <= int(v) <= 255:
                raise QuestFormatError(f"{k}={v} out of u8 range")
            self.data[off + MON_FIELDS.index(k)] = int(v)
        self.monsters[slot] = dict(zip(MON_FIELDS,
                                       self.data[off:off + MON_SIZE]))

    def clear_monster(self, slot):
        off = self._mon_off[slot]
        self.data[off:off + MON_SIZE] = bytes(MON_SIZE)
        self.monsters[slot] = dict(zip(MON_FIELDS, bytes(MON_SIZE)))

    def reward_capacity(self):
        """Slots per table (fixed regions)."""
        return REWARD_SLOTS

    def set_reward_table(self, table, records):
        """table: 1 or 2. Writes the records into the table's fixed 32-slot
        region; zeroes any slots the old list used beyond the new length
        (stale bytes past the old terminator are left untouched)."""
        if table not in (1, 2):
            raise QuestFormatError("table must be 1 or 2")
        records = list(records)
        if len(records) > REWARD_SLOTS:
            raise QuestFormatError(
                f"{len(records)} reward records > {REWARD_SLOTS} slots")
        old = self.reward1 if table == 1 else self.reward2
        start = self._rewards_start + (table - 1) * REWARD_SLOTS * 4
        for i, (iid, n, p) in enumerate(records):
            struct.pack_into("<HBB", self.data, start + i * 4, iid, n, p)
        if len(records) != len(old):
            # zero removed slots and/or the terminator slot after the list
            lo = len(records) * 4
            hi = max(len(old) * 4, min(len(records) + 1, REWARD_SLOTS) * 4)
            for i in range(lo, hi):
                self.data[start + i] = 0
        if table == 1:
            self.reward1 = records
        else:
            self.reward2 = records

    def set_rewards(self, records):
        """Legacy shim: single list, split Reward1-first like the `rewards`
        property (first len(reward1) records -> table 1, rest -> table 2)."""
        n1 = len(self.reward1)
        self.set_reward_table(1, records[:n1] if len(records) >= n1
                              else records)
        self.set_reward_table(2, records[n1:] if len(records) >= n1 else [])

    # ----------------------------------------------------------- display

    def objectives(self):
        """Decoded objective records: (clr_pattern, [(type, param_hi, id,
        num), ...]) — one or two records, zero records dropped."""
        recs = []
        for k in ("obj1", "obj2"):
            param = self.get(f"{k}_param")
            t, hi = param & 0xFFFF, param >> 16
            i, n = self.get(f"{k}_id"), self.get(f"{k}_num")
            if param or i or n:
                recs.append((t, hi, i, n))
        return self.get("clr_pattern"), recs

    def objective_text(self, mon_name=None, item_name=None):
        """Human summary of the decoded objective, e.g. 'Hunt 2 x em012'.
        mon_name/item_name: optional id->str resolvers."""
        pattern, recs = self.objectives()
        if not recs:
            return "(default: hunt all main monsters)"
        parts = []
        for t, hi, i, n in recs:
            verb = OBJ_TYPES.get(t, f"type 0x{t:x}")
            if t == 2:
                tgt = item_name(i) if item_name else f"item {i}"
            elif t in (1, 0x81, 0x101, 0x8101, 0x404, 0x2515, 0x4014):
                tgt = mon_name(i) if mon_name else f"em{i:03d}"
            else:
                tgt = f"id {i}"
            parts.append(f"{verb} {n} x {tgt}" if n > 1 else f"{verb} {tgt}")
        joiner = {1: " AND ", 2: " OR "}.get(pattern, " / ")
        return joiner.join(parts)

    def summary(self):
        mons = ", ".join(f"em{m['Type']:03d}x{m['Num']}"
                         for m in self.monsters if m["Type"])
        return (f"#{self.get('quest_no'):05d} {self.get('star')}* "
                f"map{self.get('map'):2d} {self.get('time_min')}min "
                f"[{mons or 'no large mon'}] {self.get_string('name')!r}")


def identity_rewrite(data):
    """Self-test: parse, write every field back with its own value, and
    return the result — must equal the input byte-for-byte."""
    q = Quest(data)
    for name in list(q._scalar):
        q.set(name, q.get(name))
    for slot in range(MON_SLOTS):
        q.set_monster(slot, **q.monsters[slot])
    q.set_reward_table(1, list(q.reward1))
    q.set_reward_table(2, list(q.reward2))
    for field in STRING_FIELDS:
        for lang in range(NLANG):
            q.set_string(field, q.get_string(field, lang, decode=False),
                         langs=[lang])
    return q.to_bytes()
