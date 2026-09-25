# Changelog

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
