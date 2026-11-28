"""The side panel of a calculator's tab: Files, Keys, Symbols, Functions, Data, Get programs,
Macros, Guide, Calculator info, picked on a strip of icons along the window's right edge.

Each section is built the first time it's shown. Everything that talks to the calculator goes
through the tab's Mirror (its link thread); downloads and the connection doctor run in worker
threads, so the window never freezes.
"""

import os
import queue
import tempfile
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk

import calc_models
import macros_ui
import md_render
import program_library as plib
import reference
import tool_tabs
import ui_theme as th

SECTIONS = ("Files", "Keys", "Symbols", "Functions", "Data", "Get programs", "Macros", "Guide",
            "Calculator info")
INFO = "Calculator info"  # The Info section's name (its heading; "Info" on the strip)
# The strip's short labels (the heading and the tooltip give the full name)
LABELS = {"Get programs": "Programs", INFO: "Info"}
ALIASES = {v: k for k, v in LABELS.items()}  # show("Info") is show("Calculator info")
STRIP_W = 76  # The icon strip's width (it counts in the panel's width)
WIDTH = 450 + STRIP_W  # The narrowest default; the default is a share of the window (mirror.Tab.PANEL_SHARE)
GUIDES = {"nspire": ("docs", "PYTHON_NSPIRE_GUIDE.md"), "ti84": ("docs", "TIBASIC_84.md"),
          "ti89": ("docs", "TIBASIC_89.md")}
# Save as PDF: the PDFs in docs/pdf/ (tools/docs_build/make_pdfs.py writes them, same names)
PDF_GUIDES = {"nspire": "CalcSuite - TI-Nspire CX II Python guide.pdf",
              "ti84": "CalcSuite - TI-84 Plus CE TI-Basic guide.pdf",
              "ti89": "CalcSuite - TI-89 Titanium TI-Basic guide.pdf"}
# The PC copies guide (docs/EMULATORS.md): the emulator tab's Guide (emu_tabs.py) and Calculator info
EMULATOR_GUIDE = ("docs", "EMULATORS.md")
EMULATOR_GUIDE_PDF = "CalcSuite - PC copies (CEmu and TiEmu) guide.pdf"
PDF_FUNCTIONS = {"nspire": "CalcSuite - TI-Nspire CX II functions reference.pdf",
                 "ti84": "CalcSuite - TI-84 Plus CE functions reference.pdf",
                 "ti89": "CalcSuite - TI-89 Titanium functions reference.pdf"}


# ---- The icon strip: one button per section, against the window's right edge ----
# Each icon is drawn on a 24 x 24 grid (our own drawings, MIT like the rest), rendered smooth
# into an image at the screen's scale (icon_image): ("line", points), ("ring", box), ("dot", box),
# ("text", x, y, text, font)
ICONS = {
    "Files": [("line", (3, 7, 9, 7, 11, 9, 21, 9, 21, 19, 3, 19, 3, 7))],
    "Keys": [("line", (2, 7, 22, 7, 22, 18, 2, 18, 2, 7)),
             ("line", (5, 10.5, 7, 10.5)), ("line", (9, 10.5, 11, 10.5)), ("line", (13, 10.5, 15, 10.5)),
             ("line", (17, 10.5, 19, 10.5)), ("line", (8, 14.5, 16, 14.5))],
    "Symbols": [("line", (18, 6, 18, 4, 6, 4, 12, 12, 6, 20, 18, 20, 18, 18))],
    "Functions": [("text", 12, 12, "f(x)", ("Cambria", 12, "italic"))],
    "Data": [("line", (3, 5, 21, 5, 21, 19, 3, 19, 3, 5)), ("line", (3, 10, 21, 10)),
             ("line", (3, 14.5, 21, 14.5)), ("line", (9, 5, 9, 19)), ("line", (15, 5, 15, 19))],
    "Get programs": [("line", (12, 3, 12, 14)), ("line", (7.5, 9.5, 12, 14, 16.5, 9.5)),
                     ("line", (4, 15, 4, 20, 20, 20, 20, 15))],
    "Macros": [("line", (13, 2, 6, 13, 11.5, 13, 10, 22, 18, 10, 12.5, 10, 13, 2))],
    "Guide": [("line", (12, 7, 12, 20)), ("line", (12, 7, 3, 5, 3, 18, 12, 20)),
              ("line", (12, 7, 21, 5, 21, 18, 12, 20))],
    "Calculator info": [("ring", (3, 3, 21, 21)), ("line", (12, 10.5, 12, 17)), ("dot", (10.8, 6.6, 13.2, 9))],
}


LINE_W = 1.7  # The icons' line width in grid units (pixels at 100%)
_ICON_SS = 4  # Samples a pixel each way (16 a pixel): the blended edges
_icon_masks = {}
_icon_images = {}


def ui_scale(widget):
    """The screen's scale (1.0 at 96 dpi, 1.5 at 150%, 2.0 at 200%)"""
    try:
        return max(1.0, float(widget.winfo_fpixels("1i")) / 96.0)
    except (tk.TclError, ValueError):
        return 1.0


def icon_size(scale):
    return int(round(24 * scale))


def _seg_cover(hit, n, ax, ay, bx, by, hw):
    """Marks the samples within hw of the segment a-b (sample units; round ends and joins)"""
    dx, dy = bx - ax, by - ay
    ll = dx * dx + dy * dy
    x0, x1 = max(0, int(min(ax, bx) - hw - 1)), min(n - 1, int(max(ax, bx) + hw + 1))
    y0, y1 = max(0, int(min(ay, by) - hw - 1)), min(n - 1, int(max(ay, by) + hw + 1))
    hw2 = hw * hw
    for y in range(y0, y1 + 1):
        py = y + 0.5
        row = y * n
        for x in range(x0, x1 + 1):
            px = x + 0.5
            if ll:
                t = ((px - ax) * dx + (py - ay) * dy) / ll
                t = 0.0 if t < 0 else 1.0 if t > 1 else t
                ex, ey = px - ax - t * dx, py - ay - t * dy
            else:
                ex, ey = px - ax, py - ay
            if ex * ex + ey * ey <= hw2:
                hit[row + x] = 1


def _ring_cover(hit, n, cx, cy, r, hw, fill):
    lo = 0.0 if fill else max(0.0, r - hw)
    hi = r if fill else r + hw
    lo2, hi2 = lo * lo, hi * hi
    for y in range(max(0, int(cy - hi - 1)), min(n - 1, int(cy + hi + 1)) + 1):
        py = y + 0.5 - cy
        row = y * n
        for x in range(max(0, int(cx - hi - 1)), min(n - 1, int(cx + hi + 1)) + 1):
            px = x + 0.5 - cx
            d2 = px * px + py * py
            if lo2 <= d2 <= hi2:
                hit[row + x] = 1


def icon_mask(name, scale):
    """The icon's coverage, a pixel's share 0..1 (a list, row by row, icon_size(scale) square):
    its lines, rings and dots (ICONS) drawn with blended edges. None: nothing to draw as an
    image (an unknown name, or text only: Tk draws text smooth itself). Kept per name and scale."""
    key = (name, scale)
    if key in _icon_masks:
        return _icon_masks[key]
    parts = [p for p in ICONS.get(name, []) if p[0] != "text"]
    if not parts:
        _icon_masks[key] = None
        return None
    size, ss = icon_size(scale), _ICON_SS
    n = size * ss
    f = n / 24.0  # Samples per grid unit
    # Lines a whole number of pixels wide, centred so they fill whole pixels where they run
    # straight (an even width on the grid lines, an odd one half a pixel over): crisp, not two
    # half-lit pixels
    wide = max(1, int(round(LINE_W * scale)))
    hw = wide * ss / 2.0
    shift = ss / 2.0 if wide % 2 else 0.0
    hit = bytearray(n * n)
    for part in parts:
        if part[0] == "line":
            pts = [v * f + shift for v in part[1]]
            for k in range(0, len(pts) - 2, 2):
                _seg_cover(hit, n, pts[k], pts[k + 1], pts[k + 2], pts[k + 3], hw)
        else:
            a, b, c, d = [v * f + shift for v in part[1]]
            _ring_cover(hit, n, (a + c) / 2, (b + d) / 2, (c - a) / 2, hw, part[0] == "dot")
    cover = []
    full = float(ss * ss)
    for y in range(size):
        for x in range(size):
            s = 0
            for sy in range(ss):
                base = (y * ss + sy) * n + x * ss
                s += sum(hit[base:base + ss])
            cover.append(s / full)
    _icon_masks[key] = cover
    return cover


def icon_image(widget, name, colour, bg, scale):
    """The icon in colour on bg as a PhotoImage (no Pillow), or None (see icon_mask)"""
    key = (name, colour, bg, scale)
    img = _icon_images.get(key)
    if img is not None:
        return img
    cover = icon_mask(name, scale)
    if cover is None:
        return None
    size = icon_size(scale)
    fc, bc = th._rgb(colour), th._rgb(bg)
    shades = {}
    rows = []
    for y in range(size):
        row = []
        for a in cover[y * size:(y + 1) * size]:
            hexed = shades.get(a)
            if hexed is None:
                hexed = shades[a] = "#%02x%02x%02x" % tuple(
                    int(round(fv * a + bv * (1 - a))) for fv, bv in zip(fc, bc))
            row.append(hexed)
        rows.append("{" + " ".join(row) + "}")
    img = tk.PhotoImage(master=widget, width=size, height=size)
    img.put(" ".join(rows))
    _icon_images[key] = img
    return img


def draw_icon(c, name, x0, y0, colour, scale=1.0, bg=None):
    """The icon at (x0, y0) of canvas c: its lines, rings and dots as one smooth image (tag
    "icon"), its text as Canvas text (tag "ink"); scale: the screen's (ui_scale)"""
    img = icon_image(c, name, colour, bg or str(c.cget("bg")), scale)
    if img is not None:
        c.create_image(x0, y0, image=img, anchor="nw", tags=("icon",))
    for part in ICONS.get(name, []):
        if part[0] == "text":
            c.create_text(x0 + part[1] * scale, y0 + part[2] * scale, text=part[3], font=part[4],
                          fill=colour, tags=("ink",))


class IconStrip(object):
    """A vertical strip of section buttons: an icon and a short label under it. The picked one
    is in the accent colour on PANEL2 with a 2 px accent bar on its right edge; the others DIM.
    on_pick(name) when one is clicked; the tooltip gives the full name. The icons are smooth
    images drawn for the screen's scale (crisp at 100%, 150%, 200%)."""

    ITEM_H = 56

    def __init__(self, parent, names, on_pick, labels=None, full=None):
        self.scale = s = ui_scale(parent)
        self.width = w = int(round(STRIP_W * s))
        h = int(round(self.ITEM_H * s))
        bar = max(2, int(round(2 * s)))
        self.frame = tk.Frame(parent, bg=th.PANEL, width=w)
        self.items = {}
        self.current = None
        self.hover = None
        tk.Frame(self.frame, bg=th.PANEL, height=int(round(6 * s))).pack(side="top")
        for name in names:
            c = tk.Canvas(self.frame, width=w, height=h, bg=th.PANEL,
                          highlightthickness=0, bd=0, cursor="hand2")
            c.pack(side="top")
            draw_icon(c, name, (w - icon_size(s)) // 2, int(round(7 * s)), th.DIM, s, th.PANEL)
            c.create_text(w // 2, int(round(43 * s)), text=(labels or {}).get(name, name), font=th.SMALL,
                          fill=th.DIM, tags=("ink",))
            c.create_rectangle(w - bar, 0, w, h, fill=th.PANEL, outline="", tags=("bar",))
            c.bind("<Button-1>", lambda e, n=name: on_pick(n))
            c.bind("<Enter>", lambda e, n=name: self.hovered(n))
            c.bind("<Leave>", lambda e, n=name: self.hovered(None))
            th.Tooltip(c, (full or {}).get(name, name))
            c.icon_name = name
            self.items[name] = c

    def hovered(self, name):
        old, self.hover = self.hover, name
        for n in (old, name):
            if n in self.items:
                self.paint(n)

    def select(self, name):
        old, self.current = self.current, name
        for n in (old, name):
            if n in self.items:
                self.paint(n)

    def paint(self, name):
        c = self.items[name]
        sel = name == self.current
        colour = th.ACCENT if sel else (th.FG if name == self.hover else th.DIM)
        bg = th.PANEL2 if sel else th.PANEL
        c.configure(bg=bg)
        c.itemconfigure("bar", fill=th.ACCENT if sel else bg)
        img = icon_image(c, name, colour, bg, self.scale)
        if img is not None:
            c.itemconfigure("icon", image=img)
        c.itemconfigure("ink", fill=colour)


def panel_frame(parent, names, on_pick, labels=None, full=None):
    """A side panel's frame: the icon strip on its right edge, a hairline, then the content
    (a heading and the body) to its left. (frame, strip, heading label, body)"""
    frame = tk.Frame(parent, bg=th.PANEL, width=WIDTH)
    frame.pack_propagate(False)
    strip = IconStrip(frame, names, on_pick, labels, full)
    strip.frame.pack(side="right", fill="y")
    tk.Frame(frame, bg=th.LINE, width=1).pack(side="right", fill="y")
    content = tk.Frame(frame, bg=th.PANEL)
    content.pack(side="left", fill="both", expand=True)
    head = th.heading(content, "")
    head.pack(fill="x", padx=(16, 12), pady=(14, 8))
    body = tk.Frame(content, bg=th.PANEL)
    body.pack(fill="both", expand=True, padx=(16, 12), pady=(0, 12))
    auto_wrap(frame, body)
    return frame, strip, head, body


class SidePanel(object):
    def __init__(self, parent, app, mirror):
        self.app, self.m = app, mirror
        self.calc = mirror.calc
        self.frame, self.strip, self.head, self.body = panel_frame(
            parent, SECTIONS, self.show, LABELS, {n: n for n in SECTIONS})
        self.buttons = self.strip.items  # name -> its strip button
        self.sections = {}
        self.current = None
        self.show("Keys")

    def show(self, name):
        name = ALIASES.get(name, name)
        if self.current == name:
            return
        if self.current in self.sections:
            self.sections[self.current].frame.pack_forget()
        if name not in self.sections:
            cls = {"Files": FilesSection, "Keys": KeysSection, "Symbols": SymbolsSection,
                   "Functions": FunctionsSection, "Guide": GuideSection, "Get programs": ProgramsSection,
                   INFO: InfoSection, "Data": _data_section,
                   "Macros": macros_ui.MacrosSection}[name]
            self.sections[name] = cls(self, self.body)
        self.sections[name].frame.pack(fill="both", expand=True)
        self.current = name
        self.head.configure(text=name)
        self.strip.select(name)
        if hasattr(self.sections[name], "shown"):
            self.sections[name].shown()


# ---- Text that wraps to the panel's width ----
_WRAPPED = {}   # A side panel's frame (Tk path name) -> its body: labels inside wrap to the width
MARGIN = 34     # Pixels a label sized by its own text keeps from the body's right edge (a
                # scrollbar, a box's padding)


def auto_wrap(frame, body):
    """Labels inside frame that wrap (wraplength > 0) wrap to the width the panel has instead
    of a fixed number, so their text follows the panel when it's dragged wider or narrower
    (before, they stayed 400 pixels wide: cut off in a narrower panel, a narrow column in a
    wide one). One class binding covers labels made later too (the doctor's, the About box's);
    the panel's own <Configure> brings the ones sized by their text back when it widens."""
    if not _WRAPPED:
        frame.bind_class("Label", "<Configure>", lambda e: _fit_label(e.widget), add="+")
    _WRAPPED[str(frame)] = body
    job = []

    def resized(ev):
        if job:
            frame.after_cancel(job.pop())
        job.append(frame.after(30, lambda: (job.clear(), _fit_all(body))))
    frame.bind("<Configure>", resized, add="+")


def _fit_all(widget):
    for c in widget.winfo_children():
        if isinstance(c, tk.Label):
            _fit_label(c)
        _fit_all(c)


def _fit_label(w):
    try:
        path = str(w)
        body = next((b for p, b in _WRAPPED.items() if path.startswith(p + ".")), None)
        if body is None or w.winfo_width() <= 1:  # Not laid out yet: its <Configure> comes
            return
        old = int(str(w.cget("wraplength")) or 0)
        if old <= 0:  # Made without wrapping: it stays one line
            return
        width = w.winfo_width()
        how = w.winfo_manager()
        fills = (how == "pack" and w.pack_info().get("fill") in ("x", "both")) or (
            how == "grid" and all(c in str(w.grid_info().get("sticky", "")) for c in "ew"))
        if fills and width > 20 and width != w.winfo_reqwidth():
            want = width - 4  # It gets its row's width: wrap to all of it
        else:
            # Sized by its own text: wrap where the panel's body ends (measured from where the
            # label starts, so its own size never feeds back)
            want = body.winfo_rootx() + body.winfo_width() - w.winfo_rootx() - MARGIN
            if want <= 40:
                return
        if abs(want - old) > 2:
            w.configure(wraplength=want)
    except (tk.TclError, ValueError):
        pass


def heading(parent, text):
    """A sub-heading inside a section (12 px, bold, DIM, capitals)"""
    tk.Label(parent, text=text.upper(), bg=th.PANEL, fg=th.DIM, font=(th.FONT, 9, "bold"),
             anchor="w").pack(fill="x", pady=(12, 4))


def scrolled(parent):
    """A frame inside a canvas with a scrollbar: (outer frame, inner frame)"""
    outer = tk.Frame(parent, bg=th.PANEL)
    canvas = tk.Canvas(outer, bg=th.PANEL, highlightthickness=0, bd=0)
    sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview, style="Calc.Vertical.TScrollbar")
    inner = tk.Frame(canvas, bg=th.PANEL)
    win = canvas.create_window((0, 0), window=inner, anchor="nw")
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
    canvas.configure(yscrollcommand=sb.set)
    canvas.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")

    def wheel(e):
        canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")
        return "break"
    for w in (canvas, inner):
        w.bind("<MouseWheel>", wheel)
    inner._wheel = wheel
    return outer, inner


