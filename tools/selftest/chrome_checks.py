"""The window's chrome: the live screen's size, the tab strip (short titles, "…", the order,
dragging a tab, which tabs fit), the side strip's smooth icons and the app icon's small sizes.

    python -I tools/selftest/chrome_checks.py
"""

import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(KIT, "tools"))

import window_chrome as wc  # noqa: E402


def check(ok, what):
    print("%-4s %s" % ("PASS" if ok else "FAIL", what))
    return 0 if ok else 1


def scale_checks():
    f = 0
    sc = wc.screen_scale
    # The 89 (160 x 100): x 4.91 would fit; x 4 is under 85% of it, so x 4.5
    f += check(sc(160, 100, 834, 780) == (9, 2), "screen: the 89 x 4.5 in 834 x 780")
    f += check(sc(160, 100, 1008, 780) == (6, 1), "screen: the 89 x 6 in 1008 x 780")
    f += check(sc(320, 240, 834, 780) == (2, 1), "screen: the CE x 2 in 834 x 780 (x 2.5 doesn't fit)")
    f += check(sc(320, 240, 1008, 900) == (3, 1), "screen: x 3 when it fits with the margin")
    # x 1.9 fits: x 1 would be half of it, so x 1.5 (zoom 3, every other pixel)
    f += check(sc(320, 240, 656, 600) == (3, 2), "screen: x 1.5 when x 1 would leave most of it black")
    f += check(sc(320, 240, 300, 250) == (3, 4) and sc(320, 240, 270, 230) == (2, 3),
               "screen: smaller than itself: 3/4, 2/3")
    f += check(sc(320, 240, 10, 10) == (1, 4) and sc(0, 0, 100, 100) == (1, 1), "screen: tiny or no picture")
    ok = True
    for nw, nh in ((160, 100), (320, 240), (96, 64)):
        for aw in range(60, 2400, 37):
            for ah in range(60, 1600, 53):
                z, s = sc(nw, nh, aw, ah)
                w, h = wc.shown_size(nw, nh, z, s)
                m = wc.SCREEN_MARGIN
                if z / float(s) >= 1 and (w > aw - 2 * m or h > ah - 2 * m):
                    ok = False
    f += check(ok, "screen: always inside its space with the margin all round")
    f += check(wc.screen_width_wanted(160, 100, 1108, 780) == 960 + 2 * wc.SCREEN_MARGIN,
               "screen: the 89 wants 960 px (x 6) when the panel can give it up")
    return f


def title_checks():
    f = 0
    st = wc.short_title
    f += check(st("Compare backups of the TI-84 Plus CE") == "Compare: TI-84 Plus CE",
               "tab title: Compare backups of the TI-84 Plus CE -> Compare: TI-84 Plus CE")
    f += check(st("Make a picture (TI-89 Titanium)") == "Picture: TI-89 Titanium" and
               st("Get all for the TI-Nspire") == "Get all: TI-Nspire" and
               st("Restore to the TI-89 Titanium") == "Restore: TI-89 Titanium",
               "tab title: (model), for the, to the")
    f += check(st("Solver builder") == "Solver builder" and st("ZZ renamed") == "ZZ renamed" and
               st("Test zzprog in the PC copy") == "Test zzprog in the PC copy",
               "tab title: short ones as they are")
    measure = lambda t: 7 * len(t)
    cut = wc.ellipsize("Compare: TI-84 Plus CE", 100, measure)
    f += check(cut.endswith("…") and measure(cut) <= 100 and "Compare: TI-84 Plus CE".startswith(cut[:-1]),
               "tab title: cut to the width with … (whole letters): %r" % cut)
    f += check(wc.ellipsize("Keys", 100, measure) == "Keys" and wc.ellipsize("Keys", 3, measure) == "…",
               "tab title: fits as it is; no room: only …")
    return f


