```
 ███████╗███╗   ██╗██╗ ██████╗ ███╗   ███╗ █████╗
 ██╔════╝████╗  ██║██║██╔════╝ ████╗ ████║██╔══██╗
 █████╗  ██╔██╗ ██║██║██║  ███╗██╔████╔██║███████║
 ██╔══╝  ██║╚██╗██║██║██║   ██║██║╚██╔╝██║██╔══██║
 ███████╗██║ ╚████║██║╚██████╔╝██║ ╚═╝ ██║██║  ██║
 ╚══════╝╚═╝  ╚═══╝╚═╝ ╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═╝
        a terminal Enigma  •  TUI + CLI  •  v8
```

<div align="center">

**16 historical Enigma models** • **vim-style TUI, no function keys** • **scriptable CLI**
**colourful vertical signal trace** • **wiring verified against the Crypto Museum**

`python3 python3 -m termigma` &nbsp;·&nbsp; `python3 python3 -m termigma -m m3 -t "HELLO WORLD"`

</div>

---

## ✨ What this is

A single-file Python program that is **both**:

| | |
|---|---|
| 🖥️ **an interactive terminal app** | vim-style modal editing (INSERT / NORMAL / VISUAL / COMMAND) — press letters, they light up on the lamp board, no function keys or arrow keys required |
| ⚙️ **a scriptable command-line tool** | every setting is a flag; pipe text in, get ciphertext out, exactly as usable from a shell script or a pipeline as from the keyboard |

Both sides share **one engine**, so a key you set up interactively can be printed as a
one-line CLI command on exit — and running that command reproduces the exact same output.

---

## 🚀 Quick start

```bash
# interactive TUI — just run it
python3 python3 -m termigma

# one-shot CLI
python3 python3 -m termigma -m m3 -r III II I -p A B C -s AB CD -t "HELLO WORLD"
# -> YHKUP BQIFM

# decrypt: run the exact same command on the ciphertext
python3 python3 -m termigma -m m3 -r III II I -p A B C -s AB CD -t "YHKUP BQIFM"
# -> HELLO WORLD

# pipe a file through it
cat message.txt | python3 python3 -m termigma -m m4 --refl B-thin --wheel Beta \
    -r II IV I -p A A A -o
```

**Requires:** Python 3.8+. The TUI needs a real terminal (≥ 108×34) and `curses`
(`pip install windows-curses` on Windows). The CLI needs neither.

---

## ⌨️ The TUI — vim-style, zero function keys

```
┌──────────────────────────────────────────────────────────────────────┐
│  INSERT   (you start here)                                           │
│    A–Z / SPACE  type & encipher        BACKSPACE  delete             │
│    ESC  or  `                          → NORMAL                      │
│                                                                        │
│  NORMAL                                                               │
│    h l 0 $ w b   move        i a I A   insert       x X   delete     │
│    u   undo      dd   clear  yy p      yank / paste v     visual     │
│    t   live vertical trace              :   command line   ?  help   │
│                                                                        │
│  VISUAL           h l 0 $ w b extend · o other end · d/y/c act       │
│  COMMAND          type a command below, TAB completes it, ENTER runs │
└──────────────────────────────────────────────────────────────────────┘
```

Editing anywhere in the message — or changing a setting — **re-enciphers the whole thing**
from the start key, exactly like moving the actual rotors back and retyping would.

### Commands (`:`, TAB-completing)

| | |
|---|---|
| `:model i m3 m4 n s d k swissk r r0 t a28 g111 g260 g312 custom` | switch machine (locks its wheels) |
| `:rotors` `:ring` `:pos` | wheels, ring settings, start positions |
| `:refl` `:ukw` `:ukwpos` `:ukwring` `:wheel` | reflector, custom UKW, adjustable UKW, 4th wheel |
| `:plug add AB CD` · `remove AB` · `clear` · `on` / `off` | plugboard |
| `:etw` `:notch` `:lock` | entry wheel, movable notches, decouple a wheel *(unlocked/custom)* |
| `:live` (or `t`) | toggle the vertical trace view |
| `:w [file]` / `:wv [file]` / `:wq` | save output / save trace / save & quit |
| `:show` `:set` `:reset` `:new` `:help` `:q` | summary · full settings screen · defaults · new message · help · quit |

**On exit**, the TUI prints the full configuration, input, output — **and the configuration
as one CLI command** you can paste into a shell to redo it, plus any files saved this
session.

---

## 🧰 The CLI

```
python3 python3 -m termigma [machine flags] [input] [output] [views]
```

| Group | Flags |
|---|---|
| **Machine** | `-m/--model` `-r/--rotors` `-g/--ring` `-p/--pos` `-u/--refl` `--ukw` `--ukwpos` `--ukwring` `-w/--wheel` `-s/--plug` `--etw` `--notch` `--lock` |
| **Input** | `-t/--text "..."` · `-f/--file PATH` (`-` = stdin) · *or just pipe it in* |
| **Output** | stdout by default; `-o [PATH]` also writes a file — no `PATH` ⇒ **auto-named after the settings** |
| **Shaping** | `--group N` (blocks of N) · `--letters` (one run) · `--json` · `--keep-other` (don't drop punctuation) |
| **Views** | `-V/--vertical` (+ `-P/--positions`), `--color auto\|always\|never` |
| **Utility** | `-c/--show-config` · `--list-models` · `@file.txt` (read flags from a file) · `--tui` / `--live` |

No input given on a real terminal → the TUI opens instead. Enigma is reciprocal, so
decrypting is just running the same command on the ciphertext.

### Auto-naming

`-o` with no name (or a directory) writes something like:

```
enigma_m3_III-II-I_ring010101_posABC_ukwB_plugAB-CD_20260924-071313.txt
```

— model, rotors, rings, positions, reflector and plugboard are all in the filename, and it
never overwrites an existing file. The file itself starts with a `# config:` header line
carrying the same one-line command.

