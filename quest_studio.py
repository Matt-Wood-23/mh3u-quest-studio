#!/usr/bin/env python3
"""MH3U Quest Studio — quest editor for Monster Hunter 3 Ultimate (Wii U).

* Base Game tab: the 412 village/port quests inside quest00/quest01.arc.
  Edits are kept in ./workspace and installed into your game folder
  (the original file is backed up as .arc.orig).
* DLC / Event tab: event quest packs (quest1..quest4 in the Cemu save
  folder) and loose .quest files.

Run:  python quest_studio.py
"""
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from questlib import __version__                       # noqa: E402
from questlib import gamedata as GD                    # noqa: E402
from questlib import project as P                      # noqa: E402
from questlib.dlc_pack import DlcPack, QuestFile, PackError  # noqa: E402
from questlib.quest_format import Quest, QuestFormatError    # noqa: E402
from questlib.theme import apply_dark_theme, TK_DARK, MUTED, OK_FG, ERR_FG, ACCENT  # noqa: E402
from questlib.widgets import QuestEditor               # noqa: E402

CONFIG = HERE / "studio_config.json"
DEFAULT_WORKSPACE = HERE / "workspace"
PACK_LABELS = {"quest00": "quest00 (412 quests)",
               "quest01": "quest01 (1 quest)"}


def quest_row_text(q):
    mons = ", ".join(f"{GD.mon_name(m['Type'])}" + (f" x{m['Num']}"
                                                   if m["Num"] > 1 else "")
                     for m in q.monsters if m["Type"])
    return mons or "—"


def donor_candidates(project, pack, em_id, quest_map):
    """Monster blocks from the base-game quests, best matches first."""
    if project is None:
        return []
    out = []
    for leaf, _ in project.quest_entries(pack):
        try:
            q = Quest(project.pristine_data(pack, leaf))
        except QuestFormatError:
            continue
        for slot, m in enumerate(q.monsters):
            if not m["Type"] or (em_id and m["Type"] != em_id):
                continue
            same_map = q.get("map") == quest_map
            label = (f"{'*' if same_map else ' '} {GD.mon_name(m['Type']):<22} "
                     f"#{q.get('quest_no'):05d} {q.get('star')}★ "
                     f"{GD.map_name(q.get('map')):<18} rows "
                     f"{m['Nando_hp']}/{m['Nando_at']}/{m['Nando_etc']}  "
                     f"{q.get_string('name')}")
            out.append((not same_map, q.get("star"), label, m))
    out.sort(key=lambda t: (t[0], t[1]))
    return [(label, m) for _, _, label, m in out]


# ================================================================== setup

