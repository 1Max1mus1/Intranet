from __future__ import annotations

import tkinter as tk
from tkinter import ttk

COLORS = {
    "background": "#F5F5F7",
    "surface": "#FFFFFF",
    "text": "#1D1D1F",
    "secondary": "#6E6E73",
    "accent": "#007AFF",
    "accent_hover": "#0066D6",
    "selected": "#E9E9EE",
    "border": "#D8D8DE",
}
FONT = ("Microsoft YaHei UI", 10)


def apply(root: tk.Tk) -> None:
    root.configure(bg=COLORS["background"])
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TFrame", background=COLORS["background"])
    style.configure("Sidebar.TFrame", background=COLORS["background"])
    style.configure("Card.TFrame", background=COLORS["surface"])
    style.configure("TLabel", background=COLORS["background"], foreground=COLORS["text"], font=FONT)
    style.configure("Card.TLabel", background=COLORS["surface"], foreground=COLORS["text"], font=FONT)
    style.configure("Muted.TLabel", background=COLORS["background"], foreground=COLORS["secondary"], font=("Microsoft YaHei UI", 9))
    style.configure("CardMuted.TLabel", background=COLORS["surface"], foreground=COLORS["secondary"], font=("Microsoft YaHei UI", 9))
    style.configure("Title.TLabel", background=COLORS["background"], foreground=COLORS["text"], font=("Microsoft YaHei UI", 22, "bold"))
    style.configure("Section.TLabel", background=COLORS["surface"], foreground=COLORS["text"], font=("Microsoft YaHei UI", 11, "bold"))
    style.configure("Status.TLabel", background=COLORS["background"], foreground=COLORS["accent"], font=FONT)
    style.configure("TButton", font=FONT, padding=(14, 8), borderwidth=0, focuscolor=COLORS["background"])
    style.configure("Accent.TButton", background=COLORS["accent"], foreground="white")
    style.map("Accent.TButton", background=[("active", COLORS["accent_hover"])], foreground=[("disabled", "#A0A0A5")])
    style.configure("Secondary.TButton", background=COLORS["selected"], foreground=COLORS["text"])
    style.map("Secondary.TButton", background=[("active", "#DEDEE4")])
    style.configure("Nav.TButton", background=COLORS["background"], foreground=COLORS["text"], anchor="w", padding=(16, 11))
    style.map("Nav.TButton", background=[("active", COLORS["selected"])])
    style.configure("ActiveNav.TButton", background=COLORS["selected"], foreground=COLORS["accent"], anchor="w", padding=(16, 11))
    style.configure("TEntry", fieldbackground=COLORS["surface"], foreground=COLORS["text"], bordercolor=COLORS["border"], padding=7)
    style.configure("TCheckbutton", background=COLORS["surface"], foreground=COLORS["text"], font=FONT)
    style.configure("Treeview", background=COLORS["surface"], fieldbackground=COLORS["surface"], foreground=COLORS["text"], rowheight=30, borderwidth=0)
    style.configure("Treeview.Heading", background=COLORS["surface"], foreground=COLORS["secondary"], font=("Microsoft YaHei UI", 9, "bold"))
    style.map("Treeview", background=[("selected", "#DDEAFF")], foreground=[("selected", COLORS["text"])])
    style.configure("TSpinbox", fieldbackground=COLORS["surface"], bordercolor=COLORS["border"], padding=6)