---

## 📊 The vertical trace — watch the signal move

One column per letter typed, one row per stage of the circuit, **input first, output
last**:

```
Input                 H E L L O
Plugboard ->          H E L L O
Entry Wheel (ETW)     H E L L O
Rotor R (III) ->      X K J J R
Rotor M (II) ->       ...
Reflector B           ...
<- Rotor L (I)         ...
<- Plugboard          Y H K U P
Output                Y H K U P
```

**Bold** = the letter changed at that stage · dim = it passed straight through. Every stage
has its own colour (input=blue, plugboard=yellow, entry wheel=cyan, rotors forward=green,
reflector=magenta, rotors back=blue-grey, output=green background).

- **CLI:** `-V` (add `-P` for rotor positions underneath; colour is automatic on a terminal,
  `--color never/always` to force it, `$NO_COLOR` respected).
- **TUI:** `:live` or `t` — it's *live*: type, backspace, move the cursor or make a visual
  selection, and the columns update immediately.

---

## 🕰️ Models

| Key | Machine | Adjustable UKW? | Plugboard? |
|---|---|:---:|:---:|
| `i` | Enigma I (Army / GAF) | — | ✓ |
| `m3` | M3 (Army / Navy) | — | ✓ |
| `m4` | M4 "Shark" (U-boats), 4th wheel | — | ✓ |
| `n` | N — "Norenigma" (Norway) | — | ✓ |
| `s` | S — "Sondermaschine" | — | ✓ |
| `d` | D (commercial, 1926) — trivial Ringstellung, see below | — | — |
| `k` | K (commercial, 1927) | — | — |
| `kd` | KD — K's wheels + a **rewirable** UKW-D reflector | rewirable | — |
| `swissk` | Swiss-K (Swiss Air Force) | — | — |
| `r` | R — "Rocket" (Railway, published wiring) | — | — |
| `r0` | R° (Railway, *physically-measured* wiring) | — | — |
| `t` | T — "Tirpitz" (Japan), own ETW | ✓ | — |
| `a28` | A28/G31 "Zählwerk" — cog drive | ✓ | — |
| `g111` `g260` `g312` | G-series (Abwehr) — cog drive, rotating UKW | ✓ | — |
| `custom` | fully unlocked machine | ✓ | ✓ |

A model **locks** the wheel and reflector choices to what that real machine had; `custom`
unlocks everything. The Zählwerk and G-series step with an odometer-style cog drive — no
double-step, multi-notch rotors, and the reflector itself can rotate.

---

## ✅ Accuracy — how this was checked, not just claimed

> Full evidence, exact commands and raw output are in **[`DATA.md`](DATA.md)**. Summary:

- **Enigma D's turnover notch** is fixed to the rotor core, not the ring ("trivial
  Ringstellung") — confirmed directly from Palloks' own reference documentation and its
  changelog (his own simulator had this same bug before a 2021 fix), and independently
  corroborated by the Crypto Museum's table and by 143/143 agreement with a second,
  unrelated implementation once a known bug in that implementation is excluded. An earlier
  attempt at this fix in this project was wrongly reverted on the strength of a test vector
  that turned out to be circular — see `DATA.md` §5 for the full, honest account.