def order_checks():
    f = 0
    order = ["all", 1, 2, 3, "editor"]
    f += check(wc.move(order, "editor", 1) == ["all", "editor", 1, 2, 3], "tab order: drag the editor to the front")
    f += check(wc.move(order, 1, 99) == ["all", 2, 3, "editor", 1], "tab order: drag to the end")
    f += check(wc.move(order, "editor", 0) == ["all", 1, 2, 3, "editor"][:1] + ["editor", 1, 2, 3],
               "tab order: never before All screens")
    f += check(wc.move(order, "all", 3) == order, "tab order: All screens doesn't move")
    edges = [(100, 200), (200, 260), (260, 400)]
    f += check([wc.drop_index(edges, x) for x in (90, 160, 240, 320, 999)] == [0, 1, 2, 2, 3],
               "tab drag: the gap nearest the pointer")
    # Dragging 3 to the gap before 1 while tab 2 is scrolled out of sight
    f += check(wc.target_index(order, 3, [1, "editor"], 0) == 1 and
               wc.target_index(order, 3, [1, "editor"], 2) == 4 and
               wc.target_index(order, 1, ["editor"], 0) == 3,
               "tab drag: the gap among the tabs shown -> the place in the whole order")
    saved = ["all", "ti89", "editor", "nspire", "ti84"]
    f += check(wc.insert_at(["all", "nspire"], "ti89", saved) == 1 and
               wc.insert_at(["all", "ti89", "nspire"], "editor", saved) == 2 and
               wc.insert_at(["all", "nspire"], "ti84", saved) == 2 and
               wc.insert_at(["all"], "tool:x", saved) == 1,
               "tab order: a new tab goes where it was dragged to last time, else last")
    f += check(wc.merge_saved(saved, ["all", "editor", "ti89"]) == ["all", "editor", "ti89", "nspire", "ti84"],
               "tab order: saved with the closed tabs kept")
    tmp = tempfile.mkdtemp(prefix="calcsuite_selftest_")
    old = wc.STORE
    try:
        wc.STORE = os.path.join(tmp, "settings", "tab_order.json")
        f += check(wc.load_order() == [], "tab order: none saved yet")
        f += check(wc.save_order(saved) and wc.load_order() == saved, "tab order: saved and read back")
        with open(wc.STORE, "w") as fh:
            fh.write("{not json")
        f += check(wc.load_order() == [], "tab order: a broken file is ignored")
    finally:
        wc.STORE = old
        shutil.rmtree(tmp, ignore_errors=True)
    ws = [100, 150, 150, 150, 150]
    f += check(wc.visible_window(ws, 4, 1000) == (0, 5), "tab strip: all shown when they fit")
    s, e = wc.visible_window(ws, 4, 400, 1)
    f += check(s <= 4 < e and 100 + sum(ws[s:e]) <= 400, "tab strip: the current tab in sight (%d..%d)" % (s, e))
    s, e = wc.visible_window(ws, 1, 400, 3)
    f += check(s <= 1 < e, "tab strip: scrolled back to the current one (%d..%d)" % (s, e))
    s, e = wc.visible_window(ws, None, 400, 2)
    f += check((s, e) == (2, 4), "tab strip: scrolled by hand (%d..%d)" % (s, e))
    return f


def strip_icon_checks():
    f = 0
    try:
        import ui_panels as up
    except Exception as e:  # No Tk: say so
        print("SKIP the strip icons (%s)" % e)
        return 0
    for scale in (1.0, 1.5, 2.0):
        n = up.icon_size(scale)
        ok = True
        for name in up.ICONS:
            m = up.icon_mask(name, scale)
            if m is None:
                ok = ok and all(p[0] == "text" for p in up.ICONS[name])
                continue
            ok = ok and len(m) == n * n and all(0 <= v <= 1 for v in m) and max(m) == 1
            # Smooth: some pixels part covered; crisp: straight lines fill whole pixels
            ok = ok and any(0 < v < 1 for v in m)
        f += check(ok, "strip icons: smooth images at %d%% (%d px)" % (scale * 100, n))
    m = up.icon_mask("Data", 1.0)
    full = sum(1 for v in m if v == 1)
    part = sum(1 for v in m if 0 < v < 1)
    f += check(full > part, "strip icons: straight lines on whole pixels at 100%% (%d full, %d part)" % (full, part))
    return f


def app_icon_checks():
    """assets/app.ico's small drawings: everything a pixel inside the tile, edges on the grid"""
    f = 0
    try:
        from PIL import Image
    except ImportError:
        print("SKIP the app icon (no Pillow)")
        return 0
    ico = Image.open(os.path.join(KIT, "assets", "app.ico"))
    sizes = sorted(s[0] for s in ico.info.get("sizes", ()))
    f += check(sizes[:4] == [16, 20, 24, 32], "app icon: 16, 20, 24 and 32 px drawn (%s)" % sizes)
    for size in (16, 20, 24, 32):
        im = ico.ico.getimage((size, size)).convert("RGBA")
        px = im.load()
        ring = all(px[x, y][3] == 0 for x in range(size) for y in range(size)
                   if x in (0, size - 1) or y in (0, size - 1))
        inside = True
        for y in range(size):
            for x in range(size):
                r, g, b, a = px[x, y]
                if a and r > 150 and g < 160:  # The orange calculator: a full tile pixel round it
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            if px[x + dx, y + dy][3] < 255:
                                inside = False
        # Pixel-aligned: blended (part-transparent) pixels only at the tile's rounded corners
        c = size // 4 + 1
        crisp = all(px[x, y][3] in (0, 255) for x in range(size) for y in range(size)
                    if c <= x < size - c or c <= y < size - c)
        f += check(ring and inside and crisp,
                   "app icon %d px: a clear edge, the calculator inside the tile, no half pixels" % size)
    return f


