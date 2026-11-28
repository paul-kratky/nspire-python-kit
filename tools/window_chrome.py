"""The main window's chrome, the parts that are pure logic (the self-test runs them): how big a
calculator's screen is drawn, the tab strip's titles, its order (drag a tab to move it) and
which tabs fit. mirror.App and mirror.Tab use them. MIT licence.
"""

import json
import os
import re

# ---- The live screen's size ----
SCREEN_MARGIN = 24  # Pixels kept clear around a calculator's screen on its tab (some empty space)
TILE_MARGIN = 6     # ...and around one on All screens (the tile's own padding adds to it)
CRISP_SHARE = 0.85  # A whole-number scale is used when it's at least this share of the biggest


def screen_scale(nw, nh, aw, ah, margin=SCREEN_MARGIN):
    """(zoom, subsample) for an nw x nh screen in aw x ah pixels with margin all round: shown
    as picture.zoom(zoom).subsample(subsample). A whole number when it fills most of the space
    (every calculator pixel the same size: crisp); else the largest half step (2.5, 3.5...) that
    fits; smaller than the screen itself: 3/4, 2/3, 1/2 or 1/3."""
    if nw <= 0 or nh <= 0:
        return 1, 1
    best = min((aw - 2 * margin) / float(nw), (ah - 2 * margin) / float(nh))
    if best >= 1:
        whole = int(best)
        half = int(best * 2) / 2.0
        if half > whole and whole / best < CRISP_SHARE:
            return int(half * 2), 2
        return whole, 1
    for z, s in ((3, 4), (2, 3), (1, 2), (1, 3)):
        if z / float(s) <= best:
            return z, s
    return 1, 4


def shown_size(nw, nh, zoom, sub):
    """The picture's size for screen_scale's (zoom, subsample), as Tk makes it"""
    return -(-nw * zoom // sub), -(-nh * zoom // sub)


def screen_width_wanted(nw, nh, aw_most, ah, margin=SCREEN_MARGIN):
    """The width the screen side needs to show the screen as big as it can be with at most
    aw_most pixels across (the panel at its narrowest) and ah down: the panel gives up only that"""
    z, s = screen_scale(nw, nh, aw_most, ah, margin)
    return shown_size(nw, nh, z, s)[0] + 2 * margin


# ---- Tab titles ----
_LEADS = (("Compare backups", "Compare"), ("Make a picture", "Picture"))
_SPLIT = re.compile(r"^(.*?)\s+(?:of|for|to|on) the\s+(.+)$")


def short_title(text):
    """A tab's short title: "Compare backups of the TI-84 Plus CE" -> "Compare: TI-84 Plus CE",
    "Make a picture (TI-89 Titanium)" -> "Picture: TI-89 Titanium". The tab's tooltip (and a
    popped-out window's title) keep the full one."""
    text = " ".join((text or "").split())
    lead, rest = text, None
    m = _SPLIT.match(text)
    if m and m.group(2)[:1].isupper():
        lead, rest = m.group(1), m.group(2)
    else:
        m = re.match(r"^(.*?)\s*\(([^()]+)\)$", text)
        if m and m.group(1):
            lead, rest = m.group(1), m.group(2)
    for long_, short in _LEADS:
        if lead == long_ and rest:
            lead = short
    return "%s: %s" % (lead, rest) if rest else lead


def ellipsize(text, width, measure):
    """text cut to fit width pixels (measure(text) -> pixels) with "…" on the end, whole
    characters only; the text itself when it fits"""
    if measure(text) <= width:
        return text
    lo, hi = 0, len(text)
    while lo < hi:  # The longest start that fits with the ellipsis
        mid = (lo + hi + 1) // 2
        if measure(text[:mid].rstrip() + "…") <= width:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo].rstrip() + "…" if lo else "…"


# ---- Tab order ----
FIRST = "all"  # All screens stays first


def move(order, key, index):
    """order with key moved to index (counted in the list without key); All screens stays first"""
    if key == FIRST or key not in order:
        return list(order)
    rest = [k for k in order if k != key]
    lo = 1 if rest and rest[0] == FIRST else 0
    index = max(lo, min(len(rest), index))
    return rest[:index] + [key] + rest[index:]


def drop_index(edges, x):
    """Where a dragged tab lands: edges = [(left, right)] of the other tabs in order (the one
    dragged left out), x the pointer: the index of the gap it's nearest (before the first tab
    whose middle is right of x)"""
    for k, (a, b) in enumerate(edges):
        if x < (a + b) / 2.0:
            return k
    return len(edges)


def target_index(order, key, others, gap):
    """drop_index's gap among the tabs shown (others, in order, without the dragged one) as
    move()'s index in the whole order (tabs scrolled out of sight count too)"""
    rest = [k for k in order if k != key]
    if not others:
        return len(rest)
    if gap < len(others):
        return rest.index(others[gap])
    return rest.index(others[-1]) + 1


def insert_at(order, key, saved):
    """Where a new tab goes: after the last tab now open that comes before it in the saved order
    (the order the user dragged to last time), else at the end"""
    if key not in saved:
        return len(order)
    before = saved[:saved.index(key)]
    pos = len(order) if not order else None
    for k in range(len(order) - 1, -1, -1):
        if order[k] in before:
            pos = k + 1
            break
    if pos is None:
        pos = 1 if order and order[0] == FIRST else 0
    return pos


def merge_saved(saved, order):
    """The saved order updated with the order now: the tabs open now in their new order, the
    ones not open now kept where they were (relative to their neighbours)"""
    out = [k for k in saved if k not in order]
    for k in order:
        if k in out:
            continue
        # After the item before it in order (already placed), else at the start
        idx = order.index(k)
        prev = order[idx - 1] if idx else None
        if prev is not None and prev in out:
            out.insert(out.index(prev) + 1, k)
        else:
            out.insert(0, k)
    return out


def visible_window(widths, current, avail, first=0):
    """Which tabs to show when they don't all fit: (start, end) of a run of whole tabs, the
    first kept (All screens), the current one (index) always among them; first: the run's
    preferred start (the strip's scroll). Every tab: (0, len)."""
    n = len(widths)
    if sum(widths) <= avail or n <= 1:
        return 0, n
    room = avail - widths[0]
    start = max(1, min(first, n - 1))
    if current is not None and current > 0 and current < start:
        start = current

    def end_from(s):
        used, e = 0, s
        while e < n and used + widths[e] <= room:
            used += widths[e]
            e += 1
        return e

    end = end_from(start)
    if current is not None and current >= end:  # Slide right until the current one fits
        while start < current and end <= current:
            start += 1
            end = end_from(start)
    while start > 1 and end == n and sum(widths[start - 1:end]) <= room:  # Fill to the left
        start -= 1
    return start, max(end, min(n, start + 1))


# ---- The saved order (CalcSuite files/settings/tab_order.json) ----
STORE = None  # Its path (None: paths.user_path("settings")/tab_order.json); the self-test sets one


def _store():
    if STORE:
        return STORE
    import paths
    return os.path.join(paths.user_path("settings"), "tab_order.json")


def load_order():
    try:
        with open(_store(), encoding="utf-8") as fh:
            got = json.load(fh).get("order", [])
        return [str(k) for k in got if isinstance(k, str)]
    except (OSError, ValueError, AttributeError):
        return []


def save_order(order):
    try:
        path = _store()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"order": list(order)}, fh, indent=1)
        return True
    except OSError:
        return False
