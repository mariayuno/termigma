# Changelog

## Unreleased

**Added — CLI mode, vertical trace, KD model, Enigma D notch fix**

Full CLI mode (`python3 -m termigma`)
  Every setting is now a flag.  Text comes from `--text`, `--file` or
  stdin.  When no input is given on a real terminal the TUI opens.
  Key flags: `-m/--model`, `-r/--rotors`, `-g/--ring`, `-p/--pos`,
  `-u/--refl`, `--ukw`, `--ukwpos`, `--ukwring`, `-w/--wheel`,
  `-s/--plug`, `--etw`, `--notch`, `--lock`, `--group N`, `--letters`,
  `--keep-other`, `--json`, `-o/--out [PATH]`, `--list-models`,
  `--show-config`, `--tui`, `--live`.

Vertical signal trace
  `-V/--vertical` (CLI) and `t` / `:live` (TUI) display a vertical
  trace: one column per letter typed, one row per circuit stage, from
  Input at the top to Output at the bottom.  Each cell shows the letter
  at that stage; ANSI colour distinguishes input, plugboard, ETW, rotors
  forward/back, reflector and output.  `-P/--positions` adds a row of
  rotor positions under each block.

Auto-named file output (`-o`)
  `-o` with no path writes a file named after the full machine settings
  (model, rotors, ring, pos, UKW, plugboard) with a timestamp, never
  overwriting an existing file.  The file starts with a `# config:` line
  carrying the one-liner CLI command so the origin is always traceable.

`--json` output
  Prints `{plain, cipher, output, config, cli, dropped}` as JSON.

Enigma KD
  New model (`kd`) — K wiring with a rewirable UKW-D reflector.  Ships a
  minimal placeholder reflector that enforces the one documented fixed
  contact (B↔O); operators supply their own wiring via `--ukw` / `:ukw`.

**Fixed — Enigma D trivial Ringstellung notch**
  The D-rotor turnover notch is fixed to the rotor *core*, not the ring.
  Its window letter therefore *shifts with the ring setting* (ring A → Z,
  ring B → A, …).  The previous code inherited the wrong K-model notch
  positions (Y / E / N).  Fixed to Z for all three D rotors.
  Full account in DATA.md §5.

**Added — DATA.md and rewritten README.md**
  DATA.md is the complete accuracy-evidence file: wiring-source audit,
  Crypto Museum 64/64 comparison, 2 800-message mechanics fuzz, real-
  message cross-checks, Enigma D notch history, known gaps.
  README.md rewritten to cover the full feature set.

## Unreleased

**Added**

- **`:model r0`** — R° (authentic Railway wiring, physically measured by
  Patrick Hayes 2023, confirmed by Detlev Gross).  Distinct from the older
  cryptanalytically-theorised KR tables.  Includes a settable UKW start
  position (`:ukwpos`).

- **`:lock L|M|R|UKW`** — decouple a wheel from the drive train so it never
  steps, regardless of notch state.  Toggling the same key unlocks it.
  `:lock off` clears all locks at once.  Locked wheels are shown with a
  trailing `*` in the rotor panel (e.g. `LEFT*`).  UKW locking is only
  available on rotating-reflector (G-series) models.

- **Duplicate rotor types** — the same rotor type may now appear in all three
  positions (e.g. `VI VI VI`), matching the behaviour of real machines and
  reference simulators.

- **UKW-G312 in Custom mode** — the G-series reflector is now selectable
  from `:refl` on the Custom machine.

- **Tirpitz ETW in Custom mode** — `:etw tirpitz` is now available on the
  Custom machine, not only via `:model t`.

- **Five-letter groups** — the message panel now shows a live Groups row
  beneath the cipher line, scrolled to keep the most recent groups visible.

- **Notice wrapping** — long notices (TAB-completion lists, multi-option
  errors) wrap across up to three lines rather than being silently clipped.

