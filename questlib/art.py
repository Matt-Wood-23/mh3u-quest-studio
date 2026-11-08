"""Game art for the Studio: monster icons, item icons and area maps.

Nothing from the game ships with the Studio. The pictures are read from the
player's own game files (the folders set under Game folders), decoded once and
kept as PNG files in <workspace>/art, so later starts are quick. If anything is
missing the Studio simply shows no pictures.

Textures are MT Framework TEX v0xA5 (Wii U): BC1/BC2 blocks stored in the GX2
2D-tiled layout. Plain Python, no extra packages.
"""
import json
import struct
import zlib
from pathlib import Path

from . import mt_arc

TEX_TYPE = 0x241F5DEB
COM_ARC = "ID/ID_com_eng.arc"
MON_SHEET = "GUI\\Texture\\common\\td_icon_m_ID_eng"
MON_CELL, MON_COLS = 112, 9           # 9x9 grid of 112 px icons
SCROLL_CELL = 80                      # the sheet's quest-scroll icon
ITEM_SHEET = "GUI\\Texture\\common\\td_icon_ID_eng"
ITEM_CELL, ITEM_COLS = 50, 10         # white item icons, tinted per item
MAP_SIZE = 512                        # map textures are 512x512
CACHE_VERSION = 1

# ------------------------------------------------------------ texture decode
_PIPES, _BANKS = 2, 4
_MT_PITCH, _MT_HEIGHT = 8 * _BANKS, 8 * _PIPES      # macro tile, in blocks


def _micro(x, y, bpp):
    if bpp == 64:
        return ((x & 1) | ((y & 1) << 1) | (((x >> 1) & 1) << 2)
                | (((x >> 2) & 1) << 3) | (((y >> 1) & 1) << 4)
                | (((y >> 2) & 1) << 5))
    return ((y & 1) | ((x & 1) << 1) | (((x >> 1) & 1) << 2)
            | (((x >> 2) & 1) << 3) | (((y >> 1) & 1) << 4)
            | (((y >> 2) & 1) << 5))


