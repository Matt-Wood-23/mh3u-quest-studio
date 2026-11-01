"""Base-game quest project: game folders, pristine arcs, edits, build/install.

Layout of the workspace folder (default: ./workspace next to the app):

  <region>/original/<pack>.arc        pristine copy of the game's arc
  <region>/edits/<pack>/q_NNNNN.quest edited quest records (only changed ones)
  <region>/build/<pack>.arc           rebuilt arc = original + edits

Installing copies the built arc over the game's arc in every configured game
folder; the first install backs the game's file up as <pack>.arc.orig.
Restore puts the .orig back. Cemu reads the arc at boot, so restart the
game after installing.
"""
import hashlib
import json
import os
import re
import shutil
from pathlib import Path

from . import mt_arc
from .quest_format import Quest

QUEST_TYPE = 0x1BBFD18E      # rQuestData (DTI hash) = 'QTDS' records
PACKS = ("quest00", "quest01")
TITLE_REGIONS = {"10118300": "us", "10117200": "eu", "10104d00": "jp"}
REGION_TITLES = {v: k for k, v in TITLE_REGIONS.items()}
QUEST_ENTRY = re.compile(r"q_(\d+)$")


class ProjectError(RuntimeError):
    pass


# ----------------------------------------------------------- game folders

def content_dir(path):
    """Accept a title folder, its content folder, or anything inside
    content/; return the content folder (or None)."""
    p = Path(path)
    for cand in (p, p / "content", *p.parents):
        if (cand / "nativeCafe" / "arc" / "quest").is_dir():
            return cand
    return None


def regions_in(content):
    q = Path(content) / "nativeCafe" / "arc" / "quest"
    return sorted(d.name for d in q.iterdir()
                  if d.is_dir() and (d / "quest00.arc").exists()) if q.is_dir() else []


def title_id_of(content):
    meta = Path(content).parent / "meta" / "meta.xml"
    try:
        m = re.search(r"<title_id[^>]*>([0-9A-Fa-f]{16})<", meta.read_text(
            encoding="utf8", errors="replace"))
    except OSError:
        return None
    return m.group(1).lower() if m else None


def default_region(content):
    tid = title_id_of(content)
    regions = regions_in(content)
    guess = TITLE_REGIONS.get(tid[-8:]) if tid else None
    if guess in regions:
        return guess
    return "us" if "us" in regions else (regions[0] if regions else None)


def cemu_mlc_dirs():
    """mlc01 folders of the usual Cemu installs (settings.xml mlc_path or the
    default %APPDATA%/Cemu/mlc01)."""
    out = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        cemu = Path(appdata) / "Cemu"
        try:
            txt = (cemu / "settings.xml").read_text(encoding="utf8",
                                                    errors="replace")
            m = re.search(r"<mlc_path>([^<]+)</mlc_path>", txt)
            if m and m.group(1).strip():
                out.append(Path(m.group(1).strip()))
        except OSError:
            pass
        out.append(cemu / "mlc01")
    seen, res = set(), []
    for p in out:
        if p.is_dir() and str(p).lower() not in seen:
            seen.add(str(p).lower())
            res.append(p)
    return res


def detect_game_dirs():
    """MH3U titles installed into Cemu's mlc01 (US/EU/JP)."""
    found = []
    for mlc in cemu_mlc_dirs():
        for tid in TITLE_REGIONS:
            c = mlc / "usr" / "title" / "00050000" / tid / "content"
            if (c / "nativeCafe" / "arc" / "quest").is_dir():
                found.append(c)
    return found


def cemu_save_dirs():
    """Folders holding the DLC quest packs (quest1..quest4)."""
    out = []
    for mlc in cemu_mlc_dirs():
        for tid in TITLE_REGIONS:
            base = mlc / "usr" / "save" / "00050000" / tid / "user"
            if base.is_dir():
                out += [d for d in sorted(base.iterdir())
                        if d.is_dir() and (d / "quest1").exists()]
    return out


# ------------------------------------------------------------------ config

class Config:
    def __init__(self, path):
        self.path = Path(path)
        self.game_dirs = []
        self.region = None
        self.workspace = None
        if self.path.exists():
            try:
                j = json.loads(self.path.read_text(encoding="utf8"))
            except (OSError, ValueError):
                j = {}
            self.game_dirs = [Path(p) for p in j.get("game_dirs", [])]
            self.region = j.get("region")
            self.workspace = j.get("workspace")

    def save(self):
        self.path.write_text(json.dumps({
            "game_dirs": [str(p) for p in self.game_dirs],
            "region": self.region,
            "workspace": self.workspace,
        }, indent=2), encoding="utf8")


# ----------------------------------------------------------------- project

def _sha1(b):
    return hashlib.sha1(b).hexdigest()


