"""Tk widgets shared by both Quest Studio tabs: the quest editor panel,
reward table, item picker and donor-monster picker."""
import copy
import tkinter as tk
from tkinter import ttk, messagebox

from . import gamedata as GD
from .quest_format import (Quest, QuestFormatError, MON_FIELDS, MON_SLOTS,
                           LANGS, STRING_FIELDS, OBJ_TYPES, CLR_PATTERNS,
                           NANDO_FIELDS, NANDO_MAX, REWARD_SLOTS,
                           ARENA_SLOT_TYPE, skill_points, skill_raw)
from .theme import TK_DARK, MUTED, ACCENT, OK_FG, ERR_FG, BG, BORDER, FG
from . import art

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
    ("rannyu_limite", "Rannyu_limite", 0, 65535,
     "0 in every quest; nothing in the game reads it"),
    ("nora_set_type", "NoraSetType", 0, 255,
     "0–2 in the game's quests; nothing in the game reads it"),
]
# Advanced dropdowns (field, hint); each value is labelled with the game's
# own quest that uses it.
ADVANCED_ENUMS = [
    ("demo_no", "first-meeting intro, shown until the save has seen it"),
    ("prog_no", "Moga story quests only"),
    ("ren_pattern", "checked each time a large monster goes down (6 and up "
                    "wait until two are down); copy it from a quest with the "
                    "same number of monsters"),
]
# Dropdown fields: field -> (label, {value: meaning}, dropdown width)
ENUM_FIELDS = {
    "start_param": ("Start position (StartParam)", GD.START_PARAM, 46),
    "enemy_lv": ("Monster rank (EnemyLv)", GD.ENEMY_LV, 36),
    "supp_time_flag": ("Delivery (SuppTimeFlag)", GD.SUPP_TIME, 40),
    "hagi_no": ("Supply class (HagiNo)", GD.HAGI, 36),
    "supp_enemy_type": ("Hunt delivery (SuppEnemyType)",
                        {0: "(none)", **GD.MONSTERS}, 36),
    # each crate: the base quests that use it, then what sets it apart
    "supp_set_no": ("Supply crate (SuppSetNo)",
                    {n: GD.supp_set_label(n)
                     for n in sorted({0, *GD.SUPP_SETS})}, 46),
    "demo_no": ("Intro cutscene (DemoNo)", GD.DEMO_NO, 50),
    "prog_no": ("Story step (ProgNo)", GD.PROG_NO, 50),
    "ren_pattern": ("Multi-monster order (Ren_pattern)", GD.REN_PATTERN, 50),
}
# what a dropdown shows for a value the game has no meaning for
ENUM_UNKNOWN = {"supp_set_no": "no such crate in the game"}
ENUM_RANGES = {"start_param": (0, 65535), "enemy_lv": (0, 255),
               "supp_time_flag": (0, 65535), "hagi_no": (0, 255),
               "supp_enemy_type": (0, 65535), "supp_set_no": (0, 294),
               "demo_no": (0, 255), "prog_no": (0, 255),
               "ren_pattern": (0, 65535)}
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


STAMINA_CHOICES = [GD.stamina_choice(v) for v in GD.STAMINA]
# monster fields shown as dropdowns: field -> (choices, width, read-only)
# (Spawn type's choices depend on the monster and map: see _refresh_stats)
MON_COMBOS = {"Nando2": (SPREAD_CHOICES, 16, False),
              "Sizeparam": (GD.SIZE_CHOICES, 16, True),
              "Stamina": (STAMINA_CHOICES, 26, True),
              "Starttype": ([], 22, False)}
# Monsters tab: Count sits by the monster's name, the rest in these groups
# (strength, size, start, stamina); a narrow window wraps whole groups.
MON_ICON_PX = 40     # monster icon on each Monsters-tab card
MAP_PX = 300         # the area map beside the monster cards
MON_GROUPS = [["Nando_hp", "Nando_at", "Nando_etc", "Nando2"],
              ["Size", "Sizeparam"],
              ["Starttype", "Settype"],
              ["Stamina"]]


def mon_field_text(f, v, points=None, qmap=None):
    """How a monster field's value is shown."""
    if f == "Nando2":
        return spread_choice(v)
    if f == "Sizeparam":
        return GD.size_choice(v)
    if f == "Stamina":
        return GD.stamina_choice(v)
    if f == "Starttype":
        return GD.spawn_choice(v, points, qmap)
    return str(v)


MON_HELP = (
    "• HP / Attack / Defense row: rows of the game's difficulty table "
    "(0–127), not percentages. Higher rows = more HP and attack, less damage "
    "taken. Row spread (Nando2) moves those rows at random each hunt.\n"
    "• Size spread adds a random amount to Size % each hunt.\n"
    "• Spawn type: one of the monster's own spawn points on this map, which "
    "sets the area it starts in (numbered as on the in-game map). Stamina: "
    "how soon it tires (the game uses 0 in the village, 1 for Port low and "
    "high rank, 2 for G rank, 3 in the arena).\n"
    "• The green line under each monster is what the game will apply. "
    "Easiest way to add a monster: Copy from quest… (one on the same map at "
    "a similar rank).")

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


ARENA_HELP = (
    "Arena quests don't use the hunter's own equipment: after departing, "
    "the player picks one of these gear sets. Each set is a weapon, five "
    "armor pieces, a talisman with up to two skills, a 24-slot item pouch "
    "and an 8-slot ammo pouch (bowguns load from it). The rank times grade "
    "the clear. Players find them at the Arena Clerk in Port Tanzia: Arena "
    "Quests are the Grudge Matches (60000–60011, base game) and Challenge "
    "Quests are 61000–61009, read from the quest4 event pack. The game "
    "lists only those numbers.")
# armor rows as shown (record slot index); the record stores them as head,
# chest, waist, arms, legs
ARENA_ARMOR_ROWS = (3, 4, 6, 5, 7)
ARENA_ARMOR_LABEL = {3: "Head", 4: "Chest", 6: "Arms", 5: "Waist", 7: "Legs"}
SKILL_CHOICES = [f"{i:3d}  {n}" for i, n in
                 enumerate(["(none)"] + GD.CHARM_SKILLS[1:])]


def id_choice(i, name):
    return f"{i:3d}  {name}"


def parse_clock(text, field):
    """'m:ss' -> seconds; a bare number is minutes."""
    t = text.strip()
    try:
        if ":" in t:
            m, s = t.split(":", 1)
            m, s = int(m or 0), int(s)
            if not 0 <= s < 60:
                raise ValueError
            v = m * 60 + s
        else:
            v = int(t or 0) * 60
    except ValueError:
        raise ValueError(f"{field}: {text!r} is not a time like 5:30") \
            from None
    if not 0 <= v <= 0xFFFF:
        raise ValueError(f"{field}: {text!r} is out of range")
    return v


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


def help_fold(parent, text, title="How this tab works"):
    """A one-line 'How this tab works ▸' link that shows the help text when
    clicked, so the controls start at the top of the tab."""
    box = ttk.Frame(parent)
    link = ttk.Label(box, text=f"ⓘ  {title}  ▸", foreground=ACCENT,
                     cursor="hand2")
    link.pack(anchor="w")
    body = autowrap(ttk.Label(box, text=text, foreground=MUTED,
                              justify="left"))

    def toggle(_e=None):
        if body.winfo_ismapped():
            body.pack_forget()
            link.config(text=f"ⓘ  {title}  ▸")
        else:
            body.pack(fill="x", pady=(4, 0))
            link.config(text=f"ⓘ  {title}  ▾")
    link.bind("<Button-1>", toggle)
    return box