def _addr(x, y, bpp, pitch):
    """Byte offset of block (x, y) in a GX2 TM_2D_TILED_THIN1 surface."""
    pixel_off = (_micro(x, y, bpp) * bpp) >> 3
    pipe = ((y >> 3) ^ (x >> 3)) & 1
    b = (y >> 4) & 3
    bank = (((b >> 1) | (b << 1)) ^ (x >> 3)) & 3
    bp = (pipe + _PIPES * bank) % (_PIPES * _BANKS)
    pipe, bank = bp % _PIPES, bp // _PIPES
    macro_bytes = (bpp * _MT_HEIGHT * _MT_PITCH + 7) >> 3
    macro_off = ((x // _MT_PITCH) + (pitch // _MT_PITCH) * (y // _MT_HEIGHT)) \
        * macro_bytes
    mso = (macro_off >> 3) + pixel_off
    return (((mso & ~0xFF) << 3) | (mso & 0xFF) | (pipe << 8) | (bank << 9))


def _rgb565(c):
    return (((c >> 11) & 31) * 527 + 23) >> 6, \
        (((c >> 5) & 63) * 259 + 33) >> 6, ((c & 31) * 527 + 23) >> 6


def decode_tex(blob):
    """MT TEX (BC1 or BC2, mip 0) -> (width, height, RGBA bytearray)."""
    if blob[:4] != b"\x00XET":
        raise ValueError("not a TEX file")
    _, w2, w3 = struct.unpack_from(">III", blob, 4)
    width, height, fmt = (w2 >> 13) & 0x1FFF, w2 & 0x1FFF, (w3 >> 16) & 0xFF
    bpb = {0x0B: 8, 0x0C: 16}.get(fmt)
    if bpb is None:
        raise ValueError(f"texture format {fmt:#x} not supported")
    bw, bh = (width + 3) // 4, (height + 3) // 4
    pitch = -(-bw // _MT_PITCH) * _MT_PITCH
    data = blob[16:]
    out = bytearray(width * height * 4)
    row = width * 4
    for by in range(bh):
        for bx in range(bw):
            a = _addr(bx, by, bpb * 8, pitch)
            if bpb == 16:
                alpha = int.from_bytes(data[a:a + 8], "little")
                a += 8
            c0, c1, idx = struct.unpack_from("<HHI", data, a)
            r0, g0, b0 = _rgb565(c0)
            r1, g1, b1 = _rgb565(c1)
            if bpb == 16 or c0 > c1:
                pal = ((r0, g0, b0, 255), (r1, g1, b1, 255),
                       ((2 * r0 + r1) // 3, (2 * g0 + g1) // 3,
                        (2 * b0 + b1) // 3, 255),
                       ((r0 + 2 * r1) // 3, (g0 + 2 * g1) // 3,
                        (b0 + 2 * b1) // 3, 255))
            else:
                pal = ((r0, g0, b0, 255), (r1, g1, b1, 255),
                       ((r0 + r1) // 2, (g0 + g1) // 2, (b0 + b1) // 2, 255),
                       (0, 0, 0, 0))
            for i in range(16):
                px, py = bx * 4 + (i & 3), by * 4 + (i >> 2)
                if px >= width or py >= height:
                    continue
                r, g, b, al = pal[(idx >> (2 * i)) & 3]
                if bpb == 16:
                    al = ((alpha >> (4 * i)) & 15) * 17
                o = py * row + px * 4
                out[o:o + 4] = bytes((r, g, b, al))
    return width, height, out


# ------------------------------------------------------------- image helpers
def crop(w, rgba, x, y, cw, ch):
    out = bytearray()
    for yy in range(y, y + ch):
        o = (yy * w + x) * 4
        out += rgba[o:o + cw * 4]
    return out


def resize(w, h, rgba, nw, nh):
    """Area-average resize (alpha-weighted so edges don't darken)."""
    out = bytearray(nw * nh * 4)
    sx, sy = w / nw, h / nh
    for oy in range(nh):
        y0, y1 = int(oy * sy), max(int(oy * sy) + 1, int((oy + 1) * sy))
        for ox in range(nw):
            x0, x1 = int(ox * sx), max(int(ox * sx) + 1, int((ox + 1) * sx))
            r = g = b = a = n = 0
            for yy in range(y0, min(y1, h)):
                o = (yy * w + x0) * 4
                for _ in range(x0, min(x1, w)):
                    al = rgba[o + 3]
                    r += rgba[o] * al
                    g += rgba[o + 1] * al
                    b += rgba[o + 2] * al
                    a += al
                    n += 1
                    o += 4
            o = (oy * nw + ox) * 4
            if a:
                out[o:o + 4] = bytes((r // a, g // a, b // a, a // n))
    return out


def tint(rgba, hex_rgb):
    """Multiply every pixel by a colour (the game draws its white item icons
    this way)."""
    r0, g0, b0 = (int(hex_rgb[i:i + 2], 16) for i in (0, 2, 4))
    out = bytearray(rgba)
    for o in range(0, len(out), 4):
        out[o] = out[o] * r0 // 255
        out[o + 1] = out[o + 1] * g0 // 255
        out[o + 2] = out[o + 2] * b0 // 255
    return out


def png_bytes(w, h, rgba):
    raw = b"".join(b"\x00" + bytes(rgba[y * w * 4:(y + 1) * w * 4])
                   for y in range(h))

    def chunk(tag, body):
        return (struct.pack(">I", len(body)) + tag + body
                + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


# ------------------------------------------------------------------ the art
class Art:
    """Pictures from the game. Every getter returns None when a picture
    isn't available, so callers can always fall back to text."""

    def __init__(self, game_dirs=(), cache_dir=None, layout=None):
        self.game_dirs = [Path(g) for g in game_dirs]
        self.cache = Path(cache_dir) / f"v{CACHE_VERSION}" if cache_dir else None
        self.layout = layout or {}
        self._sheets = {}         # key -> (w, h, rgba) or None
        self._photos = {}         # (kind, key, size) -> PhotoImage
        self._map_arcs = None

    # ---- where the textures live
    def _arc_path(self, rel):
        for g in reversed(self.game_dirs):          # later folders override
            p = g / "nativeCafe" / "arc" / Path(rel)
            if p.is_file():
                return p
        return None

    def _map_entry(self, stage):
        """(arc path, entry name) of a stage's area map, day version first."""
        if self._map_arcs is None:
            self._map_arcs = {}
            prefs = ("d_ID", "d_mizu_ID", "d_1_ID", "d_riku_ID", "n_ID")
            for g in reversed(self.game_dirs):
                folder = g / "nativeCafe" / "arc" / "ID" / "map"
                for p in sorted(folder.glob("ID_map_*.arc")) if folder.is_dir() else ():
                    try:
                        arc = mt_arc.read(p)
                    except Exception:
                        continue
                    for e in arc.entries:
                        leaf = e.path.rsplit("\\", 1)[-1]
                        if e.type_hash != TEX_TYPE or not leaf.startswith("td_map_m"):
                            continue
                        try:
                            st = int(leaf[8:10])
                        except ValueError:
                            continue
                        rest = leaf[10:]
                        rank = prefs.index(rest) if rest in prefs else len(prefs)
                        if st not in self._map_arcs or rank < self._map_arcs[st][0]:
                            self._map_arcs[st] = (rank, p, e.path)
        hit = self._map_arcs.get(stage)
        return (hit[1], hit[2]) if hit else None

    # ---- decoded textures, cached as zlib'd RGBA
    def _sheet(self, key, locate):
        if key in self._sheets:
            return self._sheets[key]
        img = None
        raw = self.cache / "raw" / f"{key}.rgba.z" if self.cache else None
        try:
            if raw and raw.is_file():
                b = zlib.decompress(raw.read_bytes())
                w, h = struct.unpack_from("<II", b)
                img = (w, h, bytearray(b[8:]))
            else:
                where = locate()
                if where:
                    arc = mt_arc.read(where[0])
                    i = arc.find(where[1])
                    if i is not None:
                        img = decode_tex(arc.entries[i].data)
                        if raw:
                            raw.parent.mkdir(parents=True, exist_ok=True)
                            raw.write_bytes(zlib.compress(
                                struct.pack("<II", img[0], img[1]) + bytes(img[2]), 6))
        except Exception:
            img = None
        self._sheets[key] = img
        return img

    def _photo(self, kind, key, size, make):
        """PhotoImage of a derived picture, kept as <cache>/<kind>/<key>_<size>.png."""
        k = (kind, key, size)
        if k in self._photos:
            return self._photos[k]
        photo = None
        try:
            import tkinter as tk
            path = self.cache / kind / f"{key}_{size}.png" if self.cache else None
            if path and path.is_file():
                photo = tk.PhotoImage(file=str(path))
            else:
                made = make()
                if made:
                    png = png_bytes(*made)
                    if path:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(png)
                    import base64
                    photo = tk.PhotoImage(data=base64.b64encode(png))
        except Exception:
            photo = None
        self._photos[k] = photo
        return photo

    # ---- public
    def monster_cell(self, em_id):
        return self.layout.get("monster_icon", {}).get(str(em_id))

    def monster_icon(self, em_id, size=40):
        cell = self.monster_cell(em_id)
        return None if cell is None else self.sheet_icon(cell, size)

    def sheet_icon(self, cell, size=40):
        """Any cell of the monster icon sheet (80 = the quest scroll)."""
        def make():
            sheet = self._sheet("mon", lambda: (self._arc_path(COM_ARC), MON_SHEET)
                                if self._arc_path(COM_ARC) else None)
            if not sheet:
                return None
            w, h, rgba = sheet
            x, y = (cell % MON_COLS) * MON_CELL, (cell // MON_COLS) * MON_CELL
            c = crop(w, rgba, x, y, MON_CELL, MON_CELL)
            return size, size, resize(MON_CELL, MON_CELL, c, size, size)
        return self._photo("mon", cell, size, make)

    def item_icon(self, item_id, size=24):
        """The item's icon in its colour, as the game's menus draw it."""
        table = self.layout.get("item_icon") or []
        if not 0 < item_id < len(table):
            return None
        cell, colour = table[item_id]
        pal = self.layout.get("item_colours") or ["ffffff"]
        rgb = pal[colour] if colour < len(pal) else pal[0]

        def make():
            sheet = self._sheet("item", lambda: (self._arc_path(COM_ARC), ITEM_SHEET)
                                if self._arc_path(COM_ARC) else None)
            if not sheet:
                return None
            w, h, rgba = sheet
            x, y = (cell % ITEM_COLS) * ITEM_CELL, (cell // ITEM_COLS) * ITEM_CELL
            c = tint(crop(w, rgba, x, y, ITEM_CELL, ITEM_CELL), rgb)
            return size, size, resize(ITEM_CELL, ITEM_CELL, c, size, size)
        return self._photo("item", f"{cell}_{rgb}", size, make)

    def map_image(self, stage, size=320):
        """The stage's in-game area map, size x size, or None."""
        def make():
            sheet = self._sheet(f"map{stage:02d}", lambda: self._map_entry(stage))
            if not sheet:
                return None
            w, h, rgba = sheet
            return size, size, resize(w, h, rgba, size, size)
        return self._photo("map", f"m{stage:02d}", size, make)

    def area_xy(self, stage, shown_area, size=320):
        """Where a map-numbered area (0 = camp) sits on map_image(stage, size)."""
        pos = self.layout.get("map_markers", {}).get(str(stage), {}).get(str(shown_area))
        if not pos:
            return None
        return pos[0] * size / MAP_SIZE, pos[1] * size / MAP_SIZE


ART = Art()          # replaced by setup() once the game folders are known


def setup(game_dirs, cache_dir, layout_path):
    global ART
    try:
        layout = json.loads(Path(layout_path).read_text(encoding="utf-8"))
    except Exception:
        layout = {}
    ART = Art(game_dirs, cache_dir, layout)
    return ART
