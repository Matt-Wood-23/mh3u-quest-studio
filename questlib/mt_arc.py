"""MT Framework ARC (\\0CRA v16, big-endian Wii U variant): read + rebuild.

In-memory port of the extract/repack logic in mh3u-arc-tool
(https://github.com/Matt-Wood-23/mh3u-arc-tool, MIT), including its
data-alignment fix:

  header  '\\0CRA' + u16 version + u16 count + u32 pad          (12 bytes)
  entry   char[64] path + u32 type_hash + u32 csize
          + u32 (dsize << 3 | flag) + u32 offset                (80 bytes)
  data    zlib blobs; the first starts at the first 0x8000 boundary AFTER
          the entry table (quest00.arc's 413-entry table ends at 0x811C, so
          its data starts at 0x10000), the rest follow back to back.
"""
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path

MAGIC = b"\x00CRA"
HEADER_SIZE = 12
ENTRY_SIZE = 80
DATA_ALIGN = 0x8000
DEFAULT_FLAG = 0b010


class ArcError(ValueError):
    pass


@dataclass
class Entry:
    path: str          # e.g. 'quest\\us\\q_02906'
    type_hash: int
    flag: int
    data: bytes        # decompressed payload

    @property
    def leaf(self):
        return self.path.replace("\\", "/").rsplit("/", 1)[-1]


@dataclass
class Arc:
    version: int
    entries: list = field(default_factory=list)

    def find(self, path):
        for i, e in enumerate(self.entries):
            if e.path == path:
                return i
        return None


def read(path):
    raw = Path(path).read_bytes()
    return parse(raw)


def parse(raw):
    if raw[:4] != MAGIC:
        raise ArcError(f"not an MT ARC (magic {raw[:4]!r})")
    version, count = struct.unpack_from(">HH", raw, 4)
    arc = Arc(version)
    for i in range(count):
        off = HEADER_SIZE + i * ENTRY_SIZE
        name = raw[off:off + 64].split(b"\0", 1)[0].decode("ascii", "replace")
        rtype, csize, dsize_flag, foff = struct.unpack_from(">IIII", raw,
                                                            off + 64)
        blob = raw[foff:foff + csize]
        try:
            data = zlib.decompress(blob)
        except zlib.error as exc:
            raise ArcError(f"entry {i} ({name}) is not a valid zlib stream: "
                           f"{exc}") from None
        if len(data) != dsize_flag >> 3:
            raise ArcError(f"entry {i} ({name}) size mismatch: "
                           f"{len(data)} != {dsize_flag >> 3}")
        arc.entries.append(Entry(name, rtype, dsize_flag & 7, data))
    return arc


def build(arc):
    """Serialize an Arc to bytes (zlib level 6, which the game accepts)."""
    count = len(arc.entries)
    blobs = [zlib.compress(e.data, 6) for e in arc.entries]
    table_end = HEADER_SIZE + count * ENTRY_SIZE
    off = (table_end + DATA_ALIGN - 1) // DATA_ALIGN * DATA_ALIGN
    offsets = []
    for b in blobs:
        offsets.append(off)
        off += len(b)
    buf = bytearray(off)
    struct.pack_into(">4sHHI", buf, 0, MAGIC, arc.version, count, 0)
    for i, (e, blob, boff) in enumerate(zip(arc.entries, blobs, offsets)):
        name = e.path.encode("ascii")
        if len(name) >= 64:
            raise ArcError(f"entry path too long: {e.path!r}")
        eo = HEADER_SIZE + i * ENTRY_SIZE
        buf[eo:eo + 64] = name + bytes(64 - len(name))
        struct.pack_into(">IIII", buf, eo + 64, e.type_hash, len(blob),
                         (len(e.data) << 3) | (e.flag & 7), boff)
        buf[boff:boff + len(blob)] = blob
    return bytes(buf)
