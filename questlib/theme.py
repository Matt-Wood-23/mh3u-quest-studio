"""Soft dark theme for MH3U tools.

Palette + apply_dark_theme copied verbatim from scripts/mh3u_trainer_gui.py
(2026-07-09 "less bright, smoother on the eyes"). Deliberately NOT imported
from there — the trainer module drags in pymem/live-attach dependencies.
Extended (same palette) with ttk.Treeview styling for Save Studio.
"""
import tkinter as tk  # noqa: F401  (kept for parity with the trainer module)
from tkinter import ttk

# ---- soft dark palette (2026-07-09: "less bright, smoother on the eyes") ----
BG = "#24262b"        # window / frame background
PANEL = "#2d3037"     # buttons, tabs, raised chrome
FIELD = "#33363d"     # entry / list / text backgrounds
FG = "#c7cbd1"        # main text (soft gray, not white)
MUTED = "#878d97"     # descriptions / hints
ACCENT = "#8fb6dd"    # highlights (pouch cursor)
OK_FG = "#7cbf92"     # toast ok
ERR_FG = "#d99494"    # toast error
SEL_BG = "#3d4d63"    # selection background

TK_DARK = dict(bg=FIELD, fg=FG, selectbackground=SEL_BG, selectforeground="#e4e7ec",
               highlightthickness=0, borderwidth=0)  # for tk.Listbox / tk.Text


def apply_dark_theme(root):
    root.configure(bg=BG)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=BG, foreground=FG, fieldbackground=FIELD,
                    troughcolor=PANEL, bordercolor="#3a3d44", lightcolor=BG,
                    darkcolor=BG, focuscolor="#4a5058", insertcolor=FG)
    style.configure("TNotebook", borderwidth=0)
    style.configure("TNotebook.Tab", background=PANEL, foreground=FG, padding=(10, 4))
    style.map("TNotebook.Tab", background=[("selected", "#3a3f48")],
              foreground=[("selected", "#e4e7ec")])
    style.configure("TButton", background=PANEL)
    style.map("TButton", background=[("pressed", "#262930"), ("active", "#3a3f48")])
    for w in ("TCheckbutton", "TRadiobutton"):
        style.configure(w, indicatorbackground=FIELD, indicatorforeground=FG)
        style.map(w, background=[("active", BG)],
                  indicatorbackground=[("active", "#3a3f48")])
    style.configure("TLabelframe.Label", foreground=MUTED)
    for w in ("TSpinbox", "TCombobox"):
        style.configure(w, background=PANEL, arrowcolor=FG)
        style.map(w, fieldbackground=[("readonly", FIELD)])
    style.configure("TScrollbar", background=PANEL, arrowcolor=FG, troughcolor=BG)
    style.map("TScrollbar", background=[("active", "#3a3f48")])
    # combobox dropdown is a plain tk listbox — style via the option db
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", FG)
    root.option_add("*TCombobox*Listbox.selectBackground", SEL_BG)
    root.option_add("*TCombobox*Listbox.selectForeground", "#e4e7ec")
    # --- extension for Save Studio (same palette): Treeview + Menubutton ---
    style.configure("Treeview", background=FIELD, fieldbackground=FIELD,
                    foreground=FG, bordercolor="#3a3d44")
    style.map("Treeview", background=[("selected", SEL_BG)],
              foreground=[("selected", "#e4e7ec")])
    style.configure("Treeview.Heading", background=PANEL, foreground=FG)
    style.map("Treeview.Heading", background=[("active", "#3a3f48")])
    style.configure("TMenubutton", background=PANEL, arrowcolor=FG)
    style.map("TMenubutton", background=[("active", "#3a3f48")])
