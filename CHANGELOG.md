# Changelog

What changed in the kit, newest first. Tested on a TI-Nspire CX II CAS, OS 6.40, Windows 11.

## [Unreleased]

### Changed

- **Drag tabs to rearrange them.** Drag a tab left or right (calculators, tools, PC copies, the
  editor; All screens stays first): an orange bar shows where it lands, a plain click still
  just opens it. The order is kept in `CalcSuite files/settings/tab_order.json` for next time.
- **Tab titles fit.** Tool tabs get short titles ("Compare: TI-84 Plus CE", "Picture: TI-89
  Titanium"), cut with "…" at whole letters when long, the full title in a tooltip. Many tabs
  first lose their status text, then get shorter, then the strip scrolls with **‹ ›** (or the
  mouse wheel); **Write a program** and **Open in its own window** always keep their place.
- **Bigger live screens.** A calculator's screen fills its side with a ~24 px margin: a whole
  number of times when that fills most of it, else in half steps (x 2.5, x 4.5); the side panel
  gives up width when that lets the screen be bigger (the TI-89 at 1600 px: x 6 instead of a
  small picture in a black box). All screens' tiles too.
- **Smooth side strip icons.** The panel's icons are drawn antialiased for the screen's scale
  (crisp at 100%, 150% and 200%), not as jagged Canvas lines.
- **App icon:** the original design is back (the monitor with the orange calculator and its
  screen), with 16, 20, 24 and 32 px laid out on whole pixels (not fuzzy) and every part a
  pixel inside the tile (it looked cut off at the corner).

## [1.0.3] - 2026-11-28

### Added

- **Write programs with no calculator plugged in.** **Write a program** is always in the tab
  strip; All screens with nothing plugged in offers **Program editor**, **Solver builder** and
  **Make a picture**. The editor lists every model (a model not plugged in says so): pick one
  and its language, checker, Build, Save and Test in PC copy work; **Send** and **Send and run**
  are greyed with "Plug in a TI-84 Plus CE to send" until that calculator connects, then the
  editor aims at it by itself.
- **Go to macros and quick access** (Macros panel): built-in macros that only open a screen or
  a menu (TI-84 Plus CE: Home, Y=, WINDOW, TABLE, MODE, STAT EDIT, MATRIX, PRGM, MEM; TI-89
  Titanium: Home, Y=, WINDOW, GRAPH, TABLE, Var-Link, MODE; TI-Nspire: Home, Scratchpad
  Calculate and Graph). **Pin under the screen** makes any macro a button after Copy answer;
  **Hotkey ▾** gives it Ctrl+1..9 on that calculator's tab (not on All screens, in a text box or
  in a PC copy; a key in use moves after a yes). Pins and hotkeys are saved with the macros; the
  Keys panel lists the hotkeys.
- **Compare backups** (Files, **Compare...**): two backups of a calculator, or a backup and the
  calculator now (read in full, or only its list for a quick look), as a list of what was added,
  removed and changed (by SHA-256), with sizes and dates. **Show the difference** shows a
  program's text side by side or as a unified diff (84 TI-Basic, the 89's texts and programs not
  yet run, Nspire `.py` and the Python inside a `.tns`). **Restore this one** sends a single
  item from a backup back, asking before it replaces anything. `tools/backup_compare.py` does
  the same on the command line.
