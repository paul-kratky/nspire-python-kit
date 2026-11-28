# CLAUDE.md

Guidance for Claude Code in this repository.

## The project

**CalcSuite** (`paul-kratky/CalcSuite`, public, MIT): a free Windows app that mirrors TI
calculators live, types into them from the PC, writes and sends programs, manages their files,
backs them up and checks for OS updates. For the **TI-Nspire CX II (CAS)**, the **TI-84 Plus CE**
and the **TI-89 Titanium**, several at once. Plus a command-line kit for TI-Nspire Python
(`docs/PYTHON_KIT.md`). README.md is the short tour; docs/USER_GUIDE.md is the user guide (its
PDF ships in the release); CHANGELOG.md says what changed.

## Layout

| Where | What |
| --- | --- |
| `tools/mirror.py` | The app: `App` (the window, tab strip, USB scan, the message pump), `Mirror` (one calculator's link thread), `Tab`, `AllScreens` |
| `tools/ui_panels.py` | The side panel (an icon strip on the right edge): Files, Keys, Symbols, Functions, Data, Get programs, Macros, Guide, Calculator info |
| `tools/window_chrome.py` | The window's pure parts: the live screen's scale, tab titles, the tab order (dragging, saved in `settings/tab_order.json`), which tabs fit |
| `tools/tool_tabs.py` | Tools as closable tabs of the main window (`App.open_tool_tab`; `tool_tabs.window()` for tools written as windows) |
| `tools/editor.py`, `tools/code_check.py` | The Program editor (a tab of the main window; `python tools/editor.py` opens it alone) and its strict checkers |
| `tools/calc_manager.py` | Files, backup/restore, Calculator info (clock, OS check, Exit Press-to-Test, Delete all programs, Reset) |
| `tools/calc_models.py` | Each calculator's keys, symbols, paste rules |
| `tools/calc_files.py`, `calc_backup.py`, `tns_writer.py`, `py2tns.py` | TI file formats, backups, the .tns writer (MPL-1.1, a port of Luna: must stay byte-identical, the self-test compares) |
| `tools/paths.py` | Where things are saved: `CalcSuite files` beside the exe (the zip), else Documents/LOCALAPPDATA from the source |
| `tools/calc_doctor.py`, `tools/driver_helper/` | The connection doctor and the WinUSB driver helper (LGPL, its own process) |
| `tools/nspire_cli/`, `tools/ti84_cli/` | The USB link helpers (GPL, their own processes; built by `tools/build_tools.py`) |
| `tools/fast84/` | Fast mode for the TI-84 Plus CE (CSFAST.8xp, our eZ80 hook) |
| `tools/pc_copy.py`, `tools/rom_dumpers/` | Make a PC copy (ROM dump + CEmu/TiEmu) |
| `tools/reference/`, `docs/*.md` | The Functions reference (JSON) and the guides; `docs/pdf/` their PDFs |
| `tools/release_files.py`, `app.spec` | The release zip and PyInstaller's folder build |

## Build, test, release

```sh
python -I tools/build_tools.py [--force] [--luna]   # the link helpers into tools/bin/ (MSYS2 UCRT64 gcc; --luna: the .tns test reference)
python -I tools/selftest/run_selftest.py             # every test; must print ALL PASSED
python -I tools/docs_build/check_examples.py         # every example program in the guides
python tools/docs_build/make_pdfs.py [--version vX.Y.Z]  # rebuild docs/pdf/ after changing QUICKSTART or docs/
python tools/mirror.py                                # run the app from the source
```

- **Every change goes through a pull request.** `main` is protected: signed commits, the
  `selftest` check must pass on an up-to-date branch, squash merges only, no force pushes.
  Work on a branch, `gh pr create`, wait for the checks, `gh pr merge --squash`.
- Commits and tags are signed with the owner's SSH key (held by Windows' ssh-agent). Never
  bypass signing (`--no-gpg-sign`, `-c commit.gpgsign=false`).
- **Release:** bump `APP_VERSION` in `tools/build_tools.py` and `tools/driver_helper/calcsuite_driver.rc`,
  add a `## [X.Y.Z] - date` section to CHANGELOG.md (the release notes come from it), rebuild the
  PDFs, merge, then a signed tag `git tag -s vX.Y.Z` on the merged commit and push it.
  `.github/workflows/release.yml` builds the zip on GitHub (its own PyInstaller bootloader, no
  UPX), attests it, scans it on VirusTotal (secret `VT_API_KEY`), publishes it to
  `ghcr.io/paul-kratky/calcsuite` and drafts the release; check the draft, then publish it.
- Other workflows: `tests.yml` (selftest), `codeql.yml`, `scorecard.yml`, Dependabot for the
  pinned actions. Pin every action by commit SHA.

## Rules