def autowrap(label, pad=6):
    """Re-wrap a fill='x' label to its current width. It starts at a modest
    width so a long text doesn't make the whole window ask for room."""
    if not int(str(label.cget("wraplength")) or 0):
        label.config(wraplength=360)
    label.bind("<Configure>", lambda e: label.config(
        wraplength=max(200, e.width - pad)))
    return label


def mon_choice(em_id):
    if not em_id:
        return EMPTY
    return f"{em_id:3d}  {GD.mon_name(em_id)}"


class FlowFrame(ttk.Frame):
    """Lays its children out left to right like words, starting a new line
    when the width runs out. Add children with .add(widget, gap)."""

    def __init__(self, parent, padx=6, pady=4, **kw):
        super().__init__(parent, **kw)
        self._items, self._padx, self._pady = [], padx, pady
        self._width, self._pending = 0, False
        self.bind("<Configure>", lambda e: e.width != self._width
                  and self._layout(e.width))

    def add(self, widget, gap=0):
        """gap = extra space before the widget (dropped at a line start)."""
        self._items.append((widget, gap))
        if not self._pending:
            self._pending = True
            self.after_idle(self._relayout)
        return widget

    def _relayout(self):
        self._pending = False
        self._layout(self.winfo_width())

    def _layout(self, width):
        self._width = width
        if width <= 1:                  # not shown yet: one long line
            width = 1 << 16
        lines, line, x = [], [], 0
        for w, gap in self._items:
            ww = w.winfo_reqwidth()
            if line and x + gap + ww > width:
                lines.append(line)
                line, x = [], 0
            if line:
                x += gap
            line.append((w, x))
            x += ww + self._padx
        if line:
            lines.append(line)
        y = 0
        for line in lines:
            h = max(w.winfo_reqheight() for w, _ in line)
            for w, x in line:
                w.place(x=x, y=y + (h - w.winfo_reqheight()) // 2)
            y += h + self._pady
        self.configure(height=max(1, y - self._pady))


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

ITEM_PX = 24
_BLANK = {}


def item_image(item_id, size=ITEM_PX):
    """The item's icon for a list row (a blank square when there's none, so
    the rows line up)."""
    icon = art.ART.item_icon(item_id, size) if item_id else None
    if icon:
        return icon
    if size not in _BLANK:
        _BLANK[size] = tk.PhotoImage(width=size, height=size)
    return _BLANK[size]


class ItemPickDialog(tk.Toplevel):
    """Pick a reward item; result = (item_id, num, per) or None.
    chance=False hides the chance field (pouch slots have none)."""

    def __init__(self, parent, title, item_id=0, num=1, per=0, chance=True):
        super().__init__(parent)
        self.title(title)
        self.geometry("480x540")
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
        lf = ttk.Frame(frm)
        lf.grid(row=1, column=0, columnspan=3, sticky="nsew", pady=6)
        self.listbox = ttk.Treeview(lf, show="tree", selectmode="browse",
                                    style="Items.Treeview")
        vsb = ttk.Scrollbar(lf, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.listbox.pack(side="left", fill="both", expand=True)
        frm.rowconfigure(1, weight=1)
        self.listbox.bind("<<TreeviewSelect>>", lambda e: self._pick())
        self.listbox.bind("<Double-Button-1>", lambda e: self._ok())

        ttk.Label(frm, text="Item ID:").grid(row=2, column=0, sticky="w")
        self.id_var = tk.StringVar(value=str(item_id))
        ttk.Entry(frm, textvariable=self.id_var, width=8).grid(
            row=2, column=1, sticky="w")
        self.name_lbl = ttk.Label(frm, foreground=ACCENT, compound="left")
        self.name_lbl.grid(row=2, column=2, sticky="w")
        self.id_var.trace_add("write", lambda *a: self._show_name())

        nf = ttk.Frame(frm)
        nf.grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Label(nf, text="Amount:").pack(side="left")
        self.num_var = tk.StringVar(value=str(num))
        ttk.Spinbox(nf, from_=1, to=99, textvariable=self.num_var,
                    width=5).pack(side="left", padx=(2, 12))
        self.per_var = tk.StringVar(value=str(per))
        if chance:
            ttk.Label(nf, text="Chance %:").pack(side="left")
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
        self.listbox.delete(*self.listbox.get_children())
        self._shown = []
        for iid, name in enumerate(GD.ITEMS):
            if iid == 0 or name.startswith("(None") or name == "DUMMY":
                continue
            if pat and pat not in name.lower():
                continue
            self.listbox.insert("", "end", iid=str(iid), image=item_image(iid),
                                text=f"  {name}   ({iid})")
            self._shown.append(iid)
            if len(self._shown) >= 300:
                break
        if pat and self._shown:      # typing a name selects the top match
            self.listbox.selection_set(str(self._shown[0]))
            self.listbox.see(str(self._shown[0]))

    def _pick(self):
        sel = self.listbox.selection()
        if sel:
            self.id_var.set(sel[0])

    def _show_name(self):
        try:
            iid = int(self.id_var.get())
            self.name_lbl.config(text="  " + GD.item_name(iid),
                                 image=item_image(iid))
        except ValueError:
            self.name_lbl.config(text="", image="")

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
        self.tree = ttk.Treeview(self, columns=self.COLS, show="tree headings",
                                 height=16, selectmode="browse",
                                 style="Items.Treeview")
        self.tree.column("#0", width=40, stretch=False)     # item icon
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
        autowrap(ttk.Label(self, foreground=MUTED, justify="left",
                  text=f"The two reward columns on the quest-clear screen. "
                       f"Each column holds up to {REWARD_SLOTS} entries.")
                 ).grid(row=2, column=0, columnspan=2, sticky="we")
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
                self.tree.insert("", "end", iid=f"{col}:{i}",
                                 image=item_image(iid), values=(
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


class CratePicker(tk.Toplevel):
    """Every supply crate as a row of item icons, like the in-game box.
    result = crate number or None."""

    ROW, ICON, STEP = 44, 28, 34

    def __init__(self, parent, current=None):
        super().__init__(parent)
        self.title("Choose a supply crate")
        self.geometry("900x600")
        self.configure(bg=TK_DARK["bg"])
        self.transient(parent)
        self.grab_set()
        self.result = None
        self.sel = current
        frm = ttk.Frame(self, padding=8)
        frm.pack(fill="both", expand=True)
        top = ttk.Frame(frm)
        top.pack(fill="x", pady=(0, 6))
        ttk.Label(top, text="Search:").pack(side="left")
        self.filter = tk.StringVar()
        e = ttk.Entry(top, textvariable=self.filter, width=30)
        e.pack(side="left", padx=6)
        self.filter.trace_add("write", lambda *a: self._draw())
        ttk.Label(top, foreground=MUTED,
                  text="a quest name or an item; hover an icon for its name"
                  ).pack(side="left")
        body = ttk.Frame(frm)
        body.pack(fill="both", expand=True)
        self.cv = tk.Canvas(body, bg=TK_DARK["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(body, orient="vertical", command=self.cv.yview)
        self.cv.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.cv.pack(side="left", fill="both", expand=True)
        self.cv.bind("<Button-1>", self._click)
        self.cv.bind("<Double-Button-1>", lambda e: self._ok())
        self.cv.bind("<Motion>", self._hover)
        self.cv.bind("<MouseWheel>", lambda e: self.cv.yview_scroll(
            -1 if e.delta > 0 else 1, "units"))
        self._width = 0
        self.cv.bind("<Configure>", self._resized)
        bf = ttk.Frame(frm)
        bf.pack(fill="x", pady=(6, 0))
        self.tip = ttk.Label(bf, foreground=ACCENT)
        self.tip.pack(side="left")
        ttk.Button(bf, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(bf, text="Choose", style="Save.TButton",
                   command=self._ok).pack(side="right", padx=4)
        self.bind("<Escape>", lambda ev: self.destroy())
        self.bind("<Return>", lambda ev: self._ok())
        self._rows = []           # crate numbers in drawn order
        self._icons = {}          # canvas item -> (item id, qty)
        self._first = True
        e.focus_set()

    def _resized(self, event):
        if event.width != self._width:
            self._width = event.width
            self._draw()
            if self._first:          # open at the current crate
                self._first = False
                if self.sel in self._rows:
                    r = self._rows.index(self.sel)
                    self.cv.yview_moveto(max(0, r - 3) / len(self._rows))

    def _draw(self):
        cv = self.cv
        top = cv.yview()[0]
        cv.delete("all")
        self._rows, self._icons = [], {}
        pat = self.filter.get().strip().lower()
        width = max(400, cv.winfo_width())
        y = 0
        for n in sorted(GD.SUPP_SETS):
            items = GD.supp_set_items(n) or []
            label = GD.supp_set_label(n).split(" · ")[0]
            names = " ".join(GD.item_name(i) for i, _ in items)
            if pat and pat not in f"{n} {label} {names}".lower():
                continue
            self._rows.append(n)
            if n == self.sel:
                cv.create_rectangle(0, y, width, y + self.ROW, width=0,
                                    fill=TK_DARK["selectbackground"])
            mid = y + self.ROW / 2
            cv.create_text(8, mid, anchor="w", fill=ACCENT, text=f"{n:3d}",
                           font=("TkDefaultFont", 10, "bold"))
            cv.create_text(44, mid, anchor="w", fill=FG, text=label,
                           width=190)
            x = 250
            for iid, qty in items:
                if x + self.STEP > width:
                    break
                icon = art.ART.item_icon(iid, self.ICON)
                cx = x + self.ICON / 2
                if icon:
                    k = cv.create_image(cx, mid, image=icon)
                else:
                    k = cv.create_rectangle(cx - 11, mid - 11, cx + 11,
                                            mid + 11, outline=MUTED)
                self._icons[k] = (iid, qty)
                if qty > 1:
                    cv.create_text(x + self.ICON + 3, mid + 14, anchor="se",
                                   text=str(qty), fill="#f6ead2",
                                   font=("TkDefaultFont", 8, "bold"))
                x += self.STEP
            cv.create_line(0, y + self.ROW, width, y + self.ROW, fill=BORDER)
            y += self.ROW
        cv.configure(scrollregion=(0, 0, width, y))
        cv.yview_moveto(top)

    def _row_at(self, event):
        r = int(self.cv.canvasy(event.y) // self.ROW)
        return self._rows[r] if 0 <= r < len(self._rows) else None

    def _click(self, event):
        n = self._row_at(event)
        if n is not None:
            self.sel = n
            self._draw()

    def _hover(self, event):
        x, y = self.cv.canvasx(event.x), self.cv.canvasy(event.y)
        for k in self.cv.find_overlapping(x, y, x, y):
            if k in self._icons:
                iid, qty = self._icons[k]
                self.tip.config(text=f"{GD.item_name(iid)} ×{qty}")
                return
        self.tip.config(text="")

    def _ok(self):
        if self.sel is not None:
            self.result = self.sel
            self.destroy()


class DonorDialog(tk.Toplevel):
    """Choose a monster block from another quest. candidates =
    [(label, block_dict)]. result = block dict or None."""

    MONSTER_NOTE = ("Copies the whole monster block (difficulty rows, size, "
                    "spawn type). Pick a quest on the SAME MAP so the game "
                    "has spawn data for it, at a similar rank.")

    def __init__(self, parent, title, candidates, note=MONSTER_NOTE):
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
                  text=note).pack(anchor="w")
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
            self.result = copy.deepcopy(self._shown[s[0]][1])
            self.destroy()


class SlotTable(ttk.Frame):
    """Fixed-size pouch editor: n slots of (item, count)."""

    def __init__(self, parent, title, n):
        super().__init__(parent)
        self.n = n
        self.title = title
        ttk.Label(self, text=title).grid(row=0, column=0, sticky="w")
        self.tree = ttk.Treeview(self, columns=("slot", "item", "num"),
                                 show="tree headings", height=min(n, 8),
                                 selectmode="browse", style="Items.Treeview")
        self.tree.column("#0", width=40, stretch=False)     # item icon
        for c, w, t in (("slot", 44, "Slot"), ("item", 230, "Item"),
                        ("num", 60, "Amount")):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, stretch=(c == "item"))
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=1, column=0, sticky="nsew")
        vsb.grid(row=1, column=1, sticky="ns")
        self.columnconfigure(0, weight=1)
        bf = ttk.Frame(self)
        bf.grid(row=2, column=0, sticky="w", pady=(4, 0))
        ttk.Button(bf, text="Edit…", command=self._edit).pack(side="left")
        ttk.Button(bf, text="Empty slot", command=self._clear).pack(
            side="left", padx=4)
        self.tree.bind("<Double-Button-1>", lambda e: self._edit())
        self.slots = [[0, 0]] * n

    def set(self, pairs):
        self.slots = [list(p) for p in pairs]
        self._fill()

    def get(self):
        return [list(p) for p in self.slots]

    def _fill(self, select=None):
        self.tree.delete(*self.tree.get_children())
        for i, (iid, num) in enumerate(self.slots):
            self.tree.insert("", "end", iid=str(i), image=item_image(iid),
                             values=(i + 1, f"{GD.item_name(iid)}  ({iid})"
                                     if iid else "—", num if iid else ""))
        if select is not None:
            self.tree.selection_set(str(select))
            self.tree.see(str(select))

    def _sel(self):
        s = self.tree.selection()
        return int(s[0]) if s else None

    def _edit(self):
        i = self._sel()
        if i is None:
            return
        iid, num = self.slots[i]
        dlg = ItemPickDialog(self, f"{self.title}: slot {i + 1}", iid,
                             num or 1, chance=False)
        self.wait_window(dlg)
        if dlg.result:
            self.slots[i] = [dlg.result[0], dlg.result[1]]
            self._fill(i)

    def _clear(self):
        i = self._sel()
        if i is not None:
            self.slots[i] = [0, 0]
            self._fill(i)


# =========================================================== editor panel

class QuestEditor(ttk.Frame):
    """Editor for one quest_format.Quest. The owner supplies:
       on_save(bytes) -> bool, on_revert(), donors(em_id, quest_map) ->
       [(label, block)] for 'Copy from quest…'."""

    def __init__(self, parent, on_save, on_revert, donors=None,
                 revert_label="Revert", arena_donors=None):
        super().__init__(parent)
        self.on_save = on_save
        self.on_revert = on_revert
        self.donors = donors
        self.arena_donors = arena_donors    # () -> [(label, gear set)]
        self.arena_work = []                # gear sets being edited
        self.pack_name = None               # event pack file name, if any
        self.arena_cur = 0
        self.base = None        # bytes as loaded (for dirty checks)
        self.q = None
        self._loading = False
        # Tk's dropdowns change their value on the mouse wheel, so scrolling
        # the page over one silently edited the quest. Replace that class
        # binding with a no-op: the wheel then just scrolls the page (the
        # "all" binding in ScrollFrame), and the open list still scrolls.
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind_class("TCombobox", seq, lambda e: None)

        # header: the quest's monsters, name, rank stars and map, the way the
        # quest board shows a quest
        head = ttk.Frame(self)
        head.pack(fill="x", pady=(0, 6))
        self.head_icons = ttk.Frame(head)
        self.head_icons.pack(side="left")
        self.head_map = ttk.Label(head)
        self.head_map.pack(side="right", padx=(8, 0))
        txt = ttk.Frame(head)
        txt.pack(side="left", fill="x", expand=True, padx=(8, 0))
        self.header = ttk.Label(txt, text="Select a quest", style="Title.TLabel")
        self.header.pack(anchor="w")
        sub = ttk.Frame(txt)
        sub.pack(fill="x")
        self.head_stars = ttk.Label(sub, foreground=ACCENT,
                                    font=("TkDefaultFont", 11))
        self.head_stars.pack(side="left", padx=(0, 8))
        self.subheader = ttk.Label(sub, text="", foreground=MUTED)
        self.subheader.pack(side="left")

        self.ent = {}           # numeric fields shown as plain entries
        self.enum = {}          # numeric fields shown as dropdowns
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)
        self.nb.add(self._tab_text(), text=" Text ")
        self.nb.add(self._tab_settings(), text=" Settings ")
        self.nb.add(self._tab_monsters(), text=" Monsters ")
        self.nb.add(self._tab_invaders(), text=" Invaders ")
        self.nb.add(self._tab_rewards(), text=" Rewards ")
        self.nb.add(self._tab_arena(), text=" Arena ")
        self.nb.add(self._tab_flags(), text=" Flags ")

        bf = ttk.Frame(self)
        bf.pack(fill="x", pady=6)
        self.save_btn = ttk.Button(bf, text="Save quest  (Ctrl+S)",
                                   command=self.save, style="Save.TButton")
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
        autowrap(ttk.Label(tab, foreground=MUTED, justify="left",
                  text="The game shows the slot matching the console "
                       "language (the US game has all 5 too). Untick the box "
                       "to edit one language only. The game never wraps "
                       "text: press Enter where a line should break. A "
                       "description fits 7 lines of about 39 characters, a "
                       "name about 40 (the board list shows about 23).")
                 ).grid(row=len(STRING_FIELDS) + 1, column=1, sticky="we",
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
            autowrap(ttk.Label(parent, text=hint, foreground=MUTED,
                               justify="left")).grid(
                row=r, column=2, sticky="we", padx=8)
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
        cb = self._enum_row(s, 0, "supp_set_no")
        cb.grid_configure(columnspan=1)
        ttk.Button(s, text="Browse crates…", command=self._browse_crates
                   ).grid(row=0, column=2, sticky="w", padx=6)
        # what's in the crate, as the game's item icons
        self.crate_box = ttk.Frame(s)
        self.crate_box.grid(row=1, column=0, columnspan=3, sticky="we",
                            pady=(4, 4))
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
        ttk.Button(o, text="Hunt all large monsters", command=self._hunt_all
                   ).grid(row=0, column=2, columnspan=3, sticky="w", padx=4)
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
        o.columnconfigure(5, weight=1)
        self.obj_text = autowrap(ttk.Label(o, foreground=OK_FG,
                                           justify="left"))
        self.obj_text.grid(row=5, column=0, columnspan=6, sticky="we",
                           pady=(8, 0))
        autowrap(ttk.Label(o, foreground=MUTED, justify="left",
                  text="Changing monsters does NOT change the objective: if "
                       "you swap the target monster, update Target A/B too or "
                       "the quest can't be completed. Deliver targets are "
                       "item ids.\n"
                       "A quest holds two targets at most. The game's own "
                       "3–5 monster quests name only the last one or two "
                       "and set Multi-monster order (Advanced tab) so the "
                       "monsters come in one after another. Hunt all large "
                       "monsters sets this up from the Monsters tab."
                  )).grid(row=6, column=0, columnspan=6, sticky="we",
                          pady=(4, 0))

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
        rcb = ttk.Combobox(j, textvariable=self.req_var, width=46,
                           state="readonly", values=REQ_CHOICES)
        rcb.grid(row=2, column=1, sticky="w", pady=2)
        rcb.bind("<<ComboboxSelected>>", lambda e: self._update_join())
        j.columnconfigure(2, weight=1)
        self.join_lbl = autowrap(ttk.Label(j, justify="left"))
        self.join_lbl.grid(row=3, column=0, columnspan=3, sticky="we",
                           pady=(4, 0))
        autowrap(ttk.Label(j, foreground=MUTED, justify="left",
                           text=JOIN_HELP)).grid(row=4, column=0, columnspan=3,
                                                 sticky="we", pady=(4, 0))

        a = ttk.LabelFrame(tab, text="Advanced", padding=8)
        a.pack(fill="x", pady=6)
        a.columnconfigure(2, weight=1)
        (f, label, lo, hi, hint), *rest = ADVANCED_FIELDS
        row(a, 0, f, label, hint)
        r = 1
        for f, hint in ADVANCED_ENUMS:
            self._enum_row(a, r, f)
            autowrap(ttk.Label(a, text=hint, foreground=MUTED,
                               justify="left")).grid(
                row=r + 1, column=1, columnspan=2, sticky="we", pady=(0, 2))
            r += 2
        for f, label, lo, hi, hint in rest:
            row(a, r, f, label, hint or f"{lo}–{hi:,}")
            r += 1
        # the supply rank comes from the quest number
        self.ent["quest_no"].bind("<KeyRelease>", lambda e: self._update_crate())
        return sf

    def _tab_monsters(self):
        outer = ttk.Frame(self.nb)
        panel = self._build_map_panel(outer)
        panel.pack(side="right", fill="y")
        sf = ScrollFrame(outer)
        sf.pack(side="left", fill="both", expand=True)

        def fit(e):
            """The map needs room; in a narrow window the cards keep it (each
            card's Spawn type still names the area)."""
            want = e.width >= MAP_PX + 340
            if want and not panel.winfo_manager():
                panel.pack(side="right", fill="y", before=sf)
            elif not want and panel.winfo_manager():
                panel.pack_forget()
        outer.bind("<Configure>", fit)
        tab = sf.inner
        tab.configure(padding=8)
        help_fold(tab, MON_HELP).pack(fill="x", pady=(0, 6))
        labels = dict(MON_UI)
        self._blank_icon = tk.PhotoImage(width=MON_ICON_PX, height=MON_ICON_PX)
        self._blank_small = tk.PhotoImage(width=24, height=24)
        self.mon = []
        for slot in range(MON_SLOTS):
            lf_ = ttk.LabelFrame(tab, text=f"Monster {slot + 1}", padding=6)
            lf_.pack(fill="x", pady=3)
            row = {"var": tk.StringVar(value=EMPTY)}
            refresh = (lambda s: lambda ev: self._refresh_stats(s))(slot)

            def entry(parent, f, width):
                e = ttk.Entry(parent, width=width)
                e.bind("<KeyRelease>", refresh)
                row[f] = e
                return e

            # top line: icon, monster, count, buttons
            head = FlowFrame(lf_, padx=8)
            head.pack(fill="x")
            row["icon"] = ttk.Label(head, image=self._blank_icon)
            head.add(row["icon"])
            cb = ttk.Combobox(head, textvariable=row["var"], width=28,
                              values=MON_CHOICES)
            cb.bind("<<ComboboxSelected>>",
                    lambda e, s=slot: self._monster_picked(s))
            head.add(cb)
            cnt = ttk.Frame(head)
            ttk.Label(cnt, text=labels["Num"], foreground=MUTED).pack(
                side="left", padx=(0, 4))
            entry(cnt, "Num", 4).pack(side="left")
            head.add(cnt)
            btns = ttk.Frame(head)
            ttk.Button(btns, text="Copy from quest…",
                       command=lambda s=slot: self._copy_from(s)).pack(
                side="left", padx=(0, 6))
            ttk.Button(btns, text="Clear",
                       command=lambda s=slot: self._clear_slot(s)).pack(
                side="left")
            head.add(btns, gap=8)
            # the other fields, label over box, in groups
            body = FlowFrame(lf_, padx=22, pady=6)
            body.pack(fill="x", pady=(8, 0))
            row.update(lf=lf_, head=head, body=body)   # body hides when empty
            for group in MON_GROUPS:
                grp = ttk.Frame(body)
                body.add(grp)
                for f in group:
                    cell = ttk.Frame(grp)
                    cell.pack(side="left", padx=(0, 10))
                    ttk.Label(cell, text=labels[f], foreground=MUTED).pack(
                        anchor="w")
                    if f in MON_COMBOS:
                        values, width, ro = MON_COMBOS[f]
                        e = ttk.Combobox(cell, width=width, values=values,
                                         state="readonly" if ro else "normal")
                        e.bind("<<ComboboxSelected>>", refresh)
                        e.bind("<KeyRelease>", refresh)
                        row[f] = e
                    else:
                        e = entry(cell, f, 6)
                    e.pack(anchor="w")
            row["stats"] = autowrap(ttk.Label(lf_, foreground=OK_FG,
                                              justify="left"))
            row["stats"].pack(fill="x", pady=(6, 0))
            row["warn"] = autowrap(ttk.Label(lf_, foreground=ERR_FG,
                                             justify="left"))
            row["warn"].pack(fill="x")
            self.mon.append(row)
        return outer

    def _build_map_panel(self, parent):
        """The quest's in-game area map with where each monster and the
        hunters start (pictures from the player's game files)."""
        box = ttk.Frame(parent, padding=(10, 8, 6, 8))
        self.map_title = ttk.Label(box, style="Head.TLabel")
        self.map_title.pack(anchor="w")
        self.map_canvas = tk.Canvas(box, width=MAP_PX, height=MAP_PX, bg=BG,
                                    highlightthickness=1,
                                    highlightbackground=BORDER)
        self.map_canvas.pack(pady=(4, 6))
        self.map_legend = ttk.Frame(box)
        self.map_legend.pack(fill="x")
        return box

    def _start_marks(self, qmap):
        """[(internal area, weight %)] where the hunters start, or []."""
        try:
            sp = self._num("start_param")
        except (ValueError, KeyError):
            return []
        per = GD.START_AREAS.get(qmap)
        if not per or not 0 <= sp < len(per):
            return []
        return [(a, w) for a, w in per[sp]]

    def _update_header(self):
        """Monster icons, rank stars and the map thumbnail in the header,
        from the values as edited."""
        for w in self.head_icons.winfo_children():
            w.destroy()
        if not self.q:
            self.head_stars.config(text="")
            self.head_map.config(image="")
            return
        seen = []
        for row in getattr(self, "mon", []):
            try:
                em = int(row["var"].get().split()[0])
                if int(row["Num"].get() or 0) > 0 and em not in seen:
                    seen.append(em)
            except (ValueError, IndexError):
                pass
        for em in seen[:4]:
            icon = art.ART.monster_icon(em, 48)
            if icon:
                ttk.Label(self.head_icons, image=icon).pack(side="left",
                                                            padx=(0, 2))
        stars = self._num_or("star", self.q.get("star"))
        self.head_stars.config(text="★" * max(0, min(stars, 10)))
        stage = GD.MAP_TO_INTERNAL.get(self._current_map())
        thumb = art.ART.map_image(stage, 64) if stage else None
        self.head_map.config(image=thumb or "")

    def _update_map(self):
        if not hasattr(self, "map_canvas") or self._loading:
            return
        self._update_header()
        c = self.map_canvas
        c.delete("all")
        for w in self.map_legend.winfo_children():
            w.destroy()
        if not self.q:
            self.map_title.config(text="")
            return
        qmap = self._current_map()
        stage = GD.MAP_TO_INTERNAL.get(qmap)
        self.map_title.config(text=GD.map_name(qmap))
        img = art.ART.map_image(stage, MAP_PX) if stage else None
        if img is None:
            c.create_text(MAP_PX // 2, MAP_PX // 2, fill=MUTED,
                          justify="center", width=MAP_PX - 40,
                          text="The map picture comes from your game files; "
                               "none was found for this map.")
        else:
            c.create_image(0, 0, image=img, anchor="nw")
        shown_of = GD.AREA_SHOWN.get(qmap)

        def xy(a):
            shown = shown_of[a] if shown_of and a < len(shown_of) else a
            return art.ART.area_xy(stage, shown, MAP_PX) if stage else None

        # who starts where: group by area so markers side by side don't overlap
        at = {}
        legend = []                 # (kind, em, name, where)
        for a, w in self._start_marks(qmap):
            at.setdefault(a, []).append(("you", w))
        legend.append(("you", None, "Hunters", GD.start_text(
            qmap, self._num_or("start_param", 0)).replace("always ", "")))
        for row in self.mon:
            sel = row["var"].get()
            if sel == EMPTY or not sel.strip():
                continue
            try:
                em = int(sel.split()[0])
                count = int(row["Num"].get() or 0)
                st = int(row["Starttype"].get().split()[0])
            except (ValueError, IndexError):
                continue
            if count <= 0:
                continue
            pts = GD.spawn_points(em, qmap)
            name = GD.mon_name(em) + (f" ×{count}" if count > 1 else "")
            if pts and 0 <= st < len(pts):
                a = pts[st][0]
                # Ceadeus' entrance (area 0, off the map) leads into area 1
                at.setdefault(a or (1 if qmap == 7 else 0), []).append(
                    ("mon", em))
                legend.append(("mon", em, name, GD.spawn_area_text(qmap, a)))
            else:
                legend.append(("mon", em, name,
                               "start area not known on this map"))
        # invaders the quest can get, where the game's list sends them
        invaders = self._invader_marks(qmap)
        if invaders:
            legend.append(("head", None, "Possible invaders", ""))
        for em, a, w in invaders:
            if a is not None:
                at.setdefault(a, []).append(("inv", (em, w)))
            legend.append(("inv", em, GD.mon_name(em),
                           (GD.area_text(qmap, a) if a is not None
                            else "no start area on this map")
                           + f" · {w}% of picks"))
        for a, marks in at.items():
            p = xy(a)
            if not p:
                continue
            n = len(marks)
            for i, (kind, val) in enumerate(marks):
                x = p[0] + (i - (n - 1) / 2) * 30
                y = p[1]
                if kind == "you":
                    c.create_oval(x - 11, y - 11, x + 11, y + 11,
                                  outline=ACCENT, width=3)
                    if val < 100:
                        c.create_text(x, y + 19, text=f"{val}%", fill=ACCENT,
                                      font=("TkDefaultFont", 8, "bold"))
                    continue
                if kind == "inv":
                    em, w = val
                    c.create_oval(x - 15, y - 15, x + 15, y + 15, fill=BG,
                                  outline=ERR_FG, width=2)
                    icon = art.ART.monster_icon(em, 24)
                    if icon:
                        c.create_image(x, y, image=icon)
                    else:
                        c.create_text(x, y, text="?", fill=ERR_FG)
                    c.create_text(x, y + 22, text=f"{w}%", fill=ERR_FG,
                                  font=("TkDefaultFont", 8, "bold"))
                    continue
                c.create_oval(x - 18, y - 18, x + 18, y + 18, fill=BG,
                              outline=ACCENT, width=2)
                icon = art.ART.monster_icon(val, 30)
                if icon:
                    c.create_image(x, y, image=icon)
                else:
                    c.create_text(x, y, text="?", fill=FG)
        for kind, em, name, where in legend:
            if kind == "head":
                ttk.Label(self.map_legend, text=name, foreground=ERR_FG).pack(
                    anchor="w", pady=(8, 1))
                continue
            line = ttk.Frame(self.map_legend)
            line.pack(fill="x", pady=1)
            if kind == "you":
                ring = tk.Canvas(line, width=24, height=24, bg=BG,
                                 highlightthickness=0)
                ring.pack(side="left")
                ring.create_oval(4, 4, 20, 20, outline=ACCENT, width=3)
            else:
                icon = art.ART.monster_icon(em, 24)
                ttk.Label(line, image=icon or self._blank_small).pack(side="left")
            ttk.Label(line, text=name).pack(side="left", padx=(6, 4))
            ttk.Label(line, text=where, foreground=MUTED,
                      wraplength=MAP_PX - 120, justify="left").pack(
                side="left")

    def _invader_marks(self, qmap):
        """[(em, internal area or None, weight %)] for the invaders this
        quest can get, as the Invaders tab is set; [] when none can come."""
        try:
            per, per_try, mx, table, pekko = self._inv_values()
        except (ValueError, KeyError, AttributeError):
            return []
        main = set(self._main_ems())
        peco = bool(GD.QURUPECOS & main)
        possible = (peco and (per or pekko)) or (per and not pekko and per_try)
        if not possible or mx <= 0:
            return []
        out = []
        for cand in GD.invader_list(table):
            em = cand["em"]
            if em in main:              # the game drops a repeat
                continue
            pts = GD.spawn_points(em, qmap)
            st = cand.get("Starttype", 0)
            a = pts[st][0] if pts and 0 <= st < len(pts) else None
            out.append((em, a, cand["weight"]))
        return out

    def _num_or(self, field, default):
        try:
            return self._num(field)
        except (ValueError, KeyError):
            return default

    def _tab_invaders(self):
        sf = ScrollFrame(self.nb)
        tab = sf.inner
        tab.configure(padding=8)
        help_fold(tab, INVADER_HELP).pack(fill="x", pady=(0, 6))
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

    def _tab_arena(self):
        sf = ScrollFrame(self.nb)
        tab = sf.inner
        tab.configure(padding=8)
        help_fold(tab, ARENA_HELP).pack(fill="x", pady=(0, 6))
        self.arena_state = autowrap(ttk.Label(tab, justify="left",
                                              foreground=ACCENT))
        self.arena_state.pack(fill="x", pady=(0, 6))
        body = self.arena_body = ttk.Frame(tab)

        tb = ttk.LabelFrame(body, text="Rank times", padding=8)
        tb.pack(fill="x", pady=(0, 6))
        self.arena_time = {}
        for r, (f, label) in enumerate((
                ("arena_time_s", "S rank: clear in under (m:ss)"),
                ("arena_time_a", "A rank: clear in under (m:ss)"))):
            ttk.Label(tb, text=label).grid(row=r, column=0, sticky="w",
                                           padx=(0, 8), pady=2)
            e = ttk.Entry(tb, width=8)
            e.grid(row=r, column=1, sticky="w", pady=2)
            self.arena_time[f] = e
        ttk.Label(tb, foreground=MUTED, text=(
            "B rank is always 30:00. The game's own arena quests ask for S "
            "in 4:00–12:00 and A in 6:00–20:00.")).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))

        gb = ttk.LabelFrame(body, text="Gear sets", padding=8)
        gb.pack(fill="x", pady=6)
        top = ttk.Frame(gb)
        top.pack(fill="x")
        ttk.Label(top, text="Set").pack(side="left")
        self.set_var = tk.StringVar()
        self.set_cb = ttk.Combobox(top, textvariable=self.set_var,
                                   state="readonly", width=52)
        self.set_cb.pack(side="left", padx=6)
        self.set_cb.bind("<<ComboboxSelected>>",
                         lambda e: self._arena_pick_set())
        ttk.Button(top, text="Copy set from quest…",
                   command=self._arena_copy).pack(side="left", padx=(12, 2))
        ttk.Button(top, text="Empty set", command=self._arena_clear).pack(
            side="left", padx=2)

        eq = ttk.Frame(gb)
        eq.pack(fill="x", pady=(8, 0))
        ttk.Label(eq, text="Weapon").grid(row=0, column=0, sticky="w",
                                          padx=(0, 8), pady=2)
        self.wtype_var = tk.StringVar()
        wt = ttk.Combobox(eq, textvariable=self.wtype_var, state="readonly",
                          width=18, values=[id_choice(t, GD.EQUIP_TYPES[t])
                                            for t in GD.WEAPON_TYPES])
        wt.grid(row=0, column=1, sticky="w", pady=2)
        wt.bind("<<ComboboxSelected>>", lambda e: self._arena_wtype())
        self.wpn_var = tk.StringVar()
        self.wpn_cb = ttk.Combobox(eq, textvariable=self.wpn_var,
                                   state="readonly", width=36)
        self.wpn_cb.grid(row=0, column=2, columnspan=2, sticky="w", padx=6,
                         pady=2)
        self.armor_var = {}
        for r, slot in enumerate(ARENA_ARMOR_ROWS, start=1):
            ttk.Label(eq, text=ARENA_ARMOR_LABEL[slot]).grid(
                row=r, column=0, sticky="w", padx=(0, 8), pady=2)
            v = tk.StringVar()
            ttk.Combobox(eq, textvariable=v, state="readonly", width=36,
                         values=[id_choice(i, n) for i, n in GD.equip_choices(
                             ARENA_SLOT_TYPE[slot])]).grid(
                row=r, column=1, columnspan=2, sticky="w", pady=2)
            self.armor_var[slot] = v
        r = len(ARENA_ARMOR_ROWS) + 1
        ttk.Label(eq, text="Talisman").grid(row=r, column=0, sticky="w",
                                            padx=(0, 8), pady=2)
        self.charm_var = tk.StringVar()
        ttk.Combobox(eq, textvariable=self.charm_var, state="readonly",
                     width=36, values=[id_choice(i, n) for i, n in
                                       GD.equip_choices(6)]).grid(
            row=r, column=1, columnspan=2, sticky="w", pady=2)
        self.skill_var, self.pts_var = [], []
        for k in range(2):
            ttk.Label(eq, text=f"Talisman skill {k + 1}").grid(
                row=r + 1 + k, column=0, sticky="w", padx=(0, 8), pady=2)
            sv, pv = tk.StringVar(), tk.StringVar()
            ttk.Combobox(eq, textvariable=sv, state="readonly", width=24,
                         values=SKILL_CHOICES).grid(
                row=r + 1 + k, column=1, columnspan=2, sticky="w", pady=2)
            pf = ttk.Frame(eq)
            pf.grid(row=r + 1 + k, column=3, sticky="w", padx=6)
            ttk.Label(pf, text="points").pack(side="left")
            ttk.Spinbox(pf, from_=-10, to=20, textvariable=pv,
                        width=5).pack(side="left", padx=4)
            self.skill_var.append(sv)
            self.pts_var.append(pv)

        pouches = ttk.Frame(gb)
        pouches.pack(fill="x", pady=(10, 0))
        self.pouch = SlotTable(pouches, "Item pouch", 24)
        self.pouch.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.ammo = SlotTable(pouches, "Ammo pouch (bowguns)", 8)
        self.ammo.pack(side="left", fill="x", expand=True)
        return sf

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
        self._update_header()
        self.msg.config(text="")
        self.set_enabled(False)

    def load(self, data, title, subtitle="", pack=None):
        """`pack` is the event pack's file name (None for base-game quests)."""
        self._loading = True
        self.base = bytes(data)
        self.q = Quest(data)
        self.pack_name = pack
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
        self._arena_load()
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

    # ------------------------------------------------------- arena
    def _arena_load(self):
        q = self.q
        no = q.get("quest_no")
        self.arena_work = copy.deepcopy(q.arena_sets)
        self.arena_cur = 0
        kind = GD.arena_kind(no)
        if not q.arena_sets:
            self.arena_body.pack_forget()
            self.arena_state.config(text=(
                f"#{no} has no gear sets. To make an arena quest, open the "
                f"quest4 pack in the DLC / Event tab and use New quest… with "
                f"a Grudge Match or Challenge quest as the template (or edit "
                f"a Challenge quest that's already there)."))
            return
        self.arena_body.pack(fill="x")
        listed = no in GD.GRUDGE_LISTED or no in GD.CHALLENGE_LISTED
        wrong_pack = GD.arena_pack_problem(no, self.pack_name)
        self.arena_state.config(text=(
            f"{kind} quest: the player picks one of these "
            f"{len(q.arena_sets)} sets." +
            ("" if listed else f" #{no} isn't on the Arena Clerk's list, so "
             f"the game won't show it.") +
            (f" {wrong_pack[0][0].upper()}{wrong_pack[0][1:]}."
             if wrong_pack else "") if kind else
            f"Event quests carry {len(q.arena_sets)} blank gear sets; the "
            f"game only hands sets out on arena quests."))
        for f, e in self.arena_time.items():
            e.delete(0, "end")
            e.insert(0, GD.clock(q.get(f)))
        self._arena_refresh_sets()
        self._arena_fill()

    def _arena_refresh_sets(self):
        self.set_cb.config(values=[
            f"Set {i + 1}  ·  {GD.arena_set_summary(g)}"
            for i, g in enumerate(self.arena_work)])
        self.set_cb.current(self.arena_cur)

    def _arena_fill(self):
        g = self.arena_work[self.arena_cur]
        t, wid = g["equip"][0]
        if t in GD.EQUIP_TYPES and t >= 7:
            self.wtype_var.set(id_choice(t, GD.EQUIP_TYPES[t]))
        else:
            self.wtype_var.set("")
        self._arena_weapon_list(t)
        self.wpn_var.set(id_choice(wid, GD.equip_name(t, wid)))
        for slot, v in self.armor_var.items():
            et, eid = g["equip"][slot]
            v.set(id_choice(eid, GD.equip_name(et or ARENA_SLOT_TYPE[slot],
                                               eid)))
        ct, cid = g["equip"][8]
        self.charm_var.set(id_choice(cid, GD.equip_name(6, cid)))
        for k in range(2):
            sk, raw = g["skills"][k]
            self.skill_var[k].set(id_choice(sk, GD.charm_skill_name(sk)))
            self.pts_var[k].set(str(skill_points(raw)))
        self.pouch.set(g["pouch"])
        self.ammo.set(g["ammo"])

    def _arena_weapon_list(self, t):
        self.wpn_cb.config(values=[id_choice(i, n)
                                   for i, n in GD.equip_choices(t)])

    def _arena_wtype(self):
        t = parse_int(self.wtype_var.get(), "Weapon type")
        self._arena_weapon_list(t)
        self.wpn_var.set(id_choice(0, "(none)"))

    def _arena_commit(self):
        """Widgets -> self.arena_work[self.arena_cur]."""
        if not self.arena_work:
            return
        g = copy.deepcopy(self.arena_work[self.arena_cur])
        wid = parse_int(self.wpn_var.get() or "0", "Weapon")
        t = (parse_int(self.wtype_var.get(), "Weapon type")
             if self.wtype_var.get() else g["equip"][0][0])
        g["equip"][0] = [t if wid else 0, wid]
        for slot, v in self.armor_var.items():
            g["equip"][slot] = [ARENA_SLOT_TYPE[slot],
                                parse_int(v.get() or "0", "Armor")]
        g["equip"][8] = [6, parse_int(self.charm_var.get() or "0",
                                      "Talisman")]
        for k in range(2):
            sk = parse_int(self.skill_var[k].get() or "0", "Talisman skill")
            pts = parse_int(self.pts_var[k].get() or "0", "Skill points")
            old_sk, old_raw = g["skills"][k]
            if sk == old_sk and pts == skill_points(old_raw):
                continue                      # keep the stored bytes as-is
            g["skills"][k] = [sk, skill_raw(pts) if sk else 0]
        g["pouch"] = self.pouch.get()
        g["ammo"] = self.ammo.get()
        # an untouched set keeps its exact bytes (e.g. (5, 0) empty slots)
        old = self.arena_work[self.arena_cur]
        for slot in list(self.armor_var) + [8]:
            if g["equip"][slot][1] == 0 and old["equip"][slot][1] == 0:
                g["equip"][slot] = list(old["equip"][slot])
        if g["equip"][0][1] == old["equip"][0][1] == 0:
            g["equip"][0] = list(old["equip"][0])
        self.arena_work[self.arena_cur] = g

    def _arena_pick_set(self):
        try:
            self._arena_commit()
        except ValueError as e:
            messagebox.showerror("Gear set", str(e), parent=self)
            self.set_cb.current(self.arena_cur)
            return
        self.arena_cur = self.set_cb.current()
        self._arena_refresh_sets()
        self._arena_fill()

    def _arena_copy(self):
        cands = self.arena_donors() if self.arena_donors else []
        if not cands:
            messagebox.showinfo("Copy set", "No gear sets to copy from "
                                "(the base game's arena quests weren't "
                                "found).", parent=self)
            return
        dlg = DonorDialog(self, f"Copy into set {self.arena_cur + 1}", cands,
                          note="Copies the whole set: weapon, armor, "
                               "talisman and both pouches.")
        self.wait_window(dlg)
        if dlg.result:
            self.arena_work[self.arena_cur] = dlg.result
            self._arena_refresh_sets()
            self._arena_fill()

    def _arena_clear(self):
        g = self.arena_work[self.arena_cur]
        g["equip"] = [[0, 0], [0, 0], [0, 0]] + [
            [ARENA_SLOT_TYPE[s], 0] for s in range(3, 9)]
        g["skills"] = [[0, 0], [0, 0]]
        g["pouch"] = [[0, 0]] * 24
        g["ammo"] = [[0, 0]] * 8
        self._arena_refresh_sets()
        self._arena_fill()

    def _apply_arena(self, q):
        if not self.q.arena_sets:
            return
        self._arena_commit()
        for f, e in self.arena_time.items():
            v = parse_clock(e.get(), "S rank time" if f.endswith("s")
                            else "A rank time")
            if v != q.get(f):
                q.set(f, v)
        for i, g in enumerate(self.arena_work):
            if g != q.arena_sets[i]:
                q.set_arena_set(i, g)

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

    def _set_mon(self, row, f, v, points=None):
        w = row[f]
        if isinstance(w, ttk.Combobox):
            w.set(mon_field_text(f, v, points, self._current_map()))
        else:
            w.delete(0, "end")
            w.insert(0, str(v))

    def _fill_slot(self, slot, m):
        row = self.mon[slot]
        row["var"].set(mon_choice(m["Type"]))
        pts = (GD.spawn_points(m["Type"], self._current_map())
               if m["Type"] else None)
        for f, _ in MON_UI:
            self._set_mon(row, f, m[f] if m["Type"] else 0, pts)
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
                self._set_mon(row, f, defaults.get(f, 0))
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
        self._refresh_slot(slot)
        row = self.mon[slot]
        try:
            em = int(row["var"].get().split()[0])
        except (ValueError, IndexError):
            em = None
        row["icon"].configure(image=(art.ART.monster_icon(em, MON_ICON_PX)
                                     if em else None) or self._blank_icon)
        # an empty slot is one line: pick a monster or copy one in
        shown = bool(row["body"].winfo_manager())
        if em and not shown:
            row["body"].pack(fill="x", pady=(8, 0), after=row["head"])
            row["stats"].pack(fill="x", pady=(6, 0), after=row["body"])
            row["warn"].pack(fill="x", after=row["stats"])
        elif not em and shown:
            for k in ("body", "stats", "warn"):
                row[k].pack_forget()
        row["lf"].configure(text=f"Monster {slot + 1}"
                                 + ("" if em else "  ·  empty"))
        self._update_map()

    def _refresh_slot(self, slot):
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
        qmap = self._current_map()
        self._relabel_spawn(row, em, qmap)
        vals = {}
        for f, label in MON_UI:
            try:
                vals[f] = parse_int(row[f].get() or "0", label)
            except ValueError:
                vals[f] = None
        size = vals["Size"]
        row["stats"].config(text=GD.stats_text(
            em, n["Nando_hp"], n["Nando_at"], n["Nando_etc"],
            self._current_category(), vals["Nando2"] or 0, size,
            vals["Sizeparam"] or 0))
        w = GD.legality_warnings([(slot, em)], qmap)
        if None not in vals.values():
            w += GD.monster_problems(slot, dict(vals, Type=em), qmap)
        row["warn"].config(text="\n".join(w))

    def _relabel_spawn(self, row, em, qmap):
        """Spawn type's choices are this monster's spawn points on the map;
        with no list for the pair it's a plain number box."""
        pts = GD.spawn_points(em, qmap)
        w = row["Starttype"]
        w.configure(values=[GD.spawn_choice(i, pts, qmap)
                            for i in range(len(pts))]
                    if pts else [], state="readonly" if pts else "normal")
        try:
            v = parse_int(w.get() or "0", "Spawn type")
        except ValueError:
            return
        t = GD.spawn_choice(v, pts, qmap)
        if w.get() != t:
            w.set(t)

    def _show_crate(self, no):
        """The crate's items as icon tiles (text when there's no crate)."""
        for w in self.crate_box.winfo_children():
            w.destroy()
        items = GD.supp_set_items(no) if no is not None else None
        if not items:
            if no is not None:
                ttk.Label(self.crate_box, foreground=MUTED,
                          text=GD.supp_set_summary(no)).pack(anchor="w")
            return
        flow = FlowFrame(self.crate_box, padx=6, pady=4)
        flow.pack(fill="x")
        for iid, qty in items:
            tile = ttk.Frame(flow, style="Card.TFrame", padding=(3, 2, 8, 2))
            icon = art.ART.item_icon(iid, 24)
            if icon:
                ttk.Label(tile, image=icon, style="Card.TLabel").pack(
                    side="left")
            ttk.Label(tile, text=f"{GD.item_name(iid)} ×{qty}",
                      style="Card.TLabel").pack(side="left", padx=(4, 0))
            flow.add(tile)

    def _browse_crates(self):
        if not self.q:
            return
        dlg = CratePicker(self, self._num_or("supp_set_no", None))
        self.wait_window(dlg)
        if dlg.result is not None:
            label = ENUM_FIELDS["supp_set_no"][1][dlg.result]
            self.enum["supp_set_no"].set(f"{dlg.result}  {label}")
            self._update_crate()

    def _num(self, field):
        """A numeric field as shown (entry or dropdown); raises ValueError."""
        w = self.ent.get(field)
        return parse_int(w.get() if w else self.enum[field].get(), field)

    def _update_crate(self):
        """Refresh the crate contents, supply plan and start-area previews."""
        if not self.q:
            return
        try:
            qmap, sp = self._current_map(), self._num("start_param")
            warn = GD.start_warning(qmap, sp)
            text = GD.start_text(qmap, sp)
            self.start_lbl.config(text=f"{text}. {warn}" if warn else text,
                                  foreground=ERR_FG if warn else OK_FG)
        except ValueError:
            self.start_lbl.config(text="")
        self._update_map()           # shows where the hunters start
        try:
            no = self._num("supp_set_no")
        except ValueError:
            self._show_crate(None)
            return
        self._show_crate(no)
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

    def _hunt_all(self):
        """Point the objective at all the quest's large monsters the way the
        game's quests do: two monsters with no Multi-monster order = both
        targets; otherwise the last kind (the last two for the two-at-a-time
        orders 5 and 8), with Multi-monster order on (1 if it was off).
        Counts add up repeats."""
        order, total = [], {}
        for row in self.mon:
            sel = row["var"].get().strip()
            if not sel or sel == EMPTY:
                continue
            try:
                em = int(sel.split()[0])
            except ValueError:
                try:
                    em = GD.resolve_mon_id(sel)
                except ValueError:
                    continue
            try:
                n = max(1, int(row["Num"].get() or 1))
            except ValueError:
                n = 1
            if em in order:
                order.remove(em)
            order.append(em)             # by last appearance
            total[em] = total.get(em, 0) + n
        if not order:
            self.msg.config(text="Pick the monsters first (Monsters tab).",
                            foreground=ERR_FG)
            return
        try:
            ren = self._num("ren_pattern")
        except ValueError:
            ren = 0
        slots = sum(1 for row in self.mon
                    if row["var"].get().strip() not in ("", EMPTY))
        new_ren = ren
        if (slots <= 2 and ren == 0) or ren in (5, 8):
            targets = order[-2:]        # together, or two at a time
        else:
            targets = order[-1:]        # one after another: the last one
            new_ren = ren or 1
        both = len(targets) == 2
        self.clr_var.set(f"{int(both)}  {CLR_PATTERNS[int(both)]}")
        for k, em in zip(("obj1", "obj2"), targets + [None]):
            o = self.obj[k]
            o["type"].set(f"0x1  {OBJ_TYPES[1]}" if em else
                          f"0x0  {OBJ_TYPES[0]}")
            o["id"].set(mon_choice(em) if em else "0")
            o["num"].delete(0, "end")
            o["num"].insert(0, str(total[em] if em else 0))
        if new_ren != ren:
            self.enum["ren_pattern"].set(enum_choice("ren_pattern", new_ren))
        self._update_objective()
        self.msg.config(
            text="Objective set to hunt every large monster"
                 + (f"; Multi-monster order set to {new_ren}"
                    if new_ren != ren else "")
                 + ". Update the objective text on the Text tab to match.",
            foreground=MUTED)

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

    def _main_count(self):
        """How many large monsters the quest fields (counts added up)."""
        n = 0
        for row in self.mon:
            if row["var"].get().strip() in ("", EMPTY):
                continue
            try:
                n += max(1, int(row["Num"].get() or 1))
            except ValueError:
                n += 1
        return n

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
            big = self._main_count()
            if big >= 2:
                down = "one of them is" if big == 2 else f"{big - 1} are"
                state += (f" The timer also waits while two or more of the "
                          f"quest's large monsters are up: with {big} here, "
                          f"the first try comes 2 minutes after {down} "
                          f"down.")
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
        self._update_map()

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
        self._apply_arena(q)
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
            + GD.text_problems(q) + GD.arena_problems(q, self.pack_name))

    def _monster_warnings(self, q):
        out = GD.legality_warnings(
            [(i, m["Type"]) for i, m in enumerate(q.monsters) if m["Type"]],
            q.get("map"))
        for i, m in enumerate(q.monsters):
            out += GD.monster_problems(i, m, q.get("map"))
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