def app_checks():
    """The real window with no USB scan: drag a tab (the order and its file), a click selects,
    long tool titles shortened with the full one in the tooltip, many tabs scroll"""
    try:
        import mirror
    except Exception as e:
        print("SKIP the tab strip (%s)" % e)
        return 0
    f = 0
    tmp = tempfile.mkdtemp(prefix="calcsuite_selftest_")
    old_store, wc.STORE = wc.STORE, os.path.join(tmp, "tab_order.json")
    saved_scan = mirror.App.scan_loop
    mirror.App.scan_loop = lambda self: None
    try:
        try:
            app = mirror.App()
        except Exception as e:
            print("SKIP the tab strip (no window: %s)" % e)
            return 0
        root = app.root
        root.geometry("1400x800+0+0")
        root.update()
        for k in ("a", "b", "c"):
            fr = app.new_tool_frame("zz" + k, "Compare backups of the TI-84 Plus CE")
        root.update()
        w = app.tab_widgets["tool:zza"]
        f += check(w["name"].cget("text") == "Compare: TI-84 Plus CE" and
                   w["tip"].text == "Compare backups of the TI-84 Plus CE",
                   "tab strip: a long tool title shortened, the full one in its tooltip")
        fr.title("A very long title for a tool tab that would never fit in any tab of the strip")
        root.update()
        name = app.tab_widgets["tool:zzc"]["name"].cget("text")
        f += check(name.endswith("…") and len(name) < 50, "tab strip: a long title cut with … (%r)" % name)

        class Ev(object):
            def __init__(self, x):
                self.x_root = x
        keys = app.tab_keys()
        f += check(keys[0] == "all" and keys[1:] == ["tool:zza", "tool:zzb", "tool:zzc"], "tab strip: the order made")
        a = app.tab_widgets["tool:zza"]["frame"]
        x0 = a.winfo_rootx() + 10
        app.tab_press("tool:zza", Ev(x0))
        app.tab_release("tool:zza", Ev(x0 + 2))
        f += check(app.current == "tool:zza" and app.tab_keys()[1] == "tool:zza",
                   "tab strip: a click selects, nothing moves")
        c = app.tab_widgets["tool:zzc"]["frame"]
        end = c.winfo_rootx() + c.winfo_width() - 2
        app.tab_press("tool:zza", Ev(x0))
        app.tab_motion("tool:zza", Ev(x0 + 40))
        app.tab_motion("tool:zza", Ev(end))
        marked = bool(app.drop_mark.winfo_manager())
        app.tab_release("tool:zza", Ev(end))
        root.update()
        f += check(marked and app.tab_keys() == ["all", "tool:zzb", "tool:zzc", "tool:zza"] and
                   not app.drop_mark.winfo_manager() and app.current == "tool:zza",
                   "tab strip: dragged to the end, with the drop marker while dragging")
        f += check(wc.load_order()[:4] == ["all", "tool:zzb", "tool:zzc", "tool:zza"],
                   "tab strip: the order saved for next time")
        app.tab_press("all", Ev(5))
        app.tab_motion("all", Ev(500))
        app.tab_release("all", Ev(500))
        f += check(app.tab_keys()[0] == "all", "tab strip: All screens stays first")
        for k in range(8):
            app.new_tool_frame("zzmore%d" % k, "Make a picture (TI-89 Titanium)")
        root.geometry("900x700")
        root.update()
        app.fit_tabs()
        root.update()
        shown = [k for k in app.tab_keys() if app.tab_widgets[k]["frame"].winfo_manager()]
        right = max(app.tab_widgets[k]["frame"].winfo_rootx() + app.tab_widgets[k]["frame"].winfo_width()
                    for k in shown)
        f += check(len(shown) < len(app.tab_keys()) and app.current in shown and
                   app.tab_right.winfo_manager() and right < app.write_btn.winfo_rootx(),
                   "tab strip: too many tabs scroll (whole tabs, the shown one in sight, the buttons kept)")
        start = app.tab_window[0]
        app.scroll_tabs(-1)
        f += check(app.tab_window[0] == max(1, start - 1), "tab strip: ‹ scrolls")
        root.destroy()
    finally:
        mirror.App.scan_loop = saved_scan
        wc.STORE = old_store
        shutil.rmtree(tmp, ignore_errors=True)
    return f


def main():
    f = 0
    for fn in (scale_checks, title_checks, order_checks, strip_icon_checks, app_icon_checks, app_checks):
        f += fn()
    return f


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    failures = main()
    print("\n%s" % ("ALL PASSED" if not failures else "%d FAILURE(S)" % failures))
    sys.exit(1 if failures else 0)