- **The user's calculators are real and theirs.** Create and delete only test items named
  `zz*` (`ZZ*` on the 84/89). Never send backspace or delete keys unless the user confirms. Never
  press a reset's final confirmation. Don't install or change USB drivers without asking.
- **Don't fight the user's CalcSuite for the calculators.** A second app instance takes the
  links away from theirs (their panels then wait forever). With their CalcSuite open, test with
  the link faked (`nspire_link.Session` raising `LinkError(4, [...])`, the scan returning fixed
  ids), or ask first. Never `taskkill /IM CalcSuite.exe` (it closes theirs too): stop only the
  process ids you started.
- **ROMs** are the user's own: never upload or ship one.
- **Licences:** the app is MIT. GPL/LGPL code runs only as separate programs (the link helpers,
  the driver helper, ffmpeg); never import it into the MIT code. Vendored code keeps its licence
  (`LICENSING.md`). `LICENSE` stays the plain MIT text.
- **Windows UI:** dark everywhere, dark title bars on every window and dialog
  (`ui_theme.dark_title_bar_when_shown`). Long panels get scrollbars; empty detail boxes say
  what to do.
- **Errors never pass silently** in the window: `mirror.log_error()` writes them to
  `CalcSuite files/logs/errors.log`.
- **Everything stays in the unzipped folder.** The release build keeps all it makes or downloads
  (backups, ROMs, captures, programs, emulators and their settings, caches) in `CalcSuite files`
  beside the exe, through `tools/paths.py` (`files_dir()`, `cache_dir()`): never Documents,
  AppData, Program Files or the registry. Helper programs it starts (CEmu, TiEmu, ffmpeg) are kept
  there too. Only a run from the source uses Documents/LOCALAPPDATA.
- **README:** short and concise (the owner's rule, 2026-11-28): a sentence or two per feature
  with its screenshot, nothing folded (no `<details>`). Screenshots full size (never
  `width=` shrunk), from the real app (docs/img/). The detail goes in docs/USER_GUIDE.md and
  the other guides; point links at `##` headings.
- No telemetry; go online only when the user asks (SECURITY.md lists every place).

## Writing TI-Nspire Python (the kit)

Programs for the handheld run in TI's own Python (MicroPython, OS 5.2+), not CPython.

1. Write `programs/<name>.py`: a short lowercase name, letters/digits/underscores.
2. `python -I tools/check_nspire.py programs/<name>.py`: fix every ERROR (and the warnings,
   unless the user checked that feature on the handheld with `programs/probe.py`).
3. Test the logic on the PC: `python -I tools/run_on_pc.py programs/<name>.py`
   (`--var/--list/--func/--keys`, docs/PYTHON_KIT.md).
4. "Send it" (calculator plugged in): `python -I tools/flash.py programs/<name>.py` (checks,
   builds `build/<name>.tns`, uploads to My Documents, reads it back). Otherwise `--dry-run`.
   "No TI-Nspire found": ask the user to plug in and switch on. Never run anything needing admin.
5. On the handheld: home > My Documents > `<name>.tns`, then ctrl+R. An open document keeps
   the old version until it's closed and reopened.

The language:
- **Modules:** `math`, `cmath`, `random`, `time`, `ti_system`, `ti_draw`, `ti_plotlib`,
  `ti_image` (`ti_hub`/`ti_rover` only with that hardware; the user's PyLib modules with
  `--allow`). No numpy, sympy, matplotlib, os, re, json, itertools, file I/O, threads.
- **Syntax to avoid:** f-strings, `:=`, `match`, type hints, `async`, positional-only `/`,
  `from __future__`, `except*`, `1_000`. Classes, lambda, try/except, with, generators and
  comprehensions are fine.
- MicroPython lacks `ljust`, `rjust`, `zfill`, `title`, `partition`: pad by hand.
- **Plain ASCII** source, 4-space indents. Keep programs under ~20 KB; the heap is ~2 MB and
  the stack small (recursion well under 50).
- `input()` returns a string: convert inside `try/except ValueError`. Keep printed lines
  ~30 characters.
- **ti_draw:** 318 x 212 (`get_screen_dim()`), (0,0) top left; `set_window` for math
  coordinates; `use_buffer()`/`paint_buffer()` for many shapes; end with `get_key(1)`.
- **ti_plotlib:** `plt.window(...)`, `plt.axes("on")`, `plt.plot/scatter/line/lin_reg`,
  `plt.show_plot()`. Don't mix it with ti_draw.
- **ti_system:** `recall_value/store_value`, `recall_list/store_list`, `eval_function("f", x)`,
  `get_key()`/`get_key(1)`, `get_time_ms()`, `get_platform()`. Python has no CAS: hand results
  to TI-Basic for symbolic work.

## Honesty

For learning and homework the teacher allows. Python documents are unavailable in
Press-to-Test. Never help hide programs from exam mode or get around exam rules.