def bind_wheel(widget, inner):
    widget.bind("<MouseWheel>", inner._wheel)
    for c in widget.winfo_children():
        bind_wheel(c, inner)


def _data_section(panel, parent):
    """Data: lists and matrices, Copy answer (data_bridge.py)"""
    import data_bridge
    return data_bridge.DataSection(panel, parent)


# ---- Files: the calculator manager, inside the panel ----
class FilesSection(object):
    def __init__(self, panel, parent):
        import calc_manager
        import mirror as mirror_mod
        self.frame = tk.Frame(parent, bg=th.PANEL)
        holder = tk.Frame(self.frame, bg=th.BG)
        holder.pack(fill="both", expand=True)
        m = panel.m
        m.manager = calc_manager.Manager(m, mirror_mod.KIT, mirror_mod.prepare_for_nspire,
                                         parent=holder, about_cb=lambda: panel.show(INFO))
        m.manager.win.pack(fill="both", expand=True)
        import picture_window  # Make a picture: a PC picture as the calculator's own (its window)
        th.button(self.frame, "Make a picture...", lambda: picture_window.open_for(m, mirror_mod.KIT)
                  ).pack(anchor="w", pady=(8, 0))


# ---- Keys: generated from the calculator's own key table ----
class KeysSection(object):
    def __init__(self, panel, parent):
        self.m = panel.m
        self.frame = tk.Frame(parent, bg=th.PANEL)
        outer, inner = scrolled(self.frame)
        outer.pack(fill="both", expand=True)
        self.caps = {}  # keysym -> (keycap label, calculator label)
        self.lit = None
        for group, rows in self.m.calc.key_groups():
            heading(inner, group)
            for pc, calc, keysym in rows:
                r = tk.Frame(inner, bg=th.PANEL)
                r.pack(fill="x", pady=1)
                cap = th.keycap(r, pc)
                cap.pack(side="left")
                tk.Label(r, text="→", bg=th.PANEL, fg=th.DIM).pack(side="left", padx=6)
                out = tk.Label(r, text=calc, bg=th.PANEL, fg=th.FG, anchor="w", justify="left",
                               wraplength=300)
                out.pack(side="left", fill="x", expand=True)
                if keysym:
                    self.caps[keysym] = (cap, out)
                    if keysym == "Return":
                        self.caps["KP_Enter"] = (cap, out)
        heading(inner, "Typing")
        tk.Label(inner, text="Letters, digits and symbols type themselves%s. Ctrl+V types the "
                 "clipboard: the Symbols panel's symbols too." % (
                     " (lower case is the 84's capital)" if self.m.calc.slug == "ti84" else ""),
                 bg=th.PANEL, fg=th.DIM, wraplength=400, justify="left", anchor="w").pack(fill="x")
        # The macros' hotkeys on this tab (macros_ui.MacroBox), kept up to date
        heading(inner, "Macro hotkeys (this tab)")
        self.hot = tk.Frame(inner, bg=th.PANEL)
        self.hot.pack(fill="x")
        self.inner = inner
        self.box = macros_ui.box_for(self.m)
        self.box.listeners.append(self.show_hotkeys)
        self.show_hotkeys()
        bind_wheel(inner, inner)
        self.m.listeners.append(self.pressed)

    def show_hotkeys(self):
        for c in self.hot.winfo_children():
            c.destroy()
        rows = [(n, self.box.by_hotkey(n)) for n in macros_ui.mc.HOTKEYS]
        rows = [(n, m) for n, m in rows if m is not None]
        for n, m in rows:
            r = tk.Frame(self.hot, bg=th.PANEL)
            r.pack(fill="x", pady=1)
            th.keycap(r, "Ctrl+%d" % n).pack(side="left")
            tk.Label(r, text="→", bg=th.PANEL, fg=th.DIM).pack(side="left", padx=6)
            tk.Label(r, text="macro: " + m["name"], bg=th.PANEL, fg=th.FG, anchor="w").pack(side="left")
        th.hint(self.hot, "None yet: the Macros panel gives a macro Ctrl+1 to Ctrl+9 (Hotkey)." if not rows else
                "Set in the Macros panel (Hotkey). They work while this tab has the keyboard.").pack(
                    fill="x", pady=(4, 0))
        try:
            bind_wheel(self.hot, self.inner)
        except AttributeError:
            pass

    def pressed(self, keysym):
        if self.lit is not None:
            cap, out = self.lit
            cap.configure(bg=th.KEYCAP, fg=th.FG)
            out.configure(fg=th.FG)
            self.lit = None
        if keysym in self.caps:
            cap, out = self.caps[keysym]
            cap.configure(bg=th.ACCENT, fg="#000000")
            out.configure(fg=th.ACCENT)
            self.lit = (cap, out)