class SetupDialog(tk.Toplevel):
    """Pick the game folder(s) Cemu loads and the quest region."""

    def __init__(self, parent, cfg):
        super().__init__(parent)
        self.title("Quest Studio — game folder")
        self.configure(bg=TK_DARK["bg"])
        self.geometry("760x420")
        self.transient(parent)
        self.grab_set()
        self.cfg = cfg
        self.ok = False
        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, wraplength=730, justify="left", text=(
            "Choose the MH3U game folder that Cemu actually runs. For games "
            "installed into Cemu that is mlc01\\usr\\title\\00050000\\<id>"
            "\\content. If you also keep a loose copy of the game, add both: "
            "installs go to every folder listed here.")).pack(anchor="w")
        self.lb = tk.Listbox(frm, height=6, **TK_DARK)
        self.lb.pack(fill="x", pady=8)
        for p in cfg.game_dirs:
            self.lb.insert("end", str(p))
        bf = ttk.Frame(frm)
        bf.pack(fill="x")
        ttk.Button(bf, text="Add folder…", command=self._browse).pack(
            side="left")
        ttk.Button(bf, text="Remove", command=self._remove).pack(
            side="left", padx=4)
        self.det = P.detect_game_dirs(cfg.cemu_dirs)
        if self.det:
            ttk.Button(bf, text="Add detected Cemu install",
                       command=self._add_detected).pack(side="left", padx=4)
        rf = ttk.Frame(frm)
        rf.pack(fill="x", pady=(12, 0))
        ttk.Label(rf, text="Quest region:").pack(side="left")
        self.region = tk.StringVar(value=cfg.region or "")
        self.region_cb = ttk.Combobox(rf, textvariable=self.region, width=6,
                                      state="readonly")
        self.region_cb.pack(side="left", padx=6)
        ttk.Label(rf, foreground=MUTED, text=(
            "us = North America, eu = Europe (picked from the game's title "
            "id).")).pack(side="left")
        self.info = ttk.Label(frm, foreground=MUTED, wraplength=730,
                              justify="left")
        self.info.pack(anchor="w", pady=8)
        ob = ttk.Frame(frm)
        ob.pack(fill="x", side="bottom")
        ttk.Button(ob, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(ob, text="OK", command=self._ok).pack(side="right", padx=4)
        if not cfg.game_dirs and self.det:
            self._add_detected()
        self._refresh()

    def _paths(self):
        return [Path(self.lb.get(i)) for i in range(self.lb.size())]

    def _add(self, path):
        c = P.content_dir(path)
        if c is None:
            messagebox.showerror(
                "Not a game folder", f"{path}\n\nhas no content\\nativeCafe"
                "\\arc\\quest folder. Pick the game's folder (the one with "
                "code, content and meta inside) or its content folder.",
                parent=self)
            return
        if str(c).lower() not in (str(p).lower() for p in self._paths()):
            self.lb.insert("end", str(c))
        self._refresh()

    def _browse(self):
        d = filedialog.askdirectory(parent=self, title="MH3U game folder")
        if d:
            self._add(d)

    def _add_detected(self):
        for d in self.det:
            self._add(d)

    def _remove(self):
        s = self.lb.curselection()
        if s:
            self.lb.delete(s[0])
            self._refresh()

    def _refresh(self):
        paths = self._paths()
        regions = sorted({r for p in paths for r in P.regions_in(p)})
        self.region_cb.config(values=regions)
        if paths and self.region.get() not in regions:
            self.region.set(P.default_region(paths[0]) or "")
        lines = []
        for p in paths:
            tid = P.title_id_of(p)
            lines.append(f"{p}\n    title {tid or '?'}, quest regions: "
                         f"{', '.join(P.regions_in(p)) or 'none'}")
        self.info.config(text="\n".join(lines))

    def _ok(self):
        paths = self._paths()
        if not paths:
            messagebox.showerror("No folder", "Add the game folder first.",
                                 parent=self)
            return
        if not self.region.get():
            messagebox.showerror("No region", "Pick the quest region.",
                                 parent=self)
            return
        self.cfg.game_dirs = paths
        self.cfg.region = self.region.get()
        self.cfg.save()
        self.ok = True
        self.destroy()


# ============================================================== base tab

class BaseTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=6)
        self.app = app
        self.project = None
        self.pack_name = "quest00"
        self.leaf = None

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Search:").pack(side="left")
        self.search = tk.StringVar()
        ttk.Entry(bar, textvariable=self.search, width=26).pack(side="left",
                                                                padx=4)
        self.search.trace_add("write", lambda *a: self.refresh_list())
        self.only_mod = tk.BooleanVar()
        ttk.Checkbutton(bar, text="Edited only", variable=self.only_mod,
                        command=self.refresh_list).pack(side="left", padx=8)
        ttk.Button(bar, text="Restore original game files",
                   command=self.restore).pack(side="right", padx=2)
        ttk.Button(bar, text="Install into game",
                   command=self.install).pack(side="right", padx=2)
        self.state_lbl = ttk.Label(bar, text="", foreground=MUTED)
        self.state_lbl.pack(side="right", padx=10)

        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True)
        lf = ttk.Frame(paned)
        cols = ("no", "star", "map", "name", "mons")
        self.tree = ttk.Treeview(lf, columns=cols, show="headings",
                                 selectmode="browse")
        for c, w, t in (("no", 60, "No."), ("star", 36, "★"),
                        ("map", 110, "Map"), ("name", 220, "Name"),
                        ("mons", 170, "Monsters")):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, stretch=(c in ("name", "mons")))
        vsb = ttk.Scrollbar(lf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("mod", foreground=ACCENT)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._selected())
        paned.add(lf, weight=2)

        self.editor = QuestEditor(
            paned, on_save=self._save, on_revert=self._revert,
            donors=lambda em, m: donor_candidates(self.project, "quest00",
                                                  em, m),
            revert_label="Revert to original")
        paned.add(self.editor, weight=3)

    # project
    def set_project(self, project):
        self.project = project
        self.leaf = None
        self.refresh_list()
        self.update_state()

    def refresh_list(self, keep=None):
        self.tree.delete(*self.tree.get_children())
        if not self.project:
            return
        pat = self.search.get().strip().lower()
        for pack in P.PACKS:
            try:
                entries = self.project.quest_entries(pack)
            except (P.ProjectError, OSError) as e:
                self.app.status(str(e), error=True)
                continue
            mods = set(self.project.modified(pack))
            for leaf, _ in entries:
                if self.only_mod.get() and leaf not in mods:
                    continue
                try:
                    q = Quest(self.project.load(pack, leaf))
                except QuestFormatError:
                    continue
                name = q.get_string("name")
                mons = quest_row_text(q)
                if pat and not any(pat in s.lower() for s in
                                   (name, mons, leaf)):
                    continue
                iid = f"{pack}/{leaf}"
                self.tree.insert(
                    "", "end", iid=iid, tags=("mod",) if leaf in mods else (),
                    values=(leaf[2:] + (" *" if leaf in mods else ""),
                            q.get("star"), GD.map_name(q.get("map")), name,
                            mons))
        if keep and self.tree.exists(keep):
            self.tree.selection_set(keep)
            self.tree.see(keep)

    def update_state(self):
        if not self.project:
            self.state_lbl.config(text="")
            return
        n = sum(len(self.project.modified(p)) for p in P.PACKS)
        try:
            states = {self.project.pack_status(p) for p in P.PACKS}
        except (P.ProjectError, OSError):
            states = {"pending"}
        if states == {"clean"}:
            txt, col = "No edits", MUTED
        elif "pending" not in states:
            txt, col = f"{n} edited quest(s) — installed", OK_FG
        else:
            txt, col = (f"{n} edited quest(s) — not installed yet" if n else
                        "Game files differ from the original — click "
                        "Install to restore", ERR_FG)
        self.state_lbl.config(text=txt, foreground=col)

    # editor
    def _selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        pack, leaf = sel[0].split("/")
        if (pack, leaf) == (self.pack_name, self.leaf):
            return
        if not self.app.confirm_discard(self.editor):
            prev = f"{self.pack_name}/{self.leaf}"
            if self.tree.exists(prev):
                self.tree.selection_set(prev)
            return
        self.pack_name, self.leaf = pack, leaf
        data = self.project.load(pack, leaf)
        q = Quest(data)
        mod = self.project.is_modified(pack, leaf)
        self.editor.load(
            data, f"#{q.get('quest_no'):05d}  {q.get_string('name')}",
            f"{pack}.arc · {leaf} · {GD.map_name(q.get('map'))}"
            + ("  ·  edited" if mod else "  ·  original"))

    def _save(self, data):
        try:
            self.project.save(self.pack_name, self.leaf, data)
        except (QuestFormatError, OSError) as e:
            messagebox.showerror("Save failed", str(e))
            return False
        self.refresh_list(keep=f"{self.pack_name}/{self.leaf}")
        self.update_state()
        self.app.status(f"Saved {self.leaf} to the workspace. Click "
                        f"'Install into game' to use it.")
        return True

    def _revert(self):
        if not self.leaf:
            return
        if not messagebox.askyesno(
                "Revert", f"Throw away all edits to {self.leaf} and go back "
                f"to the game's original?"):
            return
        self.project.revert(self.pack_name, self.leaf)
        data = self.project.load(self.pack_name, self.leaf)
        q = Quest(data)
        self.editor.load(data, f"#{q.get('quest_no'):05d}  "
                               f"{q.get_string('name')}",
                         f"{self.pack_name}.arc · {self.leaf}  ·  original")
        self.refresh_list(keep=f"{self.pack_name}/{self.leaf}")
        self.update_state()
        self.app.status(f"{self.leaf} reverted (install again to apply)")

    # install
    def install(self):
        if not self.project:
            return
        if self.editor.dirty() and messagebox.askyesno(
                "Unsaved changes", "Save the current quest first?"):
            self.editor.save()
        targets = []
        for p in P.PACKS:
            targets += [str(t) for t in self.project.install_targets(p)]
        if not messagebox.askyesno(
                "Install into game",
                "Write the edited quest files into:\n\n" + "\n".join(targets)
                + "\n\nThe originals are kept as .arc.orig the first time. "
                  "Close the game first, or restart it afterwards."):
            return
        done = []
        try:
            for p in P.PACKS:
                if self.project.modified(p):
                    done += self.project.install(p)
                else:
                    done += self.project.restore(p)   # no edits: original
        except (P.ProjectError, OSError) as e:
            messagebox.showerror("Install failed", str(e))
            return
        self.update_state()
        self.app.status(f"Installed into {len(done)} file(s). Restart MH3U.")
        messagebox.showinfo("Installed", "Done. Start (or restart) MH3U to "
                                         "see your quests.")

    def restore(self):
        if not self.project:
            return
        if not messagebox.askyesno(
                "Restore original game files",
                "Put the game's original quest files back? Your edits stay "
                "in the workspace and can be installed again later."):
            return
        done = []
        for p in P.PACKS:
            done += self.project.restore(p)
        self.update_state()
        self.app.status(f"Restored {len(done)} original file(s).")


