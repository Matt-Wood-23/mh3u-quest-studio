"""Tk widgets shared by both Quest Studio tabs: the quest editor panel,
reward table, item picker and donor-monster picker."""
import tkinter as tk
from tkinter import ttk, messagebox

from . import gamedata as GD
from .quest_format import (Quest, QuestFormatError, MON_FIELDS, MON_SLOTS,
                           LANGS, STRING_FIELDS, OBJ_TYPES, CLR_PATTERNS,
                           NANDO_FIELDS, NANDO_MAX, REWARD_SLOTS)
from .theme import TK_DARK, MUTED, ACCENT, OK_FG, ERR_FG

LANG_NAMES = {"en": "English", "fr": "French", "de": "German",
              "it": "Italian", "es": "Spanish"}

# (field, label, min, max, hint)
SETTINGS_FIELDS = [
    ("star", "Star rank", 0, 10, ""),
    ("time_min", "Time limit (min)", 1, 999, ""),
    ("contract", "Contract fee (z)", 0, 9_999_999, ""),
    ("reward_money", "Reward money (z)", 0, 9_999_999, ""),
    ("penalty", "Failure penalty (z)", 0, 9_999_999,
     "the game's own quests use reward ÷ 3"),
    ("main_hrp", "HR points", 0, 999_999, ""),
    ("failure_hrp", "HR points on failure", 0, 999_999, ""),
    ("supp_set_no", "Supply crate (SuppSetNo)", 0, 294,
     "picks quest/support/suppNNN.supp"),
]
# Capcom's names; the hints give the values the game's own quests use.
ADVANCED_FIELDS = [
    ("quest_no", "Quest number", 0, 65535,
     "leave as is: the quest board finds quests by this number"),
    ("demo_no", "Intro cutscene (DemoNo)", 0, 255,
     "0 = none; only key quests set one"),
    ("supp_time_flag", "SuppTimeFlag", 0, 65535, "0–3 in the game's quests"),
    ("start_param", "StartParam", 0, 65535, "0–2 in the game's quests"),
    ("ren_pattern", "Ren_pattern", 0, 65535, "0–8 in the game's quests"),
    ("rannyu_limite", "Rannyu_limite (intrusion limit)", 0, 65535,
     "0 in every base quest"),
    ("enemy_lv", "EnemyLv", 0, 255, "0–4 in the game's quests"),
    ("hagi_no", "HagiNo", 0, 255, "0–4 in the game's quests"),
]
FIELD_RANGES = {f: (lo, hi) for f, _, lo, hi, _ in
                SETTINGS_FIELDS + ADVANCED_FIELDS}
FIELD_RANGES.update({"special_flag": (0, 65535),
                     "special_cond": (0, GD.COND_COUNT - 1),
                     "special_cond2": (0, GD.COND_COUNT - 1),
                     "obj1_num": (0, 32767), "obj2_num": (0, 32767),
                     "obj1_id": (0, 65535), "obj2_id": (0, 65535),
                     "obj1_param": (0, 0xFFFFFFFF), "obj2_param": (0, 0xFFFFFFFF)})

# monster block fields as shown (field, label)
MON_UI = [("Num", "Count"), ("Nando_hp", "HP row"), ("Nando_at", "Attack row"),
          ("Nando_etc", "Defense row"), ("Size", "Size %"),
          ("Sizeparam", "Size spread"), ("Stamina", "Stamina"),
          ("Starttype", "Spawn type"), ("Settype", "Settype"),
          ("Nando2", "Nando2")]

MON_HELP = (
    "HP / Attack / Defense row = rows of the game's difficulty table (0–127), "
    "not percentages. Higher rows = more HP and attack, less damage taken. "
    "The line under each monster shows what the game will apply. "
    "Count = how many of that monster. Spawn type = where/how it appears. "
    "Easiest way to add a monster: Copy from quest… (pick one on the same map "
    "at a similar rank).")

JOIN_HELP = (
    "The rules are what the game checks, when the quest is started and when "
    "someone joins online. The board text is only what players read, so it "
    "follows the rules: changing a rule picks the matching text. Values 1–11 "
    "are unused by Capcom: the host can start the quest but nobody can join "
    "it online.")

EMPTY = "(empty)"
MON_CHOICES = [EMPTY] + [f"{i:3d}  {n}" for i, n in sorted(GD.MONSTERS.items())]
COND_CHOICES = [f"{v}  {GD.cond_name(v)}" for v in range(GD.COND_COUNT)]
REQ_CHOICES = [f"{f}  {t}" for f, t in enumerate(GD.REQ_TEXT)]


def cond_choice(v):
    return f"{v}  {GD.cond_name(v)}"


def req_choice(f):
    return f"{f}  {GD.req_text(f)}"
OBJ_CHOICES = [f"0x{k:X}  {v}" for k, v in OBJ_TYPES.items()]
MONSTER_OBJ_TYPES = {0x1, 0x81, 0x101, 0x8101, 0x404, 0x2515, 0x4014}


def parse_int(text, field):
    t = text.strip().split()[0] if text.strip() else ""
    try:
        return int(t, 0)
    except ValueError:
        raise ValueError(f"{field}: {text!r} is not a number") from None


def check_range(field, v):
    r = FIELD_RANGES.get(field)
    if r and not (r[0] <= v <= r[1]):
        raise ValueError(f"{field} = {v} is outside {r[0]}–{r[1]:,}")


def crlf(s):
    return s.replace("\r\n", "\n").replace("\n", "\r\n")