class Project:
    def __init__(self, game_dirs, region, workspace):
        if not game_dirs:
            raise ProjectError("no game folder configured")
        self.game_dirs = [Path(g) for g in game_dirs]
        self.region = region
        self.root = Path(workspace) / region
        self._arcs = {}          # pack -> mt_arc.Arc (pristine)

    # paths
    def game_arc(self, game_dir, pack):
        return (Path(game_dir) / "nativeCafe" / "arc" / "quest" / self.region
                / f"{pack}.arc")

    def pristine_path(self, pack):
        return self.root / "original" / f"{pack}.arc"

    def edits_dir(self, pack):
        return self.root / "edits" / pack

    def build_path(self, pack):
        return self.root / "build" / f"{pack}.arc"

    # pristine
    def ensure_pristine(self, pack):
        """Copy the game's untouched arc into the workspace (once). Prefers
        <pack>.arc.orig (left by an earlier install) over the live file.
        If the live arc was already modded, its changed quests are adopted
        as edits so nothing installed earlier is lost."""
        dst = self.pristine_path(pack)
        if dst.exists():
            return dst
        src = live = None
        for g in self.game_dirs:
            arc = self.game_arc(g, pack)
            orig = arc.with_suffix(".arc.orig")
            if orig.exists():
                src, live = orig, arc
                break
            if arc.exists() and src is None:
                src = arc
        if src is None:
            raise ProjectError(
                f"{pack}.arc not found under nativeCafe/arc/quest/{self.region} "
                f"in any game folder")
        mt_arc.read(src)          # validate before adopting it
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        if live is not None and live.exists():
            self._adopt(pack, live)
        return dst

    def _adopt(self, pack, arc_path):
        try:
            modded = mt_arc.read(arc_path)
        except mt_arc.ArcError:
            return 0
        base = self.arc(pack)
        n = 0
        for e in modded.entries:
            i = base.find(e.path)
            if (e.type_hash == QUEST_TYPE and i is not None
                    and base.entries[i].data != e.data):
                self._edit_file(pack, e.leaf).parent.mkdir(parents=True,
                                                            exist_ok=True)
                self._edit_file(pack, e.leaf).write_bytes(e.data)
                n += 1
        return n

    def arc(self, pack):
        if pack not in self._arcs:
            self._arcs[pack] = mt_arc.read(self.ensure_pristine(pack))
        return self._arcs[pack]

    # quests
    def _edit_file(self, pack, leaf):
        return self.edits_dir(pack) / f"{leaf}.quest"

    def quest_entries(self, pack):
        """[(entry_leaf, entry_index)] for every quest record in the arc."""
        return sorted(((e.leaf, i) for i, e in enumerate(self.arc(pack).entries)
                       if e.type_hash == QUEST_TYPE))

    def pristine_data(self, pack, leaf):
        for e in self.arc(pack).entries:
            if e.leaf == leaf and e.type_hash == QUEST_TYPE:
                return e.data
        raise ProjectError(f"{leaf} not in {pack}")

    def load(self, pack, leaf):
        f = self._edit_file(pack, leaf)
        return f.read_bytes() if f.exists() else self.pristine_data(pack, leaf)

    def is_modified(self, pack, leaf):
        return self._edit_file(pack, leaf).exists()

    def modified(self, pack):
        d = self.edits_dir(pack)
        return sorted(f.stem for f in d.glob("*.quest")) if d.is_dir() else []

    def save(self, pack, leaf, data):
        Quest(data)               # must still parse
        f = self._edit_file(pack, leaf)
        if bytes(data) == self.pristine_data(pack, leaf):
            if f.exists():
                f.unlink()
            return
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(bytes(data))

    def revert(self, pack, leaf):
        f = self._edit_file(pack, leaf)
        if f.exists():
            f.unlink()

    def find_leaf(self, pack, quest_no):
        leaf = f"q_{quest_no:05d}"
        if any(lf == leaf for lf, _ in self.quest_entries(pack)):
            return leaf
        return None

    # build / install
    def build(self, pack):
        base = self.arc(pack)
        out = mt_arc.Arc(base.version)
        for e in base.entries:
            f = self._edit_file(pack, e.leaf)
            data = (f.read_bytes() if e.type_hash == QUEST_TYPE and f.exists()
                    else e.data)
            out.entries.append(mt_arc.Entry(e.path, e.type_hash, e.flag, data))
        raw = mt_arc.build(out)
        check = mt_arc.parse(raw)     # re-read: every quest must parse
        for e in check.entries:
            if e.type_hash == QUEST_TYPE:
                Quest(e.data)
        p = self.build_path(pack)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
        self._sig_path(pack).write_text(json.dumps(self.edits_signature(pack)))
        return p

    def _sig_path(self, pack):
        return self.build_path(pack).with_suffix(".edits.json")

    def edits_signature(self, pack):
        d = self.edits_dir(pack)
        if not d.is_dir():
            return {}
        return {f.stem: _sha1(f.read_bytes()) for f in sorted(d.glob("*.quest"))}

    def pack_status(self, pack):
        """'clean' (no edits, game has the original), 'installed' (game has
        exactly the current edits) or 'pending' (install needed)."""
        states = [s for _, s in self.install_state(pack)]
        edits = self.edits_signature(pack)
        if not edits:
            return "clean" if all(s == "original" for s in states) else "pending"
        try:
            built = json.loads(self._sig_path(pack).read_text())
        except (OSError, ValueError):
            built = None
        if built == edits and states and all(s == "this build" for s in states):
            return "installed"
        return "pending"

    def install_targets(self, pack):
        return [self.game_arc(g, pack) for g in self.game_dirs
                if self.game_arc(g, pack).exists()]

    def install(self, pack):
        p = self.build(pack)
        done = []
        for target in self.install_targets(pack):
            backup = target.with_suffix(".arc.orig")
            if not backup.exists():
                shutil.copy2(target, backup)
            shutil.copy2(p, target)
            done.append(target)
        if not done:
            raise ProjectError(f"no {pack}.arc found in the game folders")
        return done

    def restore(self, pack):
        done = []
        for target in self.install_targets(pack):
            backup = target.with_suffix(".arc.orig")
            if backup.exists():
                shutil.copy2(backup, target)
                done.append(target)
        return done

    def install_state(self, pack):
        """[(target, 'original' | 'this build' | 'modded')]"""
        pristine = _sha1(self.ensure_pristine(pack).read_bytes())
        built = (_sha1(self.build_path(pack).read_bytes())
                 if self.build_path(pack).exists() else None)
        out = []
        for t in self.install_targets(pack):
            h = _sha1(t.read_bytes())
            out.append((t, "original" if h == pristine else
                        "this build" if h == built else "modded"))
        return out