# =============================================================== dlc tab

class NewQuestDialog(tk.Toplevel):
    """Pick the event quest to copy, the new quest number and a name.
    result = (template bytes, quest_no, name) or None."""

    def __init__(self, parent, templates, default_no, used, slot):
        super().__init__(parent)
        self.title("New event quest")
        self.configure(bg=TK_DARK["bg"])
        self.geometry("680x440")
        self.transient(parent)
        self.grab_set()
        self.result = None
        self.templates, self.used = templates, used
        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, wraplength=650, justify="left", foreground=MUTED, text=(
            f"The new quest goes into empty slot {slot + 1}. It starts as a "
            f"copy of the quest you pick (event quests carry data that "
            f"base-game quests don't, so the template has to be an event "
            f"quest). Edit it afterwards like any other quest.")).pack(
            anchor="w")
        self.lb = tk.Listbox(frm, **TK_DARK)
        self.lb.pack(fill="both", expand=True, pady=8)
        for label, _ in templates:
            self.lb.insert("end", label)
        self.lb.bind("<<ListboxSelect>>", lambda e: self._picked())
        g = ttk.Frame(frm)
        g.pack(fill="x")
        ttk.Label(g, text="Quest number").grid(row=0, column=0, sticky="w")
        self.no = tk.StringVar(value=str(default_no))
        ttk.Entry(g, textvariable=self.no, width=8).grid(row=0, column=1,
                                                        sticky="w", padx=6)
        ttk.Label(g, foreground=MUTED, text="unique; event quests use "
                  "20xxx").grid(row=0, column=2, sticky="w")
        ttk.Label(g, text="Name").grid(row=1, column=0, sticky="w", pady=4)
        self.name = tk.StringVar()
        ttk.Entry(g, textvariable=self.name, width=50).grid(
            row=1, column=1, columnspan=2, sticky="w", padx=6)
        bf = ttk.Frame(frm)
        bf.pack(fill="x", pady=(8, 0))
        ttk.Button(bf, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(bf, text="Create", command=self._ok).pack(side="right",
                                                             padx=4)
        if templates:
            self.lb.selection_set(0)
            self._picked()

    def _picked(self):
        s = self.lb.curselection()
        if s:
            q = Quest(self.templates[s[0]][1])
            self.name.set(f"[NEW] {q.get_string('name')}")

    def _ok(self):
        s = self.lb.curselection()
        if not s:
            messagebox.showerror("Pick one", "Pick a quest to copy.",
                                 parent=self)
            return
        try:
            no = int(self.no.get())
        except ValueError:
            no = -1
        if not 1 <= no <= 65535:
            messagebox.showerror("Quest number", "Quest number must be "
                                 "1–65535.", parent=self)
            return
        if no in self.used:
            messagebox.showerror("Quest number", f"#{no} is already used in "
                                 "these packs.", parent=self)
            return
        self.result = (self.templates[s[0]][1], no, self.name.get().strip())
        self.destroy()



class DlcTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=6)
        self.app = app
        self.pack = None
        self.slot = None

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Button(bar, text="Open pack…", command=self.open_pack).pack(
            side="left", padx=2)
        ttk.Button(bar, text="Open .quest file…",
                   command=self.open_single).pack(side="left", padx=2)
        self.quick = ttk.Menubutton(bar, text="Cemu save packs")
        self.quick.pack(side="left", padx=8)
        self.quick_menu = tk.Menu(self.quick, tearoff=False,
                                  bg=TK_DARK["bg"], fg=TK_DARK["fg"],
                                  postcommand=self._fill_quick)
        self.quick["menu"] = self.quick_menu
        ttk.Button(bar, text="Restore pack backup",
                   command=self.restore_backup).pack(side="right", padx=2)
        ttk.Button(bar, text="Delete quest",
                   command=self.delete_quest).pack(side="right", padx=2)
        ttk.Button(bar, text="New quest…",
                   command=self.new_quest).pack(side="right", padx=2)
        self.file_lbl = ttk.Label(bar, text="No pack open", foreground=MUTED)
        self.file_lbl.pack(side="left", padx=12)

        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True)
        lf = ttk.Frame(paned)
        note = ttk.Label(lf, foreground=MUTED, justify="left", wraplength=380,
                         text="Event quest packs live in Cemu's save folder as "
                              "quest1..quest4. Saving writes the pack straight "
                              "away (a .BACKUP copy is made the first time). "
                              "Close the game before saving.")
        note.pack(side="bottom", fill="x", pady=4)
        note.bind("<Configure>", lambda e: note.config(
            wraplength=max(200, e.width - 6)))
        cols = ("slot", "no", "name", "mons")
        self.tree = ttk.Treeview(lf, columns=cols, show="headings",
                                 selectmode="browse")
        for c, w, t in (("slot", 40, "Slot"), ("no", 55, "No."),
                        ("name", 200, "Name"), ("mons", 170, "Monsters")):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, stretch=(c in ("name", "mons")))
        vsb = ttk.Scrollbar(lf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._selected())
        paned.add(lf, weight=2)
        self.editor = QuestEditor(
            paned, on_save=self._save, on_revert=self._revert,
            donors=lambda em, m: donor_candidates(self.app.project, "quest00",
                                                  em, m),
            revert_label="Undo unsaved changes")
        paned.add(self.editor, weight=3)

    def _save_dirs(self):
        cfg = self.app.cfg
        return P.cemu_save_dirs(cfg.cemu_dirs, cfg.game_dirs)

    def _fill_quick(self):
        """Rebuilt each time the menu opens, so a Cemu started after Quest
        Studio (e.g. a portable copy) shows up too."""
        m = self.quick_menu
        m.delete(0, "end")
        found = self._save_dirs()
        last = None
        for label, region, d in found:
            if label != last:
                if last is not None:
                    m.add_separator()
                m.add_command(label=label, state="disabled")
                last = label
            for n in ("quest1", "quest2", "quest3", "quest4"):
                if (d / n).exists():
                    m.add_command(
                        label=f"    {region} save {d.name}  ›  {n}",
                        command=lambda p=d / n: self._open(DlcPack, p))
        if not found:
            m.add_command(label="(no Cemu save folder found)",
                          state="disabled")
        m.add_separator()
        m.add_command(label="Add a Cemu folder…", command=self._add_cemu)

    def _add_cemu(self):
        d = filedialog.askdirectory(title="Cemu folder (the one with "
                                          "Cemu.exe in it)")
        if not d:
            return
        if P.mlc_of_cemu_dir(d) is None:
            messagebox.showerror("Not a Cemu folder", f"{d}\n\nhas no mlc01 "
                                 "folder (looked in mlc01 and portable\\mlc01)."
                                 " Start that Cemu once, then try again.")
            return
        cfg = self.app.cfg
        if str(Path(d)).lower() not in (str(p).lower() for p in cfg.cemu_dirs):
            cfg.cemu_dirs.append(Path(d))
            cfg.save()
        self.app.status(f"Added Cemu folder {d}; its save packs are now in "
                        f"the 'Cemu save packs' menu.")

    def open_pack(self):
        dirs = self._save_dirs()
        path = filedialog.askopenfilename(
            title="Open quest pack (quest1..quest4)",
            initialdir=str(dirs[0][2]) if dirs else None)
        if path:
            self._open(DlcPack, path)

    def open_single(self):
        path = filedialog.askopenfilename(
            title="Open .quest file",
            filetypes=[("Quest files", "*.quest"), ("All files", "*.*")])
        if path:
            self._open(QuestFile, path)

    def _open(self, cls, path):
        if not self.app.confirm_discard(self.editor):
            return
        try:
            pack = cls(path)
            quests = pack.quests()
        except (PackError, QuestFormatError, OSError) as e:
            messagebox.showerror("Can't open", f"{path}\n\n{e}")
            return
        self.pack = pack
        self.slot = None
        self.editor.clear()
        self.file_lbl.config(text=str(path), foreground=TK_DARK["fg"])
        self.tree.delete(*self.tree.get_children())
        for i, q in quests:
            self.tree.insert("", "end", iid=str(i), values=(
                i + 1, q.get("quest_no"), q.get_string("name"),
                quest_row_text(q)))
        self.app.status(f"Opened {Path(path).name}: {len(quests)} quest(s)")
        if not quests:
            messagebox.showinfo("Empty", "This pack has no quests in it.")

    def _selected(self):
        sel = self.tree.selection()
        if not sel or not self.pack:
            return
        i = int(sel[0])
        if i == self.slot:
            return
        if not self.app.confirm_discard(self.editor):
            if self.slot is not None and self.tree.exists(str(self.slot)):
                self.tree.selection_set(str(self.slot))
            return
        self.slot = i
        self._load_slot()

    def _load_slot(self):
        data = self.pack.record(self.slot)
        q = Quest(data)
        self.editor.load(
            data, f"#{q.get('quest_no'):05d}  {q.get_string('name')}",
            f"{self.pack.path.name} · slot {self.slot + 1} · "
            f"{self.pack.file_name(self.slot)} · {GD.map_name(q.get('map'))}")

    def _save(self, data):
        try:
            self.pack.set_record(self.slot, data)
            dst = self.pack.save()
        except (PackError, QuestFormatError, OSError) as e:
            messagebox.showerror("Save failed", str(e))
            return False
        q = Quest(data)
        self.tree.item(str(self.slot), values=(
            self.slot + 1, q.get("quest_no"), q.get_string("name"),
            quest_row_text(q)))
        self.app.status(f"Saved {dst} (backup: {dst.name}.BACKUP)")
        return True

    def _revert(self):
        if self.pack is not None and self.slot is not None:
            self._load_slot()

    def _sibling_packs(self):
        """The open pack plus quest1..quest4 next to it: [(name, DlcPack)]."""
        out = [(self.pack.path.name, self.pack)]
        for n in ("quest1", "quest2", "quest3", "quest4"):
            p = self.pack.path.with_name(n)
            if p != self.pack.path and p.exists():
                try:
                    out.append((n, DlcPack(p)))
                except (PackError, OSError):
                    pass
        return out

    def new_quest(self):
        if not isinstance(self.pack, DlcPack):
            messagebox.showinfo("New quest", "Open a quest pack (quest1.."
                                             "quest4) first.")
            return
        empty = self.pack.empty_slots()
        if not empty:
            messagebox.showinfo("Pack full", f"{self.pack.path.name} has no "
                                "empty slot. Open another pack (quest3 is "
                                "often empty) or delete a quest first.")
            return
        if not self.app.confirm_discard(self.editor):
            return
        templates, used = [], set()
        for name, p in self._sibling_packs():
            for i, q in p.quests():
                used.add(q.get("quest_no"))
                templates.append((f"#{q.get('quest_no'):05d}  "
                                  f"{q.get_string('name')}  ({name} slot "
                                  f"{i + 1}, {GD.map_name(q.get('map'))})",
                                  p.record(i)))
        if not templates:
            messagebox.showinfo("New quest", "A new event quest starts as a "
                                "copy of an existing one, and there are none "
                                "in this save folder.")
            return
        events = [n for n in used if 20000 <= n < 30000]
        dlg = NewQuestDialog(self, templates, (max(events) + 1) if events
                             else 20325, used, empty[0])
        self.wait_window(dlg)
        if not dlg.result:
            return
        data, quest_no, title = dlg.result
        slot = empty[0]
        try:
            q = Quest(data)
            if title:
                q.set_string("name", title)
            self.pack.create_quest(slot, q.to_bytes(), quest_no)
            self.pack.save()
        except (PackError, QuestFormatError, OSError) as e:
            messagebox.showerror("Create failed", str(e))
            return
        self._open(DlcPack, self.pack.path)
        self.tree.selection_set(str(slot))
        self.tree.see(str(slot))
        self.app.status(f"Created #{quest_no} in slot {slot + 1} of "
                        f"{self.pack.path.name}. Edit it, then Save quest.")

    def delete_quest(self):
        if not isinstance(self.pack, DlcPack) or self.slot is None:
            return
        q = Quest(self.pack.record(self.slot))
        if not messagebox.askyesno(
                "Delete quest", f"Remove #{q.get('quest_no')} "
                f"{q.get_string('name')!r} from slot {self.slot + 1}?\n\n"
                f"The pack's .BACKUP (made on the first save) keeps the old "
                f"version.", icon="warning"):
            return
        self.pack.clear_slot(self.slot)
        try:
            self.pack.save()
        except OSError as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.editor.clear()       # nothing loaded any more: no discard prompt
        self._open(DlcPack, self.pack.path)
        self.app.status("Quest deleted")

    def restore_backup(self):
        if not self.pack:
            return
        bak = self.pack.path.with_name(self.pack.path.name + ".BACKUP")
        if not bak.exists():
            messagebox.showinfo("No backup", f"No {bak.name} yet (one is made "
                                             f"the first time you save).")
            return
        if messagebox.askyesno("Restore backup", f"Replace {self.pack.path}"
                               f"\nwith {bak.name}?"):
            self.pack.path.write_bytes(bak.read_bytes())
            self._open(type(self.pack), self.pack.path)