def lf(s):
    return s.replace("\r\n", "\n")


def autowrap(label, pad=6):
    """Re-wrap a fill='x' label to its current width."""
    label.bind("<Configure>", lambda e: label.config(
        wraplength=max(200, e.width - pad)))
    return label


def mon_choice(em_id):
    if not em_id:
        return EMPTY
    return f"{em_id:3d}  {GD.mon_name(em_id)}"


class ScrollFrame(ttk.Frame):
    """Vertically scrollable frame; put children in .inner."""

    def __init__(self, parent):
        super().__init__(parent)
        canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0,
                           bg=TK_DARK["bg"])
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.inner = ttk.Frame(canvas)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        win = canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(
            win, width=e.width))
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(
            -1 * (e.delta // 120), "units") if _under(canvas, e) else None,
            add="+")


def _under(widget, event):
    try:
        w = widget.winfo_containing(event.x_root, event.y_root)
    except KeyError:      # over a Tcl-only window (combobox popdown)
        return False
    while w is not None:
        if w is widget:
            return True
        w = w.master
    return False


# ------------------------------------------------------------ item picker

class ItemPickDialog(tk.Toplevel):
    """Pick a reward item; result = (item_id, num, per) or None."""

    def __init__(self, parent, title, item_id=0, num=1, per=0):
        super().__init__(parent)
        self.title(title)
        self.geometry("440x460")
        self.configure(bg=TK_DARK["bg"])
        self.transient(parent)
        self.grab_set()
        self.result = None
        frm = ttk.Frame(self, padding=8)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)

        ttk.Label(frm, text="Search:").grid(row=0, column=0, sticky="w")
        self.search = tk.StringVar()
        se = ttk.Entry(frm, textvariable=self.search)
        se.grid(row=0, column=1, columnspan=2, sticky="we")
        self.search.trace_add("write", lambda *a: self._refilter())
        self.listbox = tk.Listbox(frm, height=14, **TK_DARK)
        self.listbox.grid(row=1, column=0, columnspan=3, sticky="nsew", pady=6)
        frm.rowconfigure(1, weight=1)
        self.listbox.bind("<<ListboxSelect>>", lambda e: self._pick())
        self.listbox.bind("<Double-Button-1>", lambda e: self._ok())

        ttk.Label(frm, text="Item ID:").grid(row=2, column=0, sticky="w")
        self.id_var = tk.StringVar(value=str(item_id))
        ttk.Entry(frm, textvariable=self.id_var, width=8).grid(
            row=2, column=1, sticky="w")
        self.name_lbl = ttk.Label(frm, foreground=ACCENT)
        self.name_lbl.grid(row=2, column=2, sticky="w")
        self.id_var.trace_add("write", lambda *a: self._show_name())

        nf = ttk.Frame(frm)
        nf.grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Label(nf, text="Amount:").pack(side="left")
        self.num_var = tk.StringVar(value=str(num))
        ttk.Spinbox(nf, from_=1, to=99, textvariable=self.num_var,
                    width=5).pack(side="left", padx=(2, 12))
        ttk.Label(nf, text="Chance %:").pack(side="left")
        self.per_var = tk.StringVar(value=str(per))
        ttk.Spinbox(nf, from_=0, to=100, textvariable=self.per_var,
                    width=5).pack(side="left", padx=2)
        ttk.Label(frm, foreground=MUTED, wraplength=400, justify="left",
                  text="Chance is the item's weight in its reward column; "
                       "the game's own quests give fixed rewards with 0."
                  ).grid(row=4, column=0, columnspan=3, sticky="w", pady=4)

        bf = ttk.Frame(frm)
        bf.grid(row=5, column=0, columnspan=3, sticky="e", pady=(6, 0))
        ttk.Button(bf, text="OK", command=self._ok).pack(side="left", padx=4)
        ttk.Button(bf, text="Cancel", command=self.destroy).pack(side="left")
        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self._shown = []
        self._refilter()
        self._show_name()
        se.focus_set()

    def _refilter(self):
        pat = self.search.get().strip().lower()
        self.listbox.delete(0, "end")
        self._shown = []
        for iid, name in enumerate(GD.ITEMS):
            if iid == 0 or name.startswith("(None") or name == "DUMMY":
                continue
            if pat and pat not in name.lower():
                continue
            self.listbox.insert("end", f"{iid:4d}  {name}")
            self._shown.append(iid)
            if len(self._shown) >= 300:
                break
        if pat and self._shown:      # typing a name selects the top match
            self.listbox.selection_set(0)
            self._pick()

    def _pick(self):
        sel = self.listbox.curselection()
        if sel:
            self.id_var.set(str(self._shown[sel[0]]))

    def _show_name(self):
        try:
            self.name_lbl.config(text=GD.item_name(int(self.id_var.get())))
        except ValueError:
            self.name_lbl.config(text="")

    def _ok(self):
        try:
            iid, num, per = (int(self.id_var.get()), int(self.num_var.get()),
                             int(self.per_var.get()))
        except ValueError:
            messagebox.showerror("Invalid", "ID, amount and chance must be "
                                 "whole numbers", parent=self)
            return
        if not (0 < iid < 65536 and 0 <= num <= 255 and 0 <= per <= 255):
            messagebox.showerror("Invalid", "Item id 1–65535, amount and "
                                 "chance 0–255", parent=self)
            return
        self.result = (iid, num, per)
        self.destroy()


