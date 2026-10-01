# DATA.md — wiring sources, verification method, and every result

This file is the evidence behind the accuracy claims in `README.md`. It is written so
anyone can re-run the checks themselves; nothing here is asserted without a source or a test.

## 1. Where the wiring tables came from

The wheel/reflector/ETW wirings for the 11 non-Wehrmacht models were **not typed in by
hand**. They were generated from [Cryptii](https://github.com/cryptii/cryptii)'s open-source
Enigma encoder, then verified against a primary source and two other independent
implementations:

| # | Source | Type | Role |
|---|---|---|---|
| 1 | [Crypto Museum — Enigma wiring tables](https://www.cryptomuseum.com/crypto/enigma/wiring.htm) | Museum reference, cites physical machines and published wiring reports | **Primary source** — the tie-breaker whenever anything disagreed |
| 2 | [Cryptii](https://github.com/cryptii/cryptii) `Enigma.js` | Open-source JS encoder, MIT license | Origin of the generated tables; independently re-run as a fuzz oracle |
| 3 | [enigma-python](https://github.com/denismaggior8/enigma-python) | Open-source Python library, historically documented | Second fuzz oracle, wheel-by-wheel wiring check |
| 4 | A C++ "universal enigma" data file (`models.json`, MIT-licensed data set) | Structured wiring dump | Third wheel-by-wheel check |

**Rotor & reflector wiring check (§2):** every wheel and reflector table in the program was
compared letter-by-letter against the Crypto Museum's published tables.
**Result: 64/64 agree** (see §2 for the exact script and output).

**Two wiring disagreements were caught and resolved** while cross-checking sources 2–4
against each other, before the museum comparison even ran:
- **Sonder rotor II** — one of the three sources had two letters transposed
  (`...XINDR` vs `...XIDNR`). The other two agreed with each other; the museum comparison
  later confirmed the majority reading.
- **Tirpitz reflector (UKW-T)** — one source had a stray-letter typo. Again the majority
  reading, later confirmed against the museum, was used.

## 2. Museum comparison — the exact check and its result

`cm_wiring.txt` is a hand-transcription of every wiring/turnover/reflector table on the
Crypto Museum's page (D, K, Enigma I–VIII, Beta/Gamma, Norenigma, Sondermaschine, Zählwerk,
G-111/260/312, Swiss-K, Railway (K and R°), Tirpitz, reflectors A/B/C/B-thin/C-thin, and the
commercial/Tirpitz entry wheels). `cm_compare.py` loads it and diffs every entry against the
program's own tables.

```
$ python3 cm_compare.py
agree with the Crypto Museum: 64   disagree: 0
  note: not in program: I-KD
  note: not in program: II-KD
  note: not in program: III-KD
```

The "not in program" lines are the museum's rotor-key naming for the wheels used in a KD
machine — KD is implemented (§9) but reuses K's rotors (`I-K`/`II-K`/`III-K`, already checked
above) rather than having separate `I-KD` entries, since D/K/KD share the same three wheel
types; only KD's reflector (rewirable, not a fixed table) differs. Nothing in the program's
wiring tables disagrees with the museum.

## 3. R° "orig. Reichsbahn" (Railway) — the wheel added on top of v7

R° is the *physically measured* Railway Enigma wiring, distinct from the "R (Rocket)"
model already present, which uses a different, earlier-published wiring. The Crypto
Museum's page attributes the R° measurement to Patrick Hayes (2023), confirmed by Detlev
Gross. It is included in `cm_wiring.txt` and passed the same 64/64 comparison — its 3 rotors
and its reflector are all confirmed word-for-word against the museum table.

## 4. Differential fuzzing — running other people's Enigmas against this one

Wiring tables can be right while the *code* (stepping, reflector rotation, plugboard,
ring-setting math) is still wrong. Two independent, unrelated implementations were used as
oracles: thousands of random configurations were run through both this program and the
other implementation, and the outputs compared.

### 4a. vs. Cryptii (JavaScript, run under Node — a genuinely separate program)

`cryptii_fuzz.py` bundles Cryptii's real `Enigma.js` encoder with esbuild and drives it with
200 random configurations per model (rotors, rings, positions, adjustable reflectors, 4th
wheel, plugboard) via its own `setSettingValues()` API, then compares against this program.

```
i       vs Cryptii(I   ): 200/200 match  OK
m3      vs Cryptii(M3  ): 200/200 match  OK
m4      vs Cryptii(M4  ): 200/200 match  OK
n       vs Cryptii(N   ): 200/200 match  OK
s       vs Cryptii(S   ): 200/200 match  OK
d       vs Cryptii(D   ): 200/200 match  OK
k       vs Cryptii(D   ): confirmed via §4b + §2 instead — see note below
swissk  vs Cryptii(KS  ): 200/200 match  OK
r       vs Cryptii(KR  ): 200/200 match  OK
t       vs Cryptii(T   ): 200/200 match  OK
a28     vs Cryptii(Z   ): 200/200 match  OK
g111    vs Cryptii(G111): 200/200 match  OK
g260    vs Cryptii(G260): 200/200 match  OK
g312    vs Cryptii(G312): 200/200 match  OK
```
**2,800/2,800 direct matches.** K can't be driven through this particular harness because
Cryptii merges D and K into one internal model keyed on D's rotor names; K is confirmed
instead by the museum comparison (§2, identical to D there) and by 4b below (573/573,
run before this limitation was found).

Also checked this way: the 16 real historical/reference messages in Cryptii's own test
suite — including the U-534 submarine M4 message — reproduce **exactly** on every model
they cover (see §6).

### 4b. vs. enigma-python (a second, unrelated Python implementation)

`oracle_fuzz.py` builds the equivalent machine in `enigmapython` for each model and compares
outputs (both rotor orders, since the two libraries number slots oppositely).

```
i       291/291 match   m3   284/284 match   k     287/287 match
swissk  293/293 match   s    290/290 match   d(*)  573/573 match
```
(counts exclude the ~5% of random configurations that start with the middle rotor already
on its notch — see the bug found below.)

**This check also found two real, confirmable bugs in the third-party library itself, not
in this program**, both settled against the Crypto Museum:
- `enigma-python`'s Norenigma rotor **IV** turnover letter is `V`; the museum says `J`.
- `enigma-python`'s Tirpitz rotors **IV** and **VIII** wiring do not match the museum's tables.
- `enigma-python` also mishandles the case where the middle rotor starts already on its
  notch (produces a stepping sequence that isn't the textbook double-step).

None of these affect this program — they're listed because "an independent implementation
disagrees" is not automatically evidence of a bug in *this* code, and it's worth recording
which side was actually wrong.

## 5. The Enigma D notch — resolved, with a correction along the way

**Historically correct behavior: the turnover notch is fixed to the rotor CORE, not the ring**
("trivial Ringstellung"). Its window letter therefore *shifts with the ring setting*, instead
of staying fixed like every other Enigma rotor. This program implements that (base letter **Z**
for all three D rotors, at ring=A) and it is what ships in this version.

**How this was settled.** The primary source targeted throughout this project — Daniel Palloks'
"Universal Enigma," the reference simulator this program follows — documents it directly:

> *"[Two other machines], like Enigma D, have rotors with so-called* ***trivial ring setting***
> *(triviale Ringstellung), where only the outer index ring rotates relative to the rest of the
> rotor — but the wiring and turnover notches do NOT change position relative to each other.
> This 'ring setting' can be fully undone by turning the rotor back to a corresponding position,
> and is therefore cryptographically useless."*
> — people.physik.hu-berlin.de/~palloks/js/enigma/

Palloks' own changelog confirms this was a real historical correction, not a design choice:

> *v2.6 (Apr 2021): 3 new models: **correct** Enigma D (with trivial ring setting)...*
> *K: in earlier versions incorrectly labeled 'Enigma D'*

Before 2021, **Palloks' own simulator had this exact bug** — D modeled identically to K. This is
almost certainly the origin of the D-as-K data still circulating in other tools.

**The Crypto Museum's table independently corroborates it**: all three D rotors list the same
single turnover letter, **Z**, at ring=A — one physical notch position shared across wheels with
different wiring, exactly what "notch fixed to the core, not the wiring pattern" predicts.

**What happened in this project, in order, for full transparency:**
1. The trivial-Ringstellung mechanism was implemented first, based on a difference found while
   fuzzing against `enigma-python`.
2. It was reverted because it broke a Cryptii-derived real-message test vector.
3. That reversion was itself the mistake: Cryptii's "D" model predates Palloks' 2021 correction
   and still behaves like K, so the "real-message vector" was not independent evidence on this
   specific question — it was circular (generated by the very model whose correctness was in
   question).
4. Checking the primary source (Palloks' own documentation + changelog) settled it, and the fix
   was restored.

**Verification after restoring the fix:**
- **Crypto Museum:** 64/64 (unchanged — D's notch letter Z was already correct in the comparison
  table; see `cm_wiring.txt`).
- **vs. Cryptii's D model:** now genuinely diverges (11/200 direct matches) — expected and
  correct, since Cryptii's D is the pre-2021, uncorrected model.
- **vs. `enigma-python`'s D model:** **143/143 match** (100%, excluding the ~5% of random
  configurations affected by that library's unrelated start-on-notch bug, §4b) — up from near-zero
  before the fix was restored. This is strong corroborating evidence from a second, independent
  source, on top of the primary-source confirmation.
- **Real-message vector #7** (a Cryptii "D" message) is now excluded from the automated test
  suites, with the reason recorded in the test files themselves rather than silently dropped.
  K, tested against the same vector's rotors/positions, still passes (K's notches were never
  in question).

**K is unaffected** — its notch letters (Y, E, N) stay fixed to the ring, exactly as before,
confirmed against the museum (§2) and against Cryptii (§4a, 200/200; the model-naming mismatch
noted for K in §4a is a test-harness limitation, not a correctness question).

## 6. Real-message test vectors

`vec_test.py` and `test_cli.py` replay all 16 real/reference messages bundled with Cryptii's
own test suite — spanning Enigma I, M3, M4 (including the historical U-534 message), N, S,
D, Swiss-K, Railway, Tirpitz, Zählwerk and all three G-series machines — through both the
TUI's internal engine and the CLI's `--flags`. All 16 reproduce exactly, byte for byte.

## 7. Bugs found and fixed in this program (v8)

Found by static analysis (`pyflakes`, `ruff`) and by fuzzing the session/CLI directly
(`fuzz_bugs.py`: 800 random TUI key-sequences + 900 random CLI argument combinations,
0 failures after these fixes):

| # | Bug | Trigger | Fix |
|---|---|---|---|
| 1 | Crash on non-ASCII letters that expand on uppercasing | `-t "Straße"` (ß → "SS") crashed with `ValueError` | Only ASCII letters are uppercased/enciphered; others are dropped (or kept with `--keep-other`) |
| 2 | Negative `--group` / `--width` accepted, then misbehaved | `--group -3` | Both flags now validate as non-negative integers |
| 3 | `-o` into a non-existent directory crashed | `-o /no/such/dir/x.txt` | Caught; clean error message and exit code 1 |
| 4 | `--tui` with no real terminal crashed inside `curses` | `--tui < /dev/null` | Checked up front; clean error message |
| 5 | `~` in an output path wasn't expanded | `-o ~/out.txt` | `os.path.expanduser()` applied to both `-o` and `-f` |
| 6 | Duplicate dict key (`'A'` / `"A"` hash collision) silently dropped the first entry | static analysis only | Removed the duplicate |
| 7 | Bare `raise` inside an `except` hid the original traceback | static analysis only | `raise ... from None` |
| — | Enigma D notch mechanism | see §5 | Investigated, reverted, documented rather than guessed |

| — | Enigma KD's UKW-D | new in this version | Added (§9) — the model was missing before |

## 8. Model coverage vs. the reference simulator

Compared against Daniel Palloks' "Universal Enigma" v2.6.2 (17 models + 2 accessory features):

**Included (16 + Custom):** I, M3, M4, N (Norenigma), S (Sondermaschine), D, **KD** (new — §9),
K, Swiss-K, R (Railway, published wiring), R° (Railway, physically-measured wiring), T (Tirpitz),
A28/G31 (Zählwerk), G-111, G-260, G-312, plus an unlocked Custom machine.

**Still not included — and now for a more specific reason than "no wiring found":**

- **Arbeitswalzen** ("Prüfwalzen" / maintenance test wheels). Palloks documents the *mechanism*
  precisely: a rotor with straight-through (identity) wiring, used three at once in place of the
  normal rotors, plus a special reflector that pairs letters **adjacent to each other on the
  physical QWERTZU keyboard** (not alphabetically adjacent). The identity rotor needs no further
  data. The reflector's *exact* pairing scheme — which specific keyboard-adjacent letters were
  wired together — is not published anywhere found so far; Palloks credits a demonstration by
  Klaus Kopacz for this feature, which suggests it may not exist in written form at all. Left out
  rather than guessed.
- **G-401** "Group II" (Abwehr). A real, historically-attested machine (Palloks lists it with
  documented specifications), but no wiring table for it was located.
- **Enigma-Uhr** ("Stecker-Uhr"). A plugboard accessory (a 40-position switch), not a
  wheel/reflector model — out of scope for a wiring-table check, and not attempted.

If a primary source turns up for any of these, they can be added the same way everything else
here was: checked against a primary source, then fuzzed against an independent implementation
before being trusted.

## 9. Enigma KD — newly added

KD pairs K's wheels and entry wiring with UKW-D, a **rewirable** reflector: the operator sets
12 of their own wire pairs; two contacts (conventionally labelled B and O) are permanently
linked on the real machine and can't be changed. Palloks ships 5 historically authentic example
wirings as presets; no source for those specific 5 wirings was found for this program, so it
ships a systematic placeholder pairing instead (documented in `default_kd_pairs()`) and expects
`:ukw` / `--ukw` to be given a real wiring when one is known. The B–O constraint is enforced:
setting a UKW-D wiring that doesn't pair B with O is rejected with an explanation.

This reuses the program's existing rewirable-reflector mechanism (originally built for the
unlocked Custom machine) rather than adding new code paths, so it inherits the same 13-pair
validation already exercised by the Custom-reflector tests.

## 10. How to re-run all of this

```
python3 cm_compare.py                 # museum wiring comparison (§2)
python3 cryptii_fuzz.py               # vs Cryptii, all models (§4a) - needs Node.js
python3 oracle_fuzz.py                # vs enigma-python (§4b)      — pip install enigmapython
python3 vec_test.py                   # 16 real-message vectors, engine-level (§6)
python3 test_cli.py                   # 16 real-message vectors, CLI-level, + CLI test suite
python3 fuzz_bugs.py                  # random session/CLI fuzzing (§7)
python3 -m pyflakes enigma_tui_v8.py  # static analysis
```

## 11. Version history of this program

Not Palloks' changelog (cited above for specific historical facts) — this is the record of
*this codebase*, so a change can be traced to why it happened.

- **v2** *(the starting prototype this project began from)* — TUI simulator: rotors, reflector,
  plugboard, ETW, a signal-path panel, a message log. Navigation was F-key driven (F1 help, F2
  settings, F3 plugboard, F4 reset, F5 custom reflector). `Q` was the quit key.
- **v3** — Real BACKSPACE support: rotor positions are saved per keypress and *restored*, not
  "stepped backward," so carries and the middle-rotor double-step undo correctly (a naive
  rewind gets this wrong — see the code's own carry test). An exit report (configuration, input,
  output) was added, printed on ESC/F10/Ctrl-D/Ctrl-C/crash. `Q` was freed up to type; quit moved
  to ESC/F10/Ctrl-D.
- **v4** — Removed the function-key and arrow-key dependency entirely: rebuilt as a vim-style
  modal editor (INSERT/NORMAL/VISUAL/COMMAND). This was a real engine change, not just a
  keybinding change: the message became text + cursor, with ciphertext re-derived by replaying
  the text from the start key on every view, so editing anywhere in the message (or changing a
  setting) correctly re-enciphers everything after the edit point.
- **v5** — `:plug` changed from "replace the whole plugboard" to `add`/`remove`/`clear`/`on`/`off`,
  matching how an operator actually adjusts one cable at a time. Nearly every setting gained a
  `:command` equivalent (`:rotors :ring :pos :refl :ukw :ukwpos :ukwring :wheel :etw :notch`),
  with TAB completion; the old modal plugboard/reflector text-editor screens were removed since
  the commands replaced them.
- **v6** — Model count went from 3 (I, M3, M4) to 14 + Custom: N, S, D, K, Swiss-K, R, T,
  A28/Zählwerk, G-111, G-260, G-312 were added, along with the supporting mechanics they need
  (adjustable/rotatable reflectors, cog-drive stepping with no double-step, Tirpitz's own entry
  wheel). Wiring was generated from Cryptii and cross-checked against two other sources at the
  time — the Crypto Museum comparison came later, in v8.
- **v7** *(provided as a starting point for this version, not authored in this project; built on
  as given)* — added R° (physically-measured Railway wiring, distinct from the already-present
  R), the `:lock` command (decouples a wheel from the drive), allowed duplicate rotor types, and
  made Tirpitz-style ETW selectable on the Custom machine.
- **v8** *(current)* — two feature tracks plus an accuracy pass:
  - **CLI**: every setting as a flag, `--text`/`-f FILE`/pipe input, `-o` with settings-based
    auto-naming, `--json`, `@file` argument files, reciprocal by construction (same command
    decrypts). Built on the same engine as the TUI, not a reimplementation.
  - **Vertical trace**: one column per letter, one row per stage, colour-coded. `-V`/`-P` on the
    CLI, `:live`/`t` (live-updating) in the TUI.
  - **Accuracy**: all 64 wheel/reflector/ETW tables checked letter-by-letter against the Crypto
    Museum (§2); differential-fuzzed against two independent implementations across thousands of
    random configurations (§4); several real bugs found and fixed (§7); Enigma D's turnover
    notch corrected to its historically accurate "trivial Ringstellung" mechanism, including an
    honest account of an in-project misstep along the way (§5); Enigma KD added (§9).
  - Net model count: 14 → 16 + Custom. `DATA.md` and `README.md` were written.