- **Key macros** (a **Macros** panel on every calculator's tab): record keys, save them by name
  per calculator model (`CalcSuite files\macros`), play them back through the same paced path as
  typing, with optional waits; edit (rename, reorder, add or remove keys, waits), duplicate,
  delete, import and export. A few harmless examples per calculator. A macro with keys that
  delete, clear or open a reset menu asks before its first replay.
- **Solver builder** (Program editor > **Solver builder...**): type equations once (with units
  and descriptions) and get a menu-driven solver for the TI-Nspire (Python), the TI-84 Plus CE
  and the TI-89 Titanium. Unknowns are rearranged on the PC by CalcSuite's own small rearranger
  (+ - * / ^, roots, ln/log/exp, trig; linear after clearing fractions, like a divider's R2);
  the rest are solved in the program from a guess (secant method on the Nspire and the 89, the
  84's `solve(`). Every program passes the editor's checkers before it can be sent or saved.
  Eight ready-made engineering sets. A frame that can live in a main-window tab.
- **Data bridge** (a new **Data** section in the side panel): the TI-84 Plus CE's and TI-89
  Titanium's lists and matrices in a spreadsheet-style grid inside the panel (edit, add or
  remove rows and columns, copy and paste tab-separated text with Excel, import and save CSV),
  sent back under a name you choose, and a quick plot (a list against its index, or x against y).
  Lists go to the TI-Nspire as a small program (`zzdata.tns`) that stores them when run; its
  lists can't be read back over the link. Guide: `docs/DATA_BRIDGE.md`.
- **Copy answer** (the tab's button row and the Data section): the last answer on the PC
  clipboard with every digit the calculator keeps ("Copied 0.33333333333333 from the TI-84 Plus
  CE"). Neither calculator hands its answer over the link, so CalcSuite types a store on the home
  screen and reads it: the 84 `{Ans}→ZZANS`, the 89 `ans(1)→zzv` (only on its Home screen;
  exact answers stay exact: `1/3`); both are removed after. The Nspire's link has no command for it: the button says so.
- TI's number formats in `calc_files.py`: 84 reals, complex numbers, lists, matrices and OS 5's
  exact forms; 89 integers, fractions, floats, complex numbers, lists and matrices, with
  round-trip self-tests and three new fuzz targets.
- **Your PC copy in a tab of the window.** "TI-84 Plus CE (PC copy)" runs CEmu with your own
  ROM, "TI-89 Titanium (PC copy)" TiEmu: the emulator's own window inside the tab, just the
  calculator (screen and keypad; **CEmu's panels** brings CEmu's docks and menus back), with
  **Send files...**, **Screenshot**, **Start again from the backup**, **Open in its own window**
  (and back), **Close**. Click into it to type; other tabs get the keyboard back. Closing
  CalcSuite closes the emulators it started (CEmu saves its state), never others. CEmu runs with
  its own settings and state inside `CalcSuite files`, apart from a CEmu you start yourself.
  TiEmu, which has only an installer, is found where you installed it; if its window can't go
  into the tab it opens beside the window.
- **Make a PC copy happens in that tab** (no separate window): the steps, one overall bar,
  Cancel, and when it's done the bar full and green, "Done: 100%", "Your PC copy is made", then
  the copy starts there. **Open my PC copy** opens the tab.
- **Test in PC copy** (Program editor, TI-84 Plus CE): builds the program and runs it in a
  CEmu of its own with your ROM (CEmu's autotester): the keys you give, then the screen it ended
  on, and passed or failed against the screen you said to expect. The calculator isn't touched.
  Also `python -I tools/pc_test.py PROGRAM.8xp --keys "..." --expect CRC`.
- **The PC copies guide** (`docs/EMULATORS.md`, the tab's Guide, `CalcSuite - PC copies (CEmu
  and TiEmu) guide.pdf`): making a copy, the tab, CEmu's complete key table (from CEmu's wiki),
  its shortcuts, sending and getting files, screenshots and recordings, speed, its saved state,
  the command line CalcSuite uses, Test in PC copy, TiEmu (installing, its keys and menu, what's
  not checked yet), where everything is kept, common problems.

- **Make a picture** (Files panel): a PC picture (open a PNG, JPEG, BMP, GIF or TIFF, paste one
  with ctrl+V, or drag one in) made into the calculator's own picture, with a live preview at
  the calculator's resolution and colours; Fit / Fill / Stretch, dithering (Smooth, Pattern,
  None), brightness and contrast; **Send** to this tab's calculator or **Save** the file.
  TI-84 Plus CE: **Image1-0** (`.8ca`, a graph background, 133 x 83 in full colour) or
  **Pic1-0** (`.8ci`, 265 x 165 in the 15 colours). TI-89 Titanium: a picture (`.89i`, black
  and white, 159 x 77, 160 x 100 or 240 x 128). TI-Nspire CX II: a Python program that paints
  it with ti_draw (8-64 colours of its own, the finest pixel size that keeps it under 20 KB).
  Windows' own GDI+ reads the pictures (phone photos the right way up): no new dependency.
- **Get programs in sections** for each calculator: Electrical, Mechanical, Chemistry, Physics,
  Math, Computer engineering, Utilities and **Games** (8 for the TI-84 Plus CE, 7 for the TI-89
  Titanium, 8 for the TI-Nspire CX II), with a **Search** box that filters as you type. 51 new
  entries from ticalc.org, each downloaded and opened to check what it sends. Get all leaves the
  games out (send them one by one).
- **The version in the app**: the title (`CalcSuite 1.0.3`) and Calculator info, with a link
  to the releases (one place: `tools/app_version.py`; a release tag must match it).
- **Fuzzing**: an atheris harness for everything CalcSuite reads from outside (TI files,
  TI-Basic text, the link helpers' listings, TI's OS page), 2 minutes on every push and pull
  request and 30 minutes weekly; a quick run in the self-test.
- **Signed releases**: each release also carries its signed build provenance as
  `<zip>.intoto.jsonl`; 0.1.0 to 1.0.1 got the owner's SSH signatures (`.sig`, the key in
  `.github/allowed_signers`, SECURITY.md says how to check).

### Changed

- **The side panel's sections are a strip of icons** along the window's right edge (Files,
  Keys, Symbols, Functions, Data, Programs, Macros, Guide, Info), each with a short label; the
  picked one is orange with a bar on its edge, and the section's full name heads the panel
  ("Get programs", "Calculator info"). The PC copy tabs' Keys / Guide use the same strip. The
  panel still starts at about half the window, and its handle still drags and snaps.
- **Tools open as tabs of the window**, with a ✕, not as windows: Make a picture, the Solver
  builder, Compare backups and its text differences, the macro editor, Get all, Restore, a
  program's text and Test in PC copy. **Open in its own window** pops a tool tab out too.
  File pickers and yes/no questions stay dialogs.
- **Four buttons under a calculator's screen**: Screenshot, Record, Send program..., Copy
  answer, then your pinned macros and **More ▾** (Copy screen, Paste text, Reconnect, Program
  editor..., Make a picture..., Macros...). **Reconnect** also shows beside it while the link is
  down. The checkboxes are one row below.
- **One accent colour**: orange marks only what's picked or where you are (the tab, the panel
  section, the keyboard target, progress bars, the panel width's snap, a tab still connecting).
  Mint is only a connection (a connected calculator's dot) and links. Warnings are amber, added
  items in Compare blue.
- **The tab strip's connection dot is round and smooth** (drawn antialiased, sized to the
  screen's scale), no longer a jagged Canvas oval.
- **Type sizes**: headings 16 px semibold, text 13 px, hints and status lines 12 px (nothing
  smaller except the strip's labels); the status line under the screen and the panel texts got
  bigger.

- **The side panel starts at about half the window** (it was a fixed 450 pixels) and keeps that
  share when the window changes size; a width you drag to stays for the session, double-click
  the handle for the default again.
- **Info is now "Calculator info".**
- **The README is short**: a sentence and a full-size screenshot per feature, nothing folded.
  The full guide is now `docs/USER_GUIDE.md` (the User guide PDF). New screenshots from the
  real app on the three calculators.
- The app icon's small sizes keep the calculator clear of the corner (it read as cut off in
  the title bar), and windows use the icon's own small drawings.
- `Nspire Mirror.bat` (the old name's launcher) is gone: `CalcSuite.bat`.

### Fixed

- Sending several TI files in a row (Restore, Get all, Make a picture) can no longer lose its
  "Sent" message when the calculator answers the first file before the rest are queued.
- **Make a PC copy never stays on "Letting go of the link..."** (TI-84 Plus CE and TI-89
  Titanium): the ROM was dumped and saved, but the window never heard. The app's own module was
  loaded twice (as the program and by the panels' `import mirror`), and the second copy sent
  every background thread's window work to a queue nothing ran. That also froze the PC copy
  window's **Download TiEmu's installer** and **Open in CEmu** on their first status. Now one
  module, and the PC copy window takes its workers' news through its own inbox.
- The PC copy can't hang: every link command is ended when it says nothing for 2 minutes,
  Cancel ends the step it's on at once (and the window stops waiting 30 s later if a step
  still doesn't end), the mirror has 40 s to let go, every stage updates the status line, the
  TiEmu download shows its percentage, and errors go to `CalcSuite files\logs\errors.log`.
- **One progress bar for the whole PC copy**, weighted by stage (backup, garbage collect, the
  dump, reading it back, cleaning up): it only moves forward and reaches 100% when it's made,
  with "Overall n% - step n of m" under it. Before, each stage restarted the bar and the waits
  made it bounce back and forth.
- **Info always ends with an answer.** The same lost queue left **This calculator** on "Asking
  the calculator...", **Clock** on "reading..." and the **Connection doctor** on "Checking
  Windows' drivers..." for good, and a tab's status on "Connecting...". Besides that fix: a
  request still unanswered after 8 s says why it waits (not connected yet, or the link busy or
  stuck), and the link helper is stopped and restarted when it says nothing for 2 minutes.
- **The connection doctor always finishes**, normally in about a second and within about 20 s
  at the worst: each Windows query has its own time limit (a program that couldn't be stopped
  used to hold the check forever), one that fails or never answers is listed ("Not checked:
  ...") and written to errors.log, and the report is made from the others.
- **The TI-Nspire's "one connection per plug-in" is said plainly**: when it doesn't answer a new
  connection, the tab and Info say "The TI-Nspire isn't answering: unplug it, wait 3 seconds,
  plug it back in (it allows one connection per plug-in)" instead of "Connecting...".
- **Set the clock to the PC's time no longer freezes the TI-84 Plus CE.** It wrote each field
  and then asked for it ten times a second while the CE's clock was still taking it (up to 30
  requests a field, up to 12 writes). Now each field is written once, the link stays quiet for
  1.1 s while the clock takes it, then it's read back a few times 0.4 s apart; nothing more is
  written over a field that hasn't landed (an error instead), the date never passes through an
  invalid day (31 January to February), and the live picture waits 3 s after the clock is set.
  About 1.5 s a field changed (the TI-89 Titanium's one write is unchanged).
- **TI-Nspire symbols type the real symbol, never a spelling** (1.0.2 typed `integral(`,
  `infinity`, `/=`, `@i`, `@e`, `@<`, `@d`, `@E`, `@>`, `abs(`; TI's `@` spellings work only from
  a computer keyboard). The Symbols panel and Ctrl+V press the handheld's own keys: ∫ d/dx Σ the
  Calculus menu's templates (menu 4; a CX II without CAS gets its own numbers), π x² (-) EE
  their keys, √ ctrl x², → ctrl var, |x| the catalog's template tab, θ ∞ ≤ ≥ ≠ 𝑖 ℯ ∠ ⁻¹ ► the
  symbol palette, ° ± as themselves. Pasted `∫(`, `Σ(`, `∂(` with their arguments stay TI's
  function form (`integral(`...), shown as ∫ Σ d after Enter; a lone ∫ or Σ is the template. A
  long paste is cut into commands between symbols, never inside one.
- **Resizing the side panel:** Symbols couldn't get narrower than its buttons (the grid now
  reflows, 6 to 12 columns), and the Keys and Calculator info text kept a fixed width (cut off in a
  narrow panel, a narrow column in a wide one): it wraps to the panel now.
- **The TI-Nspire never connected when CalcSuite ran from the source**: `nspire-cli.exe`
  needed `libwinpthread-1.dll`, found only on MSYS2's PATH or inside the packaged app. It is
  linked fully static now.

## [1.0.2] - 2026-11-28

### Added
- **The Program editor is a tab** of the main window (beside All screens and the calculators),
  not a separate window: **Program editor...** under a calculator's screen opens it aimed at that
  calculator. The tab shows the file's name (a dot while unsaved) and closes with its ✕.
- **Delete all programs...** (Nspire: **Delete all documents...**) and **Reset the
  calculator...** in **Info**, both after a full backup. The TI-84 Plus CE's reset (Clear RAM or
  Everything) presses its own 2nd MEM > Reset menu, after you type `RESET`; the 89 and the
  Nspire show the steps on the calculator.
- **Ctrl+Backspace / Ctrl+Delete** delete a word at a time in the editor.
- **Resizable panels:** drag the handle between the screen and the side panel, and in
  Functions between the list and the description.
- Functions and Get programs: a scrollbar on the description, and a hint while nothing is picked.
- **errors.log:** every error inside the window is written to
  `CalcSuite files\logs\errors.log` instead of passing silently.
- **Trust:** the release is built and attested by GitHub (`gh attestation verify`), carries its
  signed attestation bundle, a VirusTotal scan in its notes and signed tags; SECURITY.md (private
  reporting), CodeQL code scanning, Dependabot, OpenSSF Scorecard.
- **GitHub Package:** the same zip at `ghcr.io/paul-kratky/calcsuite` (`oras pull`).

### Fixed
- **Info could stay on "Asking the calculator..." for good** (and the driver check on
  "Checking..."): an error while drawing a calculator's screen stopped the loop that hands
  background results to the window. That loop can't stop now, and the error is logged.
- The README's and the quick start's steps match the zip (the quick start was the old
  Nspire-only kit guide); `LICENSE` is the plain MIT text (exceptions in `LICENSING.md`).

### Changed
- The button is **Program editor...** (was Editor...).

## [1.0.1] - 2026-11-27

### Changed
- **One zip to download:** `CalcSuite-<version>-win64.zip` holds the CalcSuite folder (the app,
  its link tools, the guides as PDFs, the licences). Unzip it anywhere; nothing is installed.
- **Everything CalcSuite saves stays in that folder**, in `CalcSuite files`: captures
  (screenshots, recordings, GIFs), programs you write and send, backups, ROMs, downloads, and
  CalcSuite's own downloads (ffmpeg, the emulators) in its `cache` (`tools/paths.py`). Opened
  from inside the zip without unzipping, it says so and saves to `Documents\CalcSuite`.
- **No more antivirus false alarms (Defender's `Bearfoos.A!ml` on luna.exe):** the app is a
  folder instead of one exe unpacking its tools into `%TEMP%` at every start, PyInstaller's
  launcher is built from source in the release build, UPX is off, and every exe carries version
  information. `luna.exe` is gone: `tools/tns_writer.py` (a Python port of Luna's writer, MPL-1.1)
  writes the same .tns bytes; the self-test compares them with luna.exe.
- **The USB driver from CalcSuite, Zadig only as the fallback:** a calculator with no driver
  CalcSuite can use gets its tab opened on Info, with the driver setup started (it shows what
  will change; Windows asks for admin rights once).
- **Resizable panels:** drag the handle between the screen and the side panel, and between the
  Functions list and its description. The Functions list is taller.
- **Info no longer looks stuck** while its calculator isn't connected: it says it's waiting.

## [1.0.0] - 2026-11-27

### Added
- **The program editor** (`tools/editor.py`, checks in `tools/code_check.py`, both MIT): TI-84
  Plus CE and TI-89 Titanium TI-Basic and Nspire Python, checked as you type (unknown words,
  block structure, argument counts from the Functions reference, stores, labels, screen
  positions, the 89's function rules, Python's syntax, TI's modules, undefined names), each
  mistake underlined at its exact place with a fix; VS Code Dark+ colours, completion, syntax
  hints, Build (Ctrl+B) into `Documents\CalcSuite\programs\<calculator>\`, F5 send and run,
  open from the calculator, Copy AI instructions / Copy problems for the AI; it never loses
  unsaved changes. `tools/selftest/editor_checks.py` tests every rule.
- **The guides as PDFs, dark like the app.** **Save as PDF** in the Guide and Functions panels
  saves the calculator's guide or its Functions reference (every command by category, with its
  syntax, arguments, result, example and keys) where you pick (Documents\CalcSuite to start)
  and offers to open it. `docs/pdf/` has them all, the user guide, quick start and Python kit
  too; `tools/docs_build/make_pdfs.py` rebuilds them (headless Edge, standard library only:
  `tools/docs_build/md_to_pdf.py`), and the release build does so and attaches them.
- **Fast mode for the TI-84 Plus CE (experimental, off by default).** CSFAST
  (`tools/fast84/csfast.asm`, our own eZ80 assembly, MIT; the prebuilt `CSFAST.8xp` is
  committed with its SHA-256, `tools/fast84/build.py` rebuilds it byte for byte with the CE
  toolchain's fasmg) installs a key hook. Two key codes the OS doesn't use make it pack the
  screen (changed rows only, as runs) into RAM AppVars, read with the normal variable request.
  Measured on OS 5.4.0: 6.7 fps on a still home screen (0.9 before), 4.6 while typing, a key
  shows in about 0.32 s (2.2 s before). `ti84-cli` gets `snap FILE` (falls back to `shot` by
  itself) and `fast status|on|off`; the mirror's API is `Mirror.set_fast(on, done)` and
  `Mirror.fast_status()`. Home screen (and its menus) only: on the graph, table, Y= and mode screens a variable read
  would send the calculator home, so those get normal screenshots. Refused on OS 5.5+
  (assembly needs arTIfiCE there). A reset
  calculator is noticed and the mirror goes back to normal screenshots. Fast mode off removes
  the hook and every variable it made.

### Changed
- **One window, and the app is called CalcSuite.** A tab strip: **All screens** first (every
  connected calculator's live screen side by side, with its frame rate, Screenshot and
  Record; click a screen to type on it, orange outline and a KEYBOARD tag; double click opens
  its tab), then a tab per calculator (a status dot, its name, its frame rate). **Open in its
  own window** pops a calculator out into a window of its own; closing it docks it back. A
  calculator plugged in later gets a tab; one unplugged greys out ("not plugged in") and comes
  back when it's plugged in again. Each calculator still has its own link thread, as before
  (keys first, keep-alive, paste, copy, recording, Send program, Files, Backup, Restore,
  About). Dark everywhere (true black, an orange accent for the calculator you type on, mint
  for what's OK), plain Tk.
- The exe is `CalcSuite.exe`; `CalcSuite.bat` starts it from the source (`Nspire Mirror.bat`
  still works and calls it). Its files are in `Documents\CalcSuite`: the first start copies
  what's in `Documents\Nspire Mirror` (captures, programs, ...) there, never replacing a file,
  and leaves a note in the old folder (nothing is deleted). Only one CalcSuite runs at a time,
  and it also sees an old Nspire Mirror that's running. Saved TI files say "Saved by CalcSuite".
- The TI-84 key name `i` pressed imag( (0xFC83, a wrong entry); it is now 𝑖 (0xEE).
- **Nspire link:** a lost packet costs seconds, not minutes (each read waits 2 s, not 60 s, and
  a call gives up after 4 s for an ack or 10 s for an answer), and a packet that arrives in two
  USB transfers is no longer dropped by a checksum over the wrong length. In `serve`, the key
  service stays open between `key`/`keys` commands (a key command: 4.9 ms → 3.5 ms). Each
  screenshot still opens its own connection: reusing one saved ~1.5 ms a frame, but every
  60-400 frames the CX II never answered the request.

### Added
- **Get programs > Get all...:** every program CalcSuite can send by itself for the calculator
  in one list: its size (downloaded one at a time to measure, into the cache), notes (ASM on
  OS 5.5+ needs arTIfiCE, libraries, large items), whether it's on the calculator already, and
  the total against the free RAM/archive. **Send all to the calculator** (asks once before
  replacing: all, skip those, or cancel) or **Save all to the PC** (default
  `Documents\CalcSuite\library`, never over a different file); progress per item, failures
  don't stop the rest, a summary at the end. Page-only and TI items are listed as left out.
- **Info > Make a PC copy...** (84 Plus CE, 89 Titanium): says what happens, asks, pauses the
  mirror, runs the ROM dump with a progress bar and Cancel, reconnects, then offers **Open in
  CEmu** (84) or TiEmu's installer to run yourself (89); **Restore...** when RAM items went
  missing. **Open my PC copy** opens the newest ROM.
- Get programs: a send pattern also matches inside a zip's wrapping folder (the 89's Control
  System Toolbox had nothing to send).
- **A calculator's tab:** the screen big, **Screenshot**, **Copy screen**, **Paste text**,
  **Record**, **Send program...**, **Keyboard** on/off, a **Last key: F5 → GRAPH** line, and a
  side panel: **Files** (the file manager, with Back up / Restore), **Keys**, **Symbols**,
  **Guide**, **Get programs** and **Info**.
- **Keys:** which PC key presses which calculator key, grouped (Top row, Menus, Editing,
  Mouse), made from the same table the keys use (`tools/calc_models.py`), so it can't be out
  of date. The key you just pressed lights up.
- **Key history:** the last 8 keys as keycaps under the screen. **Show keys in recordings**
  puts that strip into every GIF/MP4 frame (the 89's small screen is doubled first so the keys
  stay readable). Tested on the Nspire: a GIF and an MP4 with "1 + 2 enter" in the strip.
- **The mouse on the 84 and the 89.** TI-89 Titanium: a click on a toolbar tab presses its F
  key (the tabs are found in the picture: they're as wide as their names), right click ESC,
  middle click HOME, double click ENTER, the wheel the arrows. TI-84 Plus CE: a click on a
  numbered menu line (MATH, PRGM, VARS, ...) picks it (arrows to it, then ENTER, so a
  scrolled menu and lines 0: and A: work too; the menu is recognised by its highlighted number
  block and the number-colon column, measured on OS 5.4.0), right click CLEAR, double click
  ENTER. Clicks map through the picture's real size and offset, at any zoom. Tested: the 89's
  F2 tab opened Algebra and a right click closed it; on the 84, a click on MATH's line 8 typed
  nDeriv(.
- **Symbols:** ∫ d/dx √ π θ Σ ∞ ≤ ≥ ≠ → i e ∠ ° ² ⁻¹ ‾ ± × ÷ ^ E ! |x| and more, per
  calculator; a click types it. A symbol the calculator lacks is greyed and says what to use.
  TI-84 Plus CE: its own keys (fnInt(, nDeriv(, the TEST menu's = ≠ > ≥ < ≤, 𝑖, e, °, ʳ, ³,
  ³√, ˣ√, !, abs(; from TILP's key list), each tried on a TI-84 Plus CE, OS 5.4.0. TI-89
  Titanium: 2nd 7 ∫(, 2nd 8 d(, √(, and the 89's own characters (π θ Σ ∞ ≤ ≥ ≠ → 𝑖 ℯ ∠ °),
  each tried on a TI-89 Titanium, OS 3.10. TI-Nspire: the spellings TI's handheld turns into
  symbols (`integral(`, `derivative(`, `sqrt(`, `pi`, `<=`, `/=`, `=:`, `@i`, `@e`, `@<`,
  `@d`, `@>`, `infinity`), tried on a CX II CAS, OS 6.4.
- **Ctrl+V types these symbols too,** on each calculator. The 84 can now be pasted `=`, `<`,
  `>`, `!` and the ≤ ≥ ≠ → √ π θ ² ³ ⁻¹ 𝑖 ℯ ° symbols; the 89 every character of its own set;
  the Nspire any ASCII character (`!`, `@`, `_`, `{`, `[`: its key code is the character code)
  and the symbols above. On the Nspire a pasted `x^2+1` now leaves the exponent after the 2
  (the ^ key opens a raised box), and `√(16)` leaves the root's box.
- **Guide:** the calculator's guide (TI-Basic for the 84 and the 89, Python for the Nspire)
  rendered in the app: headings, lists, tables, code, links (they open in the browser), a
  Contents list and search. Every example with a name has **Copy** and **Send to
  calculator** (TI-Basic through the same path as Send program; Python checked and converted
  first). Tested: an 84 example sent as ZZTEST, an 89 one as zztest, a Python one to the
  Nspire as zztest.tns, all deleted after.
- **Get programs:** a short list of programs picked for engineering work, per calculator
  (`tools/program_library.json`, from the research in `docs/dev/program_library_research.md`):
  name, description, category, author, licence, source, verified ones first and unverified
  ones marked. **Download and send** downloads from ticalc.org or GitHub only when you click
  (CalcSuite/1.0 User-Agent, kept in `%LOCALAPPDATA%\CalcSuite\library`), picks the right
  files from the zip and sends them (asking first, and before replacing anything; Nspire
  libraries go to MyLib with a Refresh Libraries note). Cemetech, TI-Planet and Flash-app items
  open their page; TI's own apps open TI's page (their licence) and are never downloaded by
  CalcSuite. Assembly programs on the 84 say "needs OS 5.4 or older" and are checked against
  the connected 84's OS. Tested: Converty downloaded and sent to a TI-84 Plus CE, then deleted.
- **Info:** model, OS, free memory, the OS update check, the clock and Set the clock, Exit
  Press-to-Test, Reconnect, and the connection doctor for this calculator, with its fix
  buttons. Install / Restore TI's driver first runs the helper's dry run and shows its steps;
  only OK starts the real change (Windows' admin prompt). A "Support CalcSuite" link appears
  once a sponsor page is set (`SPONSOR_URL` in `tools/mirror.py`).
- Self-test: the Markdown parser, the Keys panel against the key table, every symbol, the
  paste maps, the 84 menu and 89 toolbar clicks on made-up screens, the program list and zip
  picking, the key strip, the Documents move (`tools/selftest/ui_checks.py`).
- **Back up... and Restore...** in **Files...** (and `python -I tools/calc_backup.py backup|show|restore`).
  A backup is a folder, `Documents\CalcSuite\backups\<model>-<date>\`, with a `manifest.json`
  (the calculator, every file with its name, type, size, archived flag and SHA-256, what was
  skipped and why, what failed). TI-Nspire: every file in every folder the link shows, folder
  tree kept, empty folders too. TI-84 Plus CE: every variable as its TI file, and all of them
  in one TI Connect CE bundle (`.b84`: a ZIP with METADATA and _CHECKSUM, the layout tivars
  reads and writes; not tried in TI Connect CE). TI-89 Titanium: every variable as its TI file
  in a folder per calculator folder, and one `.89g` group. Apps and the OS can't be read over
  the link: they're listed as skipped. Restore shows what's in a backup and what's already on
  the calculator, sends the picked items one by one (Nspire folders made when missing), asks
  before replacing any name (replace / send only the others / cancel), and never wipes the
  calculator. Tested on all three: backups of the TI-Nspire CX II CAS (OS 6.40, 15 files,
  0.85 MB, 12 s), the TI-84 Plus CE (OS 5.4.0, 69 variables, 222 KB, 5 s; 18 apps skipped;
  two backups byte for byte the same; every file and the .b84 read by tivars) and the TI-89
  Titanium (OS 3.10, 6 variables; 8 apps skipped; the .89g matches the single files). Restore
  on each with a test item only (`zztest`, made for the test and deleted after): skipped while
  it was there, sent back after deleting it, the calculator's copy byte for byte the backup's;
  on the Nspire into a folder the restore had to make again. The Files window's buttons, the
  restore list and the replace question were driven by a script on all three calculators.
- **The calculator's clock** in **About this calculator**: its date and time against the
  PC's, and **Set the clock to the PC's time** (TI-84 Plus CE, TI-89 Titanium). Only the date
  and time change, not the calculator's date or time format. `ti84-cli clock`, `setclock now`
  or `setclock YYYY MM DD hh mm ss`. Tested: the TI-84 Plus CE (was 2015-01-01) and the TI-89
  Titanium (was 1997-10-20) set to the PC's time and read back within a second, also across a
  date change on the 84. The 84 Plus CE takes the time field by field and drops a field sent
  before the last one has landed, so each one is read back first (about 3 s). The TI-Nspire's
  clock can't be read or set over USB (libnspire and TILP have no command for it); About says
  so.
- **Exit Press-to-Test...** in **About this calculator**, TI's own way only (CalcSuite sends no
  test-mode command): for the TI-Nspire CX II, CalcSuite lets go of the handheld (until
  Reconnect) and opens TI-Nspire CX II Connect; for the TI-84 Plus CE, TI's steps from
  "Getting Started with the TI-84 Plus CE" (p. 60) with a link to TI's page. The TI-89
  Titanium has no Press-to-Test (its guidebook has none), and the button says so. Tested: the
  Nspire window lets go and reconnects; nothing was tried on a calculator in Press-to-Test.
- **Exact TI-84 TI-Basic:** the 84's tokenizer and detokenizer use TI-Toolkit's token sheet
  through `tivars` 1.1.1 (MIT, in `tools/third_party_py/`, nothing installed): all 808 tokens of
  the TI-84 Plus CE's current OS by the names it shows (TI-Toolkit's typing names work too),
  where our own table had 563 and some CE names wrong (MATHPRINT, CLASSIC, AUTO, DEC, Thick).
  Our table stays as the fallback. Inside strings a word stays letters unless it stands alone
  ("REDUCE" is letters), and a function at a word's start stays its token (`"sin(X)"→Y₁`).
  The viewer reads each line back and, where a plain name would come back as another token
  (`X^2` typed as `^` `2`, a minus after `(`), writes it so it does. Checked on the 84's own
  TI-Basic programs (about 4,400 lines): all but 15 lines read back byte for byte, and those
  have tokens typed inside a sentence in a string, which text can't tell from letters (one
  notes program also keeps spaces outside strings, which CalcSuite drops). Compiled (assembly)
  programs now say so instead of showing their bytes as tokens.
- **Warnings for misspelt 84 commands:** a word outside a string with lower case letters that
  isn't a command (`textcolor(`, `GridOn`) is reported before sending, with the command meant
  (`TextColor(`): the calculator would stop there with ERR:SYNTAX. Send program asks whether to
  send anyway; `send_ti.py` prints a WARNING.
- **TI-89 symbols from the PC:** `@>` (or ►) for the conversion operator (`10@>Bin`,
  `3_m@>_ft`), `@int(` ∫(, `@d(` d(, `@sum(` Σ(, `@angle` ∠, `@i` 𝑖. Tested on a TI-89
  Titanium, OS 3.10: a test program showed 0b1010, 0hFF, 1250/127·_ft and the right
  derivative, integral and sum.
- **TI-89 Titanium keep-alive: none.** Key code 0 (the do-nothing key on the Nspire and the
  84) makes a TI-89 Titanium (OS 3.10) stop answering the link about a second later, for 6 to
  8 minutes, then it answers again by itself with its screen as before (tested twice). The
  window's own screenshots kept it on for 7 minutes with no key, so its window sends none.
- **TI-84 Plus CE in the mirror app:** its own window with the live screen (about 1 frame a
  second: the calculator sends 150 KB a picture over full-speed USB), the PC keyboard as its
  keys (F1-F5 are Y= WINDOW ZOOM TRACE GRAPH, F6 MODE, F7 MATH, F8 APPS, F9 PRGM, F10 VARS,
  F11 STAT, F12 QUIT, Esc CLEAR), screenshots and recordings. It needs the WinUSB driver once
  (README, with Zadig). Tested on a TI-84 Plus CE: screenshot, typing `1+2` Enter.
- **`ti84-cli`:** our own small link for TI's DUSB protocol on libusb (info, shot, key, serve).
- **TI-89 Titanium in the mirror app:** its own window with the
  160 x 100 screen shown x4, the PC keyboard as its keys (F1-F8 its F1-F8, Home HOME, Esc ESC,
  F9 APPS, F10 MODE, F11 CATALOG, F12 CLEAR), screenshots and recordings. `ti84-cli` speaks to
  it too (`--model 89t`; its copy `ti89-cli.exe` picks the 89 by itself), and `ti84-cli
  devices` lists the TI calculators on USB. Likely needs WinUSB once with Zadig (USB ID
  `0451 E004`). Tested on a TI-89 Titanium, OS 3.10: info, screenshot (0.06 s, so the window
  runs fast), typing `1+2` Enter. Needs WinUSB once with Zadig, like the 84 Plus CE.
- **Record:** a button in each window. Saves a GIF (built in), and an MP4 too when ffmpeg is
  installed. Up to 3 minutes; a still screen costs nothing.
- **One window per calculator,** opened when it is plugged in, several at once. Tested with a
  TI-Nspire CX II and a TI-84 Plus CE open together.
- **Copy and paste:** Ctrl+V types the PC clipboard's text into the calculator (new lines are
  Enter, up to 4000 characters); Ctrl+C puts the calculator's screen on the PC clipboard as a
  picture. On the Nspire, Ctrl+Shift+C / Ctrl+Shift+V are the handheld's own copy and paste.
- **Files on the calculator:** a **Files...** button in each window. The live screen keeps
  running while it works; long transfers show their progress in the status line.
  - TI-Nspire: browse the folders (with sizes), download files to the PC (to `from-calc`, or a
    folder you pick), upload a `.py` (checked and converted) or `.tns`, new folder, rename,
    delete (with a question first). Tested on a TI-Nspire CX II CAS, OS 6.40: all of it, and
    a 300 KB file there and back byte for byte (0.9 s down).
  - TI-89 Titanium: its variables by folder and its apps; download as TI files (`.89e`,
    `.89m`, ...); texts, strings and programs not yet run shown as text; upload TI files or
    TI-Basic text; delete. Tested on a TI-89 Titanium, OS 3.10: the list, six downloads, an
    upload over a program of the same name (after the question), its text, a delete.
  - TI-84 Plus CE: its variables, programs and apps (size, RAM or Archive); download as TI
    files (`.8xp`, `.8xv`, ...) with TI's header and checksum; TI-Basic programs shown as
    text; upload TI files or TI-Basic text; delete. Tested on a TI-84 Plus CE, OS 5.4.0:
    an upload of a `.8xp` over a program of the same name (after the question), its text, a
    delete.
- **About this calculator:** model, OS, free memory, and whether TI has a newer OS (read from
  TI's download page at most once a day, never blocking the window; "couldn't check" with
  the link when the page can't be read). It never downloads an OS.
- **`nspire-cli`:** `get`, `rm` and `mv` (download with progress, delete, rename or move).
  **`ti84-cli`:** `ls`, `get`, `send FILE`, `put`, `rm` (the variables of the 84 family and
  the 89; `put` on the 84 only).
- **App icon** on every window and in the taskbar.
- **Send program to the TI-84 Plus CE and the TI-89 Titanium:** the **Send program...** button
  in their windows (and **Upload** in **Files...**) takes TI-Basic typed on the PC (`.txt`,
  `.tib`, `.bas`) or a ready TI file (`.8xp`, `.8xv`, `.8xl`, ... / `.89p`, `.89e`, ...). It
  reads the calculator's list first and asks before replacing anything; a text file whose name
  can't be the program's asks for a name. Progress shows in the status line.
  - TI-84 Plus CE: the text is turned into the calculator's tokens on the PC (`.8xp` with TI's
    header and checksum), with the PC spellings (`->`, `<=`, `>=`, `!=`, `sqrt(`, `pi`,
    `theta`, `^2`, `^-1`, `L1`, `Y1`, `E` in a number for the EE key, `-` as the negative sign
    where a number starts) or the calculator's own symbols. Checked by a round trip through
    the viewer's detokenizer (self-test).
  - TI-89 Titanium: the text goes over the way the 89's own Program Editor keeps a program
    (read back from a real one), and the 89 tokenizes it when it first runs; `Func` /
    `EndFunc` makes a function.
  - Tested on a TI-84 Plus CE, OS 5.4.0 and a TI-89 Titanium, OS 3.10: test programs sent
    from text (from the window, from Files... and from `tools/send_ti.py`) and as TI files,
    run on the calculator from the mirror's keys with the right output (loops, If/Then/Else,
    negatives, EE, `->`, `<=`, `!=`, `sqrt(`, `pi`, a 1.5 KB program in several packets, an
    89 program of odd size, which takes a different packet size), replaced, deleted; a file
    for the other calculator is refused with its name.
- **`tools/send_ti.py`:** the same from the command line: `python -I tools/send_ti.py --calc
  84|89 FILE [--name NAME] [--replace] [--out FILE]`. It stops when a variable of that name is
  on the calculator (unless `--replace`) and reads the list again afterwards to check the
  program arrived.

- **MP4 without installing ffmpeg:** the first time you press Record without ffmpeg, the app offers to download it (about 39 MB, once, from PyPI's imageio-ffmpeg, checked against its SHA-256) into `%LOCALAPPDATA%\CalcSuite\ffmpeg`. Without it you still get the GIF. MP4s use H.264, or ffmpeg's own MPEG-4 when a build has no H.264.

- **Make a PC copy of my calculator** (`tools/pc_copy.py`, [docs/PC_COPY.md](docs/PC_COPY.md);
  the window's button comes later, its API is in [docs/dev/PC_COPY_API.md](docs/dev/PC_COPY_API.md)).
  It backs the calculator up, dumps its own ROM to `Documents\CalcSuite\backups\roms\` and
  removes everything it put on the calculator:
  - **TI-84 Plus CE** (OS 5.4 or older): a Garbage Collect first, then CEmu's ROM dumper,
    sent as `ZZDUMP` and started by typing its keys; its AppVars `ROMData*` are read back and
    put together as CEmu does (boot code, OS and certificate; the archive comes out empty).
    Tested on OS 5.4.0: 123 s in all (backup 4 s, garbage collect 10 s, dump 91 s of
    waiting, reading 0.9 MB 7 s), a 4 MB `ti84ce-2026-11-27.rom` that CEmu v2.0 boots to the
    home screen, with the backup's programs and variables sent in. No crash, nothing in RAM
    lost. Without the Garbage Collect, the dump stopped half way twice (the OS wanted to ask
    "Garbage Collect?").
  - **TI-89 Titanium:** TILP's USB ROM dumper sent as `main\romdump`, run from the link, and
    the 4 MB read with TILP's dump protocol (new `ti89-cli` commands `home`, `exec`,
    `romdump`). Tested on AMS 3.10: 71 s in all (the dump 65 s), `ti89t-2026-11-27.rom`. No
    crash, nothing in RAM lost.
  - **Open in CEmu:** `python -I tools/pc_copy.py get-emulator 84` downloads CEmu v2.0 (GPL-3.0)
    from its GitHub release into `%LOCALAPPDATA%\CalcSuite\emulators\`, checked against a
    pinned SHA-256 (the release has no GitHub digest); `open 84` starts it with the ROM and
    the latest backup's files. For the 89, the only Windows build of TiEmu is its 2010
    installer: CalcSuite downloads and checks it, but you run it yourself.
  - The two dumpers are GPL programs that run on the calculator, kept apart in
    `tools/rom_dumpers/` with their sources and licences. CalcSuite never ships, uploads or
    downloads a ROM.

### Faster
- **Typing:** while you type, keys go out the moment they're pressed and the next screenshot
  waits until you pause (0.15 s on the Nspire, 0.6 s on the 84/89), instead of keys waiting
  behind a picture (up to 1.4 s on the 84 Plus CE).
- **TI-84 Plus CE keys** about twice as fast (4 keys: 0.69 s before, 0.37 s now): no more
  sleeping on the calculator's "wait" reply, the next read already waits for the answer.
- **Nspire frames:** about 19 a second (was about 10). The window looking for calculators no
  longer opens them every 3 s (it reads the USB descriptors only), which took the handheld
  from the mirror for a moment each time.

### Fixed
- **TI-89 Titanium arrow keys:** they had the TI-92 Plus's codes, so up moved left and down
  moved right; now the 89's own (up 337, left 338, down 340, right 344). Tested on a TI-89
  Titanium, OS 3.10.
- The TI-84 Plus CE's OS version read as `0.5.4.0`; now `5.4.0`.
- The Nspire's name was cut at the first space ("Connected: TI-Nspire" for a TI-Nspire CX II
  CAS).

## [0.2.0] - 2026-11-26

### Added
- **Nspire Mirror, an app:** the handheld's screen live in a window (about 9 frames a second),
  with no terminal. `Nspire Mirror.exe` is one file that needs no Python; `Nspire Mirror.bat`
  runs the same window from the source.
  - **Keyboard:** letters, digits, symbols, Enter, Esc, Tab, Backspace and the arrows go to the
    handheld. Ctrl+letter is the handheld's ctrl+letter. F1 Home, F2 Menu, F3 Doc, F4 Catalog,
    F5 Var.
  - **Mouse:** the wheel is up/down (Shift+wheel left/right), a click is the centre click key,
    a double click Enter, a right click the context menu, a middle click Menu. A click on the
    X closes the document, on the page arrow or tabs changes page.
  - **Send program:** pick a `.py` (checked and converted first) or a `.tns`.
  - **Screenshot:** a PNG in `captures/` (the app: `Documents\Nspire Mirror\captures`).
  - It connects by itself when the handheld is plugged in, and again after the cable was out.
  - One window at a time: a second copy says so and closes (two would take the handheld
    from each other and both go black).
- **`tools/screenshot.py`:** the handheld's screen as a PNG (`--scale 3` to enlarge).
- **`nspire-cli`:** `shot FILE.ppm`, `key HEX`, `keys HEX HEX ...`, and `serve` (one connection,
  commands on stdin), which the mirror and the sender use.
- **`tools/nspire_link.py`:** a Python wrapper for one kept-open connection, and a PNG writer
  with no dependencies.
- **`QUICKSTART.md`:** one page from writing a program to running it, without AI.
- **`programs/numint.py`:** trapezoid, Simpson and a reference value for an integral.

### Fixed
- **Sending worked once per plug-in, then timed out.** The CX II does its address handshake
  once after it is plugged in and is silent after that, so every later connection waited for a
  handshake that never came (up to 10 minutes inside libnspire). Reported earlier as "USB send
  times out on OS 6.40"; the OS wasn't the cause. Our copy of libnspire's `cx2.cpp`
  (`tools/nspire_cli/cx2_resume.cpp`) now asks the handheld to start the handshake again, and a
  connection takes about 1.2 s every time, with no replugging.
- **`flash.py` / `send_to_calc.py` do every step on one connection** (info, folder, upload,
  read-back), which is also faster.

### Known limits
- **The mouse can't place the handheld's pointer.** The key service has no known message for
  it, so clicks are keys and a few screen spots are shortcuts.
- **Typed characters show after about 0.15-0.3 s:** the window sees them on the next
  screenshot.
- **Key codes** come from early Nspire models (TILP's list). The common ones work on a CX II
  on OS 6.40; some special keys may not.
- **Python on the handheld can't use the CAS.** Exact answers need TI-Basic, which the kit
  doesn't send yet.
- Windows only for the USB tools.

## [0.1.0] - 2026-11-26

First public release.

- `tools/check_nspire.py`: checks a program against what TI's Python can run.
- `tools/run_on_pc.py`: runs it on the PC with stand-ins for the `ti_*` modules.
- `tools/py2tns.py`: converts `.py` to a `.tns` document (Luna).
- `tools/flash.py` / `tools/send_to_calc.py`: check, convert and send over USB (libnspire).
- Example programs: `quadratic`, `draw_demo`, `probe`, `critpts`.
