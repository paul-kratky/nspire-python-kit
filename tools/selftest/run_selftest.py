"""Self-test for the kit: examples must pass the checker, the bad sample must fail,
and the examples must run on the PC with the shim.

    python -I tools/selftest/run_selftest.py
"""

import os
import subprocess
import sys

# A Windows console in an old code page can't print ►, ∫ or →: never crash on our own output
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(os.path.dirname(HERE))
CHECK = os.path.join(KIT, "tools", "check_nspire.py")
RUN = os.path.join(KIT, "tools", "run_on_pc.py")
PY2TNS = os.path.join(KIT, "tools", "py2tns.py")
FLASH = os.path.join(KIT, "tools", "flash.py")
LUNA = os.path.join(KIT, "tools", "bin", "luna.exe")
PROGRAMS = os.path.join(KIT, "programs")

# Things bad_sample.py must be flagged for (substrings of the checker's messages).
MUST_FLAG = [
    "__future__", "module 'numpy'", "module 'os'", "type hints", "async def",
    "await is not supported", "type annotation on a variable", "f-string", "walrus",
    "match/case", "non-ASCII", "open() is not available", "math.hypot", ".ljust()",
    "list/string of 1000000", "calls itself",
]


def run(args, stdin_text=""):
    p = subprocess.run([sys.executable, "-I"] + args, input=stdin_text, capture_output=True,
                       text=True, cwd=KIT)
    return p.returncode, p.stdout + p.stderr


def version_checks():
    """tools/app_version.py, the driver helper's .rc and the release check agree"""
    import re
    from app_version import VERSION, TEXT
    import release_files
    fails = 0
    rc = open(os.path.join(KIT, "tools", "driver_helper", "calcsuite_driver.rc"), encoding="ascii").read()
    nums = tuple(int(x) for x in re.search(r"FILEVERSION (\d+),(\d+),(\d+)", rc).groups())
    for ok, what in (
            (nums == tuple(VERSION), "calcsuite_driver.rc's FILEVERSION is app_version %s" % TEXT),
            ('"%s"' % TEXT in rc, "calcsuite_driver.rc's version strings are %s" % TEXT)):
        print("%-4s version: %s" % ("PASS" if ok else "FAIL", what))
        fails += not ok
    try:
        release_files.check_version("v" + TEXT)
        release_files.check_version("0.0.0")
        ok = True
    except SystemExit:
        ok = False
    try:
        release_files.check_version("v9.9.9")
        ok = False
    except SystemExit:
        pass
    print("%-4s version: a release tag must match app_version" % ("PASS" if ok else "FAIL"))
    return fails + (not ok)


def paths_checks():
    """tools/paths.py as the packaged app sees it: files beside the exe, the inside-the-zip
    case, and the source tree's old places"""
    import importlib
    import tempfile
    sys.path.insert(0, os.path.join(KIT, "tools"))
    import paths
    failures = 0
    saved = (getattr(sys, "frozen", None), sys.executable)
    try:
        for case in ("unzipped", "inside zip", "unzipped into Temp"):
            base = tempfile.mkdtemp(dir=os.path.join(KIT, "build"))
            if case == "inside zip":  # How Explorer opens an exe inside a zip
                base = os.path.join(tempfile.gettempdir(), "Temp1_CalcSuite-test.zip")
            elif case == "unzipped into Temp":
                base = tempfile.mkdtemp()
            sys.frozen = True
            sys.executable = os.path.join(base, "CalcSuite", "CalcSuite.exe")
            os.makedirs(os.path.dirname(sys.executable), exist_ok=True)
            importlib.reload(paths)
            want = os.path.join(base, "CalcSuite", paths.FOLDER_NAME)
            if case in ("unzipped", "unzipped into Temp"):
                ok = (paths.files_dir() == want and paths.is_portable() and not paths.inside_zip()
                      and paths.cache_dir("x").startswith(os.path.join(want, "cache")))
            else:
                ok = paths.inside_zip() and not paths.is_portable() and paths.files_dir() != want
            print("%-4s paths: %s" % ("PASS" if ok else "FAIL", case))
            failures += not ok
    finally:
        if saved[0] is None:
            del sys.frozen
        else:
            sys.frozen = saved[0]
        sys.executable = saved[1]
        importlib.reload(paths)
    ok = not paths.is_portable() and paths.files_dir().endswith(os.path.join("Documents", "CalcSuite"))
    print("%-4s paths: from the source tree, Documents\CalcSuite" % ("PASS" if ok else "FAIL"))
    return failures + (not ok)


