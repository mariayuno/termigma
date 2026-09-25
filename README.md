# termigma

A terminal simulator of the Wehrmacht/Kriegsmarine Enigma machine — rotors,
plugboard, lampboard, and a live signal-path monitor, all in your terminal.

```
pip install termigma
termigma
```

No dependencies on Linux/macOS (just the standard library's `curses`). On
Windows, `pip install termigma` pulls in `windows-curses` automatically.

## What it does

You type a letter, it lights up on the lampboard, and the **signal path**
panel shows exactly how it got there: plugboard → entry wheel → through each
rotor → reflector → back through the rotors → entry wheel → plugboard → lamp.
The rotors step on every keypress, including the historically correct
middle-rotor "double step," and there's no undo — same as the real machine.

It covers three points in the machine's history:

- **Enigma I** (Army/Air Force) — 3 rotors chosen from I–V
- **M3** (Army/Navy) — 3 rotors chosen from I–VIII
- **M4 "Shark"** (U-boats) — adds a fourth, non-stepping Beta/Gamma wheel and
  a thin reflector

Plus a **commercial-style** mode that demonstrates the real quirk of
commercial Enigmas: no plugboard, and an entry wheel wired in keyboard
(QWERTZU) order instead of straight A–Z.

## Controls

| Key | Does |
|---|---|
| `A`–`Z` | Encipher a letter |
| `Space` | Visual separator (doesn't step the rotors) |
| `F1` | Help |
| `F2` | Settings — model preset, ETW mode, plugboard on/off, reflector, movable notches, 4th wheel, all three rotors |
| `F3` | Plugboard editor |
| `F5` | Custom rewirable reflector editor (needs Reflector = Custom) |
| `F4` | Reset to defaults |
| `Esc` / `Q` | Quit |

Terminal needs to be at least 108×34 or it'll ask you to resize.

## Why it looks the way it does

Real Enigmas didn't have an undo button, a Ctrl-Z, or a way to peek inside
while it ran. This tries to keep that feel — the rotors always turn, the
plugboard is genuinely optional depending on which model you pick — while
also showing you the one thing the real machine couldn't: what's happening
electrically at every stage, for every keystroke.

## Project layout

```
src/termigma/engine.py   the machine itself — no curses, fully unit-testable
src/termigma/tui.py      curses rendering and the input loop
tests/test_engine.py     pytest suite (reciprocity checks, stepping, etc.)
data/wiring_tables.json  the historical wiring data, with sourcing notes
```

## Running from source

```
git clone https://github.com/rexackermann/termigma
cd termigma
pip install -e ".[dev]"
pytest
termigma
```

## Accuracy

The rotor and reflector wiring (rotors I–VIII, the M4 Beta/Gamma wheels, and
reflectors B/C plus their thin M4 counterparts) is the widely published
historical data, checked here against a known reference test vector and a
set of round-trip (reciprocity) tests — see `tests/test_engine.py`.

What's **not** included: exact wiring for the more exotic commercial and
national variants (Enigma K, Enigma D, Swiss-K, Railway, Tirpitz, Norenigma,
Sonder-Enigma, the Abwehr G-machines). This project doesn't have confidently
sourced wiring for those, and a guess dressed up as fact is worse than an
honest gap. The "commercial-style" preset demonstrates the real no-plugboard
/ QWERTZU-entry-wheel behavior of commercial machines but reuses the Enigma I
rotor set rather than true K/D rotors. See `data/wiring_tables.json` for the
full sourcing note, and cross-check the Crypto Museum's Enigma pages if you
need one of those specific machines to be byte-exact.

## Credits

- Inspired by Daniel Palloks' [Universal Enigma](https://people.physik.hu-berlin.de/~palloks/js/enigma/enigma-u_v262_en.html),
  a browser-based simulator covering a much wider range of historical
  Enigma variants than this project attempts.
- Enigma explainer video: https://www.youtube.com/watch?v=JsBZOcqZerk — for inspiration.
- Built with help from [Claude](https://claude.ai) (Anthropic).

## License

MIT — see [LICENSE](LICENSE).