- **`:model` TAB completion** now shows the model label alongside the alias
  key so operators can find presets without memorising all 15 keys.

## Unreleased

**Added — 14 historical Enigma models (previously 3)**

`:model <key>` switches the machine between 15 configurations.  Models
other than `custom` are locked: `:rotors`, `:refl` and `:etw` refuse
changes and point to `:model custom` to unlock.  `:pos`, `:ring`,
`:plug`, `:wheel`, `:ukwpos` and `:ukwring` work on any model.

| key | Machine |
|---|---|
| `i` | Enigma I (Army/GAF) |
| `m3` | M3 (Army/Navy) |
| `m4` | M4 "Shark" (U-boats), 4th wheel |
| `n` | Norenigma |
| `s` | Sondermaschine |
| `d` | Commercial D (1926) — trivial Ringstellung |
| `k` | Commercial K (1927) |
| `swissk` | Swiss-K (Swiss Air Force) |
| `r` | Railway (published wiring) |
| `t` | Tirpitz / T (Japan), own ETW, adjustable UKW |
| `a28` | A28/G31 Zählwerk — cog drive, adjustable UKW |
| `g111` `g260` `g312` | G-series (Abwehr) — cog drive, rotating UKW |
| `custom` | Fully unlocked; any rotor, reflector, ETW |

New commands:
- `:model <key>` — switch model (TAB completes)
- `:ukwpos <A-Z>` — set UKW start position (thumbwheel machines only)
- `:ukwring <1-26>` — set UKW ring setting (thumbwheel machines only)

**Changed**

- Cog-drive stepping: Zählwerk and G-series machines use an odometer-
  style drive with no double-step anomaly.  On G-series, the reflector
  rotates when all three rotors are simultaneously at their notches.
- Adjustable UKW: Tirpitz, A28 and G-series machines have a reflector
  with a settable start position and ring; the draw panel shows these.
- `get_positions()` now returns a 4-tuple `(L, M, R, UKW)`.  The UKW
  element is always 0 on non-rotating machines, so all existing code
  that relied on a 3-tuple round-trips correctly.
- Rotor display now uses `.label` (e.g. `I` for `I-G312`).  The model
  name appears in the rotor panel title and the `:show` summary.

## Unreleased

**Changed — TUI rebuilt as a vim-style modal editor**

The entire interactive interface has been rewritten.  F-keys and the Q quit
binding are gone; only ordinary letter keys, ESC, BACKSPACE and SPACE are
needed.

Four modes (shown as a badge at the bottom-left of the screen):

