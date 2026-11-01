"""DLC / event quest packs: the quest1..quest4 files in the Cemu save folder
(mlc01/usr/save/00050000/<title>/user/<id>/), plus loose .quest files.

Pack layout (0x29024 bytes):
  0x0000  0x28-byte header (kept verbatim)
  0x0028  20 slots x 0x2010 bytes:
            0x0000  QTDS quest record, zero-padded to 0x2000
            0x2000  16-byte file name, e.g. 'q_20102.quest'
  ...     zero tail
Empty slots are all zeros. The quest records use the same format as the
base-game quests (quest_format.Quest).
"""
import shutil
from pathlib import Path

from .quest_format import Quest

HEADER = 0x28
SLOT = 0x2010
DATA = 0x2000
NAME = 16
SLOTS = 20


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