# ==================================================================== app

class App:
    def __init__(self, root):
        self.root = root
        root.title(f"MH3U Quest Studio {__version__}")
        root.geometry("1280x820")
        apply_dark_theme(root)
        self.cfg = P.Config(CONFIG)
        self.project = None

        top = ttk.Frame(root, padding=(8, 6))
        top.pack(fill="x")
        self.game_lbl = ttk.Label(top, text="", foreground=MUTED)
        self.game_lbl.pack(side="left")
        ttk.Button(top, text="Game folder…", command=self.setup).pack(
            side="right")

        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True, padx=6)
        self.base = BaseTab(nb, self)
        self.dlc = DlcTab(nb, self)
        nb.add(self.base, text="  Base Game Quests  ")
        nb.add(self.dlc, text="  DLC / Event Quests  ")

        self.status_var = tk.StringVar(value="Ready")
        self.status_lbl = ttk.Label(root, textvariable=self.status_var,
                                    anchor="w", padding=(8, 3))
        self.status_lbl.pack(fill="x", side="bottom")

        root.bind_all("<Control-s>", lambda e: self._ctrl_s(nb))
        root.protocol("WM_DELETE_WINDOW", self.quit)
        root.after(50, self.start)

    def _ctrl_s(self, nb):
        tab = nb.nametowidget(nb.select())
        tab.editor.save()

    def status(self, msg, error=False):
        self.status_var.set(msg)
        self.status_lbl.config(foreground=ERR_FG if error else TK_DARK["fg"])

    def confirm_discard(self, editor):
        if not editor.dirty():
            return True
        ans = messagebox.askyesnocancel(
            "Unsaved changes", "Save changes to the current quest first?")
        if ans is None:
            return False
        if ans:
            editor.save()
            return not editor.dirty()
        return True

    def start(self):
        if not self.cfg.game_dirs or not all(
                P.content_dir(p) for p in self.cfg.game_dirs):
            self.setup(first=True)
        else:
            self.open_project()

    def setup(self, first=False):
        dlg = SetupDialog(self.root, self.cfg)
        self.root.wait_window(dlg)
        if dlg.ok:
            self.open_project()
        elif first and not self.project:
            self.status("No game folder set — the DLC tab still works. "
                        "Click 'Game folder…' to edit base-game quests.",
                        error=True)

    def open_project(self):
        ws = Path(self.cfg.workspace) if self.cfg.workspace else DEFAULT_WORKSPACE
        try:
            self.project = P.Project(self.cfg.game_dirs, self.cfg.region, ws)
            for p in P.PACKS:
                self.project.ensure_pristine(p)
        except (P.ProjectError, OSError, ValueError) as e:
            self.project = None
            messagebox.showerror("Game folder problem", str(e))
            self.status(str(e), error=True)
            return
        self.game_lbl.config(text=f"Game: {self.cfg.game_dirs[0]}"
                                  + (f" (+{len(self.cfg.game_dirs) - 1})"
                                     if len(self.cfg.game_dirs) > 1 else "")
                                  + f"   ·   region {self.cfg.region}")
        self.base.set_project(self.project)
        adopted = sum(len(self.project.modified(p)) for p in P.PACKS)
        self.status(f"Loaded base-game quests ({self.cfg.region})"
                    + (f"; {adopted} edited quest(s) in the workspace"
                       if adopted else ""))

    def quit(self):
        for ed in (self.base.editor, self.dlc.editor):
            if not self.confirm_discard(ed):
                return
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
