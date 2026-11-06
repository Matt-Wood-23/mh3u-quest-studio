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
]
SUPPLY_FIELDS = [
    ("supp_enemy_num", "Hunt count (SuppEnemyNum)", 0, 99, "0 = off"),
]
# Capcom's names; the hints give the values the game's own quests use.
ADVANCED_FIELDS = [
    ("quest_no", "Quest number", 0, 65535,
     "leave as is: the quest board finds quests by this number"),
    ("demo_no", "Intro cutscene (DemoNo)", 0, 255,
     "first-meeting intro, shown until the save has seen it; 0 = none"),
    ("prog_no", "Story step (ProgNo)", 0, 255,
     "Moga story quests only; 0 = none"),
    ("ren_pattern", "Multi-monster order (Ren_pattern)", 0, 65535,
     "0 = none; copy from a similar quest"),
    ("rannyu_limite", "Rannyu_limite", 0, 65535,
     "0 in every quest; nothing in the game reads it"),
    ("nora_set_type", "NoraSetType", 0, 255,
     "0–2 in the game's quests; nothing in the game reads it"),
]
# Dropdown fields: field -> (label, {value: meaning}, dropdown width)
ENUM_FIELDS = {
    "start_param": ("Start position (StartParam)", GD.START_PARAM, 36),
    "enemy_lv": ("Monster rank (EnemyLv)", GD.ENEMY_LV, 36),
    "supp_time_flag": ("Delivery (SuppTimeFlag)", GD.SUPP_TIME, 40),
    "hagi_no": ("Supply class (HagiNo)", GD.HAGI, 36),
    "supp_enemy_type": ("Hunt delivery (SuppEnemyType)",
                        {0: "(none)", **GD.MONSTERS}, 36),
    # each crate: the base quests that use it, then what sets it apart
    "supp_set_no": ("Supply crate (SuppSetNo)",
                    {n: GD.supp_set_label(n)
                     for n in sorted({0, *GD.SUPP_SETS})}, 80),
}
# what a dropdown shows for a value the game has no meaning for
ENUM_UNKNOWN = {"supp_set_no": "no such crate in the game"}
ENUM_RANGES = {"start_param": (0, 65535), "enemy_lv": (0, 255),
               "supp_time_flag": (0, 65535), "hagi_no": (0, 255),
               "supp_enemy_type": (0, 65535), "supp_set_no": (0, 294)}
INVADER_FIELDS = [
    ("nora_set_per", "Start chance % (NoraSetPer)", 0, 100,
     "once per quest; 0 = stable, no invaders"),
    ("nora_per_type", "Chance per try % (NoraPerType)", 0, 100,
     "every 2 min while none is up; 20 lower per invader"),
    ("nora_set_max", "Max invaders (NoraSetMax)", 0, GD.INVADER_HARD_MAX,
     "3 at most"),
]
FIELD_RANGES = {f: (lo, hi) for f, _, lo, hi, _ in
                SETTINGS_FIELDS + SUPPLY_FIELDS + ADVANCED_FIELDS +
                INVADER_FIELDS}
