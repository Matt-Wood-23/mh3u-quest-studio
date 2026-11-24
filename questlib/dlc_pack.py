"""DLC / event quest packs: the quest1..quest4 files in the Cemu save folder
(mlc01/usr/save/00050000/<title>/user/<id>/), plus loose .quest files.

Pack layout (0x29024 bytes):
  0x0000  0x28-byte header (kept verbatim, but see the name hash below)
  0x0028  20 slots x 0x2010 bytes:
            0x0000  QTDS quest record, zero-padded to 0x2000
            0x2000  16-byte file name, e.g. 'q_20102.quest'
  ...     zero tail
Empty slots are all zeros. The quest records use the same format as the
base-game quests (quest_format.Quest).

The game counts a pack's filled slots (N) and reads only slots 1..N, so the
quests have to sit together from slot 1: a quest after an empty slot can fall
past the end and not show (gamedata.EVENT_PACKS has which packs it reads).

Header +0x14 holds a hash of the file's own name (JAMCRC of 'quest1' etc., as
in every save file). The game skips a pack whose hash is another file's: a
quest1 copied to quest2 by hand is never read.
"""
import shutil
import zlib
from pathlib import Path

from .quest_format import Quest

HEADER = 0x28
SLOT = 0x2010
DATA = 0x2000
NAME = 16
SLOTS = 20
NAME_HASH = 0x14
PACK_NAMES = ("quest1", "quest2", "quest3", "quest4")


def name_hash(name):
    """The hash a save file's header holds for its file name."""
    return zlib.crc32(name.encode("ascii")) ^ 0xFFFFFFFF


class PackError(ValueError):
    pass


def fit(data, size):
    """Trim trailing zero padding (or pad) a quest buffer to exactly `size`.
    Text edits grow the record; the slot has ~4 KB of padding to absorb it."""
    data = bytes(data)
    if len(data) <= size:
        return data + bytes(size - len(data))
    if any(data[size:]):
        raise PackError(f"quest record is {len(data.rstrip(b'\0'))} bytes, "
                        f"larger than the {size}-byte slot — shorten the text")
    return data[:size]