- **INSERT** (start-up mode) — type A-Z / SPACE to encipher at the cursor;
  BACKSPACE deletes the character to the left; ESC or `` ` `` exits to NORMAL.
- **NORMAL** — vim motion keys (h l 0 $ w b); i/a/I/A insert; x/X delete;
  u undo; dd clear message; yy/p yank/paste; v VISUAL; : COMMAND; ? help.
- **VISUAL** — extend a selection with motion keys; d/y/c act on it; o swaps
  the anchor end; ESC cancels.
- **COMMAND** — colon command line with TAB completion:
  `:rotors` `:ring` `:pos` `:refl` `:wheel` `:etw` `:ukw`
  `:plug add|remove|clear|on|off`
  `:show` `:reset` `:new` `:help` `:q`

The key architectural change is that the machine's positions are now a fixed
*start key*: they never advance while typing.  Ciphertext is derived by
replaying the text buffer from those positions on every frame, so editing
anywhere — inserting, deleting, moving the cursor, changing a setting — always
re-enciphers the whole message correctly from the start.

**Added**
- `Enigma.replay(text)` — enciphers a string from the current positions
  without permanently advancing the rotors; returns cipher text, per-character
  position snapshots and the signal path for the last letter.
- `Message` class — text buffer with cursor, vim motion keys and undo stack.
- `Session` class — owns the machine and the message; drives the modal state
  machine; handles all : commands.
- `build_exit_report()` — grouped five-letter output, supports multi-message
  sessions (`:new` starts a new message while keeping the old one for the
  report).

**Removed**
- F-key sub-screens (F1 help, F2 settings, F3 plugboard, F5 custom reflector).
  All of their functionality is now available via : commands.

## Unreleased

**Fixed**
- Backspace now correctly restores the exact rotor positions that existed
  before the deleted keypress, including any middle-rotor carry or
  double-step that it triggered.  Previously backspace was not handled at
  all in the main input loop, so deleting a character left the rotors one
  step ahead of where they should be, silently producing wrong ciphertext
  for every subsequent letter.

**Changed**
- Q is no longer a quit key.  ESC is the only way to exit.  Q was the only
  uppercase letter that could not appear in a message, which ruled out any
  word containing it.  ESC alone is unambiguous and nothing in the TUI
  needs Q for anything else.
- On exit the program prints a session summary to the terminal: the machine
  configuration in effect, the full plaintext and the corresponding
  ciphertext.  Nothing is printed if no letters were typed.

**Added**
- `Enigma.get_positions()` and `Enigma.set_positions()` — thin helpers that
  snapshot and restore the three main rotor positions as a plain tuple.
  The backspace implementation depends on them and they are independently
  tested.

## 1.0.0
Packaged for PyPI as `termigma`.

- Split the single-file prototype into `engine.py` (pure logic, no curses)
  and `tui.py` (rendering + input loop)
- Added a real `pytest` suite in `tests/test_engine.py`
- `pip install termigma` now provides a `termigma` console command
- Added CI (`.github/workflows/ci.yml`) and an auto-publish-on-release
  workflow (`.github/workflows/publish.yml`) using PyPI Trusted Publishing

## 0.2.0
Expanded feature set.

**Added**
- Rotors VI, VII, VIII (Kriegsmarine, each with *two* turnover notches)
- M4 "Shark" 4-rotor mode: non-stepping Beta/Gamma wheel + thin reflectors
  (B-thin / C-thin)
- Switchable entry wheel (ETW): military (straight-through) vs. commercial
  (wired in QWERTZU keyboard order)
- Plugboard on/off switch (commercial D/K-style machines had none); max
  plugboard pairs raised from 10 to the full theoretical 13
- Rewirable "Custom" reflector (F5), like UKW-D: any 13 pairs covering all
  26 letters
- Optional movable turnover notches per rotor (Zaehlwerk-style ring),
  off by default
- Model preset field in Settings (Enigma I / M3 / M4 / Commercial-style)
  that pre-fills sensible defaults but leaves everything editable
- "Eff" (effective rotation) readout per wheel, plus a Count/Last-input
  status line

**Changed**
- Signal-path panel now also shows both ETW passes and the optional
  4th-wheel passes (up to 15 stages for M4, was 11 fixed stages)
- Rotor panel widened to show up to 4 wheels side by side
- Minimum terminal size raised to 108x34 (was 90x30)

**Deliberately not included**
- Exact wiring for Enigma K, Enigma D, Swiss-K, Railway, Tirpitz,
  Norenigma, Sonder-Enigma, and the Abwehr G-machines — not confidently
  sourced, and a guess presented as fact would be worse than the gap.

## 0.1.0
Initial build: a 3-rotor Enigma I/M3 simulator.

- Rotors I-V, reflectors B/C, plugboard (max 10 pairs)
- Correct middle-rotor double-step stepping
- Full curses TUI: rotor windows, QWERTZ keyboard, lampboard, plugboard
  panel, an 11-stage signal-path monitor, scrolling plaintext/ciphertext log
- Settings (F2), plugboard editor (F3), reset (F4), help (F1)
- Verified against the published reference test vector (rotors I-II-III,
  rings 01-01-01, start AAA, reflector B, no plugboard -> "AAAAA" -> "BDZGO")