FIELD_RANGES.update(ENUM_RANGES)
FIELD_RANGES.update({"nora_set_table": (0, 255),
                     "special_flag": (0, 65535),
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
          ("Nando2", "Row spread")]
# Row spread (Nando2) as a dropdown: the game knows 0-2 (3+ counts as 0)
SPREAD_CHOICES = ["0  fixed", "1  −2 to +2 rows", "2  −2 to 0 rows"]


def spread_choice(v):
    return SPREAD_CHOICES[v] if 0 <= v < len(SPREAD_CHOICES)         else f"{v}  counts as 0"

MON_HELP = (
    "HP / Attack / Defense row = rows of the game's difficulty table (0–127), "
    "not percentages. Higher rows = more HP and attack, less damage taken. "
    "Row spread (Nando2) moves those rows at random each hunt: 0 = fixed, "
    "1 = 2 rows down to 2 up, 2 = 2 rows down to none. "
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

INVADER_HELP = (
    "Invaders are large monsters that can wander into a quest partway "
    "through. Each quest uses one of the game's built-in invader lists. The "
    "lists are part of the game's code, so they can't be edited here, but any "
    "quest can use any list. A list made for another map can crash the game "
    "if one of its monsters has no spawn data for this quest's map; the "
    "warnings below check that.")

EMPTY = "(empty)"
MON_CHOICES = [EMPTY] + [f"{i:3d}  {n}" for i, n in sorted(GD.MONSTERS.items())]


def inv_choice(n):
    """'75  Arzuros 70%, Pink Rathian 30%   (Narg at Nite)'."""
    users = GD.invader_used_by(n)
    tail = ""
    if users:
        first = users[0].split(" ", 1)[-1]
        more = f" +{len(users) - 1}" if len(users) > 1 else ""
        tail = f"   ({first}{more})"
    return f"{n}  {GD.invader_list_label(n)}{tail}"


INVADER_CHOICES = [inv_choice(0)] + [inv_choice(n)
                                     for n in sorted(GD.INVADER_LISTS)]
COND_CHOICES = [f"{v}  {GD.cond_name(v)}" for v in range(GD.COND_COUNT)]
REQ_CHOICES = [f"{f}  {t}" for f, t in enumerate(GD.REQ_TEXT)]


def enum_choice(field, v):
    meaning = ENUM_FIELDS[field][1].get(
        v, ENUM_UNKNOWN.get(field, "not used by the game's quests"))
    return f"{v}  {meaning}"


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
        # Tk's dropdowns change their value on the mouse wheel, so scrolling
        # the page over one silently edited the quest. Replace that class
        # binding with a no-op: the wheel then just scrolls the page (the
        # "all" binding in ScrollFrame), and the open list still scrolls.
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind_class("TCombobox", seq, lambda e: None)

        self.header = ttk.Label(self, text="Select a quest",
                                font=("TkDefaultFont", 11, "bold"))
        self.header.pack(anchor="w", pady=(0, 2))
        self.subheader = ttk.Label(self, text="", foreground=MUTED)
        self.subheader.pack(anchor="w", pady=(0, 4))

        self.ent = {}           # numeric fields shown as plain entries
        self.enum = {}          # numeric fields shown as dropdowns
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)
        self.nb.add(self._tab_text(), text=" Text ")
        self.nb.add(self._tab_settings(), text=" Settings ")
        self.nb.add(self._tab_monsters(), text=" Monsters ")
        self.nb.add(self._tab_invaders(), text=" Invaders ")
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
                # no wrap: the game doesn't wrap either, so show the real lines
                w = tk.Text(tab, width=70, height=heights[f], undo=True,
                            wrap="none", insertbackground=TK_DARK["fg"],
                            **TK_DARK)
            w.grid(row=r, column=1, sticky="we", pady=3)
            self.text_w[f] = w
        tab.columnconfigure(1, weight=1)
        ttk.Label(tab, foreground=MUTED, wraplength=640, justify="left",
                  text="The game shows the slot matching the console "
                       "language (the US game has all 5 too). Untick the box "
                       "to edit one language only. The game never wraps "
                       "text: press Enter where a line should break. A "
                       "description fits 7 lines of about 39 characters, a "
                       "name about 40 (the board list shows about 23)."
                  ).grid(row=len(STRING_FIELDS) + 1, column=1, sticky="w",
                         pady=(8, 0))
        self.loaded_text = {}
        return tab

    def _entry_row(self, parent, r, field, label, hint):
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w",
                                           pady=2, padx=(0, 8))
        e = ttk.Entry(parent, width=12)
        e.grid(row=r, column=1, sticky="w", pady=2)
        self.ent[field] = e
        if hint:
            ttk.Label(parent, text=hint, foreground=MUTED).grid(
                row=r, column=2, sticky="w", padx=8)
        return e

    def _enum_row(self, parent, r, field):
        label, choices, width = ENUM_FIELDS[field]
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w",
                                           pady=2, padx=(0, 8))
        v = tk.StringVar()
        cb = ttk.Combobox(parent, textvariable=v, width=width,
                          state="readonly",
                          values=[f"{k}  {t}" for k, t in choices.items()])
        cb.grid(row=r, column=1, columnspan=2, sticky="w", pady=2)
        cb.bind("<<ComboboxSelected>>", lambda e: self._update_crate())
        self.enum[field] = v
        return cb

    def _tab_settings(self):
        sf = ScrollFrame(self.nb)
        tab = sf.inner
        tab.configure(padding=8)
        row = self._entry_row

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
        def note(parent, r, col, fg, text="", pady=0):
            """A wrapping text line across the frame from column col."""
            lbl = autowrap(ttk.Label(parent, foreground=fg, text=text,
                                     justify="left"))
            lbl.grid(row=r, column=col, columnspan=3 - col, sticky="we",
                     pady=pady)
            return lbl

        g.columnconfigure(2, weight=1)
        r = len(SETTINGS_FIELDS) + 1
        self._enum_row(g, r, "start_param")
        self.start_lbl = note(g, r + 1, 1, OK_FG)
        self._enum_row(g, r + 2, "enemy_lv")
        note(g, r + 3, 1, MUTED, "The monsters' own code reads the rank tier: "
                                 "low (0–1), high (2–3) or G (4). It doesn't "
                                 "change their HP; the difficulty rows do.")

        s = ttk.LabelFrame(tab, text="Supplies", padding=8)
        s.pack(fill="x", pady=6)
        s.columnconfigure(2, weight=1)
        self._enum_row(s, 0, "supp_set_no")
        self.crate_lbl = note(s, 1, 0, OK_FG)
        self._enum_row(s, 2, "supp_time_flag")
        self._enum_row(s, 3, "hagi_no")
        self._enum_row(s, 4, "supp_enemy_type")
        row(s, 5, *SUPPLY_FIELDS[0][:2], SUPPLY_FIELDS[0][4])
        self.ent["supp_enemy_num"].bind("<KeyRelease>",
                                        lambda e: self._update_crate())
        # the timed delivery schedule depends on the time limit
        self.ent["time_min"].bind("<KeyRelease>",
                                  lambda e: self._update_crate(), add="+")
        self.supply_lbl = note(s, 6, 0, OK_FG, pady=(6, 0))
        self.supply_warn = note(s, 7, 0, ERR_FG)
        note(s, 8, 0, MUTED, "Read from the game code and checked in-game. "
                             "For supplies the quest's rank comes from its "
                             "quest number, not its star rank. The timed "
                             "delivery follows the time limit: every game "
                             "quest that uses it is 50 minutes, the only "
                             "length where it always comes.", pady=(4, 0))

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
        # the supply rank comes from the quest number
        self.ent["quest_no"].bind("<KeyRelease>", lambda e: self._update_crate())
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
                if f == "Nando2":
                    e = ttk.Combobox(lf_, width=15, values=SPREAD_CHOICES)
                    e.bind("<<ComboboxSelected>>",
                           lambda ev, s=slot: self._refresh_stats(s))
                else:
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

    def _tab_invaders(self):
        sf = ScrollFrame(self.nb)
        tab = sf.inner
        tab.configure(padding=8)
        autowrap(ttk.Label(tab, text=INVADER_HELP, foreground=MUTED,
                           justify="left")).pack(fill="x", pady=(0, 6))
        box = ttk.LabelFrame(tab, text="Invaders", padding=8)
        box.pack(fill="x", pady=(0, 6))
        g = ttk.Frame(box)
        g.pack(fill="x")
        for r, (f, label, lo, hi, hint) in enumerate(INVADER_FIELDS):
            self._entry_row(g, r, f, label, hint).bind(
                "<KeyRelease>", lambda e: self._update_invaders())
        r = len(INVADER_FIELDS)
        ttk.Label(g, text="Invader list (NoraSetTable)").grid(
            row=r, column=0, sticky="w", pady=2, padx=(0, 8))
        self.inv_var = tk.StringVar()
        icb = ttk.Combobox(g, textvariable=self.inv_var, width=60,
                           state="readonly", values=INVADER_CHOICES)
        icb.grid(row=r, column=1, columnspan=2, sticky="w", pady=2)
        icb.bind("<<ComboboxSelected>>", lambda e: self._update_invaders())
        self.pekko_var = tk.BooleanVar()
        ttk.Checkbutton(g, variable=self.pekko_var,
                        command=self._update_invaders,
                        text="Qurupeco quest: skip the 2-minute timer "
                             "(NoraPekko)").grid(
            row=r + 1, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self.inv_state = autowrap(ttk.Label(box, justify="left"))
        self.inv_state.pack(fill="x", pady=(6, 0))
        p = ttk.LabelFrame(tab, text="Possible invaders", padding=8)
        p.pack(fill="x", pady=6)
        self.inv_lbl = autowrap(ttk.Label(p, foreground=OK_FG,
                                          justify="left"))
        self.inv_lbl.pack(fill="x")
        self.inv_warn = autowrap(ttk.Label(p, foreground=ERR_FG,
                                           justify="left"))
        self.inv_warn.pack(fill="x", pady=(4, 0))
        autowrap(ttk.Label(p, foreground=MUTED, justify="left", text=(
            "HP and strength use the invader's own difficulty rows from the "
            "list. A monster only appears once the player has unlocked its "
            "star rank (online, the room's), so early-game players may see "
            "fewer of them."))).pack(fill="x", pady=(6, 0))
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
        self.inv_var.set(inv_choice(q.get("nora_set_table")))
        self.pekko_var.set(bool(q.get("nora_pekko")))
        for f, v in self.enum.items():
            v.set(enum_choice(f, q.get(f)))
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
        if m["Type"]:
            row["Nando2"].set(spread_choice(m["Nando2"]))
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
        if not self._loading:
            self._update_crate()     # start areas depend on the map

    def _refresh_stats(self, slot):
        self._update_invaders()      # its warnings depend on the monsters
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
        try:
            spread = parse_int(row["Nando2"].get() or "0", "Row spread")
        except ValueError:
            spread = 0
        row["stats"].config(text=GD.stats_text(
            em, n["Nando_hp"], n["Nando_at"], n["Nando_etc"],
            self._current_category(), spread))
        w = GD.legality_warnings([(slot, em)], self._current_map())
        row["warn"].config(text=w[0] if w else "")

    def _num(self, field):
        """A numeric field as shown (entry or dropdown); raises ValueError."""
        w = self.ent.get(field)
        return parse_int(w.get() if w else self.enum[field].get(), field)

    def _update_crate(self):
        """Refresh the crate contents, supply plan and start-area previews."""
        if not self.q:
            return
        try:
            self.start_lbl.config(text=GD.start_text(
                self._current_map(), self._num("start_param")))
        except ValueError:
            self.start_lbl.config(text="")
        try:
            no = self._num("supp_set_no")
        except ValueError:
            self.crate_lbl.config(text="")
            return
        self.crate_lbl.config(text="Contents: " + GD.supp_set_summary(no))
        try:
            lines, probs = GD.supply_plan(
                self._num("quest_no"), no, self._num("supp_time_flag"),
                self._num("hagi_no"), self._num("supp_enemy_type"),
                self._num("supp_enemy_num"), self._num("time_min"))
        except ValueError:
            lines, probs = [], []
        self.supply_lbl.config(text="\n".join(lines))
        self.supply_warn.config(text="\n".join(p[0].upper() + p[1:] + "."
                                               for p in probs))

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

    def _main_ems(self):
        """em-IDs picked in the monster slots (as shown, unsaved)."""
        out = []
        for row in self.mon:
            sel = row["var"].get().strip()
            if not sel or sel == EMPTY:
                continue
            try:
                out.append(int(sel.split()[0]))
            except ValueError:
                try:
                    out.append(GD.resolve_mon_id(sel))
                except ValueError:
                    pass
        return out

    def _inv_values(self):
        """(start %, per-try %, max, list, Qurupeco) as shown; raises
        ValueError."""
        return (parse_int(self.ent["nora_set_per"].get(), "Start chance"),
                parse_int(self.ent["nora_per_type"].get(), "Chance per try"),
                parse_int(self.ent["nora_set_max"].get(), "Max invaders"),
                parse_int(self.inv_var.get(), "Invader list"),
                self.pekko_var.get())

    def _update_invaders(self):
        if self._loading or not self.q:
            return
        try:
            per, per_try, mx, table, pekko = self._inv_values()
        except ValueError:
            self.inv_state.config(text="")
            return
        up_to = min(mx, GD.INVADER_HARD_MAX)
        peco = bool(GD.QURUPECOS & set(self._main_ems()))
        if peco and (per or pekko):
            state = (f"Invaders come when the Qurupeco calls, up to {up_to}. "
                     f"The game keeps one waiting from the start, so the "
                     f"2-minute timer can't run; the box above makes no "
                     f"visible difference here."
                     + (" The area shows as unstable." if per else ""))
        elif pekko:
            state = ("No invaders: the 2-minute timer is skipped and there's "
                     "no Qurupeco to call them."
                     + (" The area still shows as unstable." if per else ""))
        elif per:
            state = (f"Unstable area. {per}% of runs can have invaders; in "
                     f"those, the game tries every 2 minutes while no invader "
                     f"is up, with a {per_try}% chance (20 lower after each "
                     f"invader), up to {up_to}.")
        else:
            state = "Stable area: no invaders. The other settings do nothing."
        self.inv_state.config(text=state, foreground=OK_FG
                              if per or (pekko and peco) else MUTED)
        lines = GD.invader_lines(table, self._current_category())
        users = GD.invader_used_by(table)
        if users:
            lines.append("Used by: " + ", ".join(users[:6])
                         + (f" and {len(users) - 6} more" if len(users) > 6
                            else ""))
        self.inv_lbl.config(text="\n".join(lines) or "No list picked.")
        probs = GD.invader_problems(per, per_try, mx, table, pekko,
                                    self._current_map(), self._main_ems())
        self.inv_warn.config(text="\n".join(p[0].upper() + p[1:] + "."
                                            for p in probs))

    def _apply_invaders(self, q):
        table = parse_int(self.inv_var.get(), "Invader list")
        check_range("nora_set_table", table)
        if table != q.get("nora_set_table"):
            q.set("nora_set_table", table)
        old = q.get("nora_pekko")
        pekko = (old or 1) if self.pekko_var.get() else 0
        if pekko != old:
            q.set("nora_pekko", pekko)

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
        for f in list(self.ent) + list(self.enum):
            v = self._num(f)
            check_range(f, v)
            if v != q.get(f):
                q.set(f, v)
        m = self._current_map()
        if m != q.get("map"):
            q.set("map", m)
        self._apply_objective(q)
        self._apply_join(q)
        self._apply_invaders(q)
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
        return (self._monster_warnings(q) + GD.requirement_problems(
            q.get("special_flag"), q.get("special_cond"), q.get("special_cond2"))
            + GD.invader_problems(
                q.get("nora_set_per"), q.get("nora_per_type"),
                q.get("nora_set_max"), q.get("nora_set_table"),
                q.get("nora_pekko"), q.get("map"),
                [m["Type"] for m in q.monsters if m["Type"]])
            + GD.supply_plan(
                q.get("quest_no"), q.get("supp_set_no"),
                q.get("supp_time_flag"), q.get("hagi_no"),
                q.get("supp_enemy_type"), q.get("supp_enemy_num"),
                q.get("time_min"))[1]
            + GD.text_problems(q))

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