def tns_writer_checks():
    """tools/tns_writer.py: DES against FIPS's test vector; when tools/bin/luna.exe is there
    (a developer build), the same bytes as Luna for every sample program"""
    sys.path.insert(0, os.path.join(KIT, "tools"))
    import tns_writer
    import py2tns
    failures = 0
    ok = tns_writer.des_encrypt(bytes.fromhex("133457799BBCDFF1"),
                                bytes.fromhex("0123456789ABCDEF")).hex() == "85e813540f0ab405"
    print("%-4s DES test vector (the .tns keystream)" % ("PASS" if ok else "FAIL"))
    failures += not ok
    if not os.path.isfile(LUNA):
        print("SKIP byte comparison with luna.exe (not built here)")
        return failures
    import tempfile
    for name in sorted(os.listdir(PROGRAMS)):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(PROGRAMS, name), "rb") as f:
            src = py2tns.normalise(f.read())
        d = tempfile.mkdtemp()
        with open(os.path.join(d, name), "wb") as f:
            f.write(src)
        subprocess.run([LUNA, name, "o.tns"], cwd=d, capture_output=True)
        with open(os.path.join(d, "o.tns"), "rb") as f:
            same = f.read() == tns_writer.python_tns(name, src)
        print("%-4s .tns bytes the same as luna.exe: %s" % ("PASS" if same else "FAIL", name))
        failures += not same
    return failures