class DlcPack:
    def __init__(self, path):
        self.path = Path(path)
        self.data = bytearray(self.path.read_bytes())
        if len(self.data) < HEADER + SLOTS * SLOT:
            raise PackError(f"{self.path.name}: {len(self.data)} bytes is too "
                            f"small for a quest pack")

    def copied_from(self):
        """The pack this file is a renamed copy of, or None. Its header still
        carries the other file's name hash, so the game skips it. Only packs
        named quest1..quest4 are checked."""
        name = self.path.name.lower()
        if name not in PACK_NAMES:
            return None
        h = int.from_bytes(self.data[NAME_HASH:NAME_HASH + 4], "big")
        if h == name_hash(name):
            return None
        return next((n for n in PACK_NAMES if n != name and name_hash(n) == h),
                    None)

    def fix_name_hash(self):
        """Give the header this file's own name hash, so the game reads it."""
        name = self.path.name.lower()
        self.data[NAME_HASH:NAME_HASH + 4] = name_hash(name).to_bytes(4, "big")

    def _off(self, i):
        if not 0 <= i < SLOTS:
            raise PackError(f"slot {i} out of range")
        return HEADER + i * SLOT

    def has_quest(self, i):
        o = self._off(i)
        return self.data[o:o + 4] == b"QTDS"

    def file_name(self, i):
        o = self._off(i) + DATA
        return bytes(self.data[o:o + NAME]).split(b"\0", 1)[0].decode(
            "ascii", "replace")

    def record(self, i):
        o = self._off(i)
        return bytes(self.data[o:o + DATA])

    def set_record(self, i, data):
        Quest(data)                       # must still parse
        o = self._off(i)
        self.data[o:o + DATA] = fit(data, DATA)

    def quests(self):
        """[(slot, Quest)] for the filled slots."""
        out = []
        for i in range(SLOTS):
            if self.has_quest(i):
                out.append((i, Quest(self.record(i))))
        return out

    def empty_slots(self):
        return [i for i in range(SLOTS) if not self.has_quest(i)]

    def unread_slots(self):
        """Filled slots the game skips: it reads only as many slots from the
        top as the pack has quests, so a gap pushes the last ones out."""
        filled = [i for i in range(SLOTS) if self.has_quest(i)]
        return [i for i in filled if i >= len(filled)]

    def close_gaps(self):
        """Move each quest up into the empty slots before it, keeping their
        order. A slot moves unchanged (record and file name). Returns
        {old slot: new slot} for the quests that moved."""
        moved, n = {}, 0
        for i in range(SLOTS):
            if not self.has_quest(i):
                continue
            if i != n:
                src, dst = self._off(i), self._off(n)
                self.data[dst:dst + SLOT] = self.data[src:src + SLOT]
                self.data[src:src + SLOT] = bytes(SLOT)
                moved[i] = n
            n += 1
        return moved

    def slot_bytes(self, i):
        """A whole slot (record and file name), for moving it to another
        pack."""
        o = self._off(i)
        return bytes(self.data[o:o + SLOT])

    def put_slot(self, raw):
        """Copy a slot from slot_bytes() into the first empty slot; returns
        that slot."""
        if len(raw) != SLOT or raw[:4] != b"QTDS":
            raise PackError("not a quest slot")
        empty = self.empty_slots()
        if not empty:
            raise PackError(f"{self.path.name} has no empty slot")
        o = self._off(empty[0])
        self.data[o:o + SLOT] = raw
        return empty[0]

    def export_record(self, i):
        """The bare quest record, without the slot's zero padding and file
        name: what a loose q_NNNNN.quest file holds."""
        return self.record(i).rstrip(b"\0")

    def create_quest(self, slot, template, quest_no):
        """Fill an empty slot with a copy of an event-quest record under a
        new quest number (file name q_NNNNN.quest). Use an existing EVENT
        quest as the template: event records carry ~2 KB of data after the
        objectives that base-game quests don't have."""
        if self.has_quest(slot):
            raise PackError(f"slot {slot + 1} is not empty")
        q = Quest(template)
        q.set("quest_no", quest_no)
        self.set_record(slot, q.to_bytes())
        name = f"q_{quest_no:05d}.quest".encode("ascii")
        o = self._off(slot) + DATA
        self.data[o:o + NAME] = name + bytes(NAME - len(name))

    def clear_slot(self, slot):
        o = self._off(slot)
        self.data[o:o + SLOT] = bytes(SLOT)

    def save(self, path=None, backup=True):
        dst = Path(path) if path else self.path
        if backup and dst.exists():
            bak = dst.with_name(dst.name + ".BACKUP")
            if not bak.exists():
                shutil.copy2(dst, bak)
        dst.write_bytes(bytes(self.data))
        return dst


class QuestFile:
    """A loose .quest file (one QTDS record, any length)."""

    def __init__(self, path):
        self.path = Path(path)
        self.data = self.path.read_bytes()
        if self.data[:4] != b"QTDS":
            raise PackError(f"{self.path.name} is not a QTDS quest file")
        self.size = len(self.data)

    def record(self, i=0):
        return self.data

    def set_record(self, i, data):
        Quest(data)
        data = bytes(data)
        if self.data.endswith(bytes(16)):     # padded file: keep its length
            try:
                self.data = fit(data, self.size)
                return
            except PackError:
                pass                          # grew past the padding
        self.data = data

    def quests(self):
        return [(0, Quest(self.data))]

    def export_record(self, i=0):
        return self.data.rstrip(b"\0")

    def file_name(self, i=0):
        return self.path.name

    def save(self, path=None, backup=True):
        dst = Path(path) if path else self.path
        if backup and dst.exists():
            bak = dst.with_name(dst.name + ".BACKUP")
            if not bak.exists():
                shutil.copy2(dst, bak)
        dst.write_bytes(self.data)
        return dst
