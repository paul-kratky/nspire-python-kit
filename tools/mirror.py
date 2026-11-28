"""CalcSuite: your TI calculators' screens in one window, with your keyboard as their keypad.

    python -I tools/mirror.py            (or double-click "CalcSuite.bat")

One window with a tab strip: "All screens" (every connected calculator side by side), then
one tab per calculator (a TI-Nspire CX II, a TI-84 Plus CE, a TI-89 Titanium). A calculator
plugged in later gets its tab; one unplugged greys out until it's back. "Open in its own
window" pops a calculator's tab out into a window of its own; closing that window docks it
back.

A calculator's tab: the live picture (the Nspire about 19 frames a second, the 84 Plus CE about
1), Screenshot, Record, Send program, Copy answer, the pinned macros, More (Copy screen, Paste
text, Reconnect, ...), Keyboard on/off, and a side panel picked on an icon strip (ui_panels.py):
Files (the calculator manager, calc_manager.py, with Back up / Restore), Keys, Symbols,
Functions, Data, Get programs, Macros, Guide and Calculator info (model, OS, clock, Exit
Press-to-Test, the connection doctor). Tools (Make a picture, the Solver builder, Compare
backups, ...) open as closable tabs (tool_tabs.py, App.open_tool_tab).

The PC copy's tabs ("TI-84 Plus CE (PC copy)", "TI-89 Titanium (PC copy)": emu_tabs.py) make
the copy and then host the emulator's own window (CEmu, TiEmu: separate programs).

Each calculator has one link thread, the only thing that talks to it (Mirror.link_loop):
keys go first, the picture catches up when you pause, a do-nothing key keeps it awake.
The keys each PC key presses: calc_models.py (and the Keys panel, made from the same table).
"""

import os
import shutil
import sys
import queue
import tempfile
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import font as tkfont

# Run as the program (python tools/mirror.py, and CalcSuite.exe) this module is "__main__". The
# panels' `import mirror` then loaded a second copy of it, which patched after() again with a
# queue of its own that App.pump never runs: from then on every worker's window work was lost
# (Make a PC copy stayed on "Letting go of the link..." while the ROM was saved, 2026-11-28).
# One module under both names.
if __name__ != "mirror":
    sys.modules.setdefault("mirror", sys.modules[__name__])

# Tk may only be touched from its own thread. The link threads (and the panels' workers) ask for
# window work with after(0, ...); called from another thread that call itself is unsafe, and with
# three calculators at 20 frames a second requests were lost: the picture stopped updating while
# keys still worked (bench, 2026-11-27). From any other thread after() now queues the call, and
# App.pump() runs the queue on Tk's thread about 60 times a second. Patched once: a second copy
# of this module (loaded under another name) shares the first one's queue.
_TK_THREAD = threading.main_thread()
_TK_QUEUE = getattr(tk.Misc.after, "calcsuite_queue", None)
if _TK_QUEUE is None:
    _TK_QUEUE = queue.SimpleQueue()
    _tk_after = tk.Misc.after

    def _after(self, ms, func=None, *args):
        if func is not None and threading.current_thread() is not _TK_THREAD:
            _TK_QUEUE.put((func, args))
            return None
        return _tk_after(self, ms, func, *args)

    _after.calcsuite_queue = _TK_QUEUE
    tk.Misc.after = _after

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "nspire_cli"))
sys.path.insert(0, os.path.join(HERE, "ti84_cli"))
import nspire_link  # noqa: E402
import recorder  # noqa: E402
import calc_manager  # noqa: E402
import send_ti  # noqa: E402
import calc_models  # noqa: E402
import key_strip  # noqa: E402
import ui_theme as th  # noqa: E402
from emu_tabs import is_emu_key  # noqa: E402
import tool_tabs  # noqa: E402
import window_chrome as wc  # noqa: E402

import check_nspire  # noqa: E402
import py2tns  # noqa: E402

from calc_models import Nspire, Ti84, Ti89, CALCS  # noqa: E402,F401  (the old names still work)

APP_NAME = "CalcSuite"
from app_version import TEXT as APP_VERSION  # noqa: E402
SPONSOR_URL = None  # A sponsor / funding page; the Calculator info panel shows "Support CalcSuite" when set
DOCS = os.path.join(os.path.expanduser("~"), "Documents")
OLD_KIT = os.path.join(DOCS, "Nspire Mirror")  # Where the app kept its files before 1.0

import paths  # noqa: E402

if getattr(sys, "frozen", False):
    # The packaged app (a folder from the zip): what it makes goes to "CalcSuite files" beside
    # CalcSuite.exe (tools/paths.py), or Documents\CalcSuite when that folder can't be written
    KIT = paths.files_dir()
    py2tns.BUILD = os.path.join(KIT, "build")
else:
    KIT = os.path.dirname(HERE)
SCALE = 2
PASTE_MAX = 4000  # Characters one paste may type
KEEPALIVE_S = 60  # A do-nothing key this often while a calculator is connected and idle (0: never)
# Seconds after these commands with no screenshot, Fast mode frame or keep-alive key: the
# TI-84 Plus CE applies a clock write a moment after it acks it, and the live picture's big
# transfers must not land on it meanwhile (queued commands still run)
QUIET_AFTER = {"setclock": 3.0}
HISTORY = 8       # Keys the key-history strip shows
# Fast mode (TI-84 Plus CE): its calculator program, the typing hold-off when a frame takes
# ~0.15 s instead of 1.4 s, and after how many fallback frames in a row the status says so
FAST84_PRGM = os.path.join(HERE, "fast84", "CSFAST.8xp")
FAST_HOLDOFF = 0.15
FAST_MISSES_WARN = 3
APP = None  # The running App (tool_tabs.app() finds it: tools open as tabs of its window)


def log_error(where, detail=None):
    """The current exception, with its traceback, appended to "CalcSuite files/logs/errors.log"
    (kept under 1 MB): errors inside the window never pass silently. detail: a text to log
    instead, for a problem that isn't an exception (a check that never answered)"""
    import traceback
    try:
        folder = paths.user_path("logs")
        path = os.path.join(folder, "errors.log")
        if os.path.isfile(path) and os.path.getsize(path) > 1024 * 1024:
            os.replace(path, path + ".old")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("%s  %s, while %s:\n%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"),
                                                  APP_NAME, where,
                                                  detail if detail is not None else
                                                  traceback.format_exc()))
    except Exception:
        pass


def _os_tuple(text):
    """"5.4.0" -> (5, 4, 0)"""
    import re
    return tuple(int(x) for x in re.findall(r"\d+", text or "")[:3])


def resource(*parts):
    """A file shipped with the app: from the source tree, or unpacked beside the packaged exe"""
    for base in (os.path.dirname(HERE), getattr(sys, "_MEIPASS", HERE), HERE):
        p = os.path.join(base, *parts)
        if os.path.exists(p):
            return p
    return os.path.join(os.path.dirname(HERE), *parts)


def migrate_documents(old=OLD_KIT, new=None):
    """Documents\\Nspire Mirror -> Documents\\CalcSuite, once: copies what isn't there yet
    (captures, programs, from-calc, ...), never overwrites, never deletes; leaves a note in the
    old folder. Returns the number of files copied (or None when there was nothing to do)."""
    new = new or os.path.join(DOCS, "CalcSuite")
    note = os.path.join(old, "Moved to CalcSuite.txt")
    if not os.path.isdir(old) or os.path.exists(note):
        return None
    copied = 0
    for dirpath, _dirs, files in os.walk(old):
        rel = os.path.relpath(dirpath, old)
        dest_dir = os.path.normpath(os.path.join(new, rel))
        for f in files:
            src, dst = os.path.join(dirpath, f), os.path.join(dest_dir, f)
            if os.path.exists(dst):
                continue
            try:
                os.makedirs(dest_dir, exist_ok=True)
                shutil.copy2(src, dst)
                copied += 1
            except OSError:
                pass
    try:
        with open(note, "w", encoding="utf-8") as fh:
            fh.write("Nspire Mirror is now CalcSuite.\n\nIts files are now in %s: everything in "
                     "this folder was copied there (%d files; nothing that was already there was "
                     "replaced).\nThis folder was left as it was: delete it yourself when you "
                     "no longer need it.\n" % (new, copied))
    except OSError:
        pass
    return copied


def set_clipboard_image(w, h, rgb, scale):
    """Puts an RGB picture on the Windows clipboard (CF_DIB), enlarged by `scale`"""
    import ctypes
    import struct
    sw, sh = w * scale, h * scale
    stride = (sw * 3 + 3) & ~3
    rows = []
    for y in range(h - 1, -1, -1):  # A DIB stores the bottom row first
        line = bytearray()
        for x in range(w):
            r, g, b = rgb[(y * w + x) * 3:(y * w + x) * 3 + 3]
            line += bytes((b, g, r)) * scale
        line += b"\x00" * (stride - len(line))
        rows.extend([bytes(line)] * scale)
    data = struct.pack("<IiiHHIIiiII", 40, sw, sh, 1, 24, 0, stride * sh, 2835, 2835, 0, 0)
    data += b"".join(rows)
    k32, u32 = ctypes.windll.kernel32, ctypes.windll.user32
    k32.GlobalAlloc.restype = ctypes.c_void_p
    k32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = [ctypes.c_void_p]
    k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    u32.SetClipboardData.restype = ctypes.c_void_p
    u32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    u32.OpenClipboard.argtypes = [ctypes.c_void_p]
    handle = k32.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
    ptr = k32.GlobalLock(handle)
    ctypes.memmove(ptr, data, len(data))
    k32.GlobalUnlock(handle)
    if not u32.OpenClipboard(None):
        raise OSError("the clipboard is busy")
    try:
        u32.EmptyClipboard()
        if not u32.SetClipboardData(8, handle):  # CF_DIB; Windows owns it from here
            raise OSError("the clipboard refused the picture")
    finally:
        u32.CloseClipboard()


def prepare_for_nspire(path):
    """A .py checked and turned into a .tns (as tools/flash.py does), a .tns as it is.
    Returns (the file to send, None) or (None, why not)."""
    if not path.lower().endswith(".py"):
        return path, None
    errors = [f for f in check_nspire.check_file(path, set()) if f.level == "ERROR"]
    if errors:
        f = errors[0]
        more = " (+%d more)" % (len(errors) - 1) if len(errors) > 1 else ""
        return None, "Not sent, line %d: %s%s. Fix: %s" % (f.line, f.message, more, f.fix)
    try:
        return py2tns.convert(path, quiet=True), None
    except py2tns.TnsError as e:
        return None, "Not sent: %s" % e


def link_problem_text(calc, why):
    """A failed connect's plain advice when the helper's answer says what to do, else None.
    The TI-Nspire answers one connection per plug-in: once another program (or an earlier
    CalcSuite) has used it, every new one gets "no answer from the handheld" until it's
    replugged (2026-11-28: the tab said "Connecting..." for good)."""
    if calc.slug == "nspire" and any("no answer from the handheld" in w for w in why):
        return ("The %s isn't answering: unplug it, wait 3 seconds, plug it back in (it allows "
                "one connection per plug-in)" % calc.title)
    return None