def main():
    failures = 0

    for name in sorted(os.listdir(PROGRAMS)):
        if name.endswith(".py"):
            code, out = run([CHECK, os.path.join(PROGRAMS, name)])
            ok = code == 0
            print("%-4s checker passes %s" % ("PASS" if ok else "FAIL", name))
            if not ok:
                print(out)
                failures += 1

    code, out = run([CHECK, os.path.join(HERE, "bad_sample.py")])
    print("%-4s checker rejects bad_sample.py" % ("PASS" if code == 1 else "FAIL"))
    failures += code != 1
    for needle in MUST_FLAG:
        found = needle in out
        if not found:
            print("FAIL   bad_sample.py not flagged for: %s" % needle)
            failures += 1
    if all(n in out for n in MUST_FLAG):
        print("PASS checker flags all %d planted problems" % len(MUST_FLAG))

    cases = [
        ("quadratic.py", "1\n-3\n2\n", "x1 = 2.0"),
        ("quadratic.py", "1\n2\n5\n", "-1.0 + 2.0i"),
        ("quadratic.py", "1\n2\n1\n", "One double root: x = -1.0"),
        ("quadratic.py", "0\n2\n-4\n", "Linear: x = 2.0"),
        ("draw_demo.py", "", "fill_circle(288, 30, 16)"),
        ("probe.py", "", "screen: (318, 212)"),
    ]
    for prog, stdin_text, expect in cases:
        code, out = run([RUN, os.path.join(PROGRAMS, prog)], stdin_text)
        ok = code == 0 and expect in out
        print("%-4s runs on PC: %s -> %r" % ("PASS" if ok else "FAIL", prog, expect))
        if not ok:
            print(out)
            failures += 1

    # .py -> .tns conversion and the one-step flash.py (dry run: no calculator needed).
    if True:  # tools/tns_writer.py: no luna.exe needed any more
        out_dir = os.path.join(KIT, "build", "selftest")
        for name in sorted(os.listdir(PROGRAMS)):
            if name.endswith(".py"):
                tns = os.path.join(out_dir, name[:-3] + ".tns")
                code, out = run([PY2TNS, os.path.join(PROGRAMS, name), "-o", tns])
                ok = code == 0 and "tns OK" in out
                print("%-4s converts to .tns: %s" % ("PASS" if ok else "FAIL", name))
                if not ok:
                    print(out)
                    failures += 1
        if os.path.isfile(os.path.join(KIT, "tools", "bin", "nspire-cli.exe")):
            code, out = run([FLASH, os.path.join(PROGRAMS, "quadratic.py"), "--dry-run",
                             "--out", os.path.join(out_dir, "flash_quadratic.tns")])
            ok = code == 0 and "DRY RUN OK" in out
            print("%-4s flash.py --dry-run quadratic.py" % ("PASS" if ok else "FAIL"))
            if not ok:
                print(out)
                failures += 1
        else:
            print("SKIP flash.py --dry-run (tools/bin/nspire-cli.exe isn't built here)")
        code, out = run([FLASH, os.path.join(HERE, "bad_sample.py"), "--dry-run"])
        ok = code != 0 and "STOPPED: the checker" in out
        print("%-4s flash.py stops on checker errors" % ("PASS" if ok else "FAIL"))
        if not ok:
            print(out)
            failures += 1
        failures += tns_writer_checks()
        failures += paths_checks()
        failures += version_checks()

    failures += ti_basic_checks()
    sys.path.insert(0, HERE)
    import ui_checks  # The app's pure parts: Markdown, keys, symbols, clicks, library, strip
    failures += ui_checks.main()
    import reference_checks  # The Functions panel's reference: entries, 84 tokens, 89 conversion
    failures += reference_checks.main()
    import fast84_checks  # The TI-84 Plus CE's Fast mode: frame format, CSFAST.8xp's hash
    failures += fast84_checks.main()
    import editor_checks  # The program editor's checkers, colours, completions and hints
    failures += editor_checks.main()
    import pc_copy_checks  # Make a PC copy never hangs: faked links, the dialog, the after() queue
    failures += pc_copy_checks.main()
    import emu_checks  # The PC copy's emulator tab, its guide, Test in PC copy: faked windows and CEmu
    failures += emu_checks.main()
    import info_checks  # Info always ends: the doctor's queries, a silent link, waiting requests
    failures += info_checks.main()
    import backup_macro_checks  # Backup compare, single restore, key macros: faked links
    failures += backup_macro_checks.main()
    import solver_checks  # The Solver builder: rearranging, the three programs, run on PC, its frame
    failures += solver_checks.main()
    import picture_checks  # Make a picture: the formats byte for byte, colours, the window (faked)
    failures += picture_checks.main()
    import data_checks  # Data bridge: TI numbers, lists, matrices, the grid, Copy answer (faked link)
    failures += data_checks.main()
    import chrome_checks  # The window: screen size, tab titles, dragging tabs, smooth strip icons, app icon
    failures += chrome_checks.main()
    print("\n%s" %("ALL PASSED" if not failures else "%d FAILURE(S)" % failures))
    return 1 if failures else 0


TI84_SOURCE = """:ClrHome
:Disp "HELLO, world"
:Input "N? ",N
:For(I,1,N)
:If I>=2 and I!=5 or not(I<=1)
:Then
:Disp sqrt(I),I^2,pi*theta,I^-1
:Else
:Output(1,1,-I)
:End
:End
:1.5E-3->A
:-A+2->B
:Repeat getKey
:End
:L1(1)->C
:Prompt X,Y
:While X<=10:X+1->X:End
:Disp "e is e"
:Lbl A
:Goto A"""