class RewardTable(ttk.Frame):
    """Reward column 1 / column 2 editor over quest_format reward tuples."""

    COLS = ("col", "item", "num", "per")

    def __init__(self, parent):
        super().__init__(parent, padding=6)
        self.tree = ttk.Treeview(self, columns=self.COLS, show="headings",
                                 height=16, selectmode="browse")
        for c, w, t in (("col", 70, "Column"), ("item", 260, "Item"),
                        ("num", 60, "Amount"), ("per", 70, "Chance %")):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, stretch=(c == "item"))
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        bf = ttk.Frame(self)
        bf.grid(row=1, column=0, columnspan=2, sticky="w", pady=6)
        ttk.Button(bf, text="Add to column 1…",
                   command=lambda: self._add(1)).pack(side="left", padx=2)
        ttk.Button(bf, text="Add to column 2…",
                   command=lambda: self._add(2)).pack(side="left", padx=2)
        ttk.Button(bf, text="Edit…", command=self._edit).pack(side="left",
                                                              padx=(12, 2))
        ttk.Button(bf, text="Remove", command=self._remove).pack(side="left",
                                                                 padx=2)
        self.tree.bind("<Double-Button-1>", lambda e: self._edit())
        ttk.Label(self, foreground=MUTED, wraplength=640, justify="left",
                  text=f"The two reward columns on the quest-clear screen. "
                       f"Each column holds up to {REWARD_SLOTS} entries."
                  ).grid(row=2, column=0, columnspan=2, sticky="w")
        self.r = {1: [], 2: []}

    def set(self, r1, r2):
        self.r = {1: list(r1), 2: list(r2)}
        self._fill()

    def get(self):
        return list(self.r[1]), list(self.r[2])

    def _fill(self, select=None):
        self.tree.delete(*self.tree.get_children())
        for col in (1, 2):
            for i, (iid, num, per) in enumerate(self.r[col]):
                self.tree.insert("", "end", iid=f"{col}:{i}", values=(
                    f"{col}", f"{GD.item_name(iid)}  ({iid})", num, per))
        if select and self.tree.exists(select):
            self.tree.selection_set(select)
            self.tree.see(select)

    def _sel(self):
        s = self.tree.selection()
        if not s:
            return None
        col, i = s[0].split(":")
        return int(col), int(i)

    def _add(self, col):
        if len(self.r[col]) >= REWARD_SLOTS:
            messagebox.showwarning("Full", f"Column {col} already has "
                                   f"{REWARD_SLOTS} entries", parent=self)
            return
        dlg = ItemPickDialog(self, f"Add reward (column {col})")
        self.wait_window(dlg)
        if dlg.result:
            self.r[col].append(dlg.result)
            self._fill(f"{col}:{len(self.r[col]) - 1}")

    def _edit(self):
        s = self._sel()
        if not s:
            return
        col, i = s
        iid, num, per = self.r[col][i]
        dlg = ItemPickDialog(self, "Edit reward", iid, num, per)
        self.wait_window(dlg)
        if dlg.result:
            self.r[col][i] = dlg.result
            self._fill(f"{col}:{i}")

    def _remove(self):
        s = self._sel()
        if s:
            del self.r[s[0]][s[1]]
            self._fill()


