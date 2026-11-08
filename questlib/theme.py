"""Soft dark theme for the Studio, in the colours of the game's own menus:
dark leather brown, parchment text and gold headings. Includes Treeview.
"""
import tkinter as tk  # noqa: F401
from tkinter import ttk, font as tkfont

# ---- palette ----
BG = "#1c1814"        # window / frame background
PANEL = "#2a231c"     # buttons, tabs, cards
FIELD = "#352c23"     # entry / list / text backgrounds
FG = "#e6dac2"        # main text (parchment, not white)
MUTED = "#a6957a"     # descriptions / hints
ACCENT = "#f2b63d"    # gold: headings, highlights, stars
OK_FG = "#93d46c"     # good news, what the game will do
ERR_FG = "#ff8f73"    # problems
SEL_BG = "#7a5020"    # selection background (amber)
BORDER = "#4d3f30"
HOVER = "#3d3228"
SAVE_BG = "#c46f22"   # the one call-to-action colour (Save)
ON_GOLD = "#1c1814"   # text on a gold background

TK_DARK = dict(bg=FIELD, fg=FG, selectbackground=SEL_BG, selectforeground="#f0e6d2",
               highlightthickness=0, borderwidth=0)  # for tk.Listbox / tk.Text

SERIF = ("Palatino Linotype", "Book Antiqua", "Georgia", "DejaVu Serif",
         "Liberation Serif", "Times New Roman")


def _serif(root):
    have = set(tkfont.families(root))
    return next((f for f in SERIF if f in have), "TkDefaultFont")


_FONTS = []          # Tk deletes a named font when its Python object goes


def apply_dark_theme(root):
    root.configure(bg=BG)
    serif = _serif(root)
    # named fonts the widgets use for titles and section headings
    for name, size in (("StudioTitle", 15), ("StudioHead", 11)):
        try:
            _FONTS.append(tkfont.Font(root, name=name, family=serif, size=size,
                                      weight="bold"))
        except tk.TclError:          # already made (second window)
            tkfont.nametofont(name).configure(family=serif, size=size)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=BG, foreground=FG, fieldbackground=FIELD,
                    troughcolor=PANEL, bordercolor=BORDER, lightcolor=BG,
                    darkcolor=BG, focuscolor=HOVER, insertcolor=FG,
                    selectbackground=SEL_BG, selectforeground="#f0e6d2")
    style.configure("TNotebook", borderwidth=0)
    style.configure("TNotebook.Tab", background=PANEL, foreground=MUTED,
                    padding=(12, 5), bordercolor=BORDER)
    style.map("TNotebook.Tab", background=[("selected", HOVER)],
              foreground=[("selected", ACCENT)])
    style.configure("TButton", background=PANEL, bordercolor=BORDER)
    style.map("TButton", background=[("pressed", BG), ("active", HOVER)])
    style.configure("Save.TButton", background=SAVE_BG, foreground="#fff4de",
                    bordercolor="#e0954a")
    style.map("Save.TButton", background=[("pressed", "#a65b1a"),
                                          ("active", "#d98230"),
                                          ("disabled", PANEL)],
              foreground=[("disabled", MUTED)])
    # filter buttons (quest groups, ranks): the chosen one turns gold
    style.configure("Toolbutton", background=PANEL, foreground=FG,
                    padding=(10, 3), bordercolor=BORDER, relief="flat")
    style.map("Toolbutton",
              background=[("selected", ACCENT), ("active", HOVER)],
              foreground=[("selected", ON_GOLD)])
    for w in ("TCheckbutton", "TRadiobutton"):
        style.configure(w, indicatorbackground=FIELD, indicatorforeground=ACCENT)
        style.map(w, background=[("active", BG)],
                  indicatorbackground=[("active", HOVER)])
    style.configure("TLabelframe", bordercolor=BORDER)
    style.configure("TLabelframe.Label", foreground=ACCENT, font="StudioHead")
    # cards: a slightly raised panel
    style.configure("Card.TFrame", background=PANEL)
    style.configure("Card.TLabel", background=PANEL)
    style.configure("CardMuted.TLabel", background=PANEL, foreground=MUTED)
    style.configure("CardHead.TLabel", background=PANEL, foreground=ACCENT,
                    font="StudioHead")
    style.configure("Title.TLabel", foreground=FG, font="StudioTitle")
    style.configure("Head.TLabel", foreground=ACCENT, font="StudioHead")
    for w in ("TSpinbox", "TCombobox"):
        style.configure(w, background=PANEL, arrowcolor=ACCENT, bordercolor=BORDER)
        style.map(w, fieldbackground=[("readonly", FIELD)],
                  foreground=[("readonly", FG)])
    style.configure("TEntry", bordercolor=BORDER)
    style.configure("TScrollbar", background=PANEL, arrowcolor=MUTED, troughcolor=BG,
                    bordercolor=BG)
    style.map("TScrollbar", background=[("active", HOVER)])
    # combobox dropdown is a plain tk listbox — style via the option db
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", FG)
    root.option_add("*TCombobox*Listbox.selectBackground", SEL_BG)
    root.option_add("*TCombobox*Listbox.selectForeground", "#f0e6d2")
    # --- Treeview + Menubutton (same palette) ---
    style.configure("Treeview", background=FIELD, fieldbackground=FIELD,
                    foreground=FG, bordercolor=BORDER)
    style.map("Treeview", background=[("selected", SEL_BG)],
              foreground=[("selected", "#f0e6d2")])
    style.configure("Quests.Treeview", rowheight=32)   # room for the icons
    style.configure("Items.Treeview", rowheight=28)    # item icon rows
    style.configure("Treeview.Heading", background=PANEL, foreground=ACCENT)
    style.map("Treeview.Heading", background=[("active", HOVER)])
    style.configure("TMenubutton", background=PANEL, arrowcolor=ACCENT)
    style.map("TMenubutton", background=[("active", HOVER)])
