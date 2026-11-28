"""CalcSuite's look: one dark palette and hand-styled Tk widgets (no theme package needed)."""

import tkinter as tk
from tkinter import ttk

BG = "#000000"        # The window: true black
PANEL = "#0a0b0d"     # Panels
PANEL2 = "#111113"    # Buttons, raised things
LINE = "#1d1f24"      # Hairlines
FG = "#ece9e2"        # Text
DIM = "#8a929b"       # Secondary text
ACCENT = "#ff7a3d"    # The one "selected / you are here" colour: the tab underline, the side
                      # panel's selected section, the keyboard target, progress bars
MINT = "#8ff0cf"      # Only for connections (a connected calculator's dot) and links
RED = "#ff6a5e"       # Recording (and errors)
WARN = "#e6c25a"      # Something to look at (a warning, a check that didn't pass)
ADDED = "#8fb8ff"     # Added lines and items (Compare backups)
GREY = "#4a4f57"      # Not plugged in
KEYCAP = "#1b1c20"
KEYCAP_EDGE = "#2c2e34"
ACTIVE = "#1c1d21"
FONT = "Segoe UI"
MONO = "Consolas"
# The type scale (Tk sizes are points: at 96 dpi 12 pt = 16 px, 10 pt = 13 px, 9 pt = 12 px)
HEAD = ("Segoe UI Semibold", 12)   # A panel's or a tool's heading (16 px semibold)
BODY = (FONT, 10)                  # Body text (13 px): Tk's default font is set to it
HINT = (FONT, 9)                   # Hints and secondary lines (12 px, in DIM): never smaller
SMALL = (FONT, 8)                  # Only the side panel's icon labels (11 px)
CODE = (MONO, 10)                  # Code

BUTTON = dict(bg=PANEL2, fg=FG, activebackground=ACTIVE, activeforeground="#ffffff",
              relief="flat", padx=10, pady=5, bd=0, highlightthickness=0,
              disabledforeground="#55534e", takefocus=0, cursor="hand2")


def button(parent, text, command=None, **kw):
    opts = dict(BUTTON)
    opts.update(kw)
    return tk.Button(parent, text=text, command=command, **opts)


def check(parent, text, variable, command=None, bg=BG):
    return tk.Checkbutton(parent, text=text, variable=variable, command=command, bg=bg, fg=FG,
                          selectcolor=PANEL2, activebackground=bg, activeforeground="#ffffff",
                          highlightthickness=0, bd=0, takefocus=0, cursor="hand2")


def label(parent, text="", fg=FG, bg=BG, **kw):
    return tk.Label(parent, text=text, fg=fg, bg=bg, **kw)


def keycap(parent, text, bg=PANEL, accent=False):
    """A PC key drawn as a keycap"""
    return tk.Label(parent, text=text, bg=ACCENT if accent else KEYCAP,
                    fg="#000000" if accent else FG, font=(FONT, 9, "bold"), padx=7, pady=1,
                    highlightthickness=1, highlightbackground=KEYCAP_EDGE, bd=0)


def set_fonts(root):
    """Tk's own default fonts at the body size (13 px; Tk's default is 9 pt = 12 px). Labels,
    buttons, entries and lists without a font of their own follow it."""
    try:
        import tkinter.font as tkfont
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            f = tkfont.nametofont(name, root=root)
            if f.cget("size") != BODY[1]:
                f.configure(family=FONT, size=BODY[1])
    except (tk.TclError, RuntimeError):
        pass


def style_ttk(root):
    """ttk widgets (the file lists, scrollbars) in the same dark colours"""
    set_fonts(root)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")  # The one theme whose colours can all be set
    except tk.TclError:
        pass
    style.configure("Calc.Treeview", background="#0b0b0c", fieldbackground="#0b0b0c",
                    foreground=FG, rowheight=24, borderwidth=0)
    style.map("Calc.Treeview", background=[("selected", "#2b2b33")],
              foreground=[("selected", "#ffffff")])
    style.configure("Calc.Treeview.Heading", background=PANEL2, foreground=FG, relief="flat")
    style.map("Calc.Treeview.Heading", background=[("active", ACTIVE)])
    for orient in ("Vertical", "Horizontal"):
        style.configure("Calc.%s.TScrollbar" % orient, background=PANEL2, troughcolor=BG,
                        arrowcolor=DIM, bordercolor=BG, lightcolor=PANEL2, darkcolor=PANEL2)
        style.map("Calc.%s.TScrollbar" % orient, background=[("active", ACTIVE)])
    return style


def menu(parent):
    return tk.Menu(parent, tearoff=0, bg=PANEL2, fg=FG, activebackground=ACCENT,
                   activeforeground="#000000", bd=0, font=BODY, disabledforeground="#55534e")


def heading(parent, text, bg=PANEL):
    """A panel's or a tool's heading: its full name, 16 px semibold"""
    return tk.Label(parent, text=text, bg=bg, fg=FG, font=HEAD, anchor="w")


def hint(parent, text="", bg=PANEL, **kw):
    """A hint or secondary line: 12 px, DIM, wraps (to the panel's width in a side panel)"""
    opts = dict(bg=bg, fg=DIM, font=HINT, anchor="w", justify="left", wraplength=400)
    opts.update(kw)
    return tk.Label(parent, text=text, **opts)


# ---- A tab's connection dot: an antialiased circle (a Canvas oval is jagged at this size) ----
DOT_COLOURS = {"connected": MINT, "connecting": ACCENT, "failed": RED, "absent": GREY}
_dot_images = {}