def ti_basic_checks():
    """TI-Basic text -> .8xp and .89p (tools/calc_files.py), checked against known bytes and
    the 84 detokenizer. No calculator needed."""
    sys.path.insert(0, os.path.join(KIT, "tools"))
    import calc_files as cf
    failures = 0

    def check(ok, what):
        print("%-4s %s" % ("PASS" if ok else "FAIL", what))
        return 0 if ok else 1

    tok = cf.tokenize_84(TI84_SOURCE)
    failures += check(tok.startswith(bytes.fromhex("e13fde2a48454c4c4f2b29bbc7bbbfbbc2bbbcbbb32a")),
                      "84 tokens: ClrHome, Disp, a string with lower case")
    failures += check(bytes.fromhex("313a353bb03304413f") in tok, "84 tokens: 1.5E-3->A (EE, (-), store)")
    failures += check(bytes.fromhex("b041703204423f") in tok, "84 tokens: -A+2->B starts with (-)")
    failures += check(bytes.fromhex("bc49112b490d2bac825b2b490c") in tok,
                      "84 tokens: sqrt( ^2 pi theta ^-1")
    text = cf.detokenize_84(tok)
    failures += check("If I≥2 and I≠5 or not(I≤1)" in text and "1.5ᴇ⁻3→A" in text,
                      "84 detokenizer reads the tokens back")
    failures += check(cf.tokenize_84(text) == tok, "84 round trip: tokenize(detokenize(x)) == x")
    blob = cf.program_8xp(":ClrHome\n:Disp 1+2", "ZZTEST")
    (t, name, _v, _a, data), = cf.read_ti8x(blob)
    failures += check(t == 5 and name == b"ZZTEST" and data == bytes.fromhex("0600e13fde317032"),
                      ".8xp: header, name, length and checksum read back")
    try:
        cf.program_8xp("Disp 1", "1BAD")
        failures += check(False, ".8xp refuses a bad name")
    except ValueError:
        failures += check(True, ".8xp refuses a bad name")
    # The 89: the bytes its own Program Editor stores for this program (read from a TI-89
    # Titanium, OS 3.10), but for the cursor position (0 here)
    n, vtype, data = cf.program_89_data("zztest()\nPrgm\nDisp 1+2\nEndPrgm")
    failures += check((n, vtype, data) == ("zztest", 0x12, bytes.fromhex(
        "002228290d5072676d0d4469737020312b320d456e645072676d00000019e4e5000008dc")),
        ".89 program as text, as the 89 keeps it")
    _n, _t, data = cf.program_89_data("Disp -3,2E-5\nx^2->y\nIf x>=1 and y!=2\nDisp sqrt(pi)", "abc")
    failures += check(b"Disp \xad3,2\x95\xad5\rx^2\x16y\rIf x\x9e1 and y\x9d2\rDisp \xa8(\x8c)" in data,
                      ".89 characters: (-), EE, ->, >=, !=, sqrt(, pi")
    _n, vtype, data = cf.program_89_data("f(x)\nFunc\nReturn x^2\nEndFunc")
    failures += check(vtype == 0x13 and data.endswith(b"\x17\xe4\xe5\x00\x00\x08\xdc"), ".89 function")
    name, _t, blob = cf.program_89p("Disp 1", "zztest")
    (folder, vname, t, _a, d2), = cf.read_ti89(blob)
    failures += check((folder, vname, t) == (b"main", b"zztest", 0x12) and
                      cf.program_89_text(d2) == "()\nPrgm\nDisp 1\nEndPrgm", ".89p read back")
    _n, _t, data = cf.program_89_data("Disp 10@>Bin,2►Hex\nDisp @int(x^2,x),@d(x^3,x)\n"
                                      "Disp @sum(k,k,1,3),3*@i,5@angle30", "abc")
    failures += check(b"Disp 10\x12Bin,2\x12Hex\rDisp \xbd(x^2,x),\xbc(x^3,x)\rDisp \x8e(k,k,1,3),"
                      b"3*\x97,5\x9f30" in data, ".89 characters: @> and ►, @int( @d( @sum( @i @angle")
    failures += tokenizer_checks(cf)
    failures += bundle_checks(cf)
    return failures