# ---- Symbols ----
class SymbolsSection(object):
    COLS = 6  # Columns at the narrowest; more as the panel gets wider (reflow())

    def __init__(self, panel, parent):
        self.m = panel.m
        calc = self.m.calc
        self.ref = reference.load(calc.slug)
        self.pinned = None  # The symbol whose card stays when the mouse leaves (the last clicked)
        self.frame = tk.Frame(parent, bg=th.PANEL)
        tk.Label(self.frame, text="Click a symbol to type it on the %s." % calc.title, bg=th.PANEL,
                 fg=th.DIM, anchor="w").pack(fill="x", pady=(0, 8))
        grid = self.grid = tk.Frame(self.frame, bg=th.PANEL)
        grid.pack(fill="x")
        self.buttons = []
        self.cols = 0
        self.hint = tk.StringVar(master=self.frame, value="")
        for k, (sym, what, keys, near) in enumerate(calc.SYMBOLS):
            if keys is not None:
                keys = calc.keys_for(sym, getattr(self.m, "info", None))
            codes = calc_models.symbol_codes(calc, keys) if keys is not None else None
            if calc.slug == "nspire" and isinstance(keys, str):
                codes, missing = calc.paste_keys(keys)
                codes = None if missing else codes
            ok = codes is not None
            # No fixed width: the grid gives each column its share (a fixed one made the grid
            # wider than the panel, and the panel couldn't be made narrower than it)
            b = tk.Label(grid, text=sym, bg=th.KEYCAP if ok else th.PANEL, fg=th.FG if ok else th.GREY,
                         font=(th.FONT, 13), padx=4, pady=6, cursor="hand2" if ok else "arrow",
                         highlightthickness=1, highlightbackground=th.KEYCAP_EDGE)
            self.buttons.append(b)
            text = "%s: %s" % (sym, what) + ("" if ok else " (not on the %s: %s)" % (calc.title, near))
            if ok:
                seq = calc.keys_label(keys) if not isinstance(keys, str) else keys  # ↑×60, not 60 ↑
                text += "   keys: " + seq
                b.bind("<Button-1>", lambda e, c=codes, s=sym, b=b: self.send(c, s, b))
            b.bind("<Enter>", lambda e, t=text, s=sym, k=keys, o=ok, n=near: (
                self.hint.set(t), self.show_card(s, k) if o else self.show_missing(s, n)))
            b.bind("<Leave>", lambda e: (self.hint.set(""), self.show_card(*(self.pinned or (None, None)))))
        self.reflow(None)
        grid.bind("<Configure>", self.reflow)
        tk.Label(self.frame, textvariable=self.hint, bg=th.PANEL, fg=th.FG, anchor="w", justify="left",
                 wraplength=410, height=2).pack(fill="x", pady=(8, 0))
        tk.Label(self.frame, text="Greyed: the calculator has no such symbol; the hint says what "
                 "to use instead. Pasting text with these symbols (Ctrl+V) types them the same way.",
                 bg=th.PANEL, fg=th.DIM, anchor="w", justify="left", wraplength=410).pack(
                     side="bottom", fill="x", pady=(6, 0))
        # The card: what the symbol's command takes on THIS calculator (its own reference: the
        # TI-89's integral is not the Nspire's, and the TI-84 integrates with fnInt()
        box = tk.Frame(self.frame, bg=th.BG)
        box.pack(fill="both", expand=True, pady=(4, 0))
        self.card = tk.Text(box, bg=th.BG, fg=th.FG, relief="flat", wrap="word", height=6, padx=8,
                            pady=6, highlightthickness=0, bd=0, font=th.BODY, cursor="arrow",
                            insertwidth=0)
        csb = ttk.Scrollbar(box, orient="vertical", command=self.card.yview,
                            style="Calc.Vertical.TScrollbar")
        self.card.configure(yscrollcommand=csb.set)
        csb.pack(side="right", fill="y")
        self.card.pack(side="left", fill="both", expand=True)
        style_card(self.card)
        self.show_card(None, None)

    CELL = 64  # Pixels a symbol button wants (the widest, "d/dx", fits)

    def reflow(self, ev):
        """The buttons in as many columns as the width holds (6 at the narrowest, at most 12),
        laid out again only when that number changes"""
        width = ev.width if ev is not None else WIDTH - 24
        cols = max(self.COLS, min(12, width // self.CELL))
        if cols == self.cols:
            return
        for c in range(max(cols, self.cols)):
            self.grid.columnconfigure(c, weight=1 if c < cols else 0, uniform="sym" if c < cols else "")
        self.cols = cols
        for k, b in enumerate(self.buttons):
            b.grid(row=k // cols, column=k % cols, padx=2, pady=2, sticky="nsew")

    def show_missing(self, sym, near):
        """The card for a symbol this calculator doesn't have"""
        d = self.card
        d.configure(state="normal")
        d.delete("1.0", "end")
        d.insert("end", sym, "name")
        d.insert("end", "\nThe %s has no %s. %s" % (self.m.calc.title, sym, (near or "")[:1].upper() +
                                                     (near or "")[1:]), "hint")
        d.configure(state="disabled")

    def show_card(self, sym, keys):
        """The card for a symbol (None: what the box is for)"""
        d = self.card
        title = self.m.calc.title
        if sym is None:
            d.configure(state="normal")
            d.delete("1.0", "end")
            d.insert("end", "Point at a symbol to see how to use it on the %s: what to write "
                     "after it, its arguments and an example. Click one to type it; its card "
                     "stays here." % title, "hint")
            d.configure(state="disabled")
            return
        entry = reference.for_symbol(self.ref, sym)
        template = isinstance(keys, calc_models.TemplateKeys)
        lead = ("This button puts in the %s template: fill its boxes (tab moves to the next "
                "one). Typed as text, it's written:" % sym) if template else None
        if entry is None:
            d.configure(state="normal")
            d.delete("1.0", "end")
            d.insert("end", sym, "name")
            d.insert("end", "\nA symbol on its own on the %s: it takes no arguments." % title, "hint")
            d.configure(state="disabled")
            return
        draw_card(d, entry, lead)

    def send(self, codes, sym, b):
        calc = self.m.calc
        # Its keys now: the Nspire's Calculus menu differs between a CAS and the other CX II
        keys = calc.keys_for(sym, getattr(self.m, "info", None))
        self.pinned = (sym, keys)
        self.show_card(sym, keys)
        at = getattr(self.m, "palette_at", None)
        if getattr(keys, "cell", None) is not None:  # The Nspire's palette: walk from its last place
            names, at = calc_models.palette_keys(keys, at)
            codes = calc_models.symbol_codes(calc, names)
        elif isinstance(keys, str):
            codes, missing = calc.paste_keys(keys)
            codes = None if missing else codes
        elif keys is not None:
            codes = calc_models.symbol_codes(calc, keys)
        if not codes:
            return
        if self.m.send_codes(codes, sym):
            self.m.palette_at = at
            b.configure(bg=th.ACCENT, fg="#000000")
            b.after(250, lambda: b.configure(bg=th.KEYCAP, fg=th.FG))


# ---- A command's card (the Functions description, the Symbols helper) ----
def style_card(d):
    """The text styles a command card uses, on a Text widget"""
    d.tag_configure("name", font=(th.MONO, 12, "bold"), foreground=th.FG)
    d.tag_configure("cat", foreground=th.DIM)
    d.tag_configure("syntax", font=(th.MONO, 10), background="#121317")
    d.tag_configure("h", font=(th.FONT, 9, "bold"), foreground=th.DIM, spacing1=6)
    d.tag_configure("arg", font=(th.MONO, 10, "bold"), foreground=th.FG)
    d.tag_configure("opt", foreground=th.DIM)
    d.tag_configure("code", font=(th.MONO, 10))
    d.tag_configure("dim", foreground=th.DIM)
    d.tag_configure("warn", foreground=th.WARN)
    d.tag_configure("hint", foreground=th.DIM, font=(th.FONT, 10), spacing1=4)


def draw_card(d, e, lead=None):
    """A reference entry's card into the Text d: how to write it (every form), its arguments,
    what it gives, an example, its keys, notes. lead: a line above it, in the hint style."""
    d.configure(state="normal")
    d.delete("1.0", "end")
    if lead:
        d.insert("end", lead + "\n", "hint")
    d.insert("end", e["name"], "name")
    d.insert("end", "   " + e.get("category", "") + "\n", "cat")
    for form in e.get("forms") or [e["syntax"]]:
        d.insert("end", form + "\n", "syntax")
    if e.get("summary"):
        d.insert("end", e["summary"] + "\n")
    if e.get("args"):
        d.insert("end", "ARGUMENTS (separated by commas; [ ] = optional)\n", "h")
        for a in e["args"]:
            d.insert("end", a["name"], "arg")
            d.insert("end", "  " + (a.get("meaning") or ""))
            extra = (["optional"] if a.get("optional") else []) + (
                ["default " + str(a["default"])] if a.get("default") else [])
            if extra:
                d.insert("end", "  (%s)" % ", ".join(extra), "opt")
            d.insert("end", "\n")
    if e.get("returns"):
        d.insert("end", "GIVES  ", "h")
        d.insert("end", e["returns"] + "\n")
    if e.get("example"):
        d.insert("end", "EXAMPLE\n", "h")
        d.insert("end", e["example"] + "\n", "code")
    if e.get("key"):
        d.insert("end", "KEYS  ", "h")
        d.insert("end", e["key"] + "\n")
    if e.get("pc_spelling"):
        d.insert("end", "ON THE PC TYPE  ", "h")
        d.insert("end", e["pc_spelling"] + "\n", "code")
    if e.get("notes"):
        d.insert("end", "NOTE\n", "h")
        d.insert("end", e["notes"] + "\n", "warn")
    if not e.get("verified"):
        d.insert("end", "Not checked against TI's reference guide yet.\n", "dim")
    d.configure(state="disabled")
    d.yview_moveto(0)


# ---- Functions: every command, its arguments, Insert (tools/reference.py) ----
class FunctionsSection(object):
    ALL = "All categories"

    def __init__(self, panel, parent):
        self.m = panel.m
        self.calc = self.m.calc
        self.ref = reference.load(self.calc.slug)
        self.frame = tk.Frame(parent, bg=th.PANEL)
        top = tk.Frame(self.frame, bg=th.PANEL)
        top.pack(fill="x", pady=(0, 6))
        self.query = tk.StringVar(master=self.frame, value="")
        self.count = tk.Label(top, text="", bg=th.PANEL, fg=th.DIM)
        self.count.pack(side="right", padx=(6, 0))
        self.search = tk.Entry(top, textvariable=self.query, bg=th.PANEL2, fg=th.FG,
                               insertbackground=th.FG, relief="flat", width=16)
        self.search.pack(side="left", ipady=3, fill="x", expand=True)
        self.search.bind("<Return>", lambda e: self.pick_first())
        self.search.bind("<Down>", lambda e: self.pick_first())
        self.category = None
        self.cat_btn = tk.Menubutton(top, text=self.ALL + " ▾", bg=th.PANEL2, fg=th.FG,
                                     activebackground=th.ACTIVE, activeforeground="#ffffff",
                                     relief="flat", bd=0, padx=8, pady=4, takefocus=0)
        self.cat_btn.pack(side="left", padx=(8, 0))
        menu = th.menu(self.cat_btn)
        for c in [None] + reference.categories(self.ref):
            menu.add_command(label=c or self.ALL, command=lambda c=c: self.set_category(c))
        self.cat_btn.configure(menu=menu)
        mid = tk.Frame(self.frame, bg=th.PANEL)
        mid.pack(fill="x")
        tree = self.tree = ttk.Treeview(mid, columns=("what",), style="Calc.Treeview",
                                        selectmode="browse", height=FunctionsSection.rows or 16)
        tree.heading("#0", text="Command", anchor="w")
        tree.column("#0", width=140, anchor="w", stretch=False)
        tree.heading("what", text="What it does", anchor="w")
        tree.column("what", width=250, anchor="w")
        sb = ttk.Scrollbar(mid, orient="vertical", command=tree.yview, style="Calc.Vertical.TScrollbar")
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        tree.tag_configure("unverified", foreground=th.DIM)
        tree.bind("<<TreeviewSelect>>", lambda e: self.picked())
        tree.bind("<Double-1>", self.double)  # Double click: Insert, like its button
        tree.bind("<Return>", lambda e: self.insert())
        # A handle between the list and the description: drag it up or down
        grip = tk.Frame(self.frame, bg=th.PANEL, height=10, cursor="sb_v_double_arrow")
        grip.pack(fill="x")
        gline = tk.Frame(grip, bg=th.PANEL2, height=2)
        gline.place(relx=0.5, rely=0.5, relwidth=0.15, anchor="center")
        grip.bind("<B1-Motion>", self.drag_split)
        grip.bind("<Enter>", lambda e: gline.configure(bg=th.ACCENT))
        grip.bind("<Leave>", lambda e: gline.configure(bg=th.PANEL2))
        box = tk.Frame(self.frame, bg=th.BG)  # The description and its scrollbar
        box.pack(fill="both", expand=True)
        self.detail = tk.Text(box, bg=th.BG, fg=th.FG, relief="flat", wrap="word", height=4,
                              padx=8, pady=6, highlightthickness=0, bd=0, font=th.BODY,
                              cursor="arrow", insertwidth=0)
        dsb = ttk.Scrollbar(box, orient="vertical", command=self.detail.yview,
                            style="Calc.Vertical.TScrollbar")
        self.detail.configure(yscrollcommand=dsb.set)
        dsb.pack(side="right", fill="y")
        self.detail.pack(side="left", fill="both", expand=True)
        style_card(self.detail)
        self.show_hint()
        bar = tk.Frame(self.frame, bg=th.PANEL)
        bar.pack(fill="x", pady=(6, 0))
        self.insert_btn = th.button(bar, "Insert", self.insert, state="disabled")
        self.insert_btn.pack(side="left")
        self.copy_btn = th.button(bar, "Copy", self.copy, state="disabled")
        self.copy_btn.pack(side="left", padx=(6, 0))
        self.copy_ex_btn = th.button(bar, "Copy example", self.copy_example, state="disabled")
        self.copy_ex_btn.pack(side="left", padx=(6, 0))
        th.button(bar, "Save as PDF", lambda: save_pdf(
            self.frame, PDF_FUNCTIONS[self.calc.slug], self.status.set)).pack(side="right")
        self.status = tk.StringVar(master=self.frame, value="")
        tk.Label(self.frame, textvariable=self.status, bg=th.PANEL, fg=th.DIM, anchor="w",
                 justify="left", wraplength=410).pack(fill="x", pady=(6, 0))
        self.items, self.item = [], None
        self.query.trace_add("write", lambda *a: self.refresh())
        self.refresh()
        if self.ref.get("error"):
            self.status.set("The function list isn't there: %s" % self.ref["error"])
        else:
            self.status.set("Type a name or a word (\"integral\", \"matrix\"), or paste code to "
                            "see the commands it uses.")

    def drag_split(self, ev):
        """The list's height follows the handle, a whole number of rows"""
        try:
            row = int(ttk.Style().lookup("Calc.Treeview", "rowheight") or 22)
        except (ValueError, tk.TclError):
            row = 22
        rows = (ev.y_root - self.tree.winfo_rooty() - row) // row  # Minus the heading row
        # Room kept below the list: the handle, a few lines of description, the buttons, the note
        bottom = self.frame.winfo_rooty() + self.frame.winfo_height()
        most = (bottom - self.tree.winfo_rooty() - 190) // row - 1
        FunctionsSection.rows = max(4, min(most, rows))
        self.tree.configure(height=FunctionsSection.rows)

    rows = 0  # The height the user dragged the list to (this session)

    def shown(self):
        self.search.focus_set()

    def set_category(self, c):
        self.category = c
        self.cat_btn.configure(text=(c or self.ALL) + " ▾")
        self.refresh()

    def refresh(self):
        q = self.query.get()
        if any(s in q for s in (":", "->", "→", "\n")) or (q.count("(") and q.count(",")):
            # Code: list the commands it uses, in order
            self.items = [e for e in reference.referenced(self.calc.slug, q, self.ref)
                          if not self.category or e.get("category") == self.category]
            what = "used in that code"
        else:
            self.items = reference.search(self.ref, q, self.category)
            what = "found" if q.strip() else ""
        tree = self.tree
        tree.delete(*tree.get_children())
        for k, e in enumerate(self.items):
            tree.insert("", "end", iid=str(k), text=e["name"], values=(e.get("summary", ""),),
                        tags=(() if e.get("verified") else ("unverified",)))
        n = len(self.items)
        self.count.configure(text="%d %s" % (n, what) if what else "%d commands" % n)

    def pick_first(self):
        if self.items:
            self.tree.focus_set()
            self.tree.selection_set("0")
            self.tree.focus("0")
            self.tree.see("0")
        return "break"

    def double(self, ev):
        row = self.tree.identify_row(ev.y)
        if row:
            self.tree.selection_set(row)
            self.picked()
            self.insert()
        return "break"

    def show_hint(self):
        """What the description box says while no command is picked"""
        d = self.detail
        d.configure(state="normal")
        d.delete("1.0", "end")
        d.insert("end", "Pick a command in the list to see what it does: how to write it, its "
                 "arguments, what it gives back, an example and the keys that type it.\n\n"
                 "Double-click it (or Insert) to type it on the calculator. Search above by name "
                 "or by a word such as \"integral\", or paste code to see the commands it uses.",
                 "hint")
        d.configure(state="disabled")

    def picked(self):
        sel = self.tree.selection()
        if not sel:
            self.show_hint()
            return
        e = self.item = self.items[int(sel[0])]
        d = self.detail
        draw_card(d, e)
        d.yview_moveto(0)
        kind, _what, why = reference.insert_plan(self.calc.slug, e)
        self.insert_btn.configure(state="normal" if kind else "disabled")
        self.copy_btn.configure(state="normal")
        self.copy_ex_btn.configure(state="normal" if e.get("example") else "disabled")
        self.status.set(why if not kind else "")

    def insert(self):
        """Types the command on the calculator, the way the Symbols panel sends its symbols"""
        e = self.item
        if e is None:
            return
        calc = self.calc
        kind, what, note = reference.insert_plan(calc.slug, e)
        if kind is None:
            self.status.set(note)
            return
        if kind == "keys":
            codes = [calc.resolve(k) for k in what]
            if any(c is None for c in codes):
                self.status.set("No key for %s on the %s" % (e["name"], calc.title))
                return
        else:
            codes, missing = calc.paste_keys(what)
            if missing:
                self.status.set("Can't type %s on the %s: use %s" % (
                    " ".join(sorted(missing)), calc.title, e.get("key") or "the catalog"))
                return
        if not self.m.connected():
            self.status.set("The %s isn't connected" % calc.title)
            return
        if self.m.send_codes(codes, "insert " + e["name"]):
            if kind == "keys" and what[0] == "catalog":
                self.status.set(note)  # Only opened the catalog at its letter
            else:
                self.status.set("Typed %s%s" % (e["name"], ". " + note if note else ""))

    def clip(self, text, what):
        self.frame.clipboard_clear()
        self.frame.clipboard_append(text)
        self.status.set("Copied %s" % what)

    def copy(self):
        """The command as typed on the PC (a program file, the Guide's examples)"""
        if self.item is not None:
            text = self.item.get("pc_spelling") or self.item["name"]
            self.clip(text, text)

    def copy_example(self):
        if self.item is not None and self.item.get("example"):
            self.clip(self.item["example"], "the example")


# ---- Guide: the calculator's guide, rendered ----
class GuideSection(object):
    """The calculator's guide (GUIDES), or the panel's own (panel.guide: (folder, name, PDF),
    the emulator tab's docs/EMULATORS.md)"""

    def __init__(self, panel, parent):
        import mirror as mirror_mod
        self.panel, self.m = panel, panel.m
        self.mirror_mod = mirror_mod
        own = getattr(panel, "guide", None)
        if own:
            self.guide_file, self.pdf = (own[0], own[1]), own[2]
        else:
            self.guide_file, self.pdf = GUIDES[self.m.calc.slug], PDF_GUIDES[self.m.calc.slug]
        self.frame = tk.Frame(parent, bg=th.PANEL)
        top = tk.Frame(self.frame, bg=th.PANEL)
        top.pack(fill="x", pady=(0, 6))
        self.contents = tk.Menubutton(top, text="Contents ▾", bg=th.PANEL2, fg=th.FG,
                                      activebackground=th.ACTIVE, activeforeground="#ffffff",
                                      relief="flat", bd=0, padx=8, pady=4, takefocus=0)
        self.contents.pack(side="left")
        self.search = tk.Entry(top, bg=th.PANEL2, fg=th.FG, insertbackground=th.FG, relief="flat",
                               width=18)
        self.search.pack(side="left", padx=(8, 4), ipady=3)
        self.search.bind("<Return>", lambda e: self.find())
        th.button(top, "Find", self.find, pady=2).pack(side="left")
        th.button(top, "Save as PDF", lambda: save_pdf(
            self.frame, self.pdf, self.note.set), pady=2).pack(side="right")
        self.found = tk.Label(top, text="", bg=th.PANEL, fg=th.DIM)
        self.found.pack(side="left", padx=6)
        mid = tk.Frame(self.frame, bg=th.PANEL)
        mid.pack(fill="both", expand=True)
        self.box = tk.Text(mid, bg=th.BG, fg=th.FG, relief="flat", wrap="word", padx=10, pady=8,
                           highlightthickness=0, bd=0, cursor="arrow", insertwidth=0)
        sb = ttk.Scrollbar(mid, orient="vertical", command=self.box.yview, style="Calc.Vertical.TScrollbar")
        self.box.configure(yscrollcommand=sb.set)
        self.box.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.note = tk.StringVar(master=self.frame, value="")
        tk.Label(self.frame, textvariable=self.note, bg=th.PANEL, fg=th.DIM, anchor="w",
                 justify="left", wraplength=410).pack(fill="x", pady=(6, 0))
        self.last_find = ("", "1.0")
        self.loaded = False

    def shown(self):
        if not self.loaded:
            self.loaded = True
            self.frame.after(10, self.load)

    def load(self):
        folder, name = self.guide_file
        path = self.mirror_mod.resource(folder, name)
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError as e:
            self.note.set("The guide isn't there: %s" % e)
            return
        blocks = md_render.parse(text)
        colors = dict(fg=th.FG, dim=th.DIM, accent=th.ACCENT, code_bg="#121317", link=th.MINT,
                      rule=th.LINE, bg=th.BG)
        fonts = dict(body=(th.FONT, 10), bold=(th.FONT, 10, "bold"), italic=(th.FONT, 10, "italic"),
                     code=(th.MONO, 10), h1=(th.FONT, 16, "bold"), h2=(th.FONT, 13, "bold"),
                     h3=(th.FONT, 11, "bold"))
        self.anchors = md_render.render(self.box, blocks, {"copy": self.copy, "send": self.send},
                                        colors, fonts)
        menu = th.menu(self.contents)
        for level, text_, anchor in md_render.headings(blocks, 3):
            if level == 1:
                continue
            menu.add_command(label=("    " if level == 3 else "") + text_,
                             command=lambda a=anchor: self.box.yview("h_" + a))
        self.contents.configure(menu=menu)
        self.note.set("%s. Examples with a name have Send to calculator." % name if self.m is not None
                      else name)

    def find(self):
        q = self.search.get().strip()
        self.box.tag_remove("found", "1.0", "end")
        if not q:
            self.found.configure(text="")
            return
        start = self.last_find[1] if self.last_find[0] == q else "1.0"
        idx = self.box.search(q, start, nocase=True, stopindex="end")
        if not idx and start != "1.0":
            idx = self.box.search(q, "1.0", nocase=True, stopindex="end")
        if not idx:
            self.found.configure(text="not found")
            return
        end = "%s+%dc" % (idx, len(q))
        self.box.tag_add("found", idx, end)
        self.box.see(idx)
        count = len(self.box.tag_ranges("found"))
        total, pos = 0, "1.0"
        while True:
            pos = self.box.search(q, pos, nocase=True, stopindex="end")
            if not pos:
                break
            total += 1
            pos = "%s+%dc" % (pos, len(q))
        self.found.configure(text="%d found (Enter: next)" % total if count else "")
        self.last_find = (q, end)

    def copy(self, text):
        self.box.clipboard_clear()
        self.box.clipboard_append(text)
        self.note.set("Copied")

    def send(self, name, info, text):
        if self.m is None:
            self.note.set("Copy it instead: this guide isn't for one calculator")
            return
        m, slug = self.m, self.m.calc.slug
        if not m.connected():
            self.note.set("The %s isn't connected" % m.calc.title)
            return
        folder = os.path.join(tempfile.gettempdir(), "calcsuite_guide")
        os.makedirs(folder, exist_ok=True)
        if slug == "nspire":
            path = os.path.join(folder, name + ".py")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text + "\n")
            tns, error = self.mirror_mod.prepare_for_nspire(path)
            if error:
                self.note.set(error)
                return
            self.note.set("Sending %s.tns..." % name)
            m.send_nspire_files([(tns, "/")], lambda ok, msg: self.note.set(
                msg + (". Run it: My Documents > %s, then ctrl+R" % name if ok else "")))
            return
        import send_ti
        path = os.path.join(folder, name + ".txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        self.note.set("Sending %s..." % name)
        send_ti.send_path(m, path, self.mirror_mod.KIT, lambda ok, msg: self.note.set(msg), name=name)


# ---- Get programs ----
class ProgramsSection(object):
    def __init__(self, panel, parent):
        import mirror as mirror_mod
        self.m = panel.m
        self.kit = mirror_mod.KIT
        slug = self.m.calc.slug
        self.items = plib.for_calc(plib.load(), slug)
        self.frame = tk.Frame(parent, bg=th.PANEL)
        tk.Label(self.frame, text="Programs and games by section. Downloads happen only when you "
                 "click, from ticalc.org or GitHub.", bg=th.PANEL, fg=th.DIM, anchor="w",
                 justify="left", wraplength=410).pack(fill="x", pady=(0, 6))
        # Search: filters the list as you type (name, description, section, category, author)
        top = tk.Frame(self.frame, bg=th.PANEL)
        top.pack(fill="x", pady=(0, 6))
        self.query = tk.StringVar(master=self.frame, value="")
        self.count = tk.Label(top, text="", bg=th.PANEL, fg=th.DIM)
        self.count.pack(side="right", padx=(6, 0))
        tk.Label(top, text="Search", bg=th.PANEL, fg=th.DIM).pack(side="left", padx=(0, 6))
        self.search = tk.Entry(top, textvariable=self.query, bg=th.PANEL2, fg=th.FG,
                               insertbackground=th.FG, relief="flat", width=16)
        self.search.pack(side="left", ipady=3, fill="x", expand=True)
        self.search.bind("<Return>", lambda e: self.pick_first())
        self.search.bind("<Down>", lambda e: self.pick_first())
        self.search.bind("<Escape>", lambda e: self.query.set(""))
        mid = tk.Frame(self.frame, bg=th.PANEL)
        mid.pack(fill="both", expand=True)
        tree = self.tree = ttk.Treeview(mid, columns=("cat",), style="Calc.Treeview",
                                        selectmode="browse", height=12)
        tree.heading("#0", text="Program", anchor="w")
        tree.column("#0", width=270, anchor="w")
        tree.heading("cat", text="Category", anchor="w")
        tree.column("cat", width=110, anchor="w")
        sb = ttk.Scrollbar(mid, orient="vertical", command=tree.yview, style="Calc.Vertical.TScrollbar")
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        tree.tag_configure("unverified", foreground=th.DIM)
        tree.tag_configure("section", foreground=th.FG, font=(th.FONT, 10, "bold"))
        self.closed = set()  # Sections the user folded (kept while the search changes)
        tree.bind("<<TreeviewOpen>>", lambda e: self.folded(False))
        tree.bind("<<TreeviewClose>>", lambda e: self.folded(True))
        tree.bind("<<TreeviewSelect>>", lambda e: self.picked())
        tree.bind("<Double-1>", self.double)  # Double click: the same as its button (get it)
        tree.bind("<Return>", lambda e: self.act_on() if self.item and not self.busy else None)
        box = tk.Frame(self.frame, bg=th.BG)  # The description and its scrollbar
        box.pack(fill="x", pady=(8, 0))
        self.detail = tk.Text(box, bg=th.BG, fg=th.FG, relief="flat", wrap="word", height=11,
                              padx=8, pady=6, highlightthickness=0, bd=0, font=th.BODY)
        dsb = ttk.Scrollbar(box, orient="vertical", command=self.detail.yview,
                            style="Calc.Vertical.TScrollbar")
        self.detail.configure(yscrollcommand=dsb.set)
        dsb.pack(side="right", fill="y")
        self.detail.pack(side="left", fill="both", expand=True)
        self.detail.tag_configure("b", font=(th.FONT, 10, "bold"))
        self.detail.tag_configure("dim", foreground=th.DIM)
        self.detail.tag_configure("warn", foreground=th.WARN)
        self.detail.tag_configure("link", foreground=th.MINT, underline=True)
        self.detail.tag_configure("hint", foreground=th.DIM, font=(th.FONT, 10), spacing1=4)
        self.show_hint()
        bar = tk.Frame(self.frame, bg=th.PANEL)
        bar.pack(fill="x", pady=(6, 0))
        self.act = th.button(bar, "Download and send", self.act_on, state="disabled")
        self.act.pack(side="left")
        self.info_btn = th.button(bar, "Info page", self.open_info, state="disabled")
        self.info_btn.pack(side="left", padx=(6, 0))
        th.button(bar, "Get all...", self.get_all).pack(side="right")
        self.all_dialog = None
        games = sum(1 for i in self.items if plib.section_of(i) == "Games")
        self.status = tk.StringVar(master=self.frame, value="%d programs and %d games for the %s" % (
            len(self.items) - games, games, self.m.calc.title))
        tk.Label(self.frame, textvariable=self.status, bg=th.PANEL, fg=th.DIM, anchor="w",
                 justify="left", wraplength=410).pack(fill="x", pady=(6, 0))
        self.item = None
        self.busy = False
        self.query.trace_add("write", lambda *a: self.refresh())
        self.refresh()

    def refresh(self):
        """The list again for what's typed: a row per section (open or folded), its items under it"""
        tree = self.tree
        keep = self.item
        tree.delete(*tree.get_children())
        q = self.query.get().strip()
        shown = plib.search(self.items, q)
        for section, items in plib.by_section(shown):
            sid = "s:" + section
            tree.insert("", "end", iid=sid, text="%s (%d)" % (section, len(items)), values=("",),
                        open=bool(q) or section not in self.closed, tags=("section",))
            for i in items:
                name = i["name"] + ("" if i.get("verified") else "  (unverified)")
                tree.insert(sid, "end", iid=str(self.items.index(i)), text=name,
                            values=(i.get("category", ""),),
                            tags=(() if i.get("verified") else ("unverified",)))
        self.count.configure(text=("%d found" % len(shown)) if q else "")
        if keep is not None and keep in shown:
            iid = str(self.items.index(keep))
            tree.selection_set(iid)
            tree.see(iid)
            return
        self.item = None  # What was picked is filtered out: nothing picked
        self.act.configure(state="disabled")
        self.info_btn.configure(state="disabled")
        if q and not shown:
            self.show_hint('Nothing matches "%s". Try a shorter word, or a section name (Games, '
                           'Electrical, Chemistry...).' % q)
        else:
            self.show_hint()

    def folded(self, closed):
        """A section row was folded or opened: remembered (while no search is typed)"""
        iid = self.tree.focus()
        if iid.startswith("s:") and not self.query.get().strip():
            (self.closed.add if closed else self.closed.discard)(iid[2:])

    def pick_first(self):
        """Enter or Down in the search box: the first program shown"""
        for sid in self.tree.get_children():
            kids = self.tree.get_children(sid)
            if kids:
                self.tree.item(sid, open=True)
                self.tree.focus_set()
                self.tree.selection_set(kids[0])
                self.tree.focus(kids[0])
                self.tree.see(kids[0])
                break
        return "break"

    def shown(self):
        self.search.focus_set()

    def double(self, ev):
        row = self.tree.identify_row(ev.y)
        if not row or self.busy:
            return "break"
        if row.startswith("s:"):  # A section: fold or open it, like its arrow
            now_open = not self.tree.item(row, "open")
            self.tree.item(row, open=now_open)
            self.tree.focus(row)
            self.folded(not now_open)
            return "break"
        self.tree.selection_set(row)
        self.picked()
        self.act_on()
        return "break"

    def show_hint(self, text=None):
        """What the description box says while no program is picked"""
        d = self.detail
        d.configure(state="normal")
        d.delete("1.0", "end")
        d.insert("end", text or "Pick a program in the list to see what it does, who made it, its "
                 "licence and how it gets onto the calculator. Type in the box above to search.\n\n"
                 "Double-click it (or the button below) to download it and send it, or to open its "
                 "page when CalcSuite can't send it itself. Get all... lists every program CalcSuite "
                 "can send at once (games go one by one, from the list).", "hint")
        d.configure(state="disabled")

    def picked(self):
        sel = self.tree.selection()
        if not sel or sel[0].startswith("s:"):  # Nothing, or a section's row
            self.item = None
            self.act.configure(state="disabled")
            self.info_btn.configure(state="disabled")
            self.show_hint("%s: %d. Pick one to see what it does; double-click the section to fold "
                           "it." % (sel[0][2:], len(self.tree.get_children(sel[0]))) if sel else None)
            return
        i = self.item = self.items[int(sel[0])]
        d = self.detail
        d.configure(state="normal")
        d.delete("1.0", "end")
        d.insert("end", i["name"] + "\n", "b")
        d.insert("end", (i.get("description") or "") + "\n")
        d.insert("end", "%s  ·  %s  ·  by %s  ·  licence: %s\n" % (
            plib.section_of(i), i.get("category", ""), i.get("author") or "not checked",
            i.get("license") or "not stated"), "dim")
        if i.get("os_notes"):
            d.insert("end", "Runs on: %s\n" % i["os_notes"], "dim")
        d.insert("end", "Source: %s%s\n" % (i.get("source_site") or "", "" if i.get("verified")
                                             else "  (unverified: from a directory listing)"), "dim")
        flag, note = plib.needs_old_os(i, self.m.calc.slug, self.m.info.get("os"))
        if note:
            d.insert("end", note + "\n", "warn" if flag or flag is None else "dim")
        if i.get("dependencies"):
            d.insert("end", "Needs: %s\n" % ", ".join(i["dependencies"]), "warn")
        if i.get("special_handling"):
            d.insert("end", "Note: %s\n" % i["special_handling"], "dim")
        if i.get("action") == "ti_page":
            d.insert("end", "TI's own app: TI's page has its licence; download it there and send "
                     "it with Files > Upload. CalcSuite never downloads TI files.\n", "dim")
        elif i.get("action") == "page":
            d.insert("end", "Opens its page: CalcSuite can't send this one itself (an app, or an "
                     "install with steps on the calculator).\n", "dim")
        d.configure(state="disabled")
        self.act.configure(text=plib.action_text(i), state="normal" if not self.busy else "disabled")
        self.info_btn.configure(state="normal" if i.get("info_url") else "disabled")

    def open_info(self):
        if self.item and self.item.get("info_url"):
            webbrowser.open(self.item["info_url"])

    def get_all(self):
        d = self.all_dialog
        if d is not None and d.alive():
            d.win.lift()
            return
        self.all_dialog = GetAllDialog(self)

    def act_on(self):
        i = self.item
        if i is None:
            return
        if i.get("action") == "ti_page":
            if messagebox.askokcancel("TI's page", "TI's own apps come with TI's licence, which "
                                      "you accept on TI's page when you download. Open it in your "
                                      "browser?", parent=self.frame):
                webbrowser.open(i.get("info_url") or "https://education.ti.com/en/software/search")
            return
        if i.get("action") != "download":
            webbrowser.open(i.get("info_url") or i.get("download_url"))
            return
        if not self.m.connected():
            self.status.set("The %s isn't connected" % self.m.calc.title)
            return
        flag, note = plib.needs_old_os(i, self.m.calc.slug, self.m.info.get("os"))
        if flag and not messagebox.askyesno("Assembly program", note + "\n\nSend it anyway?",
                                            icon="warning", parent=self.frame):
            return
        self.busy = True
        self.act.configure(state="disabled")
        self.status.set("Downloading %s..." % i["name"])

        def progress(done, total):
            self.say("Downloading %s: %s%s" % (i["name"], human(done),
                                                " of %s" % human(total) if total else ""))

        def work():
            try:
                path = plib.download(i["download_url"], progress)
                files = plib.pick_files(path, i)
            except Exception as e:
                alt = i.get("alt_download_url")
                try:
                    if not alt:
                        raise
                    path = plib.download(alt, progress)
                    files = plib.pick_files(path, i)
                except Exception:
                    self.ui(self.done, False, "Couldn't get it: %s" % e)
                    return
            out = os.path.join(plib.CACHE, "files", i["id"])
            os.makedirs(out, exist_ok=True)
            local = []
            for name, data, folder in files:
                p = os.path.join(out, name)
                with open(p, "wb") as f:
                    f.write(data)
                local.append((p, folder))
            self.ui(self.send_files, local)
        threading.Thread(target=work, daemon=True).start()

    def say(self, text):
        self.ui(self.status.set, text)

    def ui(self, fn, *args):
        try:
            self.frame.after(0, lambda: fn(*args))
        except (tk.TclError, RuntimeError):
            pass

    def send_files(self, local):
        m = self.m
        names = ", ".join(os.path.basename(p) for p, _f in local[:4])
        more = " and %d more" % (len(local) - 4) if len(local) > 4 else ""
        if not messagebox.askyesno("Send to the %s?" % m.calc.title, "Send %s%s to the %s?%s" % (
                names, more, m.calc.title, "\n\nNspire: into %s" % ", ".join(sorted(set(f or "/" for _p, f in local)))
                if m.calc.slug == "nspire" else ""), parent=self.frame):
            self.done(False, "Downloaded, not sent (it's kept in %s)" % plib.CACHE)
            return
        self.status.set("Sending %d file(s)..." % len(local))
        if m.calc.slug == "nspire":
            m.send_nspire_files([(p, f or "/") for p, f in local],
                                lambda ok, msg: self.done(ok, msg + (self.after_note() if ok else "")))
            return
        import send_ti
        prepared = []
        for p, _f in local:
            try:
                prepared.append(send_ti.prepare(p, m.calc.slug))
            except (OSError, ValueError) as e:
                self.done(False, "%s can't be sent: %s" % (os.path.basename(p), e))
                return
        send_ti.send_prepared(m, prepared, lambda ok, msg: self.done(ok, msg + (self.after_note() if ok else "")))

    def after_note(self):
        sh = (self.item or {}).get("special_handling") or ""
        if "MyLib" in sh or "Refresh Libraries" in sh:
            return ". Library: on the handheld, doc > Refresh Libraries (or restart it)"
        if "install()" in sh:
            return ". Then run install() on the 89"
        return ""

    def done(self, ok, msg):
        self.busy = False
        self.status.set(msg)
        if self.item is not None:
            self.act.configure(state="normal")


def open_bundled_pdf(name, widget=None):
    """Opens one of the bundled PDFs (docs/pdf/) in the PC's PDF viewer"""
    import mirror as mirror_mod
    src = mirror_mod.resource("docs", "pdf", name)
    try:
        os.startfile(src)
    except (OSError, AttributeError) as e:
        log_error("opening %s" % name)
        if widget is not None:
            messagebox.showinfo("CalcSuite", "The guide couldn't be opened: %s" % short_error(e),
                                parent=widget.winfo_toplevel())


def save_pdf(widget, name, say):
    """Save as PDF (Guide, Functions): copies the bundled PDF (docs/pdf/) to a folder the user
    picks, CalcSuite files by default, and offers to open it"""
    import shutil
    import mirror as mirror_mod
    src = mirror_mod.resource("docs", "pdf", name)
    if not os.path.isfile(src):
        say("The PDF isn't there (%s). Build it: python tools/docs_build/make_pdfs.py" % name)
        return
    import paths
    start = paths.files_dir()
    try:
        os.makedirs(start, exist_ok=True)
    except OSError:
        start = os.path.expanduser("~")
    folder = filedialog.askdirectory(parent=widget.winfo_toplevel(), title="Save %s in which folder?"
                                     % name, initialdir=start, mustexist=False)
    if not folder:
        return
    dest = os.path.join(os.path.normpath(folder), name)
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(src, dest)
    except OSError as e:
        say("Couldn't save the PDF: %s" % short_error(e))
        return
    say("Saved %s" % dest)
    if messagebox.askyesno("Save as PDF", "Saved:\n%s\n\nOpen it now?" % dest,
                           parent=widget.winfo_toplevel()):
        try:
            os.startfile(dest)
        except OSError as e:
            say("Saved, but it didn't open: %s" % short_error(e))


def human(n):
    for unit in ("B", "KB", "MB"):
        if n < 1024 or unit == "MB":
            return ("%d %s" % (n, unit)) if unit == "B" else "%.1f %s" % (n, unit)
        n /= 1024.0


def on_tk(widget, fn, *args):
    """fn(*args) on Tk's thread, from a worker (nothing when the window has gone)"""
    try:
        widget.after(0, lambda: fn(*args))
    except (tk.TclError, RuntimeError):
        pass


def ask_on_tk(widget, fn, alive=lambda: True):
    """fn() on Tk's thread (a question), waited for from a worker: its answer, or None"""
    box, ev = {}, threading.Event()

    def run():
        try:
            box["r"] = fn()
        finally:
            ev.set()
    on_tk(widget, run)
    while not ev.wait(0.2):
        if not alive():
            return None
    return box.get("r")


def short_error(e):
    text = str(e) or e.__class__.__name__
    return text if len(text) < 90 else text[:87] + "..."


def progress_style(widget, done=False):
    """The progress bars' style: the accent colour, running and done"""
    style = ttk.Style(widget)
    name, colour = ("CalcDone.Horizontal.TProgressbar", th.ACCENT) if done else \
        ("Calc.Horizontal.TProgressbar", th.ACCENT)
    style.configure(name, background=colour, troughcolor=th.PANEL2, bordercolor=th.PANEL,
                    lightcolor=colour, darkcolor=colour)
    return name


GET_ALL_LIMIT = None  # Test hook: only the first n items in Get all (or CALCSUITE_GET_ALL_LIMIT=n)


class GetAllDialog(object):
    """Get programs > Get all: every item CalcSuite can send by itself, with its size, notes and
    whether it's on the calculator already, then Send all to the calculator or Save all to the
    PC. Downloads go one at a time (into the cache) on a worker thread; the calculator is only
    reached through the tab's link thread (run_batch)."""

    COLS = (("size", "Size", 70), ("notes", "Notes", 250), ("calc", "On the calculator", 110),
            ("state", "", 150))

    def __init__(self, section):
        self.sec, self.m = section, section.m
        self.slug, self.title = self.m.calc.slug, self.m.calc.title
        items, self.skipped = plib.get_all_plan(plib.load(), self.slug)
        limit = GET_ALL_LIMIT or os.environ.get("CALCSUITE_GET_ALL_LIMIT")
        if limit:
            items = items[:int(limit)]
        self.items = items
        self.ids = {i["id"] for i in items}
        self.rows = {i["id"]: {"files": None, "size": plib.size_hint(i), "measured": False, "ram": 0,
                               "archive": 0, "error": None, "on_calc": None, "clash": set(),
                               "state": ""} for i in items}
        self.missing_folders = set()  # Nspire folders the handheld doesn't have yet
        self.stop = threading.Event()
        self.busy = "measure"
        # A tab of the main window (a window of its own without it)
        w = self.win = tool_tabs.window(section.frame, "getall:%s" % self.slug, "Get all (%s)" % self.title)
        w.title("Get all for the %s" % self.title)
        w.configure(bg=th.BG)
        w.geometry("860x620")
        w.minsize(660, 440)
        w.protocol("WM_DELETE_WINDOW", self.close)
        self.gone = False
        w.bind("<Destroy>", self.destroyed, add="+")
        tk.Label(w, text="%d programs for the %s that CalcSuite can send by itself. They download "
                 "one at a time from ticalc.org and GitHub, into CalcSuite's cache (a download is "
                 "never repeated)." % (len(items), self.title), bg=th.BG, fg=th.FG, anchor="w",
                 justify="left", wraplength=820).pack(fill="x", padx=12, pady=(12, 6))
        mid = tk.Frame(w, bg=th.BG)
        mid.pack(fill="both", expand=True, padx=12)
        tree = self.tree = ttk.Treeview(mid, columns=[c for c, _t, _w in self.COLS],
                                        style="Calc.Treeview", selectmode="none")
        tree.heading("#0", text="Program", anchor="w")
        tree.column("#0", width=230, anchor="w")
        for c, text, width in self.COLS:
            tree.heading(c, text=text, anchor="w")
            tree.column(c, width=width, anchor="w", stretch=c in ("notes", "state"))
        sb = ttk.Scrollbar(mid, orient="vertical", command=tree.yview, style="Calc.Vertical.TScrollbar")
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        tree.tag_configure("warn", foreground=th.WARN)
        tree.tag_configure("ok", foreground=th.FG)
        tree.tag_configure("bad", foreground=th.RED)
        for i in items:
            tree.insert("", "end", iid=i["id"], text=i["name"])
            self.draw_row(i)
        self.fit = tk.Label(w, text="", bg=th.BG, fg=th.DIM, anchor="w", justify="left", wraplength=820)
        self.fit.pack(fill="x", padx=12, pady=(8, 0))
        if self.skipped:
            names = ", ".join(i["name"] for i, _r in self.skipped)
            tk.Label(w, text="Not in this set (%d): %s. They open their page instead (TI's own "
                     "apps, Flash apps, installs with steps on the calculator): pick them in the "
                     "list." % (len(self.skipped), names), bg=th.BG, fg=th.DIM, anchor="w",
                     justify="left", wraplength=820).pack(fill="x", padx=12, pady=(4, 0))
        self.bar = ttk.Progressbar(w, style=progress_style(w), mode="determinate", maximum=max(len(items), 1))
        self.bar.pack(fill="x", padx=12, pady=(8, 0))
        self.status = tk.StringVar(master=w, value="")
        tk.Label(w, textvariable=self.status, bg=th.BG, fg=th.DIM, anchor="w", justify="left",
                 wraplength=820).pack(fill="x", padx=12, pady=(4, 0))
        row = tk.Frame(w, bg=th.BG)
        row.pack(fill="x", padx=12, pady=10)
        self.send_btn = th.button(row, "Send all to the %s" % self.title, self.send_all, state="disabled")
        self.send_btn.pack(side="left")
        self.save_btn = th.button(row, "Save all to the PC...", self.save_all, state="disabled")
        self.save_btn.pack(side="left", padx=(6, 0))
        self.stop_btn = th.button(row, "Stop", self.stop_now)
        self.stop_btn.pack(side="left", padx=(6, 0))
        th.button(row, "Close", self.close).pack(side="right")
        self.work(self.measure_work)

    # ---- Plumbing ----
    def alive(self):
        """Whether the window is still open (a flag: safe from a worker thread)"""
        return not self.gone

    def destroyed(self, ev):
        if ev.widget is self.win:
            self.gone = True

    def ui(self, fn, *args):
        if self.alive():
            on_tk(self.win, fn, *args)

    def say(self, text):
        self.ui(self.status.set, text)

    def ask(self, fn):
        return ask_on_tk(self.win, fn, self.alive)

    def work(self, fn, *args):
        self.stop.clear()

        def run():
            try:
                fn(*args)
            except Exception as e:  # Never leave the dialog stuck as busy
                self.say("Stopped: %s" % short_error(e))
            finally:
                self.ui(self.idle)
        threading.Thread(target=run, daemon=True).start()

    def idle(self):
        self.busy = None
        self.send_btn.configure(state="normal")
        self.save_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.show_fit()

    def start(self, what):
        self.busy = what
        self.send_btn.configure(state="disabled")
        self.save_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")

    def stop_now(self):
        if self.busy:
            self.stop.set()
            self.say("Stopping after this item...")

    def close(self):
        self.stop.set()
        try:
            self.win.destroy()
        except tk.TclError:
            pass

    def set_bar(self, done, total):
        self.bar.configure(maximum=max(total, 1), value=done)

    # ---- The list ----
    def draw_row(self, i):
        if not self.alive():
            return
        r = self.rows[i["id"]]
        if r["measured"]:
            size = human(r["size"])
        elif r["size"]:
            size = "~" + human(r["size"])
        else:
            size = "?"
        flags = plib.item_flags(i, self.slug, self.m.info.get("os"), r["size"], self.ids)
        notes = "; ".join(t for _l, t in flags)
        if r["error"]:
            notes = "couldn't get it: %s" % r["error"] + ("; " + notes if notes else "")
        calc = {None: "", "no": "no", "yes": "yes", "some": "some files"}[r["on_calc"]]
        tag = ("bad",) if r["error"] or r["state"].startswith("failed") else (
            ("ok",) if r["state"].startswith(("sent", "saved")) else
            ("warn",) if any(l == "warn" for l, _t in flags) or r["on_calc"] in ("yes", "some") else ())
        self.tree.item(i["id"], values=(size, notes, calc, r["state"]), tags=tag)

    def set_state(self, i, state):
        self.rows[i["id"]]["state"] = state
        self.ui(self.draw_row, i)

    def totals(self):
        ram = sum(r["ram"] for r in self.rows.values())
        arc = sum(r["archive"] for r in self.rows.values())
        unknown = [i["name"] for i in self.items if not self.rows[i["id"]]["measured"]]
        return ram, arc, unknown

    def show_fit(self):
        if not self.alive():
            return
        ram, arc, unknown = self.totals()
        if not self.m.connected() and not self.m.info:
            self.fit.configure(text="%s in all. Connect the %s to compare with its free space." % (
                human(ram + arc), self.title), fg=th.DIM)
            return
        ok, text = plib.fit_check(ram, arc, self.m.info, self.slug)
        if unknown:
            text += " (%d not measured: %s)" % (len(unknown), ", ".join(unknown[:4]))
        lead = {True: "Fits. ", False: "Doesn't fit. ", None: ""}[ok]
        self.fit.configure(text=lead + text, fg=th.FG if ok else th.WARN)

    def set_files(self, i, files):
        r = self.rows[i["id"]]
        ram = arc = 0
        for _n, data, _f in files:
            where, n = plib.file_place(data, self.slug)
            if where == "ram":
                ram += n
            else:
                arc += n
        r.update(files=files, size=ram + arc, ram=ram, archive=arc, measured=True, error=None)

    def get_files(self, i, k, n, verb):
        """The item's files (cached, or downloaded now): None when they can't be had"""
        r = self.rows[i["id"]]
        if r["files"] is not None:
            return r["files"]
        files = plib.cached_files(i)
        if files is None:
            self.say("%s %d of %d: downloading %s..." % (verb, k + 1, n, i["name"]))

            def progress(done, total):
                self.say("%s %d of %d: downloading %s, %s%s" % (verb, k + 1, n, i["name"], human(done),
                                                                " of %s" % human(total) if total else ""))
            try:
                files = plib.fetch_files(i, progress)
            except Exception as e:
                r["error"] = short_error(e)
                self.ui(self.draw_row, i)
                return None
        self.set_files(i, files)
        self.ui(self.draw_row, i)
        return files

    def measure_work(self):
        n = len(self.items)
        for k, i in enumerate(self.items):
            if self.stop.is_set():
                self.say("Stopped: some sizes aren't known yet (they download when you send or save)")
                return
            self.get_files(i, k, n, "Measuring")
            self.ui(self.set_bar, k + 1, n)
        else:
            self.say("Sizes measured.")
        if self.m.connected():
            self.say("Checking what's on the %s..." % self.title)
            if self.list_calc():
                self.say("Ready. Send all to the %s, or Save all to the PC." % self.title)
            else:
                self.say("Couldn't read the %s's list: it's checked again when you send." % self.title)
        else:
            self.say("Ready. The %s isn't connected: Save all to the PC works without it." % self.title)

    def list_calc(self):
        """Marks what's on the calculator already (worker thread). False when it can't tell."""
        import calc_files as cf
        if self.slug == "nspire":
            import calc_manager
            folders = sorted({f or "/" for r in self.rows.values() for _n, _d, f in (r["files"] or [])})
            listing = {}
            self.missing_folders = set()
            for folder in folders:
                code, lines = self.m.run_batch([("ls " + folder, None)])[0]
                if code and not self.m.connected():
                    return False
                if code:
                    self.missing_folders.add(folder)
                listing[folder] = {calc_manager.shown(e["name"]).lower()
                                   for e in cf.parse_nspire_ls(lines)} if code == 0 else set()
            for i in self.items:
                r = self.rows[i["id"]]
                if r["files"] is not None:
                    r["clash"] = set(plib.nspire_clashes([(nm, f) for nm, _d, f in r["files"]], listing))
                    r["on_calc"] = self.on_calc_word(r)
                    self.ui(self.draw_row, i)
            return True
        import send_ti
        code, lines = self.m.run_batch([("ls", None)])[0]
        if code:
            return False
        for i in self.items:
            r = self.rows[i["id"]]
            if r["files"] is None:
                continue
            r["clash"] = set()
            for nm, data, _f in r["files"]:
                try:
                    if send_ti.clashes(send_ti.variables(data, self.slug), lines, self.slug):
                        r["clash"].add(nm)
                except ValueError:
                    pass
            r["on_calc"] = self.on_calc_word(r)
            self.ui(self.draw_row, i)
        return True

    @staticmethod
    def on_calc_word(r):
        if not r["clash"]:
            return "no"
        return "yes" if len(r["clash"]) == len(r["files"]) else "some"

    # ---- Send all ----
    def send_all(self):
        if self.busy:
            return
        if not self.m.connected():
            self.status.set("The %s isn't connected. Save all to the PC works without it." % self.title)
            return
        self.start("send")
        self.work(self.send_work)

    def send_work(self):
        n = len(self.items)
        for k, i in enumerate(self.items):  # Anything not measured yet downloads first
            if self.stop.is_set():
                self.say("Stopped before sending: nothing was sent")
                return
            self.get_files(i, k, n, "Getting")
        self.say("Checking what's on the %s..." % self.title)
        if not self.list_calc():
            self.say("Not sent: couldn't read the %s's list" % self.title)
            return
        ready = [i for i in self.items if self.rows[i["id"]]["files"]]
        if not ready:
            self.say("Nothing to send: no download worked")
            return
        osv = self.m.info.get("os")
        asm = [i for i in ready if plib.needs_old_os(i, self.slug, osv)[0] is True]
        clash = [i for i in ready if self.rows[i["id"]]["clash"]]
        ram, arc, _u = self.totals()
        ok, fit = plib.fit_check(ram, arc, self.m.info, self.slug)
        files = sum(len(self.rows[i["id"]]["files"]) for i in ready)
        msg = "Send %d programs (%d files) to the %s?\n\n%s%s" % (
            len(ready), files, self.title, fit,
            "\n\nIt doesn't look like it fits: whatever doesn't fit fails and the rest is sent."
            if ok is False else "")
        if not self.ask(lambda: messagebox.askokcancel("Send all?", msg, parent=self.win)):
            self.say("Not sent")
            return
        skip_items = set()
        if asm:
            a = self.ask(lambda: messagebox.askyesnocancel(
                "Assembly programs", "%d of them are assembly programs, which OS %s doesn't run "
                "without arTIfiCE: %s.\n\nYes: send them too (they run once arTIfiCE is on).\nNo: "
                "leave them out.\nCancel: send nothing." % (
                    len(asm), osv, ", ".join(i["name"] for i in asm[:8])), icon="warning", parent=self.win))
            if a is None:
                self.say("Not sent")
                return
            if a is False:
                skip_items |= {i["id"] for i in asm}
        replace = False
        clash = [i for i in clash if i["id"] not in skip_items]
        if clash:
            names = sorted({nm for i in clash for nm in self.rows[i["id"]]["clash"]})
            a = self.ask(lambda: messagebox.askyesnocancel(
                "Already on the %s" % self.title, "%d file(s) are on the %s already: %s%s.\n\n"
                "Yes: replace them all.\nNo: skip those (the calculator keeps its own).\nCancel: "
                "send nothing." % (len(names), self.title, ", ".join(names[:12]),
                                   " and %d more" % (len(names) - 12) if len(names) > 12 else ""),
                icon="warning", parent=self.win))
            if a is None:
                self.say("Not sent")
                return
            replace = bool(a)
        self.send_items(ready, skip_items, replace)

    def send_items(self, ready, skip_items, replace):
        summary = {"sent": [], "partly": [], "failed": [], "skipped": []}
        reached = []  # The items that got at least one file there
        made = set()
        total = len(ready)
        for k, i in enumerate(ready):
            r = self.rows[i["id"]]
            if self.stop.is_set():
                self.set_state(i, "not sent (stopped)")
                summary["skipped"].append(i["name"])
                continue
            if i["id"] in skip_items:
                self.set_state(i, "not sent (assembly)")
                summary["skipped"].append(i["name"])
                continue
            if not self.m.connected():
                self.set_state(i, "failed: not connected")
                summary["failed"].append("%s: not connected" % i["name"])
                continue
            out = os.path.join(plib.CACHE, "files", i["id"])
            os.makedirs(out, exist_ok=True)
            sent, errors, kept = 0, [], 0
            for nm, data, folder in r["files"]:
                if nm in r["clash"] and not replace:
                    kept += 1
                    continue
                path = os.path.join(out, nm)
                with open(path, "wb") as f:
                    f.write(data)
                self.set_state(i, "sending %s..." % nm)

                def progress(done, size, nm=nm, k=k):
                    self.say("Sending %d of %d: %s, %d%%" % (k + 1, total, nm,
                                                            100 * done // size if size else 0))
                if self.slug == "nspire":
                    folder = folder or "/"
                    if folder in self.missing_folders and folder not in made:
                        self.m.run_batch([("mkdir " + folder, None)])
                        made.add(folder)
                    line = "put %s|%s" % (os.path.abspath(path), folder.rstrip("/") + "/" + nm)
                else:
                    line = "send " + os.path.abspath(path)
                code, lines = self.m.run_batch([(line, progress)], timeout=600)[0]
                if code == 0:
                    sent += 1
                else:
                    err = [l for l in lines if l.startswith("ERR")]
                    errors.append("%s: %s" % (nm, err[-1][4:] if err else "exit %d" % code))
            if errors:
                self.set_state(i, "failed: " + errors[0])
                (summary["partly"] if sent else summary["failed"]).append("%s (%s)" % (i["name"], errors[0]))
                if sent:
                    reached.append(i)
            elif sent:
                self.set_state(i, "sent" + (" (%d kept)" % kept if kept else ""))
                summary["sent"].append(i["name"])
                reached.append(i)
            else:
                self.set_state(i, "not sent (already there)")
                summary["skipped"].append(i["name"])
            self.ui(self.set_bar, k + 1, total)
        after = sorted({"%s: %s" % (i["name"], t) for i in reached
                        for _l, t in plib.item_flags(i, self.slug, self.m.info.get("os"), ids=self.ids)
                        if "afterwards" in t or "to install" in t})
        text = "Sent %d of %d programs to the %s." % (len(summary["sent"]), total, self.title)
        if summary["partly"]:
            text += "\n\nPartly sent: " + "; ".join(summary["partly"][:6])
        if summary["failed"]:
            text += "\n\nNot sent: " + "; ".join(summary["failed"][:6])
        if summary["skipped"]:
            text += "\n\nLeft out: " + ", ".join(summary["skipped"][:10])
        if after:
            text += "\n\nThen:\n" + "\n".join(after[:10])
        self.say(text.split("\n")[0])
        self.ui(lambda: messagebox.showinfo("Send all", text, parent=self.win) if self.alive() else None)
        if self.m.manager is not None:
            self.ui(self.m.manager.refresh)

    # ---- Save all to the PC ----
    def save_all(self):
        if self.busy:
            return
        start = plib.default_save_folder()
        try:
            os.makedirs(start, exist_ok=True)
        except OSError:
            start = os.path.expanduser("~")
        folder = filedialog.askdirectory(parent=self.win, title="Save all into which folder?",
                                         initialdir=start, mustexist=False)
        if not folder:
            return
        self.start("save")
        self.work(self.save_work, os.path.normpath(folder))

    def save_work(self, folder):
        import calc_manager
        n = len(self.items)
        saved, same, failed, files_written = [], 0, [], 0
        for k, i in enumerate(self.items):
            if self.stop.is_set():
                self.set_state(i, "not saved (stopped)")
                continue
            files = self.get_files(i, k, n, "Saving")
            if files is None:
                self.set_state(i, "failed: " + (self.rows[i["id"]]["error"] or "no download"))
                failed.append(i["name"])
                continue
            dest = os.path.join(folder, plib.save_dir_name(i))
            try:
                for nm, data, sub in files:
                    where = dest if not sub or sub == "/" else os.path.join(dest, *sub.strip("/").split("/"))
                    os.makedirs(where, exist_ok=True)
                    path = os.path.join(where, nm)
                    if os.path.isfile(path):
                        with open(path, "rb") as f:
                            if f.read() == data:
                                same += 1
                                continue
                        path = calc_manager.unique_path(where, nm)  # Never over a different file
                    with open(path, "wb") as f:
                        f.write(data)
                    files_written += 1
            except OSError as e:
                self.set_state(i, "failed: " + short_error(e))
                failed.append(i["name"])
                continue
            self.set_state(i, "saved (%d file%s)" % (len(files), "" if len(files) == 1 else "s"))
            saved.append(i["name"])
            self.ui(self.set_bar, k + 1, n)
        text = "Saved %d of %d programs in %s (%d new files%s)." % (
            len(saved), n, folder, files_written, ", %d already there" % same if same else "")
        if failed:
            text += "\n\nNot saved: " + ", ".join(failed[:10])
        self.say(text.split("\n")[0])

        def done():
            if self.alive() and messagebox.askyesno("Save all", text + "\n\nOpen the folder?", parent=self.win):
                try:
                    os.startfile(folder)
                except (OSError, AttributeError):
                    pass
        self.ui(done)


# ---- Calculator info: About, the clock, Press-to-Test, the connection doctor ----
class InfoSection(object):
    def __init__(self, panel, parent):
        import mirror as mirror_mod
        self.panel, self.m = panel, panel.m
        self.mirror_mod = mirror_mod
        self.frame = tk.Frame(parent, bg=th.PANEL)
        outer, inner = scrolled(self.frame)
        outer.pack(fill="both", expand=True)
        self.inner = inner
        heading(inner, "This calculator")
        self.about = tk.Frame(inner, bg=th.BG)
        self.about.pack(fill="x")
        row = tk.Frame(inner, bg=th.PANEL)
        row.pack(fill="x", pady=(8, 0))
        th.button(row, "Refresh", self.refresh_about).pack(side="left")
        th.button(row, "Reconnect", self.m.reconnect).pack(side="left", padx=(6, 0))
        heading(inner, "PC copy")
        self.pcc = tk.Frame(inner, bg=th.PANEL)
        self.pcc.pack(fill="x")
        self.pc_dialog = None
        self.build_pc_copy()
        heading(inner, "Connection doctor")
        self.doctor = tk.Frame(inner, bg=th.PANEL)
        self.doctor.pack(fill="x")
        th.button(inner, "Check again", self.check).pack(anchor="w", pady=(6, 0))
        heading(inner, "CalcSuite")
        ver = tk.Label(inner, text="Version %s: what's new and newer versions" % mirror_mod.APP_VERSION,
                       bg=th.PANEL, fg=th.MINT, cursor="hand2", font=(th.FONT, 10, "underline"))
        ver.pack(anchor="w")
        ver.bind("<Button-1>", lambda e: webbrowser.open(
            "https://github.com/paul-kratky/CalcSuite/releases"))
        if mirror_mod.SPONSOR_URL:
            a = tk.Label(inner, text="Support CalcSuite", bg=th.PANEL, fg=th.MINT, cursor="hand2",
                         font=(th.FONT, 10, "underline"))
            a.pack(anchor="w")
            a.bind("<Button-1>", lambda e: webbrowser.open(mirror_mod.SPONSOR_URL))
        self.inner_wheel = inner
        self.built = False

    def shown(self):
        if not self.built:
            self.built = True
            self.refresh_about()
            self.check()

    def manager(self):
        m = self.m
        if "Files" not in self.panel.sections:  # Builds the manager (its file list, not shown)
            self.panel.sections["Files"] = FilesSection(self.panel, self.panel.body)
        return m.manager

    def refresh_about(self):
        mgr = self.manager()
        mgr.build_about(self.about)

    # ---- PC copy (tools/pc_copy.py; docs/dev/PC_COPY_API.md) ----
    def build_pc_copy(self):
        for c in self.pcc.winfo_children():
            c.destroy()
        slug = self.m.calc.slug
        if slug not in PC_COPY:
            tk.Label(self.pcc, text="Not for the Nspire: reading its ROM needs Ndless on the "
                     "handheld, which CalcSuite doesn't install.", bg=th.PANEL, fg=th.DIM,
                     anchor="w", justify="left", wraplength=400).pack(fill="x")
            return
        tk.Label(self.pcc, text="A copy of this calculator that runs on the PC, in %s, made from "
                 "its own ROM." % PC_COPY[slug]["emulator"], bg=th.PANEL, fg=th.FG, anchor="w",
                 justify="left", wraplength=400).pack(fill="x")
        row = tk.Frame(self.pcc, bg=th.PANEL)
        row.pack(fill="x", pady=(6, 0))
        th.button(row, "Make a PC copy...", lambda: self.pc_copy("make")).pack(side="left")
        roms = existing_roms(slug)
        if roms:
            th.button(row, "Open my PC copy", lambda: self.pc_copy("open")).pack(side="left", padx=(6, 0))
            tk.Label(self.pcc, text="Latest: %s" % rom_line(roms[0]), bg=th.PANEL, fg=th.DIM,
                     anchor="w", justify="left", wraplength=400).pack(fill="x", pady=(4, 0))
        a = tk.Label(self.pcc, text="The PC copies guide (CEmu's keys, sending files, TiEmu)", bg=th.PANEL,
                     fg=th.MINT, cursor="hand2", anchor="w", font=(th.FONT, 9, "underline"))
        a.pack(fill="x", pady=(6, 0))
        a.bind("<Button-1>", lambda e: open_bundled_pdf(EMULATOR_GUIDE_PDF, self.pcc))
        bind_wheel(self.pcc, self.inner)

    def pc_copy(self, mode):
        """Make a PC copy / Open my PC copy: in the calculator's "(PC copy)" tab of the main window
        (emu_tabs.EmuTab.make_copy), or a window of its own where there are no such tabs"""
        app = self.panel.app
        if hasattr(app, "pc_copy_tab"):
            app.pc_copy_tab(self, mode)
            return
        d = self.pc_dialog
        if d is not None and d.alive():
            d.win.lift()
            return
        self.pc_dialog = PcCopyDialog(self, mode)

    # ---- The connection doctor ----
    # The check itself gives up on any Windows query after calc_doctor's time limits (a report
    # comes within about 20 s at the worst, in about a second normally); this is the window's own
    # limit on top, whatever happens to the worker
    DOCTOR_WAIT_S = 25

    def check(self):
        """The connection doctor on a worker thread. The window polls for its report (nothing
        crosses from the worker to Tk) and always ends with the report or a plain error."""
        for c in self.doctor.winfo_children():
            c.destroy()
        tk.Label(self.doctor, text="Checking Windows' drivers...", bg=th.PANEL, fg=th.DIM).pack(anchor="w")
        self.doctor_gen = gen = getattr(self, "doctor_gen", 0) + 1
        box = {}
        log = self.mirror_mod.log_error

        def work():
            try:
                import calc_doctor
                # probe=False: CalcSuite itself holds the calculator (it would show as busy)
                box["report"] = calc_doctor.diagnose(probe=False)
            except Exception as e:
                log("checking the drivers (connection doctor)")
                box["report"] = {"devices": [], "notes": [],
                                 "errors": ["The check failed: %s: %s" % (type(e).__name__, e)]}
        threading.Thread(target=work, daemon=True, name="doctor").start()
        t0 = time.time()

        def poll():
            if gen != self.doctor_gen:
                return  # Check again started a newer one
            try:
                if "report" in box:
                    report = box["report"]
                    for e in report.get("errors", []):
                        log("checking the drivers (connection doctor)", detail=e)
                    self.show_doctor(report)
                elif time.time() - t0 >= self.DOCTOR_WAIT_S:
                    why = "the driver check didn't finish within %d s" % self.DOCTOR_WAIT_S
                    log("checking the drivers (connection doctor)", detail=why)
                    self.doctor_failed("The check didn't finish within %d s: Windows didn't answer "
                                       "its device queries. Press Check again; if it keeps "
                                       "happening, unplug the calculator, wait 3 seconds and plug "
                                       "it back in." % self.DOCTOR_WAIT_S)
                else:
                    self.frame.after(150, poll)
            except tk.TclError:
                pass  # The panel was closed
            except Exception:
                log("showing the connection doctor's report")
                self.doctor_failed("The check's report couldn't be shown (details in errors.log).")
        self.frame.after(150, poll)

    def doctor_failed(self, text):
        for c in self.doctor.winfo_children():
            c.destroy()
        tk.Label(self.doctor, text=text, bg=th.PANEL, fg=th.WARN, anchor="w", justify="left",
                 wraplength=400).pack(fill="x")

    def show_doctor(self, report):
        for c in self.doctor.winfo_children():
            c.destroy()
        pid = "%04x" % self.m.calc.pid
        mine = [d for d in report.get("devices", []) if d.get("pid") == pid]
        if not mine:
            tk.Label(self.doctor, text="Windows doesn't list this calculator now.", bg=th.PANEL,
                     fg=th.FG, anchor="w").pack(fill="x")
        for d in mine[:1]:
            ok = d.get("status") == "ready"
            line = tk.Frame(self.doctor, bg=th.PANEL)
            line.pack(fill="x")
            dot = tk.Canvas(line, width=10, height=10, bg=th.PANEL, highlightthickness=0)
            dot.create_oval(1, 1, 9, 9, fill=th.MINT if ok else th.WARN, outline="")
            dot.pack(side="left", padx=(0, 6))
            tk.Label(line, text=d.get("headline", ""), bg=th.PANEL, fg=th.FG if ok else th.WARN,
                     font=(th.FONT, 10, "bold")).pack(side="left")
            text = d.get("text", "")
            if all(p.startswith("CalcSuite") for p in report.get("programs", [])):
                # The link programs running are CalcSuite's own (this window's): no advice needed
                import re
                text = re.sub(r" \([^()]*(\([^()]*\)[^()]*)*is running: if a transfer fails, close it\.\)",
                              "", text)
            tk.Label(self.doctor, text=text, bg=th.PANEL, fg=th.FG, anchor="w",
                     justify="left", wraplength=400).pack(fill="x", pady=(2, 0))
            if d.get("driver"):
                tk.Label(self.doctor, text="Driver: %s (%s)" % (d["driver"], d.get("provider") or "unknown"),
                         bg=th.PANEL, fg=th.DIM, anchor="w").pack(fill="x")
            row = tk.Frame(self.doctor, bg=th.PANEL)
            row.pack(fill="x", pady=(6, 0))
            if d.get("fix") == "install_winusb":
                th.button(row, "Install the WinUSB driver...",
                          lambda d=d: self.fix("install", d)).pack(side="left", padx=(0, 6))
            if d.get("alt_fix") == "restore_ti" or (d.get("can_restore_ti") and d.get("present")):
                th.button(row, "Restore TI's driver...",
                          lambda d=d: self.fix("restore", d)).pack(side="left")
        for e in report.get("errors", [])[:3]:  # A query that failed or never answered
            tk.Label(self.doctor, text="Not checked: %s" % e, bg=th.PANEL, fg=th.WARN, anchor="w",
                     justify="left", wraplength=400).pack(fill="x", pady=(4, 0))
        for n in report.get("notes", [])[:2]:
            tk.Label(self.doctor, text=n, bg=th.PANEL, fg=th.DIM, anchor="w", justify="left",
                     wraplength=400).pack(fill="x", pady=(4, 0))

    def fix(self, which, d):
        """Shows the helper's dry run first; the real change (admin prompt) only on OK"""
        import calc_doctor
        fn = calc_doctor.install_winusb if which == "install" else calc_doctor.restore_ti
        for c in self.doctor.winfo_children():
            if isinstance(c, tk.Frame):
                for b in c.winfo_children():
                    if isinstance(b, tk.Button):
                        b.configure(state="disabled")

        def dry():
            res = fn(d["pid"], dry_run=True)
            self.frame.after(0, lambda: self.confirm(which, d, fn, res))
        threading.Thread(target=dry, daemon=True).start()

    def confirm(self, which, d, fn, res):
        steps = "\n".join("- " + s for s in res.get("steps", [])[:12]) or "(the helper listed no steps)"
        errs = "\n".join(res.get("errors", [])[:4])
        what = ("put the WinUSB driver on the %s" % d["model"] if which == "install" else
                "take CalcSuite's WinUSB driver off the %s" % d["model"])
        warn = ""
        if which == "restore" and not d.get("ti_driver_installed"):
            warn = ("\n\nTI's own driver isn't installed on this PC: the calculator will have no "
                    "driver until TI's software is installed again.")
        if not messagebox.askokcancel(
                "Change the driver?", "This will %s. Windows asks for admin rights.\n\nWhat it "
                "will do:\n%s%s%s\n\nCalcSuite lets go of the calculator while it runs." % (
                    what, steps, "\n\nNote: " + errs if errs else "", warn),
                icon="warning", parent=self.frame):
            self.check()
            return
        self.m.release()

        def work():
            r = fn(d["pid"])
            self.frame.after(0, lambda: self.fixed(r))
        threading.Thread(target=work, daemon=True).start()

    def fixed(self, res):
        if res.get("cancelled"):
            msg = "Not changed (the admin prompt was declined)"
        elif res.get("ok"):
            msg = "Done: %s" % res.get("result")
        else:
            msg = "Didn't work: %s" % "; ".join(res.get("errors", [])[:2])
        self.m.set_status(msg)
        self.m.reconnect()
        self.check()


# ---- PC copy: the dialog behind Calculator info > Make a PC copy / Open my PC copy ----
PC_COPY = {"ti84": {"model": "84", "emulator": "CEmu", "time": "about 2 minutes",
                    "dumper": "ZZDUMP", "rest": "the ROMData AppVars"},
           "ti89": {"model": "89", "emulator": "TiEmu", "time": "about 70 seconds",
                    "dumper": "main\\romdump", "rest": ""}}
STAGES = {"connect": "Connecting", "check": "Checking the calculator", "backup": "Backing up",
          "tidy": "Tidying the archive", "send": "Sending the dump program",
          "run": "Starting the dump program", "wait": "The dump program is running",
          "fetch": "Reading the pieces", "dump": "Reading the ROM", "assemble": "Putting it together",
          "save": "Saving the ROM", "clean": "Cleaning up", "download": "Downloading",
          "done": "Done", "open": "Opening"}
RUNNING_STAGES = ("run", "wait", "fetch", "dump")  # The dump program is on the calculator
# The one progress bar of Make a PC copy: each stage's share of the whole job (about its time on
# the bench), in order. Within a stage its done/total moves the bar through that share; a wait
# with no total (the garbage collect) keeps it where the stage began. "done" is the end (100%).
PROGRESS_WEIGHTS = {
    "ti84": [("connect", 2), ("check", 2), ("backup", 15), ("tidy", 8), ("send", 3), ("run", 2),
             ("wait", 40), ("fetch", 20), ("assemble", 1), ("save", 1), ("clean", 6), ("done", 0)],
    "ti89": [("connect", 3), ("check", 3), ("backup", 25), ("send", 5), ("run", 4), ("dump", 50),
             ("save", 2), ("clean", 8), ("done", 0)],
}
BAR_MAX = 1000


def overall_progress(slug, stage, done=None, total=None):
    """The whole job's fraction (0..1) at this stage and its done/total, or None (a stage the
    table doesn't know: the bar stays)"""
    table = PROGRESS_WEIGHTS.get(slug)
    names = [s for s, _w in table or []]
    if stage not in names:
        return None
    if stage == "done":
        return 1.0
    whole = float(sum(w for _s, w in table))
    k = names.index(stage)
    before = sum(w for _s, w in table[:k])
    inside = min(max(done or 0, 0), total) / float(total) if total else 0.0
    return (before + table[k][1] * inside) / whole


RELEASE_WAIT_S = 40   # The mirror's link thread lets go within this (a connect takes up to 25 s)
CANCEL_GIVE_UP_S = 30  # After Cancel the dialog stops waiting for the worker after this


def log_error(where):
    """mirror.log_error (CalcSuite files\\logs\\errors.log): never raises"""
    try:
        import mirror
        mirror.log_error(where)
    except Exception:
        pass


def existing_roms(slug):
    """pc_copy.list_roms for the model, without making the folders when there's none yet"""
    import calc_backup as cb
    if not os.path.isdir(os.path.join(cb.backups_root(), "roms")):
        return []
    import pc_copy
    try:
        return pc_copy.list_roms(slug)
    except OSError:
        return []


def rom_line(r):
    info = r.get("info") or {}
    return "%s%s (%s)" % (time.strftime("%Y-%m-%d %H:%M", time.localtime(r["made"])),
                          ", OS %s" % info["os"] if info.get("os") else "", os.path.basename(r["path"]))


def show_in_folder(path):
    import subprocess
    try:
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
    except OSError:
        pass


class PcCopyDialog(object):
    """make: explains, asks, lets go of the tab's link, runs pc_copy.dump_rom on a worker with
    a progress bar (Cancel between steps), takes the link back, then offers the emulator.
    open: the newest ROM and the emulator."""

    def __init__(self, section, mode, parent=None, on_made=None, on_close=None):
        """parent: a frame to fill (the "(PC copy)" tab, emu_tabs.EmuTab) instead of a window of
        its own; on_made(rom, backup, auto): the copy is made (or Open is pressed) and the
        emulator should start (auto: by itself, nothing to read first); on_close(): Close."""
        import pc_copy
        self.pc = pc_copy
        self.sec, self.m = section, section.m
        self.embedded = parent is not None
        self.on_made, self.on_close = on_made, on_close
        self.slug, self.title = self.m.calc.slug, self.m.calc.title
        self.spec = PC_COPY[self.slug]
        self.cancel = threading.Event()
        self.running = False
        # Workers never call Tk: they put work in this inbox, which drain() runs on Tk's thread
        # (its own after() loop, started here on Tk's thread). Before, their after(0, ...) calls
        # could be lost and the dialog then waited forever (2026-11-28).
        self.inbox = queue.SimpleQueue()
        self.worker = None       # The dump's thread while it runs
        self.cancelled_at = None  # When Cancel was pressed (time.time())
        self.shown_end = False    # finished() has run (a late answer is then ignored)
        self.last_stage = "connect"
        if self.embedded:
            w = self.win = tk.Frame(parent, bg=th.BG)
            w.pack(fill="both", expand=True)
        else:
            w = self.win = tk.Toplevel(section.frame)
            w.title("PC copy of the %s" % self.title)
            w.configure(bg=th.BG)
            w.geometry("640x560")
            w.minsize(520, 420)
            w.protocol("WM_DELETE_WINDOW", self.close)
        self.gone = False
        w.bind("<Destroy>", self.destroyed, add="+")
        self.body = None
        self.status = tk.StringVar(master=w, value="")
        if mode == "make":
            self.intro()
        else:
            self.open_mode()
        self.drain()

    # ---- Plumbing ----
    def alive(self):
        """Whether the window is still open (a flag: safe from a worker thread)"""
        return not self.gone

    def destroyed(self, ev):
        if ev.widget is self.win:
            self.gone = True

    def ui(self, fn, *args):
        """fn(*args) on Tk's thread, from a worker: through the inbox drain() runs"""
        if self.alive():
            self.inbox.put((fn, args))

    def drain(self):
        """Tk's thread, every 50 ms while the window is open: what the workers asked for, then
        the watchdog (a Cancel the worker doesn't answer, a worker gone without a word)"""
        if self.gone:
            return
        try:
            for _ in range(100):
                try:
                    fn, args = self.inbox.get_nowait()
                except queue.Empty:
                    break
                try:
                    fn(*args)
                except Exception:
                    log_error("the PC copy window")
            self.watchdog()
        finally:
            if not self.gone:
                try:
                    self.win.after(50, self.drain)
                except tk.TclError:
                    pass

    def watchdog(self):
        if not self.running or self.shown_end or self.worker is None:
            return
        if not self.worker.is_alive() and self.inbox.empty():
            # The worker always hands in its result before it ends: this is a bug, not a hang
            self.finished(None, self.pc.PcCopyError(self.last_stage, "the PC copy stopped without "
                                                    "saying why (see CalcSuite files\\logs\\errors.log)"))
        elif self.cancelled_at is not None and time.time() - self.cancelled_at > CANCEL_GIVE_UP_S:
            try:
                raise self.pc.PcCopyError(self.last_stage, "CalcSuite stopped waiting: the %s step "
                                          "didn't stop within %d s of Cancel" %
                                          (STAGES.get(self.last_stage, self.last_stage).lower(),
                                           CANCEL_GIVE_UP_S))
            except self.pc.PcCopyError as e:
                log_error("cancelling the PC copy of the %s" % self.title)
                try:
                    self.m.reconnect()  # The mirror tries again by itself until the link is free
                except Exception:
                    log_error("giving the %s back to the mirror" % self.title)
                self.finished(None, e)

    def fresh(self):
        if self.body is not None:
            self.body.destroy()
        self.body = tk.Frame(self.win, bg=th.BG)
        self.body.pack(fill="both", expand=True, padx=16, pady=14)
        return self.body

    def text(self, parent, text, fg=th.FG, bold=False, pady=(0, 6)):
        lab = tk.Label(parent, text=text, bg=th.BG, fg=fg, anchor="w", justify="left", wraplength=590,
                       font=(th.FONT, 11 if bold else 9, "bold" if bold else "normal"))
        lab.pack(fill="x", pady=pady)
        return lab

    def close(self):
        if self.running:
            self.do_cancel()
            return
        try:
            self.win.destroy()
        except tk.TclError:
            pass
        if self.on_close is not None:
            self.on_close()

    # ---- Make: what happens, then Start ----
    def intro(self):
        b = self.fresh()
        s, ti84 = self.spec, self.slug == "ti84"
        self.text(b, "Make a PC copy of the %s" % self.title, bold=True)
        self.text(b, "A PC copy is your calculator running on this PC, in %s: the same operating "
                  "system, with your programs and variables." % s["emulator"])
        steps = [
            "CalcSuite backs up the calculator to this PC first: everything in RAM and in the "
            "archive, like Files > Backup.",
            ("It tidies the archive (Garbage Collect), sends a small ROM dump program (%s) and "
             "runs it on the calculator." if ti84 else
             "It sends a small ROM dump program (%s) and runs it on the calculator.") % s["dumper"],
            "The program reads the calculator's ROM (its operating system) and hands it to the PC. "
            "All of it takes %s: leave the calculator and the cable alone meanwhile." % s["time"],
            "CalcSuite removes the dump program again and checks that everything that was in RAM "
            "is still there (the backup is there if not).",
        ]
        for k, t in enumerate(steps):
            self.text(b, "%d.  %s" % (k + 1, t), pady=(0, 4))
        self.text(b, "The ROM stays on this PC (CalcSuite files\\backups\\roms) and is never "
                  "uploaded anywhere. It's TI's software: keep it for yourself.", fg=th.DIM, pady=(8, 4))
        self.text(b, "The screen mirror pauses while it runs (the dump needs the link to itself) and "
                  "comes back afterwards.%s" % (
                      " Needs OS 5.4 or older, 66 KB of free RAM and about 1.1 MB of free archive."
                      if ti84 else ""), fg=th.DIM)
        tk.Label(b, textvariable=self.status, bg=th.BG, fg=th.ACCENT, anchor="w", justify="left",
                 wraplength=590).pack(fill="x", pady=(6, 0))
        row = tk.Frame(b, bg=th.BG)
        row.pack(fill="x", side="bottom")
        th.button(row, "Start the PC copy", self.start).pack(side="left")
        th.button(row, "Cancel", self.close).pack(side="left", padx=(6, 0))

    def start(self):
        if not self.m.connected():
            self.status.set("The %s isn't connected: plug it in, switch it on and wait for the "
                            "mirror, then start." % self.title)
            return
        if not messagebox.askokcancel("Start the PC copy?", "Back up the %s, then run the ROM dump "
                                      "program on it (%s)?" % (self.title, self.spec["time"]),
                                      parent=self.win):
            return
        self.running = True
        self.cancel.clear()
        b = self.fresh()
        self.text(b, "Making the PC copy of the %s" % self.title, bold=True)
        self.stage = self.text(b, "Letting go of the link...", fg=th.ACCENT, pady=(6, 2))
        self.line = self.text(b, "", fg=th.FG)
        # One bar for the whole job (BAR_MAX = done), weighted by stage: it only moves forward
        self.bar = ttk.Progressbar(b, style=progress_style(b), mode="determinate", maximum=BAR_MAX)
        self.bar.pack(fill="x", pady=(4, 2))
        self.bar_value = 0
        self.bar_values = []  # Every value the bar was set to (the self-test reads it)
        self.overall = self.text(b, "Overall 0%", fg=th.DIM, pady=(0, 6))
        self.text(b, "Don't touch the calculator or the cable until it says done.", fg=th.DIM)
        tk.Label(b, textvariable=self.status, bg=th.BG, fg=th.DIM, anchor="w", justify="left",
                 wraplength=590).pack(fill="x")
        row = tk.Frame(b, bg=th.BG)
        row.pack(fill="x", side="bottom")
        self.cancel_btn = th.button(row, "Cancel", self.do_cancel)
        self.cancel_btn.pack(side="left")
        self.t0 = time.time()
        self.shown_end, self.cancelled_at = False, None
        self.worker = threading.Thread(target=self.run, daemon=True)
        self.worker.start()

    def do_cancel(self):
        if not self.running or self.cancel.is_set():
            return
        self.cancel.set()
        self.cancelled_at = time.time()
        self.cancel_btn.configure(state="disabled")
        self.status.set("Cancelling: CalcSuite stops the step it's on (within a few seconds). A dump "
                        "program already running on the calculator finishes there by itself: "
                        "CalcSuite just stops waiting for it.")

    def report(self, stage, text, done=None, total=None):
        if stage:
            self.last_stage = stage
        self.ui(self.show_progress, stage, text, done, total)

    def show_progress(self, stage, text, done, total):
        if not self.running or self.shown_end:
            return
        self.stage.configure(text=STAGES.get(stage, stage) + "...")
        if text:
            self.line.configure(text=text)
        frac = overall_progress(self.slug, stage, done, total)
        if frac is not None:
            self.bar_value = max(self.bar_value, int(round(frac * BAR_MAX)))  # Never back
            self.bar.configure(value=self.bar_value)
            self.bar_values.append(self.bar_value)
        order = [s for s, _w in PROGRESS_WEIGHTS[self.slug]]
        step = ("  -  step %d of %d" % (order.index(stage) + 1, len(order) - 1)
                if stage in order and stage != "done" else "")
        self.overall.configure(text="Overall %d%%%s" % (100 * self.bar_value // BAR_MAX, step))
        if not self.cancel.is_set():
            self.status.set("%d s so far (%s in all)" % (time.time() - self.t0, self.spec["time"]))

    def let_go(self):
        """The worker: asks the tab's link thread to let go of the calculator and waits until it
        says it has (Mirror.let_go), at most RELEASE_WAIT_S; Cancel stops the wait"""
        m, pc = self.m, self.pc
        flag = getattr(m, "let_go", None)
        m.release()  # The dump opens its own sessions: the tab's link thread lets go first
        m.set_status("Making a PC copy of the %s: the mirror is paused" % self.title)
        t = time.time()
        while not (flag.is_set() if flag is not None else m.session is None):
            waited = time.time() - t
            if self.cancel.is_set():
                raise pc.Cancelled("connect")
            if waited > RELEASE_WAIT_S:
                raise pc.PcCopyError("connect", "the mirror didn't let go of the %s within %d s (it may "
                                     "be in the middle of a transfer: try again in a moment)" %
                                     (self.title, RELEASE_WAIT_S))
            self.report("connect", "Waiting for the mirror to let go of the %s (%d s)..." % (self.title, waited))
            time.sleep(0.2)
        self.report("connect", "The mirror has let go of the %s" % self.title)
        time.sleep(0.5)

    def run(self):
        m = self.m
        res, err = None, None
        try:
            self.let_go()
            res = self.pc.dump_rom(self.spec["model"], self.report, self.cancel)
        except Exception as e:  # PcCopyError, Cancelled, or anything unexpected
            err = e
            if not isinstance(e, self.pc.Cancelled):
                log_error("making the PC copy of the %s" % self.title)
        finally:
            try:
                m.reconnect()  # The tab takes the calculator back
            except Exception:
                log_error("giving the %s back to the mirror" % self.title)
            self.ui(self.finished, res, err)

    def finished(self, res, err):
        if self.shown_end:
            return  # The watchdog already said how it ended
        self.shown_end = True
        self.running = False
        try:
            self.bar.stop()
        except tk.TclError:
            pass
        b = self.fresh()
        if err is not None:
            self.failed(b, err)
        else:
            self.made(b, res)
        try:
            self.sec.build_pc_copy()  # "Open my PC copy" now
        except tk.TclError:
            pass

    def failed(self, b, err):
        pc = self.pc
        stage = getattr(err, "stage", None)
        if isinstance(err, pc.Cancelled):
            self.text(b, "Cancelled", bold=True)
            self.text(b, "No PC copy was made.")
        elif isinstance(err, pc.PcCopyError):
            self.text(b, "The PC copy wasn't made", bold=True)
            msg = str(err)
            self.text(b, msg[:1].upper() + msg[1:] + ("" if msg.endswith(".") else "."))
        else:
            self.text(b, "The PC copy wasn't made", bold=True)
            self.text(b, "Something unexpected stopped it: %s" % short_error(err))
        if stage in RUNNING_STAGES:
            rest = " and " + self.spec["rest"] if self.spec["rest"] else ""
            self.text(b, "The dump program had started: %s%s may still be on the calculator. They're "
                      "CalcSuite's, not yours: delete them in Files once the dump program has "
                      "finished." % (self.spec["dumper"], rest), fg=th.ACCENT)
        if stage and stage not in ("connect", "check") and not isinstance(err, pc.Cancelled):
            self.text(b, "The backup from before is in CalcSuite files\\backups.", fg=th.DIM)
        detail = getattr(err, "detail", None) or []
        if detail:
            self.text(b, "The tool said: " + " / ".join(str(d) for d in detail[-3:]), fg=th.DIM)
        self.text(b, "The mirror is connecting again.", fg=th.DIM)
        row = tk.Frame(b, bg=th.BG)
        row.pack(fill="x", side="bottom")
        th.button(row, "Close", self.close).pack(side="left")

    def made(self, b, res):
        # Done, and it says so: the bar full and green, "Done" in green (the owner: "make sure
        # when dumping the ROM it marks as complete when finished")
        self.bar_value = BAR_MAX
        self.done_bar = ttk.Progressbar(b, style=progress_style(b, done=True), mode="determinate",
                                        maximum=BAR_MAX, value=BAR_MAX)
        self.done_bar.pack(fill="x", pady=(0, 2))
        self.text(b, "Done: 100%", fg=th.FG, bold=True, pady=(0, 8))
        self.text(b, "Your PC copy is made", bold=True)
        self.text(b, "In %d s. ROM: %s (%s, OS %s)." % (res.get("seconds") or 0, res["rom"],
                                                         human(res.get("size") or 0), res.get("os") or "?"))
        if res.get("backup"):
            self.text(b, "The backup from before: %s" % res["backup"], fg=th.DIM)
        for n in res.get("notes") or []:
            if n:
                self.text(b, n, fg=th.ACCENT)
        lost = res.get("ram_cleared") or res.get("missing")
        if lost:
            self.text(b, "Some of what was in RAM is gone (%s). Restore... puts it back from the "
                      "backup: you pick what goes back." % (
                          "all of it" if res.get("ram_cleared") else ", ".join(res["missing"][:8])),
                      fg=th.ACCENT)
        self.text(b, "The mirror is connecting again.", fg=th.DIM)
        self.emulator(b, res["rom"], res.get("backup"), restore=res.get("backup") if lost else None)
        if self.embedded and self.on_made is not None and not lost and not any(res.get("notes") or []):
            # In its tab: the copy starts there by itself in a moment
            self.status.set("Starting your PC copy here in a moment...")
            self.win.after(2500, lambda: self.alive() and self.on_made(res["rom"], res.get("backup"), True))

    # ---- Open: the newest ROM ----
    def open_mode(self):
        b = self.fresh()
        roms = existing_roms(self.slug)
        self.text(b, "Your PC copy of the %s" % self.title, bold=True)
        if not roms:
            self.text(b, "There's no PC copy yet: Make a PC copy... first.")
            row = tk.Frame(b, bg=th.BG)
            row.pack(fill="x", side="bottom")
            th.button(row, "Close", self.close).pack(side="left")
            return
        r = roms[0]
        self.text(b, "Made %s." % rom_line(r))
        if len(roms) > 1:
            self.text(b, "%d copies in all; this is the newest." % len(roms), fg=th.DIM)
        self.emulator(b, r["path"], (r.get("info") or {}).get("backup"))

    # ---- The emulator ----
    def emulator(self, b, rom, backup, restore=None):
        pc = self.pc
        self.rom, self.backup = rom, backup
        if self.slug == "ti84":
            have = pc.cemu_path()
            self.text(b, "CEmu (GPL-3.0, from its makers on GitHub) runs the copy in a tab of the main "
                      "window, \"TI-84 Plus CE (PC copy)\", and gets your programs and variables from "
                      "the backup.%s" % (
                          "" if have else " The first time, CalcSuite downloads CEmu 2.0 (about "
                          "19 MB) and checks it against its SHA-256."), fg=th.DIM, pady=(10, 6))
            first = ("Open in CEmu", self.open_cemu)
        elif pc.tiemu_path():
            self.text(b, "TiEmu is installed: it opens the copy in a tab of the main window, \"TI-89 "
                      "Titanium (PC copy)\". Your programs aren't sent for you (TiEmu takes one file at "
                      "a time: right-click it, Send file to TiEmu; the backup is in CalcSuite "
                      "files\\backups).", fg=th.DIM, pady=(10, 6))
            first = ("Open in TiEmu", self.open_tiemu)
        else:
            self.text(b, "TiEmu, the TI-89 emulator, was last released in 2010 (3.03), and its "
                      "Windows installer is that old, unsigned setup.exe, so CalcSuite doesn't run it "
                      "for you. CalcSuite can download it (3 MB from SourceForge, checked against "
                      "its checksums) and show it to you; you run it, then come back to Open my "
                      "PC copy.", fg=th.DIM, pady=(10, 6))
            first = ("Download TiEmu's installer", self.get_tiemu)
        if self.embedded and self.on_made is not None:  # In its tab: the tab runs the emulator
            first = ("Open the PC copy here", lambda: self.on_made(rom, backup, False))
        tk.Label(b, textvariable=self.status, bg=th.BG, fg=th.ACCENT, anchor="w", justify="left",
                 wraplength=590).pack(fill="x")
        row = tk.Frame(b, bg=th.BG)
        row.pack(fill="x", side="bottom")
        self.emu_btn = th.button(row, first[0], first[1])
        self.emu_btn.pack(side="left")
        th.button(row, "Show the ROM", lambda: show_in_folder(rom)).pack(side="left", padx=(6, 0))
        if restore:
            th.button(row, "Restore...", lambda: self.restore(restore)).pack(side="left", padx=(6, 0))
        th.button(row, "Close", self.close).pack(side="right")

    def emu_work(self, fn):
        self.emu_btn.configure(state="disabled")

        def run():
            try:
                msg = fn()
            except Exception as e:
                log_error("getting the emulator for the %s ready" % self.title)
                msg = "Didn't work: %s" % short_error(e)
            self.ui(self.emu_done, msg)
        threading.Thread(target=run, daemon=True).start()

    def emu_done(self, msg):
        self.status.set(msg)
        try:
            self.emu_btn.configure(state="normal")
        except tk.TclError:
            pass

    def dl_report(self, stage, text, done=None, total=None):
        if text:
            if total and done is not None and "%" not in text:
                text = "%s (%d%%)" % (text, 100 * min(done, total) // total)
            self.ui(self.status.set, text)

    def tab_app(self):
        """The main window, when it has emulator tabs (App.open_emulator_tab), else None"""
        app = getattr(getattr(self.sec, "panel", None), "app", None)
        return app if hasattr(app, "open_emulator_tab") else None

    def open_tab(self):
        """The emulator in a tab of the main window (emu_tabs.py); the tab gets CEmu ready itself"""
        app = self.tab_app()
        app.open_emulator_tab(self.slug, self.rom, self.backup)
        self.status.set("%s opens in its own tab of the main window: %s (PC copy)." % (
            self.spec["emulator"], self.title))

    def open_cemu(self):
        if self.tab_app() is not None:
            self.open_tab()
            return

        def go():
            self.pc.get_emulator("84", self.dl_report)
            self.pc.open_in_emulator("84", self.rom, self.backup)
            return "CEmu is opening: it boots the copy and gets your programs from the backup."
        self.status.set("Getting CEmu ready...")
        self.emu_work(go)

    def open_tiemu(self):
        if self.tab_app() is not None:
            self.open_tab()
            return

        def go():
            self.pc.open_in_emulator("89", self.rom)
            return "TiEmu is opening the copy."
        self.emu_work(go)

    def get_tiemu(self):
        def go():
            emu = self.pc.get_emulator("89", self.dl_report)
            if emu.get("ready"):
                if self.tab_app() is not None:
                    self.ui(self.open_tab)
                    return "TiEmu is installed: it opens in its own tab of the main window."
                self.pc.open_in_emulator("89", self.rom)
                return "TiEmu is opening the copy."
            show_in_folder(emu["path"])
            return emu.get("todo") or "Run %s yourself to install TiEmu." % emu["path"]
        self.status.set("Downloading TiEmu's installer...")
        self.emu_work(go)

    def restore(self, folder):
        import calc_backup as cb
        import calc_manager
        mgr = self.sec.manager()
        if not mgr.connected():
            self.status.set("Wait until the %s is connected again, then press Restore... again." % self.title)
            return
        try:
            man = cb.load(folder)
        except (OSError, ValueError) as e:
            self.status.set("The backup can't be read: %s" % short_error(e))
            return
        calc_manager.RestoreDialog(mgr, folder, man)