class Mirror(object):
    """One calculator: its link thread, its frames, its keys. The views (its tab, its tile in
    All screens) draw what it has."""

    def __init__(self, app, calc):
        self.app = app
        self.calc = calc
        self.root = app.root    # Where dialogs hang and after() runs: the tab's frame, later
        self.session = None
        self.jobs = []          # Commands for the link thread (key presses, uploads)
        self.jobs_lock = threading.Lock()
        self.last_key = 0.0     # When a key was last queued (time.time())
        self.last_keepalive = time.time()
        self.quiet_until = 0.0  # No pictures or keep-alive keys before this (QUIET_AFTER)
        self.link_problem = None  # What the user must do about the last failed connect, or None
        self.running = True
        self.present = True     # On USB now (the App's scan says)
        self.want_reconnect = False
        self.released = False   # Let go of the calculator for another program (until Reconnect)
        self.let_go = threading.Event()  # Set by the link thread once it has let go (released, no session)
        self.keys_on = tk.BooleanVar(master=app.root, value=True)
        self.status = tk.StringVar(master=app.root, value="Connecting...")
        self.frame_path = os.path.join(tempfile.gettempdir(),
                                       "calc_mirror_%s_%d.ppm" % (calc.slug, os.getpid()))
        self.frames = 0
        self.frames_total = 0
        self.fps = 0.0
        self.t0 = time.time()
        self.rec = None         # A recorder.Recorder while recording
        self.rec_lock = threading.Lock()
        self.manager = None     # The calculator manager (calc_manager.Manager) when open
        self.info = {}          # The calculator's last "info" answer (name, OS, free space)
        self.driver_checked = False  # The connection doctor asked once why it won't open
        self.views = []         # ScreenViews showing this calculator
        self.image = None       # The last frame as a PhotoImage, the calculator's own size
        self.latest = None      # The newest frame's PPM bytes, not drawn yet (link thread -> pump)
        self.native = None      # Its (w, h)
        self.history = []       # The last keys pressed, as labels (newest last)
        self.last_press = tk.StringVar(master=app.root, value="Last key: none yet")
        self.listeners = []     # fn(keysym) called after a key press (the Keys panel)
        self.key_taps = []      # fn(line) for every key command queued (recording a macro)
        self.click_acted = 0.0  # When a single click last pressed keys (double click skips)
        # Fast mode (the TI-84 Plus CE only, experimental, off until set_fast(True)): see
        # set_fast() and docs/dev/FAST84_PLAN.md
        self.fast_state = "off"  # off | starting | on | stopping | lost | error
        self.fast_note = ""      # The last thing worth telling about it, in plain words
        self.fast_misses = 0     # Frames in a row Fast mode couldn't give
        self.fast_listeners = []  # fn(state, note), called on the link thread when it changes
        threading.Thread(target=self.link_loop, daemon=True).start()

    # ---- The link thread: the only one that talks to the calculator ----
    def link_loop(self):
        while self.running:
            if self.released:  # Another program (TI's) has the calculator: wait for Reconnect
                if self.session is not None:
                    self.session.close()
                    self.session = None
                self.let_go.set()  # The PC copy waits for this before it opens its own link
                time.sleep(0.2)
                continue
            if self.session is None:
                if not self.present:  # Unplugged: wait for the scan to see it again
                    self.set_status("Not plugged in")
                    self.wait_reconnect(1.0)
                    continue
                try:
                    self.session = nspire_link.Session(cli=self.calc.cli)
                    self.palette_at = None  # Where the symbol palette was left: unknown again
                    code, lines = self.session.cmd("info")
                    d = nspire_link.info_dict(lines)
                    self.info = d
                    self.link_problem = None
                    name = d.get("name", self.calc.title).replace("_", " ")
                    self.set_status("Connected: %s%s" % (name, ", OS %s" % d["os"] if "os" in d else ""))
                except nspire_link.LinkError as e:
                    self.session = None
                    # What the link helper said, so a stuck link says why (not just "looking")
                    why = [l[4:] if l.startswith("ERR ") else l for l in e.lines if l.strip()]
                    self.link_problem = link_problem_text(self.calc, why)
                    self.set_status(self.link_problem or
                                    "Looking for the %s... (plugged in, switched on, TI's own "
                                    "software closed)%s" % (self.calc.title,
                                                           "\nLink: " + why[-1][:160] if why else ""))
                    if not self.driver_checked:
                        self.driver_checked = True
                        threading.Thread(target=self.check_driver, daemon=True).start()
                    self.wait_reconnect(2.0)  # Tries again by itself
                    continue
            with self.jobs_lock:
                jobs, self.jobs = self.jobs, []
            # Key presses that queued up while a picture was coming go out as one command
            merged = []
            for line, note, done, progress in jobs:
                if line.startswith("key ") and merged and merged[-1][0].startswith("keys ") and \
                        merged[-1][0].count(" ") < MAX_KEYS_LINE:  # The helper reads 2048 bytes a line
                    merged[-1] = (merged[-1][0] + " " + line[4:], note, None, None)
                elif line.startswith("key "):
                    merged.append(("keys " + line[4:], note, None, None))
                else:
                    merged.append((line, note, done, progress))
            for k, (line, note, done, progress) in enumerate(merged):
                code, lines = self.session.cmd(line, progress)
                if note:
                    ok = [l for l in lines if l.startswith(("OK", "ERR"))]
                    self.set_status("%s: %s" % (note, ok[-1] if ok else "exit %d" % code))
                quiet = QUIET_AFTER.get(line.split(" ", 1)[0])
                if quiet:  # Nothing else goes to the calculator meanwhile (see QUIET_AFTER)
                    self.quiet_until = time.time() + quiet
                if done is not None:
                    try:
                        done(code, lines)  # On this thread: it hands any window work to Tk
                    except Exception:  # A caller's mistake must never stop the link
                        log_error("handing back the answer to %r" % line.split(" ", 1)[0])
                if code == 4 and self.link_dead():
                    for _, _, d, _ in merged[k + 1:]:  # Everyone waiting gets an answer
                        if d is not None:
                            d(4, ["ERR the link closed"])
                    break
            if self.session is None:
                continue
            # Keep-alive: the calculator switches itself off after a few idle minutes and only a
            # key press counts as use, so while it's connected a key that does nothing goes out
            # once a minute when you haven't typed
            if time.time() < self.quiet_until:
                time.sleep(0.05)
                continue
            ka = getattr(self.calc, "keepalive_key", None)
            if ka and KEEPALIVE_S and time.time() - max(self.last_key, self.last_keepalive) >= KEEPALIVE_S:
                self.last_keepalive = time.time()
                self.session.cmd("key " + ka)
            # While typing, keys go out as they come and the picture waits: a screenshot can't be
            # interrupted, so a key typed during one waits for all of it (1.4 s on the 84 Plus CE)
            fast = self.fast_state == "on"
            if time.time() - self.last_key < (FAST_HOLDOFF if fast else self.calc.shot_holdoff):
                time.sleep(0.015)
                continue
            tmp = self.frame_path + ".new"
            code, lines = self.session.cmd(("snap " if fast else "shot ") + tmp)
            if fast:
                self.fast_result(code, lines)
            if code == 0:
                try:
                    with open(tmp, "rb") as f:
                        data = f.read()
                except OSError:
                    data = None
                if data:
                    # The window draws from memory (never from the file, which Windows wouldn't
                    # let us replace while the window read it: frames were dropped); the file is
                    # for screenshots, copies and recordings
                    self.latest = data
                    self.frames += 1
                    self.frames_total += 1
                    for _ in range(3):
                        try:
                            os.replace(tmp, self.frame_path)
                            break
                        except OSError:
                            time.sleep(0.005)
                    with self.rec_lock:
                        if self.rec is not None:
                            self.rec.add(self.frame_path)
            elif self.link_dead():
                continue
            else:
                time.sleep(0.5)

    # ---- Fast mode (TI-84 Plus CE, experimental) ----
    # A small assembly program (tools/fast84: CSFAST) installs a key hook on the calculator
    # that compresses the screen into AppVars on request; `snap` reads them in ~0.15 s instead
    # of the 1.2-1.4 s screenshot. The UI calls set_fast(True/False) and reads fast_status();
    # changes are reported to fast_listeners (on the link thread: hand window work to Tk).
    def fast_supported(self):
        """(True, "") when Fast mode can be offered for this calculator, else (False, why)"""
        if self.calc.slug != "ti84":
            return False, "Fast mode is for the TI-84 Plus CE"
        if not os.path.isfile(FAST84_PRGM):
            return False, "CSFAST.8xp is missing from tools/fast84"
        osv = self.info.get("os", "")
        if osv and _os_tuple(osv) >= (5, 5):
            return False, ("OS %s doesn't run assembly programs: Fast mode needs arTIfiCE on OS 5.5 "
                           "or newer" % osv)
        return True, ""

    def fast_status(self):
        """{supported, why, state, note, on}: state is off | starting | on | stopping | lost | error"""
        ok, why = self.fast_supported()
        return {"supported": ok, "why": why, "state": self.fast_state, "note": self.fast_note,
                "on": self.fast_state == "on"}

    def set_fast(self, on, done=None):
        """Turns Fast mode on or off on the calculator (queued on the link thread, a few
        seconds). done(ok, note) is called on the link thread when it's finished."""
        ok, why = self.fast_supported()
        if on and not ok:
            self._fast_set("error", why)
            if done is not None:
                done(False, why)
            return
        self._fast_set("starting" if on else "stopping",
                       "Starting Fast mode on the calculator..." if on else "Turning Fast mode off...")

        def finished(code, lines):
            last = [l for l in lines if l.startswith(("OK", "ERR"))]
            text = last[-1][4:].strip() if last and last[-1].startswith("ERR") else ""
            if on and code == 0:
                self.fast_misses = 0
                self._fast_set("on", "Fast mode is on (experimental)")
            elif on:
                self._fast_set("error", text or "Fast mode didn't start (exit %d)" % code)
            elif code == 0:
                self._fast_set("off", "Fast mode is off; the calculator is as it was")
            else:
                self._fast_set("error", text or "Fast mode didn't turn off (exit %d)" % code)
            if done is not None:
                done(self.fast_state == ("on" if on else "off"), self.fast_note)
        self.queue("fast %s %s" % ("on" if on else "off", FAST84_PRGM), None, finished)

    def _fast_set(self, state, note):
        changed = (state, note) != (self.fast_state, self.fast_note)
        self.fast_state, self.fast_note = state, note
        if note:
            self.set_status(note)
        if changed:
            for fn in list(self.fast_listeners):
                try:
                    fn(state, note)
                except Exception:  # A listener's mistake must never stop the link
                    pass

    def fast_result(self, code, lines):
        """What a `snap` said: a frame by Fast mode, a fallback shot, or Fast mode gone"""
        gone = [l for l in lines if l.startswith("FAST gone")]
        if gone:
            # CSSNAP isn't there: a RAM reset (or someone deleted it) took Fast mode away
            self._fast_set("lost", "Fast mode stopped: the calculator no longer has it (was it "
                                   "reset?). Back to normal screenshots.")
            return
        if any(l.startswith("FAST away") for l in lines):
            # Graph, table, Y=, mode...: reading Fast mode's AppVars there would send the
            # calculator to its home screen, so these screens come by normal screenshots
            if self.fast_misses < FAST_MISSES_WARN:
                self.set_status("Fast mode works on the home screen (and its menus); normal "
                                "screenshots on this screen")
            self.fast_misses = FAST_MISSES_WARN
        elif any(l.startswith("FAST fallback") for l in lines):
            self.fast_misses += 1
            if self.fast_misses == FAST_MISSES_WARN:
                why = [l for l in lines if l.startswith("FAST fallback")][-1][len("FAST fallback "):]
                self.set_status("Fast mode can't take this screen (%s): normal screenshots meanwhile" % why)
        elif code == 0:
            if self.fast_misses >= FAST_MISSES_WARN:
                self.set_status("Fast mode is back")
            self.fast_misses = 0

    def link_dead(self):
        s = self.session
        if s is not None and not s.alive():
            self.session = None
            if s.dead:  # It went quiet and was stopped: say so in errors.log too
                log_error("talking to the %s" % self.calc.title, detail=s.dead)
                self.set_status("The %s stopped answering (%s). Reconnecting..." %
                                (self.calc.title, s.dead))
                s.close(timeout=1)
            else:
                self.set_status("The link closed (cable pulled?). Reconnecting when it's back...")
            self.wait_reconnect(2.0)
            return True
        return False

    def check_driver(self):
        """Link thread helper: a calculator that won't open may have no driver CalcSuite can use
        (a new PC, or TI's own driver). If so, the app offers to set WinUSB up: Zadig is only
        the fallback now."""
        try:
            import calc_doctor
            report = calc_doctor.diagnose(probe=False)
        except Exception:
            log_error("checking the %s's driver" % self.calc.title)
            return
        for e in report.get("errors", []):
            log_error("checking the %s's driver" % self.calc.title, detail=e)
        pid = "%04x" % self.calc.pid
        for d in report.get("devices", []):
            if d.get("pid") == pid and d.get("present") and d.get("fix") == "install_winusb":
                self.app.root.after(0, lambda d=d: self.app.offer_driver(self, d))
                return

    def wait_reconnect(self, seconds):
        """Until the Reconnect button, or `seconds` have passed"""
        self.want_reconnect = False
        t = time.time()
        while self.running and not self.want_reconnect and time.time() - t < seconds:
            time.sleep(0.1)

    def reconnect(self):
        self.released = False
        self.let_go.clear()
        if self.session is not None:
            self.session.close()
            self.session = None
        self.want_reconnect = True
        self.set_status("Connecting...")

    def release(self):
        """Lets go of the calculator so another program (TI's) can open it, until Reconnect.
        let_go is set once the link thread has closed its session."""
        self.let_go.clear()
        self.released = True
        self.set_status("CalcSuite has let go of the %s so TI's software can use it. Close that, "
                        "then press Reconnect (Calculator info)." % self.calc.title)

    def queue(self, line, note=None, done=None, progress=None):
        """A command for the link thread. done(code, lines) is called on the link thread when it
        has run; progress(bytes, total) during a transfer."""
        with self.jobs_lock:
            self.jobs.append((line, note, done, progress))
            if line.startswith(("key ", "keys ")):
                self.last_key = time.time()
                for tap in list(getattr(self, "key_taps", ())):  # A macro recording (macros.py)
                    tap(line)

    def run_batch(self, cmds, timeout=900):
        """[(line, progress)] on the link thread, waited for: [(code, lines)]. For a worker
        thread only (never Tk's)."""
        results = [None] * len(cmds)
        left = [len(cmds)]
        ev = threading.Event()
        for k, (line, progress) in enumerate(cmds):
            def done(code, lines, k=k):
                results[k] = (code, lines)
                left[0] -= 1
                if left[0] == 0:
                    ev.set()
            self.queue(line, None, done, progress)
        t0 = time.time()
        while cmds and not ev.wait(0.5):
            if not self.running or time.time() - t0 > timeout:
                break
        return [r or (4, ["ERR no answer (closed, or the cable?)"]) for r in results]

    def set_status(self, text):
        if self.running:
            try:
                self.app.root.after(0, self.status.set, text)
            except (tk.TclError, RuntimeError):
                pass

    def connected(self):
        return self.session is not None

    # ---- Frames ----
    def draw_frame(self):
        """The newest frame onto every view showing it (Tk's thread; App.pump calls it)"""
        data, self.latest = self.latest, None
        if not (self.running and data):
            return
        visible = [v for v in self.views if v.visible()]
        try:
            img = tk.PhotoImage(master=self.app.root, data=data, format="ppm")
        except tk.TclError:
            return
        self.image = img
        self.native = (img.width(), img.height())
        for v in visible:
            v.show(img)

    def frame_rgb(self):
        try:
            return recorder.read_ppm(self.frame_path)
        except (OSError, ValueError):
            return None

    def tick(self):
        """Once a second (the App's tick): the frame rate, the recording's time limit"""
        dt = time.time() - self.t0
        if dt >= 5:
            self.fps = self.frames / dt if self.frames else 0.0
            self.frames, self.t0 = 0, time.time()
        if self.session is None:
            self.fps = 0.0
        with self.rec_lock:
            if self.rec is not None and self.rec.seconds() >= recorder.MAX_SECONDS:
                self.app.root.after(0, self.toggle_record)

    def rec_seconds(self):
        with self.rec_lock:
            return None if self.rec is None else self.rec.seconds()

    # ---- Keys ----
    def key_names(self, ev):
        """The calculator key names for a PC key press"""
        names = self.calc.tk_keys.get(ev.keysym)
        if names is None and ev.char and ev.char.isprintable():
            names = [ev.char]
        if ev.state & 0x4:  # Ctrl
            key = ev.keysym.lower() if len(ev.keysym) == 1 else (names[0] if names else "")
            names = ["ctrl+" + key]
        return names or []

    def on_key(self, ev):
        ctrl, shift = ev.state & 0x4, ev.state & 0x1
        if ctrl and not shift and ev.keysym.lower() == "c":
            self.copy_screen()  # The PC's clipboard (Ctrl+Shift+C: the handheld's own copy)
            return
        if ctrl and not shift and ev.keysym.lower() == "v":
            self.paste_text()
            return
        if ctrl and shift and ev.keysym.lower() in ("c", "v"):
            ev.keysym = ev.keysym.lower()
        if ev.keysym in ("Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R",
                         "Caps_Lock", "Win_L", "Win_R", "Num_Lock"):
            return
        if not self.keys_on.get() or self.session is None:
            return
        names = self.key_names(ev)
        codes = []
        for name in names:
            code = self.calc.code_for(name)
            if code is None:
                self.set_status("No %s key for %r" % (self.calc.title, name))
                return
            codes.append(code)
        for name, code in zip(names, codes):
            self.queue("key " + self.calc.key_fmt % code, "Key %s" % name)
        if names:
            self.pressed(ev.keysym, ev.char, names)

    def pressed(self, keysym, char, names, text=None):
        """Remembers a press for the Last key line, the key-history strip and the Keys panel"""
        label = self.calc.keys_label(names) if names else (text or "")
        self.history.append(label)
        del self.history[:-HISTORY]
        self.last_press.set("Last key: " + (text or self.calc.describe_press(keysym, char, names)))
        for fn in list(self.listeners):
            try:
                fn(keysym)
            except tk.TclError:
                pass

    def send_key(self, name):
        if not self.keys_on.get() or self.session is None or not name:
            return False
        code = self.calc.code_for(name)
        if code is not None:
            self.queue("key " + self.calc.key_fmt % code, "Key %s" % name)
            return True
        return False

    def send_names(self, names, what=None):
        """Several key names (a mouse action, a symbol), in order; remembered as one press"""
        if not names or not self.keys_on.get() or self.session is None:
            return False
        codes = [self.calc.resolve(n) for n in names]
        if any(c is None for c in codes):
            return False
        self.queue("keys " + " ".join(self.calc.key_fmt % c for c in codes))
        self.pressed(None, None, names, text=what)
        return True

    def send_codes(self, codes, what):
        if self.session is None:
            self.set_status("Not connected yet")
            return False
        if not self.keys_on.get():
            self.set_status("The keyboard is off for the %s (Keyboard)" % self.calc.title)
            return False
        # One command for the whole press (a palette symbol is ~80 keys): split in two, a
        # failed first half would still send the second's arrows and enter into the document
        for i in range(0, len(codes), MAX_KEYS_LINE):
            self.queue("keys " + " ".join(self.calc.key_fmt % c for c in codes[i:i + MAX_KEYS_LINE]))
        self.history.append(what)
        del self.history[:-HISTORY]
        self.last_press.set("Last key: " + what)
        for fn in list(self.listeners):
            fn(None)
        return True

    def paste_text(self, text=None):
        """The PC clipboard's text typed into the calculator, key by key"""
        if self.session is None:
            self.set_status("Not connected yet")
            return
        if text is None:
            try:
                text = self.app.root.clipboard_get()
            except tk.TclError:
                self.set_status("The clipboard has no text")
                return
        text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", "    ")
        if len(text) > PASTE_MAX:
            self.set_status("Too long to paste: %d characters (up to %d)" % (len(text), PASTE_MAX))
            return
        codes, missing = self.calc.paste_keys(text, self.info)
        if missing:
            shown = " ".join(sorted(repr(c) for c in missing))
            self.set_status("Can't type %s on the %s: nothing pasted" % (shown, self.calc.title))
            return
        # Never cut one symbol's keys (an Nspire palette walk) into two commands: a failed first
        # half would leave the second's arrows and enter to the document
        for run in calc_models.chunks(codes, 64):
            self.queue("keys " + " ".join(self.calc.key_fmt % c for c in run))
        self.palette_at = None  # A pasted palette symbol moved the palette's remembered place
        self.set_status("Pasting %d characters..." % len(text))
        shown = text.replace("\n", " ↵ ")
        self.pressed(None, None, [], text="paste " + (shown[:24] + "..." if len(shown) > 24 else shown))

    def copy_screen(self):
        """The calculator's screen, as a picture, on the PC clipboard"""
        if not os.path.isfile(self.frame_path):
            self.set_status("No picture yet")
            return
        try:
            w, h, rgb = recorder.read_ppm(self.frame_path)
            set_clipboard_image(w, h, rgb, 2 if w >= 320 else 6)
            self.set_status("Screen copied: paste it anywhere (Ctrl+V)")
        except (OSError, ValueError) as e:
            self.set_status("Couldn't copy: %s" % e)

    # ---- The mouse on the screen (x, y in the calculator's pixels) ----
    def on_click(self, x, y):
        names = self.calc.click(x, y, self.frame_rgb())
        if names and self.send_names(names, "click → " + self.calc.keys_label(names)):
            self.click_acted = time.time()

    def on_double(self):
        if time.time() - self.click_acted < 0.6:
            return  # The single click already picked (an 84 menu line)
        if self.calc.double_click:
            self.send_names([self.calc.double_click], "double click → " +
                            self.calc.calc_label(self.calc.double_click))

    def on_button(self, which):
        name = {"right": self.calc.right_click, "middle": self.calc.middle_click}[which]
        if name:
            self.send_names([name], "%s click → %s" % (which, self.calc.calc_label(name)))

    def on_wheel(self, delta, shift):
        if not self.keys_on.get() or self.session is None:
            return
        steps = max(1, min(5, abs(delta) // 120))
        up, down, left, right = self.calc.wheel
        name = (left if delta > 0 else right) if shift else (up if delta > 0 else down)
        with self.jobs_lock:  # A spinning wheel never queues more than a screenful
            if len(self.jobs) > 12:
                return
        for _ in range(steps):
            self.send_key(name)
        self.pressed(None, None, [name], text="wheel → " + self.calc.calc_label(name))

    # ---- Screenshots, recordings ----
    def capture_stem(self):
        os.makedirs(os.path.join(KIT, "captures"), exist_ok=True)
        return os.path.join(KIT, "captures", time.strftime(self.calc.slug + "-%Y%m%d-%H%M%S"))

    def screenshot(self):
        if not os.path.isfile(self.frame_path):
            self.set_status("No picture yet")
            return
        out = self.capture_stem() + ".png"
        try:
            nspire_link.ppm_to_png(self.frame_path, out, 2)
            self.set_status("Saved %s" % out)
        except (OSError, ValueError) as e:
            self.set_status("Couldn't save: %s" % e)

    def toggle_record(self):
        with self.rec_lock:
            rec = self.rec
            if rec is None:
                if self.app.burn_keys.get():  # The key strip in every frame, from the start
                    burner = key_strip.Burner(lambda: list(self.history))
                    w = self.native[0] if self.native else 320
                    scale = max(1, SCALE // burner.zoom_for(w))
                    self.rec = recorder.Recorder(scale, burner)
                else:
                    self.rec = recorder.Recorder(SCALE)
                if os.path.isfile(self.frame_path):
                    self.rec.add(self.frame_path)  # The recording starts with what's on screen
            else:
                self.rec = None
        self.app.recording_changed(self)
        if rec is None:
            self.set_status("Recording (up to %d s)... press Stop to save" % recorder.MAX_SECONDS)
            self.offer_ffmpeg()
            return
        if not rec.frames:
            self.set_status("Nothing was recorded")
            return
        self.set_status("Saving the recording...")
        stem = self.capture_stem()

        def work():
            try:
                paths = rec.save(stem)
                self.set_status("Saved " + " and ".join(os.path.basename(p) for p in paths) +
                                " in " + os.path.dirname(stem))
            except Exception as e:  # A recording must never take the window down
                self.set_status("Couldn't save the recording: %s" % e)

        threading.Thread(target=work, daemon=True).start()

    _ffmpeg_asked = False  # Once per run, for every calculator

    def offer_ffmpeg(self):
        """No ffmpeg: offer to download it once, while the recording runs (MP4 needs it; GIF
        doesn't)"""
        if recorder.find_ffmpeg() or Mirror._ffmpeg_asked:
            return
        Mirror._ffmpeg_asked = True
        if not messagebox.askyesno(
                "MP4 recordings", "Recordings are saved as a GIF. For an MP4 as well, CalcSuite "
                "needs ffmpeg (free, about %d MB, downloaded once).\n\nDownload it now? It "
                "downloads while you record.\n\n(No: GIF only. OBS or any screen recorder works "
                "too.)" % recorder.FFMPEG_DOWNLOAD_MB, parent=self.root):
            return

        def work():
            shown = [-1]

            def progress(done, total):
                pct = done * 100 // total if total else -1
                if pct != shown[0] and pct % 5 == 0:  # Every 5 %, not every 64 KB
                    shown[0] = pct
                    self.set_status("Recording... downloading ffmpeg %d%%" % pct)
            try:
                recorder.download_ffmpeg(progress)
                self.set_status("Recording... ffmpeg is ready: the MP4 comes with the GIF")
            except Exception as e:  # Never takes the window down; GIF still works
                self.set_status("Recording... couldn't get ffmpeg (%s): GIF only" % e)

        threading.Thread(target=work, daemon=True).start()

    # ---- Sending ----
    def send_program(self):
        if self.calc.slug != "nspire":  # The 84 and the 89: TI-Basic text or a TI file
            send_ti.send_from_window(self, KIT)
            return
        path = filedialog.askopenfilename(
            parent=self.root, title="Send to the handheld",
            initialdir=os.path.join(KIT, "programs"),
            filetypes=[("Python programs and TI documents", "*.py *.tns"), ("All files", "*.*")])
        if not path:
            return
        path, error = prepare_for_nspire(path)
        if error:
            self.set_status(error)
            return
        self.send_nspire_files([(path, "/")])

    def send_nspire_files(self, files, done=None):
        """[(local file, calculator folder)] to the Nspire: makes a missing folder, asks before
        replacing a file of the same name. done(ok, message) on Tk's thread."""
        folders = sorted(set(f for _p, f in files))

        def work():
            names = {}
            for folder in folders:
                code, lines = self.run_batch([("ls " + folder, None)])[0]
                if code and folder != "/":
                    self.run_batch([("mkdir " + folder, None)])
                    code, lines = 0, []
                import calc_files as cf
                names[folder] = {calc_manager.shown(i["name"]).lower()
                                 for i in cf.parse_nspire_ls(lines)} if code == 0 else set()
            self.app.root.after(0, lambda: ask(names))

        def ask(names):
            same = [os.path.basename(p) for p, f in files if os.path.basename(p).lower() in names[f]]
            if same and not messagebox.askyesno(
                    "Replace?", "%s %s already on the handheld. Replace?" % (
                        ", ".join(same[:12]), "is" if len(same) == 1 else "are"), parent=self.root):
                self.set_status("Not sent")
                if done:
                    done(False, "Not sent")
                return
            state = {"left": len(files), "errors": []}
            for p, folder in files:
                base = os.path.basename(p)
                remote = folder.rstrip("/") + "/" + base

                def sent(code, lines, base=base):
                    if code:
                        ok = [l for l in lines if l.startswith("ERR")]
                        state["errors"].append("%s: %s" % (base, ok[-1][4:] if ok else code))
                    state["left"] -= 1
                    if state["left"] == 0:
                        msg = ("Sent %s" % ", ".join(os.path.basename(p) for p, _f in files[:4]) +
                               (" and %d more" % (len(files) - 4) if len(files) > 4 else "")
                               if not state["errors"] else "Not sent: " + "; ".join(state["errors"][:3]))
                        self.set_status(msg)
                        if done:
                            self.app.root.after(0, done, not state["errors"], msg)

                def progress(n, total, base=base):
                    self.set_status("Sending %s: %d%%" % (base, 100 * n // total if total else 0))
                self.queue("put %s|%s" % (os.path.abspath(p), remote), None, sent, progress)
        threading.Thread(target=work, daemon=True).start()

    def open_files(self):
        """The Files panel of this calculator's tab"""
        self.app.show_tab(self.calc.pid)
        self.app.tabs[self.calc.pid].show_section("Files")

    def stop(self, tk_side=True):
        """Ends this calculator's link. tk_side=False: only the part that needs no Tk (App.quit
        runs that for every calculator at once on worker threads)."""
        if tk_side and self.manager is not None and self.manager.alive():
            self.manager.close()
        self.running = False
        self.want_reconnect = True
        with self.rec_lock:
            rec, self.rec = self.rec, None
        if rec is not None and rec.frames:  # Closing mid-recording keeps what was recorded
            try:
                rec.save(self.capture_stem())
            except Exception:
                pass
        if self.session is not None:
            self.session.close(timeout=0.8)
        try:
            os.remove(self.frame_path)
        except OSError:
            pass


MAX_KEYS_LINE = 200  # Key codes in one "keys" command: 7 bytes each, the helper reads 2048 a line


class ScreenView(object):
    """A calculator's picture in a Label, as big as its space allows with an even margin round
    it: a whole number of times when that fills most of it (crisp), else in half steps
    (window_chrome.screen_scale)"""

    def __init__(self, parent, mirror, big, visible, fit, bg=th.BG):
        self.m = mirror
        self.big = big
        self.visible = visible   # () -> True when it's on screen
        self.fit = fit           # () -> (width, height) it may use
        self.zoom = None         # (zoom, subsample) of the shown picture
        self.photo = None
        self.source = None       # The frame the shown picture was made from
        self.label = tk.Label(parent, bg=bg, bd=0, highlightthickness=0, cursor="crosshair" if big else "hand2")
        mirror.views.append(self)

    def scale_for(self, w, h):
        """(zoom, subsample) for a w x h picture in the space fit() gives"""
        aw, ah = self.fit()
        return wc.screen_scale(w, h, aw, ah, wc.SCREEN_MARGIN if self.big else wc.TILE_MARGIN)

    def show(self, img=None):
        img = img or self.m.image
        if img is None:
            return
        w, h = img.width(), img.height()
        z, sub = self.scale_for(w, h)
        shown = img.zoom(z, z) if z > 1 else img
        if sub > 1:  # A half step (x 2.5 = x 5 then every other pixel) or smaller than itself
            shown = shown.subsample(sub, sub)
        self.zoom = (z, sub)
        self.photo = shown
        self.source = img
        try:
            self.label.configure(image=shown)
        except tk.TclError:
            pass

    def refit(self):
        """Its space changed size: draws it again only when the scale changes (a drag sends
        many of these, and re-zooming the picture on each one smears the window)"""
        img = self.m.image
        if img is None:
            return
        if self.photo is not None and self.source is img and \
                self.scale_for(img.width(), img.height()) == self.zoom:
            return
        self.show()

    def to_calc(self, ev):
        """A mouse event -> (x, y) in the calculator's pixels, or None outside the picture"""
        if self.photo is None or self.zoom is None or self.m.native is None:
            return None
        pw, ph = self.photo.width(), self.photo.height()
        ox = (self.label.winfo_width() - pw) // 2
        oy = (self.label.winfo_height() - ph) // 2
        x, y = ev.x - ox, ev.y - oy
        if not (0 <= x < pw and 0 <= y < ph):
            return None
        nw, nh = self.m.native
        return x * nw // pw, y * nh // ph


class Tab(object):
    """A calculator's tab: the big screen, its buttons and the side panel"""

    def __init__(self, app, mirror):
        import ui_panels
        self.app = app
        self.m = mirror
        calc = mirror.calc
        self.frame = tk.Frame(app.content, bg=th.BG)
        mirror.root = self.frame
        self.popped = False
        # The screen side takes what's left once the panel has its width (packed last, below)
        left = tk.Frame(self.frame, bg=th.BG)
        self.screen_box = tk.Frame(left, bg=th.BG, width=640, height=480)
        self.screen_box.pack(fill="both", expand=True)
        self.screen_box.pack_propagate(False)
        self.view = ScreenView(self.screen_box, mirror, True, self.visible, self.fit)
        self.view.label.pack(fill="both", expand=True)
        lab = self.view.label
        lab.bind("<Button-1>", self.on_click)
        lab.bind("<Double-Button-1>", lambda e: mirror.on_double())
        lab.bind("<Button-3>", lambda e: mirror.on_button("right"))
        lab.bind("<Button-2>", lambda e: mirror.on_button("middle"))
        lab.bind("<MouseWheel>", lambda e: mirror.on_wheel(e.delta, e.state & 0x1))
        self.screen_box.bind("<Configure>", lambda e: self.view.refit())

        self.strip = tk.Frame(left, bg=th.BG, height=26)  # The key history
        self.strip_on = False
        # The button row: the four main buttons, the pinned macros after them, "More" (the
        # rest) on the right, and Reconnect beside it only while the link is down
        bar = tk.Frame(left, bg=th.BG)
        bar.pack(fill="x", pady=(8, 0))
        self.button_row = bar
        self.main_buttons = {}
        for name, cmd in (("Screenshot", mirror.screenshot), ("Record", mirror.toggle_record),
                          ("Send program...", mirror.send_program), ("Copy answer", self.copy_answer)):
            b = th.button(bar, name, cmd)
            b.pack(side="left", padx=(0 if not self.main_buttons else 6, 0))
            self.main_buttons[name] = b
        self.rec_btn = self.main_buttons["Record"]
        # More (and Reconnect) are packed before the pins, so a narrow tab cuts a pin, never them
        self.more_btn = th.button(bar, "More ▾", self.show_more)
        self.more_btn.pack(side="right")
        self.pins = tk.Frame(bar, bg=th.BG)  # The pinned macros' buttons (macros_ui.MacroBox)
        self.pins.pack(side="left")
        self.reconnect_btn = th.button(bar, "Reconnect", mirror.reconnect)
        self.reconnect_shown = False
        self.more = th.menu(self.frame)
        for label, cmd in (("Copy screen", mirror.copy_screen), ("Paste text", lambda: mirror.paste_text()),
                           ("Reconnect", mirror.reconnect), (None, None),
                           ("Program editor...", self.open_editor),
                           ("Make a picture...", self.open_picture),
                           ("Macros...", lambda: self.panel.show("Macros"))):
            if label is None:
                self.more.add_separator()
            else:
                self.more.add_command(label=label, command=cmd)
        self.more_fixed = int(self.more.index("end")) + 1  # Entries after these: pins that didn't fit
        self.pin_buttons, self.pins_hidden = [], []
        bar.bind("<Configure>", lambda e: self.fit_pins(), add="+")
        # The checkboxes in one row (packed before the last key, so a long key name gets cut,
        # never a checkbox)
        line = tk.Frame(left, bg=th.BG)
        line.pack(fill="x", pady=(8, 0))
        self.check_row = line
        self.hist_var = tk.BooleanVar(master=self.frame, value=False)
        th.check(line, "Keyboard", mirror.keys_on).pack(side="right")
        th.check(line, "Key history", self.hist_var, self.toggle_history).pack(side="right", padx=(0, 14))
        th.check(line, "Show keys in recordings", app.burn_keys).pack(side="right", padx=(0, 14))
        if mirror.calc.slug == "ti84":  # Fast mode (experimental): ~7 frames/s on the home screen
            self.fast_var = tk.BooleanVar(master=self.frame, value=False)
            th.check(line, "Fast mode (experimental)", self.fast_var, self.toggle_fast).pack(
                side="right", padx=(0, 14))
            mirror.fast_listeners.append(
                lambda state, note: self.app.root.after(0, self.fast_changed, state, note))
        tk.Label(line, textvariable=mirror.last_press, bg=th.BG, fg=th.DIM, anchor="w",
                 font=th.HINT).pack(side="left", fill="x", expand=True)
        tk.Label(left, textvariable=mirror.status, bg=th.BG, fg=th.DIM, anchor="w", justify="left",
                 font=th.HINT, wraplength=640).pack(fill="x", pady=(6, 0))
        self.left = left
        self.panel = ui_panels.SidePanel(self.frame, app, mirror)
        self.panel.frame.pack(side="right", fill="y")
        self.panel.frame.configure(width=self.panel_width_now())
        # A handle between the screen and the panel: drag it to make the panel wider or narrower
        grip = tk.Frame(self.frame, bg=th.BG, width=8, cursor="sb_h_double_arrow")
        grip.pack(side="right", fill="y", pady=(10, 10))
        line = tk.Frame(grip, bg=th.PANEL2, width=2)
        line.place(relx=0.5, rely=0.5, relheight=0.12, anchor="center")
        self.grip_line = line
        # While dragging only this guide line moves; the panel changes width once, on release
        # (laying the window out again on every mouse move is what smeared it)
        self.guide = None  # The guide line and its "Default width" tag: made on the first drag
        self.drag_w = None
        grip.bind("<B1-Motion>", self.drag_panel)
        grip.bind("<ButtonRelease-1>", self.drop_panel)
        grip.bind("<Double-Button-1>", lambda e: self.set_panel_width(None))
        grip.bind("<Enter>", lambda e: line.configure(bg=th.ACCENT))
        grip.bind("<Leave>", lambda e: self.drag_w is None and line.configure(bg=th.PANEL2))
        left.pack(side="left", fill="both", expand=True, padx=(14, 8), pady=(10, 10))
        mirror.listeners.append(self.key_pressed)
        import macros_ui  # The macros (pinned buttons, Ctrl+1..9) before the Macros panel is opened
        self.macro_box = macros_ui.box_for(mirror)
        self.macro_box.listeners.append(self.refresh_pins)
        self.refresh_pins()
        # The default width follows the window (a share of it); a dragged width stays put
        self.fit_job = None
        self.frame.bind("<Configure>", self.window_resized)

    panel_width = 0  # The width the user dragged the side panel to (every tab, this session; 0: the default)

    SNAP = 60  # Pixels: a drag this close to the default width snaps to it
    PANEL_SHARE = 0.47  # The default: the panel gets ~half the window (its left edge at ~1000 of 1920)

    def tab_width(self):
        """The width a calculator's tab has (every tab fills the same space)"""
        w = self.app.content.winfo_width()
        if w <= 1:  # Not laid out yet: the window's own width
            self.app.root.update_idletasks()
            w = self.app.content.winfo_width()
            if w <= 1:
                w = self.app.root.winfo_reqwidth()
        return w

    def panel_limits(self):
        """(narrowest, widest) the panel may be: the screen side keeps room for its checkbox
        row (the 84's has four)"""
        import ui_panels
        keep = max(360, self.check_row.winfo_reqwidth() + 30)
        lo = ui_panels.WIDTH - 70
        return lo, max(lo, self.tab_width() - 36 - keep)  # 36: the paddings and the handle

    def default_panel_width(self):
        """A share of the window, but narrower (down to its narrowest) when that lets the
        calculator's screen be drawn bigger: the screen gets the width it can use (a wide 89
        screen in a tall window was a small picture in a big black box), the panel the rest"""
        lo, hi = self.panel_limits()
        share = max(lo, min(hi, int(round(self.tab_width() * self.PANEL_SHARE))))
        h = self.screen_box.winfo_height()
        if h <= 1:
            return share
        nw, nh = self.m.native or self.m.calc.native
        most = self.tab_width() - 36 - lo  # The screen side's width with the panel at its narrowest
        want = wc.screen_width_wanted(nw, nh, most, h)
        return max(lo, min(share, self.tab_width() - 36 - want))

    def panel_width_now(self):
        """The width the panel should have now: the dragged one (within the limits), else the default"""
        if Tab.panel_width:
            lo, hi = self.panel_limits()
            return max(lo, min(hi, Tab.panel_width))
        return self.default_panel_width()

    def window_resized(self, ev):
        """The window changed size: the panel keeps its share (once the resize settles a little:
        one layout, not one per pixel)"""
        if self.fit_job is not None:
            self.frame.after_cancel(self.fit_job)
        self.fit_job = self.frame.after(40, self.fit_panel)

    def fit_panel(self):
        self.fit_job = None
        if self.drag_w is not None:
            return
        w = self.panel_width_now()
        if self.panel.frame.winfo_reqwidth() != w:
            self.panel.frame.configure(width=w)

    def drag_panel(self, ev):
        """Dragging the handle: a guide line shows where the panel's edge will go; near the
        default width it jumps there (mint, with a tag)"""
        f = self.panel.frame
        right = f.winfo_x() + f.winfo_width()  # The panel's right edge in the tab
        default = self.default_panel_width()
        lo, hi = self.panel_limits()
        w = max(lo, min(right - (ev.x_root - self.frame.winfo_rootx()), hi))
        snapped = abs(w - default) <= self.SNAP
        if snapped:
            w = default
        self.drag_w = w
        x = right - w - 5  # The middle of the handle, left of the panel's new edge
        color = th.ACCENT if snapped else th.DIM
        self.grip_line.configure(bg=color)
        line, tag = self.guide or self.make_guide()
        # Their own little windows, moved over the tab: Windows composes them, so nothing
        # under them repaints (a widget moved inside the window left trails)
        gx, gy = self.frame.winfo_rootx() + x, self.frame.winfo_rooty() + 10
        h = max(1, self.frame.winfo_height() - 20)
        line.configure(bg=color)
        line.geometry("3x%d+%d+%d" % (h, gx, gy))
        if line.state() == "withdrawn":
            line.deiconify()
        if snapped:
            tag.geometry("+%d+%d" % (gx - tag.winfo_reqwidth() - 6, gy + 4))
            if tag.state() == "withdrawn":
                tag.deiconify()
        elif tag.state() != "withdrawn":
            tag.withdraw()

    def make_guide(self):
        def floating():
            w = tk.Toplevel(self.frame)
            w.withdraw()
            w.overrideredirect(True)
            w.attributes("-topmost", True)
            return w
        line = floating()
        tag = floating()
        tk.Label(tag, text="Default width", bg=th.ACCENT, fg="#000000", font=(th.FONT, 9, "bold"),
                 padx=6, pady=1).pack()
        tag.update_idletasks()
        self.guide = (line, tag)
        return self.guide

    def drop_panel(self, ev):
        """The drag ended: the panel (on every tab) takes the width the guide showed"""
        w, self.drag_w = self.drag_w, None
        if self.guide:
            for g in self.guide:
                g.withdraw()
        self.grip_line.configure(bg=th.ACCENT)
        if w is not None:
            # Dropped on the default (it snapped there): it follows the window again
            self.set_panel_width(None if w == self.default_panel_width() else w)

    def set_panel_width(self, w):
        """The panel's width on every tab; None: the default (a share of the window)"""
        Tab.panel_width = w or 0
        for t in self.app.tabs.values():
            t.fit_panel()

    def open_editor(self):
        """The program editor, aimed at this calculator (TI-Basic or Nspire Python)"""
        import editor
        editor.open_editor(self.app, list(self.app.mirrors.values()), initial_target=self.m)

    def copy_answer(self):
        import data_bridge
        data_bridge.copy_answer(self.m, self.button_row, self.m.set_status)

    def open_picture(self):
        import picture_window
        picture_window.open_for(self.m, KIT)

    def show_more(self):
        """More ▾: the rest of the tab's commands, under the button"""
        b = self.more_btn
        box = getattr(self, "macro_box", None)
        self.more.delete(self.more_fixed, "end")  # The pins that didn't fit the row, again
        if box is not None and getattr(self, "pins_hidden", None):
            self.more.add_separator()
            for m in self.pins_hidden:
                self.more.add_command(label="Macro: " + m["name"], command=lambda m=m: box.play(m, self.frame))
        try:
            self.more.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())
        finally:
            self.more.grab_release()

    def link_state(self, up):
        """The App's tick: Reconnect shows beside More only while the link is down"""
        down = not up
        if down != self.reconnect_shown:
            self.reconnect_shown = down
            if down:
                self.reconnect_btn.pack(side="right", padx=(0, 6), before=self.pins)  # Left of More
            else:
                self.reconnect_btn.pack_forget()
            self.fit_pins()

    def refresh_pins(self):
        """The pinned macros as buttons after the main four (macros_ui.MacroBox calls this)"""
        for c in self.pins.winfo_children():
            c.destroy()
        self.pin_buttons = []
        box = getattr(self, "macro_box", None)
        if box is None:
            return
        for m in box.pinned():
            label = m["name"] if len(m["name"]) <= 18 else m["name"][:17] + "…"
            b = th.button(self.pins, label, lambda m=m: box.play(m, self.frame))
            tip = m["name"] + (" (Ctrl+%d)" % m["hotkey"] if m.get("hotkey") else "")
            th.Tooltip(b, tip)
            self.pin_buttons.append((b, m))
        self.fit_pins()

    def fit_pins(self):
        """As many pinned buttons as the row has room for, in order; the rest are in More ▾
        (a pin is never cut in half)"""
        try:
            bar = self.button_row
            room = bar.winfo_width()
            if room <= 1:
                room = bar.winfo_reqwidth()
            room -= sum(b.winfo_reqwidth() + 6 for b in self.main_buttons.values())
            room -= self.more_btn.winfo_reqwidth() + 6
            if self.reconnect_shown:
                room -= self.reconnect_btn.winfo_reqwidth() + 6
            used, self.pins_hidden = 0, []
            for b, m in self.pin_buttons:
                need = b.winfo_reqwidth() + 6
                if used + need <= room and not self.pins_hidden:
                    used += need
                    if not b.winfo_ismapped():
                        b.pack(side="left", padx=(6, 0))
                else:
                    b.pack_forget()
                    self.pins_hidden.append(m)
        except (tk.TclError, AttributeError):
            pass

    _fast_explained = False

    def toggle_fast(self):
        """The Fast mode checkbox: explains once, then turns it on or off on the calculator"""
        on = self.fast_var.get()
        if on:
            ok, why = self.m.fast_supported()
            if not ok:
                self.fast_var.set(False)
                messagebox.showinfo("Fast mode", why, parent=self.app.root)
                return
            if not Tab._fast_explained and not messagebox.askokcancel(
                    "Fast mode (experimental)",
                    "Fast mode sends a small add-on (CSFAST) to the TI-84 Plus CE that makes the "
                    "home screen mirror at about 7 frames a second instead of 1.\n\n"
                    "- It works on the home screen; graphs, tables and Y= keep the normal speed.\n"
                    "- It uses about 40 KB of the calculator's RAM while it's on.\n"
                    "- Turning it off removes everything it added.\n\n"
                    "Your calculator's files aren't touched. Turn it on?", parent=self.app.root):
                self.fast_var.set(False)
                return
            Tab._fast_explained = True
        self.m.set_status("Turning Fast mode %s..." % ("on" if on else "off"))
        self.m.set_fast(on)

    def fast_changed(self, state, note):
        """Fast mode's state changed (on Tk's thread): the checkbox follows it"""
        self.fast_var.set(state in ("on", "starting"))
        names = {"on": "Fast mode is on", "off": "Fast mode is off", "lost": "Fast mode stopped",
                 "error": "Fast mode couldn't start"}
        if state in names:
            self.m.set_status(names[state] + (": " + note if note else ""))

    def fit(self):
        return max(1, self.screen_box.winfo_width()), max(1, self.screen_box.winfo_height())

    def visible(self):
        return self.popped or self.app.current == self.m.calc.pid

    def on_click(self, ev):
        self.view.label.focus_set()
        p = self.view.to_calc(ev)
        if p is not None:
            self.m.on_click(*p)

    def show_section(self, name):
        self.panel.show(name)

    def toggle_history(self):
        if self.hist_var.get():
            self.strip.pack(fill="x", pady=(6, 0), after=self.screen_box)
            self.draw_history()
        else:
            self.strip.pack_forget()

    def key_pressed(self, keysym):
        if self.hist_var.get():
            self.draw_history()

    def draw_history(self):
        for c in self.strip.winfo_children():
            c.destroy()
        keys = self.m.history[-HISTORY:]
        for k, label in enumerate(keys):
            th.keycap(self.strip, label, accent=k == len(keys) - 1).pack(side="left", padx=(0, 4))

    def recording(self, on):
        self.rec_btn.configure(text="Stop" if on else "Record", fg=th.RED if on else th.FG)


class AllScreens(object):
    """Every connected calculator's live screen side by side"""

    def __init__(self, app):
        self.app = app
        self.frame = tk.Frame(app.content, bg=th.BG)
        self.grid = tk.Frame(self.frame, bg=th.BG)
        self.grid.pack(fill="both", expand=True, padx=14, pady=(14, 6))
        # Nothing plugged in: what to do, and what works without a calculator
        self.empty = tk.Frame(self.grid, bg=th.BG)
        tk.Label(self.empty, bg=th.BG, fg=th.DIM, justify="center", font=(th.FONT, 11),
                 text="No calculator is plugged in yet.\n\nPlug one in and switch it on: "
                      "its screen appears here by itself.\nTI's own software must be "
                      "closed. The first time, CalcSuite offers to set up each calculator's driver.").pack()
        tk.Label(self.empty, bg=th.BG, fg=th.FG, font=th.HEAD,
                 text="You can still write programs").pack(pady=(28, 4))
        tk.Label(self.empty, bg=th.BG, fg=th.DIM, font=th.HINT, justify="center",
                 text="For the TI-Nspire CX II (Python), the TI-84 Plus CE and the TI-89 Titanium "
                      "(TI-Basic): checked as you type, built and saved;\nsent once the calculator "
                      "is plugged in. Test in PC copy runs a TI-84 Plus CE program in CEmu.").pack()
        row = tk.Frame(self.empty, bg=th.BG)
        row.pack(pady=(12, 0))
        self.empty_buttons = {}
        for k, (text, cmd) in enumerate((("Program editor", lambda: app.open_editor_tab()),
                                         ("Solver builder", lambda: app.open_solver_builder()),
                                         ("Make a picture", lambda: app.open_picture()))):
            b = th.button(row, text, cmd)
            b.pack(side="left", padx=(0 if k == 0 else 8, 0))
            self.empty_buttons[text] = b
        tk.Label(self.frame, text="Click a screen to type on it. Double click opens its tab.",
                 bg=th.BG, fg=th.DIM, anchor="w").pack(fill="x", padx=14, pady=(0, 10))
        self.tiles = {}  # pid -> (frame, view, name label, fps label, outline)
        self.grid.bind("<Configure>", lambda e: self.layout())

    def add(self, mirror):
        pid = mirror.calc.pid
        outer = tk.Frame(self.grid, bg=th.BG, highlightthickness=2, highlightbackground=th.BG)
        head = tk.Frame(outer, bg=th.PANEL)
        head.pack(fill="x")
        name = tk.Label(head, text=mirror.calc.title, bg=th.PANEL, fg=th.FG, font=(th.FONT, 10, "bold"))
        name.pack(side="left", padx=8, pady=4)
        kb = tk.Label(head, text="KEYBOARD", bg=th.ACCENT, fg="#000000", font=(th.FONT, 9, "bold"), padx=5)
        fps = tk.Label(head, text="", bg=th.PANEL, fg=th.DIM)
        fps.pack(side="left")
        th.button(head, "Record", mirror.toggle_record, pady=2).pack(side="right", padx=(4, 6), pady=3)
        th.button(head, "Screenshot", mirror.screenshot, pady=2).pack(side="right", pady=3)
        box = tk.Frame(outer, bg=th.PANEL, width=330, height=250)
        box.pack(fill="both", expand=True)
        box.pack_propagate(False)
        view = ScreenView(box, mirror, False, lambda: self.app.current == "all",
                          lambda b=box: (b.winfo_width() - 8, b.winfo_height() - 8), bg=th.PANEL)
        view.label.pack(fill="both", expand=True, padx=4, pady=4)
        view.label.bind("<Button-1>", lambda e: self.app.set_target(pid))
        view.label.bind("<Double-Button-1>", lambda e: self.app.show_tab(pid))
        box.bind("<Configure>", lambda e: view.refit())
        self.tiles[pid] = dict(frame=outer, view=view, name=name, fps=fps, kb=kb)
        self.layout()

    def remove(self, pid):
        t = self.tiles.pop(pid, None)
        if t:
            t["frame"].destroy()
            self.layout()

    def layout(self):
        tiles = [self.tiles[p] for p in sorted(self.tiles, key=self.app.order)]
        for t in tiles:
            t["frame"].grid_forget()
        if not tiles:
            self.empty.place(relx=0.5, rely=0.45, anchor="center")
            return
        self.empty.place_forget()
        n = len(tiles)
        for k, t in enumerate(tiles):
            t["frame"].grid(row=0, column=k, sticky="nsew", padx=6, pady=6)
        for k in range(4):
            self.grid.columnconfigure(k, weight=1 if k < n else 0, uniform="tiles" if k < n else "")
        self.grid.rowconfigure(0, weight=1)

    def update(self):
        for pid, t in self.tiles.items():
            m = self.app.mirrors[pid]
            here = m.present and m.session is not None
            target = self.app.target == pid
            t["frame"].configure(highlightbackground=th.ACCENT if target else th.BG)
            if target:
                t["kb"].pack(side="left", padx=(6, 0), after=t["name"])
            else:
                t["kb"].pack_forget()
            sec = m.rec_seconds()
            text = ("%.1f fps" % m.fps if here and m.fps else
                    "not plugged in" if not m.present else "connecting..." if not here else "")
            if sec is not None:
                text += "   REC %d:%02d" % (sec // 60, sec % 60)
            t["fps"].configure(text=text, fg=th.RED if sec is not None else th.DIM)
            t["name"].configure(fg=th.FG if m.present else th.GREY)


class App(object):
    """The one window: the tab strip, All screens, a tab per calculator; watches USB"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("%s %s%s" % (APP_NAME, APP_VERSION,
                                     "" if getattr(sys, "frozen", False) else " (from source)"))
        self.root.configure(bg=th.BG)
        self.root.geometry("1200x780")
        self.root.minsize(900, 600)
        set_app_icon(self.root)
        th.style_ttk(self.root)
        self.burn_keys = tk.BooleanVar(master=self.root, value=False)
        self.mirrors = {}     # pid -> Mirror
        self.tabs = {}        # pid -> Tab
        self.found = set()
        self.scanned = False
        self.offered_driver = {}  # pid -> True once the driver setup was offered (offer_driver)
        self.editor = None        # The Program editor tab's Editor, while it's open
        self.editor_frame = None
        self.emus = {}        # "emu:ti84" / "emu:ti89" -> emu_tabs.EmuTab (the PC copy in its emulator)
        self.current = "all"  # "all", a pid, "editor", an emulator tab's key or a tool tab's key
        self.previous = "all"  # The tab shown before the current one (a closed tool goes back to it)
        self.target = None    # The keyboard target on All screens (a pid)
        self.tools = {}       # "tool:..." -> tool_tabs.ToolFrame (Solver builder, Make a picture, ...)
        global APP
        APP = self            # tool_tabs.app(): tools open as tabs of this window
        th.set_fonts(self.root)

        strip = tk.Frame(self.root, bg=th.PANEL)
        strip.pack(fill="x")
        self.strip = tk.Frame(strip, bg=th.PANEL)
        self.strip.pack(side="left", fill="y")
        self.pop_btn = th.button(strip, "Open in its own window", self.pop_out, bg=th.PANEL)
        self.pop_btn.pack(side="right", padx=10, pady=6, before=self.strip)  # Many tabs cut a tab, not it
        # Writing programs needs no calculator: the editor is always one click away
        self.write_btn = th.button(strip, "Write a program", lambda: self.open_editor_tab(), bg=th.PANEL)
        self.write_btn.pack(side="right", pady=6, before=self.strip)
        # Tabs that don't fit: a run of them with these to scroll; the marker while dragging one
        self.tab_left = tk.Label(self.strip, text="‹", bg=th.PANEL, fg=th.FG, font=(th.FONT, 13),
                                 padx=7, cursor="hand2")
        self.tab_right = tk.Label(self.strip, text="›", bg=th.PANEL, fg=th.FG, font=(th.FONT, 13),
                                  padx=7, cursor="hand2")
        self.tab_left.bind("<Button-1>", lambda e: self.scroll_tabs(-1))
        self.tab_right.bind("<Button-1>", lambda e: self.scroll_tabs(1))
        self.drop_mark = tk.Frame(self.strip, bg=th.ACCENT, width=3)
        self.tab_order = []   # The tabs' keys in the strip's order (drag a tab to move it)
        self.tab_window = (0, 0)
        self.saved_order = wc.load_order()  # Their names in the order the user dragged them to
        tk.Frame(self.root, bg=th.LINE, height=1).pack(fill="x")
        self.content = tk.Frame(self.root, bg=th.BG)
        self.content.pack(fill="both", expand=True)
        self.tab_widgets = {}  # "all" / pid -> dict(frame, dot, name, fps, line)
        self.all = AllScreens(self)
        self.make_tab_button("all", "All screens")
        self.show_tab("all")

        self.root.bind_all("<Key>", self.on_key)
        self.root.bind_all("<Tab>", self.on_key)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        threading.Thread(target=self.scan_loop, daemon=True).start()
        self.root.after(300, self.sync)
        self.root.after(1000, self.tick)
        self.root.after(15, self.pump)
        middle_click_autoscroll(self.root)
        self.root.bind("<Configure>", lambda e: e.widget is self.root and self.fit_tabs_soon(), add="+")

    def pump(self):
        """Tk's thread, ~60 times a second: the work other threads asked for, then each
        calculator's newest frame (only the newest: a slow window never falls behind)"""
        try:
            for _ in range(200):
                try:
                    func, args = _TK_QUEUE.get_nowait()
                except queue.Empty:
                    break
                try:
                    func(*args)
                except Exception:  # One bad request must never stop the window
                    log_error("a background result")
            for m in list(self.mirrors.values()):
                if m.latest:
                    try:
                        m.draw_frame()
                    except Exception:
                        m.latest = None
                        log_error("drawing the %s's screen" % m.calc.title)
        finally:
            # Always again: if this stopped, nothing from another thread would reach the window
            self.root.after(15, self.pump)

    @staticmethod
    def order(pid):
        return [c.pid for c in CALCS].index(pid) if pid in [c.pid for c in CALCS] else 9

    # ---- The tab strip ----
    TAB_MAX = 210  # A tab's title at most this wide (pixels at 100%); the full one in its tooltip
    TAB_MIN = 120  # ...shrunk down to this when many tabs don't fit, before the strip scrolls
    DRAG = 6       # Pixels the mouse moves with the button down before a click becomes a drag
    tab_limit = TAB_MAX  # The titles' width now (fit_tabs lowers it when tabs don't fit)

    def tab_name(self, key):
        """A tab's name in the saved order: a calculator's slug, else its key ("editor",
        "emu:ti84", "tool:compare:ti84"; a second copy's "#2" dropped)"""
        for c in CALCS:
            if c.pid == key:
                return c.slug
        return str(key).split("#")[0]

    def make_tab_button(self, key, text):
        f = tk.Frame(self.strip, bg=th.PANEL, cursor="hand2")
        inner = tk.Frame(f, bg=th.PANEL)
        inner.pack(padx=14, pady=(8, 6))
        dot = th.status_dot(inner)  # An antialiased dot (a Canvas oval is jagged this small)
        tool = tool_tabs.is_tool_key(key)
        if key not in ("all", "editor") and not tool:
            dot.pack(side="left", padx=(0, 7), pady=(1, 0))  # On the text's centre line
        name = tk.Label(inner, text=text, bg=th.PANEL, fg=th.FG, font=(th.FONT, 10, "bold"))
        name.pack(side="left")
        shut = None
        if key == "editor" or is_emu_key(key) or tool:
            # The editor's tab closes (asking about unsaved changes first); an emulator's tab
            # closes the emulator (CEmu saves its state); a tool's tab closes the tool
            shut = tk.Label(inner, text="✕", bg=th.PANEL, fg=th.DIM, font=(th.FONT, 9), cursor="hand2")
            shut.pack(side="right", padx=(10, 0))
            if key == "editor":
                shut.bind("<Button-1>", lambda e: (self.editor and self.editor.close(), "break")[-1])
            elif tool:
                shut.bind("<Button-1>", lambda e, k=key: (self.close_tool_tab(k), "break")[-1])
            else:
                shut.bind("<Button-1>", lambda e, k=key: (self.close_emulator_tab(k), "break")[-1])
            shut.bind("<Enter>", lambda e: shut.configure(fg=th.ACCENT))
            shut.bind("<Leave>", lambda e: shut.configure(fg=th.DIM))
        fps = tk.Label(inner, text="", bg=th.PANEL, fg=th.DIM, font=(th.FONT, 9))
        fps.pack(side="left", padx=(8, 0))
        line = tk.Frame(f, bg=th.PANEL, height=2)
        line.pack(fill="x", side="bottom")
        # Click: shows the tab; drag it left or right: moves it (All screens stays first)
        for w in (f, inner, dot, name, fps):
            w.bind("<ButtonPress-1>", lambda e, k=key: self.tab_press(k, e))
            w.bind("<B1-Motion>", lambda e, k=key: self.tab_motion(k, e))
            w.bind("<ButtonRelease-1>", lambda e, k=key: self.tab_release(k, e))
            w.bind("<MouseWheel>", lambda e: self.scroll_tabs(-1 if e.delta > 0 else 1))
        tip = th.Tooltip(f, "", below=True)
        self.tab_widgets[key] = dict(frame=f, dot=dot, name=name, fps=fps, line=line, inner=inner,
                                     full=text, tip=tip, shut=shut)
        self.set_tab_title(key, text)
        # Its place: where the user dragged it to last time; the calculators otherwise in the
        # order Nspire, 84, 89; anything else last
        order = [k for k in self.tab_order if k in self.tab_widgets and k != key]
        names = [self.tab_name(k) for k in order]
        mine = self.tab_name(key)
        saved = self.saved_order if mine in self.saved_order else ["all"] + [c.slug for c in CALCS]
        pos = 0 if key == wc.FIRST else wc.insert_at(names, mine, saved)
        self.tab_order = order[:pos] + [key] + order[pos:]
        f.bind("<Destroy>", lambda e, w=f: e.widget is w and self.fit_tabs_soon(), add="+")
        self.pack_tabs()
        self.fit_tabs_soon()

    def set_tab_title(self, key, text):
        """The tab's title: a tool's short form ("Compare: TI-84 Plus CE"), cut with "…" to the
        tabs' width now (whole letters), the full title in its tooltip when it's shortened"""
        w = self.tab_widgets.get(key)
        if w is None:
            return
        w["full"] = text
        short = wc.short_title(text) if tool_tabs.is_tool_key(key) else text
        try:
            scale = max(1.0, float(self.root.winfo_fpixels("1i")) / 96.0)
            font = tkfont.Font(root=self.root, font=w["name"].cget("font"))
            shown = wc.ellipsize(short, int(self.tab_limit * scale), font.measure)
        except (tk.TclError, ValueError):
            shown = short
        w["name"].configure(text=shown)
        w["tip"].text = text if shown != text else ""

    def tab_keys(self):
        """The tabs in the strip's order (the ones still open)"""
        self.tab_order = [k for k in self.tab_order if k in self.tab_widgets]
        for k in self.tab_widgets:  # Never lose one
            if k not in self.tab_order:
                self.tab_order.append(k)
        return self.tab_order

    def pack_tabs(self, window=None):
        """The tab buttons in order; window=(start, end): only those (and All screens) shown,
        with ‹ › to scroll to the others"""
        keys = self.tab_keys()
        start, end = window or (0, len(keys))
        for k in keys:
            self.tab_widgets[k]["frame"].pack_forget()
        self.tab_left.pack_forget()
        self.tab_right.pack_forget()
        for i, k in enumerate(keys):
            if i == 0 or start <= i < end:
                self.tab_widgets[k]["frame"].pack(side="left")
        if window and (start > 1 or end < len(keys)):
            self.tab_left.configure(fg=th.FG if start > 1 else th.GREY)
            self.tab_right.configure(fg=th.FG if end < len(keys) else th.GREY)
            self.tab_left.pack(side="left", after=self.tab_widgets[keys[0]]["frame"])
            self.tab_right.pack(side="left")
        self.tab_window = (start, end)

    def scroll_tabs(self, step):
        """‹ / › (or the wheel over the tabs): the run of tabs shown moves by one"""
        start, end = self.tab_window
        n = len(self.tab_keys())
        if (start <= 1 and end >= n) or (step < 0 and start <= 1) or (step > 0 and end >= n):
            return
        self.tab_first = start + step
        self.fit_tabs(scrolled=True)

    def fit_tabs_soon(self):
        if getattr(self, "fit_tabs_job", None) is None:
            self.fit_tabs_job = self.root.after(30, self.fit_tabs)

    def fit_tabs(self, scrolled=False):
        """Many tabs in a narrow window: the tabs not shown lose their status text ("connecting",
        the frame rate) and some padding, then the titles get shorter (with "…"), then the strip
        shows a run of whole tabs with ‹ › to scroll (the shown one always in sight). Write a
        program and Open in its own window always keep their place."""
        self.fit_tabs_job = None
        try:
            avail = (self.root.winfo_width() - self.pop_btn.winfo_reqwidth() -
                     self.write_btn.winfo_reqwidth() - 40)
            if avail <= 100:
                return
            keys = self.tab_keys()
            self.pack_tabs()
            steps = [(False, self.TAB_MAX)] + [(True, lim) for lim in
                                               range(self.TAB_MAX, self.TAB_MIN - 1, -15)]
            ws = []
            for compact, limit in steps:
                for k in keys:
                    w = self.tab_widgets[k]
                    hide = compact and k != self.current
                    w["inner"].pack_configure(padx=8 if compact else 14)
                    if hide and w["fps"].winfo_manager():
                        w["fps"].pack_forget()
                    elif not hide and not w["fps"].winfo_manager():
                        w["fps"].pack(side="left", padx=(8, 0), after=w["name"])
                if limit != self.tab_limit:
                    self.tab_limit = limit
                    for k in keys:
                        self.set_tab_title(k, self.tab_widgets[k]["full"])
                self.strip.update_idletasks()
                ws = [self.tab_widgets[k]["frame"].winfo_reqwidth() for k in keys]
                if sum(ws) <= avail:
                    self.tab_first = 1
                    return
            arrows = self.tab_left.winfo_reqwidth() + self.tab_right.winfo_reqwidth()
            cur = keys.index(self.current) if self.current in keys else None
            self.pack_tabs(wc.visible_window(ws, None if scrolled else cur, avail - arrows,
                                             getattr(self, "tab_first", 1)))
            self.tab_first = self.tab_window[0]
        except tk.TclError:
            pass

    # ---- Dragging a tab to a new place ----
    def tab_press(self, key, ev):
        self.drag = dict(key=key, x=ev.x_root, moving=False, index=None, others=[])
        self.show_tab(key)

    def tab_motion(self, key, ev):
        d = getattr(self, "drag", None)
        if not d or d["key"] != key or key == wc.FIRST:
            return
        if not d["moving"]:
            if abs(ev.x_root - d["x"]) < self.DRAG:
                return
            d["moving"] = True
            self.root.configure(cursor="sb_h_double_arrow")
            self.tab_widgets[key]["line"].configure(bg=th.FG)
        others = [k for k in self.tab_keys() if k not in (key, wc.FIRST) and
                  self.tab_widgets[k]["frame"].winfo_manager()]
        edges = []
        for k in others:
            fr = self.tab_widgets[k]["frame"]
            edges.append((fr.winfo_rootx(), fr.winfo_rootx() + fr.winfo_width()))
        if not edges:
            return
        i = wc.drop_index(edges, ev.x_root)
        d["index"], d["others"] = i, others
        # The drop marker: an accent bar in the gap the tab would land in
        x = (edges[i][0] if i < len(edges) else edges[-1][1]) - self.strip.winfo_rootx()
        h = self.strip.winfo_height()
        self.drop_mark.place(in_=self.strip, x=max(0, x - 2), y=4, width=3, height=max(4, h - 8))
        self.drop_mark.lift()

    def tab_release(self, key, ev):
        d, self.drag = getattr(self, "drag", None), None
        if not d or not d["moving"]:
            return
        self.drop_mark.place_forget()
        self.root.configure(cursor="")
        if d["index"] is not None:
            self.move_tab(key, wc.target_index(self.tab_keys(), key, d["others"], d["index"]))
        self.show_tab(key)  # Its line back to the accent

    def move_tab(self, key, index):
        """Moves a tab to index (counted without it; All screens stays first) and keeps the
        order for next time (CalcSuite files/settings/tab_order.json)"""
        self.tab_order = wc.move(self.tab_keys(), key, index)
        self.saved_order = wc.merge_saved(self.saved_order, [self.tab_name(k) for k in self.tab_order])
        wc.save_order(self.saved_order)
        self.fit_tabs()

    def show_tab(self, key):
        if key != "all" and key in self.tabs and self.tabs[key].popped:
            top = self.tabs[key].frame
            try:
                self.root.tk.call("wm", "deiconify", top._w)
                self.root.tk.call("raise", top._w)
            except tk.TclError:
                pass
            return
        if key in self.tools and self.tools[key].popped:
            try:
                self.root.tk.call("wm", "deiconify", self.tools[key]._w)
                self.root.tk.call("raise", self.tools[key]._w)
            except tk.TclError:
                pass
            return
        old = self.current
        if old != key:
            self.previous = old
        self.current = key
        self.fit_tabs_soon()
        for k, w in self.tab_widgets.items():
            sel = k == key
            for part in ("frame", "inner", "name", "fps"):
                w[part].configure(bg=th.PANEL2 if sel else th.PANEL)
            th.set_dot(w["dot"], bg=th.PANEL2 if sel else th.PANEL)
            w["line"].configure(bg=th.ACCENT if sel else th.PANEL)
        frames = [self.all.frame] + [t.frame for t in self.tabs.values() if not t.popped]
        frames += [e.frame for e in self.emus.values()]
        frames += [t for t in self.tools.values() if not t.popped]
        if self.editor is not None:
            frames.append(self.editor_frame)
        if key == "editor":
            want = self.editor_frame
        elif key in self.emus:
            want = self.emus[key].frame
        elif key in self.tools:
            want = self.tools[key]
        else:
            want = self.all.frame if key == "all" else self.tabs[key].frame
        for f in frames:
            if f is not want:
                f.pack_forget()
        want.pack(fill="both", expand=True)
        self.pop_btn.configure(state="normal" if key in self.tabs or key in self.emus or key in self.tools
                               else "disabled")
        if old in self.emus and old != key:
            self.emus[old].hidden()  # The keyboard back to CalcSuite from the emulator's window
        if key in self.tools:
            self.all.update()
            return
        if key in self.emus:
            self.emus[key].shown()
            self.all.update()
            return
        if key == "editor":
            try:
                self.editor.text.focus_set()
            except (AttributeError, tk.TclError):
                pass
        elif key != "all":
            self.target = key
            self.tabs[key].view.show()
        elif old != "all":
            for t in self.all.tiles.values():
                t["view"].show()
        self.all.update()

    # ---- The program editor, a tab of this window ----
    def open_editor_tab(self, initial_target=None, path=None):
        """Opens (or shows) the Program editor tab, aimed at initial_target (a Mirror or a slug)"""
        import editor
        if self.editor is None:
            self.editor_frame = tk.Frame(self.content, bg=th.BG)
            self.make_tab_button("editor", "Program editor")
            self.editor = editor.Editor(self.root, list(self.mirrors.values()), initial_target, path,
                                        host=self)
        else:
            if initial_target is not None:
                self.editor.set_target(initial_target)
            if path:
                self.editor.open_path(path)
        self.show_tab("editor")
        return self.editor

    def open_solver_builder(self):
        """The Solver builder (in a tab), through the Program editor (its Send and Open in the
        editor); no calculator needed"""
        ed = self.open_editor_tab()
        return ed.open_solver_builder()

    def open_picture(self, m=None):
        """Make a picture: for a calculator's tab (m), or with none plugged in (choose the model
        in it; Save makes the file)"""
        import picture_window
        if m is not None:
            return picture_window.open_for(m, KIT)
        key = "picture:pc"
        return self.open_tool_tab(key, "Make a picture", lambda parent: picture_window.PicturePanel(
            parent, None, KIT, "ti84", on_close=lambda: self.drop_tool_tab(key)))

    def editor_title(self, text):
        """The editor's file name (with a dot while unsaved) beside the tab's name"""
        w = self.tab_widgets.get("editor")
        if w:
            w["fps"].configure(text=text)

    def editor_closed(self, ed):
        if ed is not self.editor:
            return
        self.editor = None
        w = self.tab_widgets.pop("editor", None)
        if w:
            w["frame"].destroy()
        try:
            self.editor_frame.destroy()
        except (AttributeError, tk.TclError):
            pass
        if self.current == "editor":
            self.show_tab("all")

    def set_target(self, pid):
        self.target = pid
        self.all.update()
        try:
            self.all.tiles[pid]["view"].label.focus_set()
        except (KeyError, tk.TclError):
            pass

    # ---- The PC copy's emulator, a tab of this window (emu_tabs.py) ----
    def open_emulator_tab(self, slug, rom, backup=None):
        """Opens (or shows) the emulator tab of that model's PC copy: "TI-84 Plus CE (PC copy)"
        (CEmu) or "TI-89 Titanium (PC copy)" (TiEmu), with that ROM. A tab already open with
        another ROM keeps running: close it first to switch."""
        import emu_tabs
        key = emu_tabs.key_of(slug)
        tab = self.emus.get(key)
        if tab is None:
            self.make_tab_button(key, emu_tabs.SPECS[slug]["title"])
            tab = emu_tabs.EmuTab(self, slug, rom, backup)
            self.emus[key] = tab
            self.show_tab(key)
            tab.start()
            return tab
        if tab.session is None or not tab.session.running():
            tab.rom, tab.backup = rom, backup or tab.backup
            tab.start()
        self.show_tab(key)
        if tab.session is not None and tab.session.state == "own window":
            tab.raise_own()
        return tab

    def pc_copy_tab(self, section, mode):
        """Calculator info > Make a PC copy / Open my PC copy: the calculator's "(PC copy)" tab.
        make: the dump runs in it (steps, one overall bar, Cancel, "Your PC copy is made"), then
        the emulator starts there; open: the newest copy in its emulator (made first if none)."""
        import emu_tabs
        import ui_panels
        slug = section.m.calc.slug
        key = emu_tabs.key_of(slug)
        roms = ui_panels.existing_roms(slug)
        newest = roms[0] if roms else None
        if mode == "open" and newest is not None:
            tab = self.open_emulator_tab(slug, newest["path"], (newest.get("info") or {}).get("backup"))
            tab.section = section
            return tab
        tab = self.emus.get(key)
        if tab is None:
            self.make_tab_button(key, emu_tabs.SPECS[slug]["title"])
            tab = emu_tabs.EmuTab(self, slug, newest["path"] if newest else None,
                                  (newest.get("info") or {}).get("backup") if newest else None)
            self.emus[key] = tab
        self.show_tab(key)
        tab.make_copy(section)
        return tab

    def close_emulator_tab(self, key):
        tab = self.emus.get(key)
        if tab is not None:
            tab.close_tab()

    def emulator_tab_closed(self, tab):
        """EmuTab.close_tab: the tab's button goes; All screens is shown if it was current"""
        self.emus.pop(tab.key, None)
        w = self.tab_widgets.pop(tab.key, None)
        if w:
            w["frame"].destroy()
        if self.current == tab.key:
            self.show_tab("all")

    # ---- Tools in tabs (tool_tabs.py): Solver builder, Make a picture, Compare backups, ... ----
    def new_tool_frame(self, key, title):
        """A new tool tab (shown at once): the ToolFrame the tool builds itself into"""
        key = tool_tabs.tab_key(key)
        f = tool_tabs.ToolFrame(self.content, self, key, title)
        self.tools[key] = f
        self.make_tab_button(key, title)
        self.show_tab(key)
        return f

    def open_tool_tab(self, key, title, make_frame):
        """A tool as a closable tab of this window: make_frame(parent) -> its frame (packed to
        fill the tab unless it's placed already). The same key again shows the tab it has and
        returns its frame. The tab closes when the frame is destroyed (its own Close) or by the
        tab's ✕ (the frame's close() when it has one)."""
        k = tool_tabs.tab_key(key)
        holder = self.tools.get(k)
        if holder is not None:
            self.show_tab(k)
            return holder.panel if holder.panel is not None else holder
        holder = self.new_tool_frame(k, title)
        try:
            panel = make_frame(holder)
        except Exception:
            holder.destroy()
            raise
        if panel is None:
            panel = holder
        if panel is not holder:
            holder.panel = panel
            if not panel.winfo_manager():
                panel.pack(fill="both", expand=True)
            panel.bind("<Destroy>", lambda e, p=panel, h=holder: (
                e.widget is p and h.after_idle(h.destroy)), add="+")
        return panel

    def tool_title(self, key, text):
        if key in self.tab_widgets:
            self.set_tab_title(key, text)
            self.fit_tabs_soon()
        t = self.tools.get(key)
        if t is not None and t.popped:
            self.root.tk.call("wm", "title", t._w, "%s - %s" % (text, APP_NAME))

    def close_tool_tab(self, key):
        """The tool tab's ✕"""
        t = self.tools.get(tool_tabs.tab_key(key))
        if t is not None:
            try:
                t.request_close()
            except Exception:
                log_error("closing a tool's tab")
                t.destroy()

    def drop_tool_tab(self, key):
        """The tool closed itself (its own Close): its tab goes, nothing asked"""
        t = self.tools.get(tool_tabs.tab_key(key))
        if t is not None:
            t.destroy()

    def tool_closed(self, key):
        """A ToolFrame was destroyed: its tab button goes; the tab shown before it comes back"""
        self.tools.pop(key, None)
        w = self.tab_widgets.pop(key, None)
        if w:
            try:
                w["frame"].destroy()
                self.fit_tabs_soon()
            except tk.TclError:
                pass
        if self.current == key:
            back = self.previous
            ok = back == "all" or back in self.tabs or back in self.emus or back in self.tools or (
                back == "editor" and self.editor is not None)
            try:
                self.show_tab(back if ok and back != key else "all")
            except tk.TclError:
                pass

    def pop_out(self):
        key = self.current
        if key in self.emus:  # The emulator's own window back as a normal window
            self.emus[key].pop_out()
            return
        if key in self.tools:
            self.pop_out_tool(key)
            return
        if key == "all" or key not in self.tabs:
            return
        tab = self.tabs[key]
        f = tab.frame
        f.pack_forget()
        try:
            self.root.tk.call("wm", "manage", f._w)
        except tk.TclError as e:
            messagebox.showinfo(APP_NAME, "Couldn't open a window: %s" % e, parent=self.root)
            f.pack(fill="both", expand=True)
            return
        tab.popped = True
        name = self.root.register(lambda k=key: self.dock(k))
        self.root.tk.call("wm", "protocol", f._w, "WM_DELETE_WINDOW", name)
        self.root.tk.call("wm", "title", f._w, "%s - %s" % (tab.m.calc.title, APP_NAME))
        try:
            self.root.tk.call("wm", "iconphoto", f._w, self.root._app_icon)
        except (tk.TclError, AttributeError):
            pass
        f.after(50, lambda: dark_title_bar_path(self.root, f))
        self.tab_widgets[key]["fps"].configure(text="own window")
        self.show_tab("all")
        tab.view.show()

    def pop_out_tool(self, key):
        """A tool's tab as a window of its own (closing that window puts it back in its tab)"""
        t = self.tools[key]
        t.pack_forget()
        try:
            self.root.tk.call("wm", "manage", t._w)
        except tk.TclError as e:
            messagebox.showinfo(APP_NAME, "Couldn't open a window: %s" % e, parent=self.root)
            t.pack(fill="both", expand=True)
            return
        t.popped = True
        name = self.root.register(lambda k=key: self.dock(k))
        self.root.tk.call("wm", "protocol", t._w, "WM_DELETE_WINDOW", name)
        self.root.tk.call("wm", "title", t._w, "%s - %s" % (t.title(), APP_NAME))
        try:
            self.root.tk.call("wm", "geometry", t._w, "1100x720")
            self.root.tk.call("wm", "iconphoto", t._w, self.root._app_icon)
        except (tk.TclError, AttributeError):
            pass
        t.after(50, lambda: dark_title_bar_path(self.root, t))
        self.tab_widgets[key]["fps"].configure(text="own window")
        self.show_tab(self.previous if self.previous != key and (
            self.previous == "all" or self.previous in self.tabs) else "all")

    def dock(self, key):
        t = self.tools.get(key)
        if t is not None:
            if t.popped:
                try:
                    self.root.tk.call("wm", "forget", t._w)
                except tk.TclError:
                    pass
                t.popped = False
                self.tab_widgets[key]["fps"].configure(text="")
                self.show_tab(key)
            return
        tab = self.tabs.get(key)
        if tab is None or not tab.popped:
            return
        try:
            self.root.tk.call("wm", "forget", tab.frame._w)
        except tk.TclError:
            pass
        tab.popped = False
        self.show_tab(key)

    def popped_frame_of(self, widget):
        """The popped-out tab a widget sits in, else None"""
        for pid, t in self.tabs.items():
            if t.popped:
                w = widget
                while w is not None:
                    if w is t.frame:
                        return pid
                    w = getattr(w, "master", None)
        return None

    # ---- Keys: to the keyboard target ----
    def on_key(self, ev):
        w = ev.widget
        try:
            cls = w.winfo_class()
        except (AttributeError, tk.TclError):
            return None
        if cls in ("Entry", "TEntry", "Text", "Treeview", "TCombobox", "Listbox", "Spinbox"):
            return None  # Typing into CalcSuite itself (search box, file list)
        try:
            top = w.winfo_toplevel()
        except tk.TclError:
            return None
        pid = self.popped_frame_of(w)
        if pid is None:
            if top is not self.root:
                return None  # A dialog
            pid = self.current if self.current != "all" else self.target
        m = self.mirrors.get(pid)
        if m is None:
            return None
        # Ctrl+1..9: a macro's hotkey, only on that calculator's own tab (not All screens)
        if (ev.state & 0x4) and not (ev.state & 0x1) and ev.keysym in tuple("123456789") and (
                self.current == pid or self.tabs[pid].popped):
            box = getattr(self.tabs[pid], "macro_box", None)
            if box is not None and box.hotkey(int(ev.keysym), self.tabs[pid].frame):
                return "break"
        m.on_key(ev)
        return "break"

    # ---- USB: calculators come and go ----
    def scan_loop(self):
        while True:
            self.found = nspire_link.usb_calculators()
            self.scanned = True
            time.sleep(3)

    def sync(self):
        if self.scanned:
            for calc in CALCS:
                present = calc.pid in self.found
                m = self.mirrors.get(calc.pid)
                if present and m is None:
                    self.add(calc)
                elif m is not None and m.present != present:
                    m.present = present
                    if present:
                        m.want_reconnect = True
        self.root.after(1000, self.sync)

    def add(self, calc):
        m = Mirror(self, calc)
        self.mirrors[calc.pid] = m
        self.make_tab_button(calc.pid, calc.title)  # In the order the user dragged them to last
        self.tabs[calc.pid] = Tab(self, m)
        self.all.add(m)
        if self.editor is not None:  # The editor's Send targets follow
            self.editor.calculators_changed(self.mirrors.values())
        if self.target is None:
            self.target = calc.pid
        self.all.update()

    def offer_driver(self, m, d):
        """A calculator is plugged in but Windows has no driver CalcSuite can use: its tab opens
        on Calculator info, and the same check-then-install that panel's button runs starts (it shows
        what will change; Windows asks for admin rights). Once per calculator per session."""
        tab = self.tabs.get(m.calc.pid)
        if tab is None or self.offered_driver.get(m.calc.pid):
            return
        self.offered_driver[m.calc.pid] = True
        self.show_tab(m.calc.pid)
        import ui_panels
        tab.panel.show(ui_panels.INFO)
        info = tab.panel.sections.get(ui_panels.INFO)
        if info is not None and hasattr(info, "fix"):
            m.set_status("The %s needs a driver CalcSuite can use: setting it up..." % m.calc.title)
            info.fix("install", d)

    def recording_changed(self, m):
        tab = self.tabs.get(m.calc.pid)
        if tab:
            tab.recording(m.rec_seconds() is not None)

    def tick(self):
        if self.editor is not None:  # A calculator connected or lost: the editor's Send follows
            sig = tuple((pid, m.connected()) for pid, m in sorted(self.mirrors.items()))
            if sig != getattr(self, "editor_sig", None):
                self.editor_sig = sig
                try:
                    self.editor.calculators_changed(self.mirrors.values())
                except Exception:
                    log_error("updating the editor's calculators")
        for pid, m in self.mirrors.items():
            m.tick()
            w = self.tab_widgets[pid]
            here = m.present and m.session is not None
            set_dot(w["dot"], "connected" if here else "connecting" if m.present else "absent")
            self.tabs[pid].link_state(here)
            w["name"].configure(fg=th.FG if m.present else th.GREY)
            sec = m.rec_seconds()
            if self.tabs[pid].popped:
                text = "own window"
            elif not m.present:
                text = "not plugged in"
            elif here:
                text = "%.1f fps" % m.fps if m.fps else ""
            else:
                text = "connecting"
            if sec is not None:
                text = "REC %d:%02d" % (sec // 60, sec % 60)
            w["fps"].configure(text=text, fg=th.RED if sec is not None else th.DIM)
            if self.tabs[pid].popped:
                fps = " - %.1f frames/s" % m.fps if m.fps else ""
                try:
                    self.root.tk.call("wm", "title", self.tabs[pid].frame._w,
                                      "%s%s - %s" % (m.calc.title, fps, APP_NAME))
                except tk.TclError:
                    pass
        self.all.update()
        self.root.after(1000, self.tick)

    def quit(self):
        """Closes at once: the window goes away first, then every calculator's link stops at the
        same time (each helper gets 0.8 s to finish what it's doing, then it's ended). Before,
        each link waited up to 5 s, one after another: closing took many seconds."""
        try:  # Unsaved programs first: Save / Don't save / Cancel (Cancel keeps the app open)
            import editor
            if not editor.confirm_close_all(self.root):
                return
        except ImportError:
            pass
        # The emulators this window started (only those processes): given back hidden and asked
        # to close (CEmu saves its state); ended below if they don't within CLOSE_WAIT_S
        emus = []
        for e in list(self.emus.values()):
            try:
                s = e.stop_for_quit()
                if s is not None:
                    emus.append(s)
            except Exception:
                log_error("closing the %s" % e.name)
        emus_t0 = time.time()
        mirrors = list(self.mirrors.values())
        for m in mirrors:  # Tk's part first, on Tk's thread
            m.running = False
            if m.manager is not None and m.manager.alive():
                try:
                    m.manager.close()
                except Exception:
                    pass
        try:
            self.root.withdraw()
            self.root.update_idletasks()
        except tk.TclError:
            pass
        workers = [threading.Thread(target=m.stop, kwargs={"tk_side": False}, daemon=True)
                   for m in mirrors]
        for w in workers:
            w.start()
        deadline = time.time() + 3.0  # A recording being saved can take longer: it's a daemon
        for w in workers:
            w.join(max(0.0, deadline - time.time()))
        for m in mirrors:  # Anything still running is ended
            s = m.session
            if s is not None and s.p.poll() is None:
                try:
                    s.p.kill()
                except OSError:
                    pass
        if emus:
            import emu_host
            while any(s.running() for s in emus) and time.time() - emus_t0 < emu_host.CLOSE_WAIT_S:
                time.sleep(0.05)
            for s in emus:
                s.kill()  # Only the process its tab started; a no-op once it has closed
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def set_dot(dot, state):
    """A tab's dot: "connected" (mint), "connecting" (orange), "absent" (grey), "failed" (red)"""
    if getattr(dot, "dot_state", None) != state:
        th.set_dot(dot, state)


def middle_click_autoscroll(root):
    """Middle button held in a text panel (the Guide, lists): the Windows way, the page scrolls
    toward where the mouse moves, faster the further it goes. Tk's own middle-drag moves the page
    with the mouse, which reads as backwards (the owner, 2026-11-27)."""
    state = {"y0": 0, "y": 0, "w": None, "job": None}

    def step():
        w = state["w"]
        if w is None:
            return
        dy = state["y"] - state["y0"]
        if abs(dy) > 6:
            try:
                w.yview_scroll(max(-12, min(12, int(dy / 14) or (1 if dy > 0 else -1))), "units")
            except tk.TclError:
                state["w"] = None
                return
        state["job"] = root.after(40, step)

    def press(e):
        state.update(y0=e.y, y=e.y, w=e.widget)
        if state["job"] is None:
            step()
        return "break"

    def motion(e):
        state["y"] = e.y
        return "break"

    def release(e):
        state["w"] = None
        if state["job"] is not None:
            root.after_cancel(state["job"])
            state["job"] = None
        return "break"

    for cls in ("Text", "Listbox", "Treeview"):
        root.bind_class(cls, "<Button-2>", press)
        root.bind_class(cls, "<B2-Motion>", motion)
        root.bind_class(cls, "<ButtonRelease-2>", release)


def set_app_icon(root):
    """The app icon (assets/app.png) on every window, and the taskbar's own for this app"""
    for path in (os.path.join(os.path.dirname(HERE), "assets", "app.png"),  # From the source
                 os.path.join(HERE, "assets", "app.png")):                  # The packaged app
        if os.path.isfile(path):
            try:
                root._app_icon = tk.PhotoImage(master=root, file=path)
                root.iconphoto(True, root._app_icon)  # True: every window made later too
            except tk.TclError:
                pass
            break
    # Windows: the .ico too, so the title bar and taskbar use its own small drawings (16-48 px)
    # instead of shrinking the 256 px PNG (the calculator came out clipped at 16 px)
    for path in (os.path.join(os.path.dirname(HERE), "assets", "app.ico"),
                 os.path.join(HERE, "assets", "app.ico")):
        if os.path.isfile(path):
            try:
                root.iconbitmap(default=path)  # default=: every window made later too
                # And on this window itself (WM_SETICON): without it Windows reported no icon
                # for the main window, and captures of it showed the generic one (2026-11-28)
                root.iconbitmap(path)
            except tk.TclError:
                pass
            break
    try:  # Run from Python, the taskbar would group the windows under python.exe's icon
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("CalcSuite.App")
    except (AttributeError, OSError):
        pass
    # Every window (the main one, popped-out tabs, dialogs) gets a dark title bar when it appears
    root.bind_class("Toplevel", "<Map>", lambda e: dark_title_bar(e.widget), add="+")
    root.bind_class("Tk", "<Map>", lambda e: dark_title_bar(e.widget), add="+")


def dark_title_bar(win):
    """Windows 10 (2004+) and 11: the window's title bar in dark mode. Does nothing elsewhere."""
    try:
        if win.winfo_toplevel() is not win:
            return
    except tk.TclError:
        return
    th.dark_title_bar(win)  # Only marked done once Windows accepted it (a dialog not yet shown
    #                         has no title bar: the <Map> hook tries again when it appears)


def dark_title_bar_path(root, frame):
    """The same for a frame made a window by `wm manage` (a popped-out tab)"""
    try:
        import ctypes
        hwnd = int(root.tk.call("wm", "frame", frame._w), 16)
        _dark_hwnd(hwnd)
    except (AttributeError, OSError, ValueError, tk.TclError):
        pass


def _dark_hwnd(hwnd):
    import ctypes
    from ctypes import wintypes
    on = ctypes.c_int(1)
    for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE, and its number before Windows 10 2004
        if ctypes.windll.dwmapi.DwmSetWindowAttribute(wintypes.HWND(hwnd), attr, ctypes.byref(on),
                                                      ctypes.sizeof(on)) == 0:
            break
    # Repaint the frame now (SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
    ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0020)


MUTEX_NAMES = ("CalcSuite.single", "NspireMirror.single")  # The second: versions before 1.0


def already_running():
    """One copy at a time: a second one would take the calculators away from the first, and
    both would go black. Checks the old app's name too (Nspire Mirror), and holds both so an
    old copy started later sees this one."""
    if os.name != "nt":
        return False
    import ctypes
    global _mutexes  # Kept for the life of the process
    _mutexes = []
    taken = False
    for name in MUTEX_NAMES:
        h = ctypes.windll.kernel32.CreateMutexW(None, False, name)
        if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            taken = True
        _mutexes.append(h)
    return taken


def main():
    if already_running():
        r = tk.Tk()
        r.withdraw()
        messagebox.showinfo(APP_NAME, "CalcSuite is already open.")
        return
    if getattr(sys, "frozen", False):
        if not paths.is_portable():
            migrate_documents()
        os.makedirs(os.path.join(KIT, "programs"), exist_ok=True)
        if paths.inside_zip():
            r = tk.Tk()
            r.withdraw()
            messagebox.showwarning(APP_NAME, "CalcSuite is running from inside the zip.\n\nUnzip it "
                                   "first (right-click the zip, Extract All), then open CalcSuite.exe "
                                   "in the folder it makes. Until then, what you save goes to "
                                   "Documents\\CalcSuite.")
            r.destroy()
    App().run()


if __name__ == "__main__":
    main()