def _rgb(c):
    c = c.lstrip("#")
    return tuple(int(c[k:k + 2], 16) for k in (0, 2, 4))


def dot_image(widget, colour, bg, size):
    """A round dot of colour on bg, size x size pixels, its edge blended (4 x 4 samples a
    pixel), as a PhotoImage (no Pillow). Kept: one per colour, background and size."""
    key = (colour, bg, size)
    img = _dot_images.get(key)
    if img is not None:
        return img
    fc, bc = _rgb(colour), _rgb(bg)
    r = size / 2.0
    rows = []
    for y in range(size):
        row = []
        for x in range(size):
            n = 0
            for sy in range(4):
                for sx in range(4):
                    dx, dy = x + (sx + 0.5) / 4 - r, y + (sy + 0.5) / 4 - r
                    n += dx * dx + dy * dy <= r * r
            a = n / 16.0
            row.append("#%02x%02x%02x" % tuple(int(round(f * a + b * (1 - a))) for f, b in zip(fc, bc)))
        rows.append("{" + " ".join(row) + "}")
    img = tk.PhotoImage(master=widget, width=size, height=size)
    img.put(" ".join(rows))
    _dot_images[key] = img
    return img


def status_dot(parent, bg=PANEL, state="absent"):
    """A Label showing the connection dot (set_dot changes it; its background may change too)"""
    lab = tk.Label(parent, bg=bg, bd=0, highlightthickness=0, padx=0, pady=0)
    try:
        scale = float(parent.winfo_fpixels("1i")) / 96.0
    except (tk.TclError, ValueError):
        scale = 1.0
    lab.dot_size = max(7, int(round(8 * scale)))
    set_dot(lab, state)
    return lab


def set_dot(lab, state=None, bg=None):
    """The dot's state ("connected" mint, "connecting" orange, "absent" grey, "failed" red)
    and, when given, its background (a selected tab's is lighter)"""
    if state is not None:
        lab.dot_state = state
    if bg is not None:
        lab.configure(bg=bg)
    try:
        colour = DOT_COLOURS.get(getattr(lab, "dot_state", "absent"), GREY)
        lab.configure(image=dot_image(lab, colour, str(lab.cget("bg")), lab.dot_size))
    except tk.TclError:
        pass


class Tooltip(object):
    """A small dark tip beside a widget while the mouse rests on it (below it: below=True);
    no text, no tip (the text may change later)"""

    def __init__(self, widget, text, delay=450, below=False):
        self.w, self.text, self.delay, self.below = widget, text, delay, below
        self.job = self.tip = None
        widget.bind("<Enter>", self.enter, add="+")
        widget.bind("<Leave>", self.leave, add="+")
        widget.bind("<ButtonPress>", self.leave, add="+")

    def enter(self, ev=None):
        self.cancel()
        try:
            self.job = self.w.after(self.delay, self.show)
        except tk.TclError:
            pass

    def cancel(self):
        if self.job is not None:
            try:
                self.w.after_cancel(self.job)
            except tk.TclError:
                pass
            self.job = None

    def show(self):
        self.job = None
        if not self.text:
            return
        try:
            t = self.tip = tk.Toplevel(self.w)
            t.withdraw()
            t.overrideredirect(True)
            t.attributes("-topmost", True)
            tk.Label(t, text=self.text, bg=PANEL2, fg=FG, font=HINT, padx=8, pady=3,
                     highlightthickness=1, highlightbackground=LINE).pack()
            t.update_idletasks()
            if self.below:  # A tab of the strip at the window's top
                x = self.w.winfo_rootx()
                y = self.w.winfo_rooty() + self.w.winfo_height() + 4
            else:
                # Left of it: the side panel's strip is against the window's right edge
                x = self.w.winfo_rootx() - t.winfo_reqwidth() - 6
                if x < 0:
                    x = self.w.winfo_rootx() + self.w.winfo_width() + 6
                y = self.w.winfo_rooty() + (self.w.winfo_height() - t.winfo_reqheight()) // 2
            t.geometry("+%d+%d" % (x, y))
            t.deiconify()
        except tk.TclError:
            self.tip = None

    def leave(self, ev=None):
        self.cancel()
        if self.tip is not None:
            try:
                self.tip.destroy()
            except tk.TclError:
                pass
            self.tip = None


def dark_title_bar(win):
    """Windows 10 (2004+) and 11: the window's own title bar in dark mode. Only counts as done
    once Windows accepted it: before the window is on screen there is no title bar yet, so the
    caller should call again after it appears (dark_title_bar_when_shown does both)."""
    if getattr(win, "_dark_done", False):
        return True
    if not isinstance(win, (tk.Tk, tk.Toplevel)):
        return False  # A tool in a tab of the main window (tool_tabs.ToolFrame): no title bar
    try:
        import ctypes
        from ctypes import wintypes
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        if not hwnd:
            return False
        on = ctypes.c_int(1)
        ok = False
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE, and its number before Windows 10 2004
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(wintypes.HWND(hwnd), attr, ctypes.byref(on),
                                                          ctypes.sizeof(on)) == 0:
                ok = True
                break
        if not ok:
            return False
        # Repaint the frame now (SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0020)
        win._dark_done = True
        return True
    except (AttributeError, OSError, tk.TclError):
        return False


def dark_title_bar_when_shown(win):
    """Dark title bar now if possible, and again once the window is on screen"""
    dark_title_bar(win)
    try:
        win.bind("<Map>", lambda e: dark_title_bar(win) if e.widget is win else None, add="+")
        win.after(30, lambda: dark_title_bar(win))
    except tk.TclError:
        pass