- **Wiring** — every rotor, reflector and entry-wheel table (64 in total) was compared
  letter-by-letter against the **[Crypto Museum](https://www.cryptomuseum.com/crypto/enigma/wiring.htm)**'s
  published tables. **64/64 agree.** Two typos found in secondary sources along the way
  (Sonder rotor II, the Tirpitz reflector) were caught by cross-referencing and settled
  against the museum.
- **Mechanics** — 2,800 randomly-configured messages were run through this program *and*
  through [Cryptii](https://github.com/cryptii/cryptii)'s independent JavaScript encoder
  (bundled and run for real, not reimplemented): **2,800/2,800 match**. A second,
  unrelated library (`enigma-python`) was used the same way as a cross-check, and in the
  process two real bugs were found **in that library** (a wrong Norenigma turnover letter,
  wrong Tirpitz wiring on two rotors) — not in this program.
- **Real messages** — all 16 real/reference messages in Cryptii's own test suite, including
  the historical U-534 submarine M4 message, reproduce **exactly**.
- **Enigma KD** was added: K's wheels plus a rewirable UKW-D reflector, with the real
  machine's fixed B↔O contact pair enforced. No source was found for Palloks' 5 historical
  example wirings, so it ships a placeholder wiring and expects a real one via `:ukw` /
  `--ukw` when one is known, rather than presenting a guess as authentic. See `DATA.md` §9.
- **Fuzzing** — 800 random TUI key-sequences and 900 random CLI argument combinations run
  against the live program: 0 crashes, 0 invariant violations.

### Known gaps (not guessed at — see `DATA.md` §8)
No verifiable wiring was found for **G-401**. The **Arbeitswalzen** (maintenance test
wheels) mechanism is documented — an identity-wiring rotor plus a reflector pairing
keyboard-adjacent letters — but the exact pairing itself isn't published anywhere found so
far. The **Enigma-Uhr** accessory isn't modelled. All three are left out on purpose rather
than filled in with a guess — see `DATA.md` §8.

---

## 🕓 Version history

| | |
|---|---|
| **v2** *(starting point)* | The original prototype: TUI simulator, rotors/reflector/plugboard/ETW, signal-path panel, F-key driven (F1 help, F2 settings, F3 plugboard...). `Q` quit. |
| **v3** | Real BACKSPACE — restores the *exact* prior rotor positions (not just "step back one"), correctly undoing carries and the double-step. Exit report added (config, input, output). `Q` freed up to type. |
| **v4** | **No function keys, no arrow keys** — rebuilt as vim-style modal editing (INSERT / NORMAL / VISUAL / COMMAND). The message became text + cursor with ciphertext re-derived by replay, so editing mid-message correctly re-enciphers everything after it. |
| **v5** | `:plug` became `add` / `remove` / `clear` / `on` / `off` instead of replace-the-whole-board. Nearly every setting became a `:command`, with TAB completion. |
| **v6** | **3 models → 14 + Custom.** Added N, S, D, K, Swiss-K, R, T, A28/Zählwerk, G-111/260/312, with adjustable reflectors and cog-drive stepping for the mechanical variants that need it. |
| **v7** | *(provided, built on)* R° (physically-measured Railway wiring), `:lock`, duplicate rotor types allowed, Tirpitz-style ETW available in Custom. |
| **v8** | **CLI mode** (every setting as a flag, pipes, auto-named output files, `--json`) + **colourful vertical trace** (CLI `-V` and live `:live`/`t` in the TUI) + a rigorous accuracy pass (Crypto Museum wiring check, differential fuzzing against two independent implementations, several real bugs found and fixed) + **KD** added + Enigma D's notch corrected to its historically accurate mechanism + `DATA.md` / `README.md` written. **14 → 16 models + Custom.** |

Full technical detail for v6–v8 — exact sources, exact test counts, what changed and why — is in
[`DATA.md`](DATA.md).

## 🙏 Credits

- **Wiring data:** [Crypto Museum](https://www.cryptomuseum.com/) — the primary source for
  every wheel in this program.
- **Tables generated from / cross-checked against:** [Cryptii](https://github.com/cryptii/cryptii)
  (MIT), [enigma-python](https://github.com/denismaggior8/enigma-python).
- **Feature reference:** [Daniel Palloks' "Universal Enigma"](https://people.physik.hu-berlin.de/~palloks/js/enigma/) —
  the model roster this program targets.
- **R° wiring:** physically measured by Patrick Hayes (2023), confirmed by Detlev Gross.

---

<div align="center">

*Enigma is reciprocal — the same settings both encrypt and decrypt.*
*Built for the terminal. No function keys were harmed in the making of this simulator.*

</div>