def tokenizer_checks(cf):
    """The 84 tokenizer with TI-Toolkit's token sheet (tivars) and with the builtin table"""
    failures = 0

    def check(ok, what):
        print("%-4s %s" % ("PASS" if ok else "FAIL", what))
        return 0 if ok else 1

    source = cf.token_source()
    failures += check(source.startswith("tivars"), "84 tokens come from tivars (%s)" % source)
    cases = [  # text, the tokens it must give
        ('Disp "REDUCE"', "de2a5245445543452a"),          # A word in a string stays letters
        ('Disp "RED WINS"', "de2aef422957494e532a"),      # ...unless it stands alone
        ('"sin(X)"->Y1', "2ac258112a045e10"),             # A function in a string: its token
        ("MATHPRINT:Thick", "ef373e7e06"),                 # Names from the CE's token sheet
        ("Wait 1:toString(5", "ef96313eef9735"),
        ("e^(1)+e", "bf311170bb31"),
    ]
    for text, hexed in cases:
        failures += check(cf.tokenize_84(text).hex() == hexed, "84 tokens: %s" % text)
    # Tokens a plain name would read back as others: X ^ 2 isn't X², a minus after "(", a ':'
    # starting a line, a → inside a string followed by a space
    for hexed in ("58f032", "10715811", "3ede31", "2a3132042a29bbb0"):
        toks = bytes.fromhex(hexed)
        text = cf.detokenize_84(bytes((len(toks), 0)) + toks)
        failures += check(cf.tokenize_84(text) == toks, "84 round trip of %s as %r" % (hexed, text))
    bad = [b for b, _n in cf._names_84() if b not in (b"\x3f", b"\x3e", b"\x29", b"\x2a") and
           cf.tokenize_84("A" + cf.detokenize_84(b) + "A") != b"A" + b + b"A"]
    failures += check(len(bad) <= 3, "84 round trip of every token on its own (%d of %d don't: "
                      "lower case e, @ and ` share names)" % (len(bad), len(cf._names_84())))
    warnings = []
    cf.tokenize_84("ClrHome\ntextcolor(1,2)\nDisp \"textcolor\",e\nGridOn", warnings)
    failures += check(len(warnings) == 2 and "TextColor(" in warnings[0] and "GridOff" in warnings[1],
                      "84 warns of misspelt commands (textcolor(, GridOn), not of strings or e")
    failures += check(cf.is_compiled_84(b"\x04\x00\xef\x7b\x00\x00") and
                      not cf.is_compiled_84(b"\x02\x00\xde\x31"), "84 compiled programs recognised")
    cf.set_token_source("builtin")
    try:
        tok = cf.tokenize_84(TI84_SOURCE)
        failures += check(cf.tokenize_84(cf.detokenize_84(tok)) == tok and
                          cf.token_source() == "builtin", "84 builtin table (no tivars): round trip")
    finally:
        cf.set_token_source("tivars")
    return failures


def bundle_checks(cf):
    """The backup's group files: a .b84 bundle and a .89g group, read back"""
    import calc_backup as cb
    failures = 0

    def check(ok, what):
        print("%-4s %s" % ("PASS" if ok else "FAIL", what))
        return 0 if ok else 1

    p1 = cf.program_8xp("Disp 1", "ZZTEST")
    p2 = cf.ti8x_bytes([(0x04, b"\xaa\x00", 0, False, b"\x01\x00\x31")])
    blob = cb.b84_bytes([("ZZTEST.8xp", p1), ("Str1.8xs", p2)])
    failures += check(cb.read_b84(blob) == [("ZZTEST.8xp", p1), ("Str1.8xs", p2)],
                      ".b84 bundle: the files and the checksum read back")
    try:
        sys.path.insert(0, os.path.join(KIT, "tools", "third_party_py"))
        from tivars.bundle import TIBundle
        b = TIBundle()
        b.load_bytes(blob)
        failures += check(b.metadata["bundle_target_device"] == "84CE" and len(b.unbundle()) == 2,
                          ".b84 bundle read by tivars")
    except ImportError:
        print("SKIP .b84 bundle read by tivars (not found)")
    _n, t1, d1 = cf.program_89_data("Disp 1", "zza")
    _n, t2, d2 = cf.program_89_data("Disp 2", "zzb")
    g = cb.ti89_group_bytes([(b"main", b"zza", t1, False, d1), (b"zzdir", b"zzb", t2, True, d2)])
    got = cf.read_ti89(g)
    failures += check([(f, n, d) for f, n, _t, _a, d in got] == [(b"main", b"zza", d1), (b"zzdir", b"zzb", d2)]
                      and got[1][3], ".89g group: two folders, the data and the archive flag read back")
    return failures


if __name__ == "__main__":
    sys.exit(main())