class DonorDialog(tk.Toplevel):
    """Choose a monster block from another quest. candidates =
    [(label, block_dict)]. result = block dict or None."""

    def __init__(self, parent, title, candidates):
        super().__init__(parent)
        self.title(title)
        self.geometry("720x420")
        self.configure(bg=TK_DARK["bg"])
        self.transient(parent)
        self.grab_set()
        self.result = None
        self.cands = candidates
        frm = ttk.Frame(self, padding=8)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, foreground=MUTED, wraplength=690, justify="left",
                  text="Copies the whole monster block (difficulty rows, size, "
                       "spawn type). Pick a quest on the SAME MAP so the game "
                       "has spawn data for it, at a similar rank.").pack(
            anchor="w")
        sf = ttk.Frame(frm)
        sf.pack(fill="x", pady=4)
        ttk.Label(sf, text="Filter:").pack(side="left")
        self.filter = tk.StringVar()
        e = ttk.Entry(sf, textvariable=self.filter)
        e.pack(side="left", fill="x", expand=True, padx=4)
        self.filter.trace_add("write", lambda *a: self._fill())
        self.lb = tk.Listbox(frm, **TK_DARK, font=("Consolas", 9))
        self.lb.pack(fill="both", expand=True)
        self.lb.bind("<Double-Button-1>", lambda ev: self._ok())
        bf = ttk.Frame(frm)
        bf.pack(fill="x", pady=(6, 0))
        ttk.Button(bf, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(bf, text="Copy", command=self._ok).pack(side="right",
                                                           padx=4)
        self.bind("<Escape>", lambda ev: self.destroy())
        self._shown = []
        self._fill()
        e.focus_set()

    def _fill(self):
        pat = self.filter.get().lower()
        self.lb.delete(0, "end")
        self._shown = [c for c in self.cands if pat in c[0].lower()]
        for label, _ in self._shown:
            self.lb.insert("end", label)

    def _ok(self):
        s = self.lb.curselection()
        if s:
            self.result = dict(self._shown[s[0]][1])
            self.destroy()


# =========================================================== editor panel

class QuestEditor(ttk.Frame):
    """Editor for one quest_format.Quest. The owner supplies:
       on_save(bytes) -> bool, on_revert(), donors(em_id, quest_map) ->
       [(label, block)] for 'Copy from quest…'."""

    def __init__(self, parent, on_save, on_revert, donors=None,
                 revert_label="Revert"):
        super().__init__(parent)
        self.on_save = on_save
        self.on_revert = on_revert
        self.donors = donors
        self.base = None        # bytes as loaded (for dirty checks)
        self.q = None
        self._loading = False

        self.header = ttk.Label(self, text="Select a quest",
                                font=("TkDefaultFont", 11, "bold"))
        self.header.pack(anchor="w", pady=(0, 2))
        self.subheader = ttk.Label(self, text="", foreground=MUTED)
        self.subheader.pack(anchor="w", pady=(0, 4))

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)
        self.nb.add(self._tab_text(), text=" Text ")
        self.nb.add(self._tab_settings(), text=" Settings ")
        self.nb.add(self._tab_monsters(), text=" Monsters ")
        self.nb.add(self._tab_rewards(), text=" Rewards ")
        self.nb.add(self._tab_flags(), text=" Flags ")

        bf = ttk.Frame(self)
        bf.pack(fill="x", pady=6)
        self.save_btn = ttk.Button(bf, text="Save quest  (Ctrl+S)",
                                   command=self.save)
        self.save_btn.pack(side="left")
        ttk.Button(bf, text=revert_label, command=self._revert).pack(
            side="left", padx=6)
        self.msg = ttk.Label(bf, text="", foreground=MUTED)
        self.msg.pack(side="left", padx=10)
        self.set_enabled(False)

    # ---------------------------------------------------------- tabs
    def _tab_text(self):
        tab = ttk.Frame(self.nb, padding=8)
        top = ttk.Frame(tab)
        top.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        ttk.Label(top, text="Language:").pack(side="left")
        self.lang = tk.StringVar(value="en")
        cb = ttk.Combobox(top, textvariable=self.lang, values=LANGS, width=4,
                          state="readonly")
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda e: self._lang_changed())
        self.all_langs = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Write my text into all 5 language slots",
                        variable=self.all_langs).pack(side="left", padx=16)
        heights = {"name": 0, "client": 0, "objective": 2,
                   "sub_objective": 2, "failure": 2, "description": 8}
        labels = {"name": "Name", "objective": "Objective",
                  "sub_objective": "Sub objective", "failure": "Fail when",
                  "client": "Client", "description": "Description"}
        self.text_w = {}
        for r, f in enumerate(STRING_FIELDS, start=1):
            ttk.Label(tab, text=labels[f]).grid(row=r, column=0, sticky="nw",
                                                pady=3, padx=(0, 8))
            if heights[f] == 0:
                w = ttk.Entry(tab, width=70)
            else:
                w = tk.Text(tab, width=70, height=heights[f], undo=True,
                            wrap="word", insertbackground=TK_DARK["fg"],
                            **TK_DARK)
            w.grid(row=r, column=1, sticky="we", pady=3)
            self.text_w[f] = w
        tab.columnconfigure(1, weight=1)
        ttk.Label(tab, foreground=MUTED, wraplength=640, justify="left",
                  text="The game shows the slot matching the console "
                       "language. Untick the box to edit one language only."
                  ).grid(row=len(STRING_FIELDS) + 1, column=1, sticky="w",
                         pady=(8, 0))
        self.loaded_text = {}
        return tab

    def _tab_settings(self):
        sf = ScrollFrame(self.nb)
        tab = sf.inner
        tab.configure(padding=8)
        self.ent = {}

        def row(parent, r, field, label, hint):
            ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w",
                                               pady=2, padx=(0, 8))
            e = ttk.Entry(parent, width=12)
            e.grid(row=r, column=1, sticky="w", pady=2)
            self.ent[field] = e
            if hint:
                ttk.Label(parent, text=hint, foreground=MUTED).grid(
                    row=r, column=2, sticky="w", padx=8)

        g = ttk.LabelFrame(tab, text="Quest", padding=8)
        g.pack(fill="x", pady=(0, 6))
        ttk.Label(g, text="Map").grid(row=0, column=0, sticky="w", pady=2)
        self.map_var = tk.StringVar()
        self.map_cb = ttk.Combobox(
            g, textvariable=self.map_var, width=30, state="readonly",
            values=[f"{i}  {n}" for i, n in sorted(GD.MAP_NAMES.items())])
        self.map_cb.grid(row=0, column=1, columnspan=2, sticky="w", pady=2)
        self.map_cb.bind("<<ComboboxSelected>>",
                         lambda e: self._refresh_all_stats())
        for r, (f, label, lo, hi, hint) in enumerate(SETTINGS_FIELDS, 1):
            row(g, r, f, label, hint or f"{lo}–{hi:,}")
        self.crate_lbl = ttk.Label(g, foreground=OK_FG, wraplength=560,
                                   justify="left")
        self.crate_lbl.grid(row=len(SETTINGS_FIELDS) + 1, column=0,
                            columnspan=3, sticky="w", pady=(4, 0))
        self.ent["supp_set_no"].bind("<KeyRelease>",
                                     lambda e: self._update_crate())

        o = ttk.LabelFrame(tab, text="Objective (what clears the quest)",
                           padding=8)
        o.pack(fill="x", pady=6)
        ttk.Label(o, text="Combine").grid(row=0, column=0, sticky="w")
        self.clr_var = tk.StringVar()
        ttk.Combobox(o, textvariable=self.clr_var, width=16, state="readonly",
                     values=[f"{k}  {v}" for k, v in CLR_PATTERNS.items()]
                     ).grid(row=0, column=1, sticky="w", pady=2)
        self.obj = {}
        for i, k in enumerate(("obj1", "obj2")):
            r0 = 1 + i * 2
            ttk.Label(o, text=f"Target {'AB'[i]}").grid(row=r0, column=0,
                                                       sticky="w", pady=(6, 0))
            tv = tk.StringVar()
            tcb = ttk.Combobox(o, textvariable=tv, width=18,
                               values=OBJ_CHOICES)
            tcb.grid(row=r0, column=1, sticky="w", pady=(6, 0))
            idv = tk.StringVar()
            idcb = ttk.Combobox(o, textvariable=idv, width=26,
                                values=MON_CHOICES[1:])
            idcb.grid(row=r0, column=2, sticky="w", padx=4, pady=(6, 0))
            ttk.Label(o, text="count").grid(row=r0, column=3, sticky="e",
                                            pady=(6, 0))
            nv = ttk.Entry(o, width=7)
            nv.grid(row=r0, column=4, sticky="w", padx=4, pady=(6, 0))
            lbl = ttk.Label(o, foreground=ACCENT)
            lbl.grid(row=r0 + 1, column=1, columnspan=4, sticky="w")
            self.obj[k] = dict(type=tv, id=idv, num=nv, lbl=lbl, idcb=idcb)
            for var in (tv, idv):
                var.trace_add("write", lambda *a, k=k: self._obj_changed(k))
        self.obj_text = ttk.Label(o, foreground=OK_FG, wraplength=560,
                                  justify="left")
        self.obj_text.grid(row=5, column=0, columnspan=5, sticky="w",
                           pady=(8, 0))
        ttk.Label(o, foreground=MUTED, wraplength=560, justify="left",
                  text="Changing monsters does NOT change the objective: if "
                       "you swap the target monster, update Target A/B too or "
                       "the quest can't be completed. Deliver targets are "
                       "item ids.").grid(row=6, column=0, columnspan=5,
                                         sticky="w", pady=(4, 0))

        j = ttk.LabelFrame(tab, text="Who can join", padding=8)
        j.pack(fill="x", pady=6)
        self.cond_vars = []
        for i, label in enumerate(("Rule 1", "Rule 2")):
            ttk.Label(j, text=label).grid(row=i, column=0, sticky="w", pady=2,
                                          padx=(0, 8))
            v = tk.StringVar()
            cb = ttk.Combobox(j, textvariable=v, width=30, state="readonly",
                              values=COND_CHOICES)
            cb.grid(row=i, column=1, sticky="w", pady=2)
            cb.bind("<<ComboboxSelected>>", lambda e: self._rules_changed())
            self.cond_vars.append(v)
        ttk.Label(j, text="Board text").grid(row=2, column=0, sticky="w",
                                             pady=2, padx=(0, 8))
        self.req_var = tk.StringVar()
        rcb = ttk.Combobox(j, textvariable=self.req_var, width=62,
                           state="readonly", values=REQ_CHOICES)
        rcb.grid(row=2, column=1, sticky="w", pady=2)
        rcb.bind("<<ComboboxSelected>>", lambda e: self._update_join())
        self.join_lbl = ttk.Label(j, wraplength=560, justify="left")
        self.join_lbl.grid(row=3, column=0, columnspan=2, sticky="w",
                           pady=(4, 0))
        ttk.Label(j, foreground=MUTED, wraplength=560, justify="left",
                  text=JOIN_HELP).grid(row=4, column=0, columnspan=2,
                                       sticky="w", pady=(4, 0))

        a = ttk.LabelFrame(tab, text="Advanced", padding=8)
        a.pack(fill="x", pady=6)
        for r, (f, label, lo, hi, hint) in enumerate(ADVANCED_FIELDS):
            row(a, r, f, label, hint or f"{lo}–{hi:,}")
        return sf

    def _tab_monsters(self):
        sf = ScrollFrame(self.nb)
        tab = sf.inner
        tab.configure(padding=8)
        autowrap(ttk.Label(tab, text=MON_HELP, foreground=MUTED,
                           justify="left")).pack(fill="x", pady=(0, 6))
        self.mon = []
        for slot in range(MON_SLOTS):
            lf_ = ttk.LabelFrame(tab, text=f"Monster {slot + 1}", padding=6)
            lf_.pack(fill="x", pady=3)
            row = {"var": tk.StringVar(value=EMPTY)}
            cb = ttk.Combobox(lf_, textvariable=row["var"], width=28,
                              values=MON_CHOICES)
            cb.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
            cb.bind("<<ComboboxSelected>>",
                    lambda e, s=slot: self._monster_picked(s))
            ttk.Button(lf_, text="Copy from quest…",
                       command=lambda s=slot: self._copy_from(s)).grid(
                row=0, column=3, columnspan=2, sticky="w", padx=4)
            ttk.Button(lf_, text="Clear",
                       command=lambda s=slot: self._clear_slot(s)).grid(
                row=0, column=5, sticky="w")
            for i, (f, label) in enumerate(MON_UI):
                r, c = divmod(i, 5)
                ttk.Label(lf_, text=label, foreground=MUTED).grid(
                    row=1 + r * 2, column=c, sticky="w", padx=3)
                e = ttk.Entry(lf_, width=9)
                e.grid(row=2 + r * 2, column=c, sticky="w", padx=3)
                e.bind("<KeyRelease>", lambda ev, s=slot: self._refresh_stats(s))
                row[f] = e
            row["stats"] = ttk.Label(lf_, foreground=OK_FG)
            row["stats"].grid(row=5, column=0, columnspan=6, sticky="w",
                              pady=(4, 0))
            row["warn"] = ttk.Label(lf_, foreground=ERR_FG)
            row["warn"].grid(row=6, column=0, columnspan=6, sticky="w")
            self.mon.append(row)
        return sf

    def _tab_rewards(self):
        self.rewards = RewardTable(self.nb)
        return self.rewards

    def _tab_flags(self):
        sf = ScrollFrame(self.nb)
        tab = sf.inner
        tab.configure(padding=8)
        top = ttk.Frame(tab)
        top.pack(fill="x")
        ttk.Label(top, text="Category flags (hex):").pack(side="left")
        self.cat_var = tk.StringVar()
        ce = ttk.Entry(top, textvariable=self.cat_var, width=22)
        ce.pack(side="left", padx=6)
        ce.bind("<KeyRelease>", lambda e: self._cat_typed())
        self.cat_sum = autowrap(ttk.Label(tab, foreground=OK_FG,
                                          justify="left"))
        self.cat_sum.pack(fill="x", pady=(4, 6))
        autowrap(ttk.Label(tab, foreground=MUTED, justify="left",
                  text="Capcom's quest Category bit field. Only the HP x0.55 "
                       "bits are confirmed in the game code; the rest are "
                       "labeled by which base quests use them. To make a "
                       "quest behave like another kind (e.g. a Harvest Tour), "
                       "copy that kind's bits.")).pack(fill="x", pady=(0, 6))
        grid = ttk.Frame(tab)
        grid.pack(fill="x")
        self.cat_bits = []
        for b in range(32):
            v = tk.BooleanVar()
            info = GD.FLAG_BITS[b]
            ex = (f" — e.g. {info['examples'][0]}" if info["examples"]
                  and not info["confirmed"] else "")
            cb = ttk.Checkbutton(
                grid, variable=v, command=self._cat_ticked,
                text=f"{info['mask']}  {GD.flag_label(b)}{ex}")
            cb.grid(row=b, column=0, sticky="w")
            self.cat_bits.append(v)
        return sf

    # ------------------------------------------------------- state
    def set_enabled(self, on):
        state = "normal" if on else "disabled"
        self.save_btn.config(state=state)

    def is_loaded(self):
        return self.q is not None

    def clear(self):
        """Show nothing (e.g. after the quest was deleted)."""
        self.q = self.base = None
        self.header.config(text="Select a quest")
        self.subheader.config(text="")
        self.msg.config(text="")
        self.set_enabled(False)

    def load(self, data, title, subtitle=""):
        self._loading = True
        self.base = bytes(data)
        self.q = Quest(data)
        self.header.config(text=title)
        self.subheader.config(text=subtitle)
        q = self.q
        # text
        self._fill_text()
        # settings
        for f, e in self.ent.items():
            e.delete(0, "end")
            e.insert(0, str(q.get(f)))
        m = q.get("map")
        self.map_var.set(f"{m}  {GD.map_name(m)}")
        c = q.get("clr_pattern")
        self.clr_var.set(f"{c}  {CLR_PATTERNS.get(c, '?')}")
        self.cond_vars[0].set(cond_choice(q.get("special_cond")))
        self.cond_vars[1].set(cond_choice(q.get("special_cond2")))
        self.req_var.set(req_choice(q.get("special_flag")))
        for k in ("obj1", "obj2"):
            p = q.get(f"{k}_param")
            t = p & 0xFFFF
            label = OBJ_TYPES.get(t)
            self.obj[k]["type"].set(f"0x{p:X}  {label}" if label and p >> 16 == 0
                                    else f"0x{p:X}")
            i = q.get(f"{k}_id")
            self.obj[k]["id"].set(mon_choice(i) if t in MONSTER_OBJ_TYPES and i
                                  else str(i))
            self.obj[k]["num"].delete(0, "end")
            self.obj[k]["num"].insert(0, str(q.get(f"{k}_num")))
        # monsters
        for slot, row in enumerate(self.mon):
            self._fill_slot(slot, q.monsters[slot])
        # rewards
        self.rewards.set(q.reward1, q.reward2)
        # flags
        self.cat_var.set(f"0x{q.get('category'):X}")
        self._cat_typed()
        self._loading = False
        self._update_crate()
        self._update_objective()
        self._update_join()
        self._refresh_all_stats()
        self.set_enabled(True)
        self.msg.config(text="")

    def _fill_text(self):
        li = LANGS.index(self.lang.get())
        self.loaded_text = {}
        for f, w in self.text_w.items():
            raw = self.q.get_string(f, li)
            self.loaded_text[f] = raw
            if isinstance(w, ttk.Entry):
                w.delete(0, "end")
                w.insert(0, raw)
            else:
                w.delete("1.0", "end")
                w.insert("1.0", lf(raw))

    def _lang_changed(self):
        if not self.q:
            return
        try:      # keep text typed in the previous language (unsaved)
            self._apply_text(self.q, commit=True)
        except QuestFormatError:
            pass
        self._fill_text()

    def _fill_slot(self, slot, m):
        row = self.mon[slot]
        row["var"].set(mon_choice(m["Type"]))
        for f, _ in MON_UI:
            row[f].delete(0, "end")
            row[f].insert(0, str(m[f]) if m["Type"] else "0")
        self._refresh_stats(slot)

    def _monster_picked(self, slot):
        """A monster chosen for a slot with no numbers yet (count 0) gets
        usable defaults instead of all zeros (count 0 = never spawns,
        size 0)."""
        row = self.mon[slot]
        try:
            count = int(row["Num"].get() or 0)
        except ValueError:
            count = 0
        if row["var"].get() != EMPTY and count == 0:
            rows = (30, 30, 30)
            for other in self.mon:
                if other is row or other["var"].get() == EMPTY:
                    continue
                try:
                    vals = tuple(int(other[f].get()) for f in NANDO_FIELDS)
                    if int(other["Num"].get() or 0) > 0:
                        rows = vals
                        break
                except ValueError:
                    pass
            defaults = dict(zip(NANDO_FIELDS, rows), Num=1, Size=100)
            for f, _ in MON_UI:
                row[f].delete(0, "end")
                row[f].insert(0, str(defaults.get(f, 0)))
            self.msg.config(text=f"Monster {slot + 1}: filled in count 1, "
                                 f"size 100 and the difficulty rows of the "
                                 f"quest's other monster. Copy from quest… "
                                 f"gives the game's own values.",
                            foreground=MUTED)
        self._refresh_stats(slot)

    def _clear_slot(self, slot):
        self._fill_slot(slot, dict.fromkeys(MON_FIELDS, 0))

    def _copy_from(self, slot):
        if not self.q or not self.donors:
            return
        sel = self.mon[slot]["var"].get()
        em = int(sel.split()[0]) if sel != EMPTY else None
        qmap = self._current_map()
        cands = self.donors(em, qmap)
        if not cands:
            messagebox.showinfo("Copy from quest", "No base-game quest has "
                                "that monster.", parent=self)
            return
        dlg = DonorDialog(self, f"Copy a monster into slot {slot + 1}", cands)
        self.wait_window(dlg)
        if dlg.result:
            self._fill_slot(slot, dlg.result)
            self.msg.config(text=f"Monster {slot + 1}: copied "
                                 f"{GD.mon_name(dlg.result['Type'])} — "
                                 f"not saved yet", foreground=MUTED)

    def _current_map(self):
        try:
            return int(self.map_var.get().split()[0])
        except (ValueError, IndexError):
            return self.q.get("map") if self.q else 0

    def _current_category(self):
        try:
            return int(self.cat_var.get(), 16)
        except ValueError:
            return self.q.get("category") if self.q else 0

    def _refresh_all_stats(self):
        for s in range(MON_SLOTS):
            self._refresh_stats(s)

    def _refresh_stats(self, slot):
        row = self.mon[slot]
        sel = row["var"].get()
        if sel == EMPTY or not sel.strip():
            row["stats"].config(text="")
            row["warn"].config(text="")
            return
        try:
            em = int(sel.split()[0])
            n = {f: int(row[f].get() or 0) for f in NANDO_FIELDS}
        except ValueError:
            row["stats"].config(text="")
            return
        row["stats"].config(text=GD.stats_text(
            em, n["Nando_hp"], n["Nando_at"], n["Nando_etc"],
            self._current_category()))
        w = GD.legality_warnings([(slot, em)], self._current_map())
        row["warn"].config(text=w[0] if w else "")

    def _update_crate(self):
        try:
            no = int(self.ent["supp_set_no"].get(), 0)
        except ValueError:
            self.crate_lbl.config(text="")
            return
        self.crate_lbl.config(text="Start crate: " + GD.supp_set_summary(no))

    def _obj_changed(self, k):
        if self._loading:
            return
        o = self.obj[k]
        try:
            t = parse_int(o["type"].get(), "type") & 0xFFFF
        except ValueError:
            return
        o["idcb"].config(values=MON_CHOICES[1:] if t in MONSTER_OBJ_TYPES
                         else [])
        self._update_objective()

    def _update_objective(self):
        try:
            q = Quest(self.base)
            self._apply_objective(q)
            self.obj_text.config(text="Reads as: " + q.objective_text(
                GD.mon_name, GD.item_name))
        except (ValueError, QuestFormatError):
            self.obj_text.config(text="")
        for k, o in self.obj.items():
            try:
                t = parse_int(o["type"].get(), "type") & 0xFFFF
                i = parse_int(o["id"].get(), "target")
                o["lbl"].config(text=(GD.item_name(i) if t == 2 else ""))
            except ValueError:
                o["lbl"].config(text="")

    def _cat_typed(self):
        cat = self._current_category()
        for b, v in enumerate(self.cat_bits):
            v.set(bool(cat >> b & 1))
        self._cat_summary(cat)

    def _cat_ticked(self):
        cat = self._current_category() & ~0xFFFFFFFF
        for b, v in enumerate(self.cat_bits):
            if v.get():
                cat |= 1 << b
        self.cat_var.set(f"0x{cat:X}")
        self._cat_summary(cat)

    def _cat_summary(self, cat):
        cut = (" Monster HP is multiplied by 0.55 on this quest."
               if cat & GD.HP_CUT_MASK else "")
        self.cat_sum.config(text=f"Set: {GD.category_summary(cat)}.{cut}")
        if not self._loading:
            self._refresh_all_stats()

    # ------------------------------------------------------- apply
    def _apply_text(self, q, commit=False):
        """Write changed text boxes into q. commit=True also marks them as
        the new baseline (used when switching the shown language)."""
        li = LANGS.index(self.lang.get())
        langs = range(len(LANGS)) if self.all_langs.get() else [li]
        for f, w in self.text_w.items():
            cur = w.get() if isinstance(w, ttk.Entry) else crlf(
                w.get("1.0", "end-1c"))
            if cur != self.loaded_text.get(f):
                q.set_string(f, cur, langs=langs)
                if commit:
                    self.loaded_text[f] = cur

    def _join_values(self):
        """(board text, rule 1, rule 2) as shown; raises ValueError."""
        return (parse_int(self.req_var.get(), "Board text"),
                parse_int(self.cond_vars[0].get(), "Rule 1"),
                parse_int(self.cond_vars[1].get(), "Rule 2"))

    def _rules_changed(self):
        """A rule changed: switch the board text to one that describes it."""
        try:
            flag, c1, c2 = self._join_values()
        except ValueError:
            return
        best = GD.text_for_rules((c1, c2), flag)
        if best is not None and best != flag:
            self.req_var.set(req_choice(best))
        self._update_join()

    def _update_join(self):
        try:
            problems = GD.requirement_problems(*self._join_values())
        except ValueError:
            problems = []
        if problems:
            self.join_lbl.config(text="\n".join(p[0].upper() + p[1:] + "."
                                                for p in problems),
                                 foreground=ERR_FG)
        else:
            self.join_lbl.config(text="Board text matches the rules.",
                                 foreground=OK_FG)

    def _apply_join(self, q):
        for f, v in zip(("special_flag", "special_cond", "special_cond2"),
                        self._join_values()):
            check_range(f, v)
            if v != q.get(f):
                q.set(f, v)

    def _apply_objective(self, q):
        q.set("clr_pattern", parse_int(self.clr_var.get(), "Combine"))
        for k, o in self.obj.items():
            p = parse_int(o["type"].get(), f"Target {k} type")
            check_range(f"{k}_param", p)
            i = parse_int(o["id"].get(), f"Target {k} id")
            check_range(f"{k}_id", i)
            n = parse_int(o["num"].get(), f"Target {k} count")
            check_range(f"{k}_num", n)
            q.set(f"{k}_param", p)
            q.set(f"{k}_id", i)
            q.set(f"{k}_num", n)

    def build(self):
        """Return the edited record bytes (raises ValueError on bad input)."""
        q = Quest(self.q.to_bytes())
        self._apply_text(q)
        for f, e in self.ent.items():
            v = parse_int(e.get(), f)
            check_range(f, v)
            if v != q.get(f):
                q.set(f, v)
        m = self._current_map()
        if m != q.get("map"):
            q.set("map", m)
        self._apply_objective(q)
        self._apply_join(q)
        for slot, row in enumerate(self.mon):
            sel = row["var"].get().strip()
            if sel == EMPTY or not sel:
                if q.monsters[slot]["Type"]:
                    q.clear_monster(slot)
                continue
            try:
                em = int(sel.split()[0])
            except ValueError:
                em = GD.resolve_mon_id(sel)
            fields = {"Type": em}
            for f, label in MON_UI:
                v = parse_int(row[f].get() or "0", f"Monster {slot + 1} {label}")
                hi = NANDO_MAX if f in NANDO_FIELDS else 255
                if not 0 <= v <= hi:
                    raise ValueError(f"Monster {slot + 1} {label} = {v} is "
                                     f"outside 0–{hi}")
                fields[f] = v
            if fields != q.monsters[slot]:
                q.set_monster(slot, **fields)
        r1, r2 = self.rewards.get()
        if r1 != list(q.reward1):
            q.set_reward_table(1, r1)
        if r2 != list(q.reward2):
            q.set_reward_table(2, r2)
        try:
            cat = int(self.cat_var.get(), 16)
        except ValueError:
            raise ValueError("Category flags must be a hex number") from None
        if not 0 <= cat < 1 << 64:
            raise ValueError("Category flags out of range")
        if cat != q.get("category"):
            q.set("category", cat)
        out = q.to_bytes()
        Quest(out)          # must re-parse
        return out

    def dirty(self):
        """True if the widgets hold changes not yet saved."""
        if not self.q:
            return False
        try:
            return self.build() != self.base
        except (ValueError, QuestFormatError):
            return True

    def warnings(self, data):
        q = Quest(data)
        return self._monster_warnings(q) + GD.requirement_problems(
            q.get("special_flag"), q.get("special_cond"), q.get("special_cond2"))

    def _monster_warnings(self, q):
        out = GD.legality_warnings(
            [(i, m["Type"]) for i, m in enumerate(q.monsters) if m["Type"]],
            q.get("map"))
        for i, m in enumerate(q.monsters):
            if m["Type"] and m["Num"] == 0:
                out.append(f"monster {i + 1}: {GD.mon_name(m['Type'])} has "
                           f"count 0, so it won't appear")
            elif m["Type"] and m["Size"] == 0:
                out.append(f"monster {i + 1}: {GD.mon_name(m['Type'])} has "
                           f"size 0%")
        return out

    def save(self):
        if not self.q:
            return
        try:
            data = self.build()
        except (ValueError, QuestFormatError) as e:
            messagebox.showerror("Can't save", str(e), parent=self)
            return
        warns = self.warnings(data)
        note = ("\n\n(A monster 1 with no spawn data for the map crashes the "
                "game when the quest loads.)"
                if self._monster_warnings(Quest(data)) else "")
        if warns and not messagebox.askyesno(
                "Check before saving",
                "Possible problems:\n\n" + "\n".join(f"• {w}" for w in warns) +
                note + "\n\nSave anyway?",
                icon="warning", parent=self):
            return
        if self.on_save(data):
            self.q = Quest(data)
            self.base = bytes(data)
            self.loaded_text = {}
            self._fill_text()
            self.msg.config(text="Saved.", foreground=OK_FG)

    def _revert(self):
        if self.q:
            self.on_revert()
