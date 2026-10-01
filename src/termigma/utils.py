"""Shared utilities used by both the CLI and the TUI.

Functions here are pure (no curses, no argparse) so they are easily testable
and can be imported from either the interactive or the scriptable entry point.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .engine import Enigma

from .engine import ALPHA, MODELS


# ---------------------------------------------------------------------------
# Text normalisation and encipherment
# ---------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    """Return only A-Z letters and single spaces (any whitespace run -> one space)."""
    out: list[str] = []
    for ch in text:
        if ch.isascii() and ch.isalpha():
            out.append(ch.upper())
        elif ch.isspace() and out and out[-1] != " ":
            out.append(" ")
    return "".join(out).strip()


def encipher_text(machine: "Enigma", text: str, keep_other: bool = False):
    """Encipher raw text through *machine*.

    Letters are enciphered; whitespace passes through; anything else is
    dropped (or kept unchanged when *keep_other* is True).  The machine's
    positions are restored to their start state afterwards.

    Returns ``(output, dropped_count)``.
    """
    start = machine.get_positions()
    out: list[str] = []
    dropped = 0
    try:
        for ch in text:
            if ch.isascii() and ch.isalpha():
                out.append(machine.encode_letter(ch.upper())[0])
            elif ch.isspace() or keep_other:
                out.append(ch)
            else:
                dropped += 1
    finally:
        machine.set_positions(start)
    return "".join(out), dropped


def format_output(cipher: str, group: int = 0, letters: bool = False) -> str:
    """Shape the ciphertext for display or output.

    - Default (group=0, letters=False): return as typed, spaces preserved.
    - ``letters=True``: strip spaces, return one run of letters.
    - ``group=N``: strip spaces, return N-letter blocks separated by spaces.
    """
    if not (group or letters):
        return cipher
    raw = "".join(c for c in cipher if c.isascii() and c.isalpha())
    if group:
        return " ".join(raw[i : i + group] for i in range(0, len(raw), group))
    return raw


# ---------------------------------------------------------------------------
# Machine configuration serialisation
# ---------------------------------------------------------------------------

ALIAS_BY_LABEL = {m["label"]: a for a, m in MODELS.items()}
ALIAS_BY_LABEL["Custom"] = "custom"


def config_oneliner(machine: "Enigma") -> str:
    """Return the machine settings as a single CLI command-line string.

    Feeding this back (with the message) to the CLI reproduces — or reverses —
    the encryption exactly, because the start positions are part of the string.
    """
    m = machine
    alias = ALIAS_BY_LABEL.get(m.model_label, "custom")
    parts = ["--model", alias]

    # Reflector / UKW
    if m.model_label == "Custom":
        if m.reflector_kind == "Custom":
            pairs = " ".join(f"{a}{b}" for a, b in m.custom_reflector_pairs.items()
                             if a < b)
            parts += ["--ukw", pairs]
        else:
            parts += ["--refl", m.reflector_kind]

    # 4th wheel
    if m.fourth:
        parts += ["--wheel", m.fourth.name]

    # Rotors (label form for display, e.g. 'I' not 'I-G312')
    wheels = [m.left, m.middle, m.right]
    parts += ["--rotors"] + [w.label for w in wheels]

    # Ring and position (4th wheel first if present)
    all_wheels = ([m.fourth] if m.fourth else []) + wheels
    parts += ["--ring"]  + [f"{w.ring_setting:02d}" for w in all_wheels]
    parts += ["--pos"]   + [w.position_letter       for w in all_wheels]

    # Adjustable UKW
    if m.refl_thumb:
        parts += ["--ukwpos", m.reflector.position_letter,
                  "--ukwring", f"{m.reflector.ring_setting:02d}"]

    # Plugboard
    if m.plugboard_enabled:
        plugs = [f"{a}{b}" for a, b in m.plugboard.pairs_list()]
        if plugs:
            parts += ["--plug"] + plugs
    else:
        parts += ["--plug", "off"]

    # Locked wheels
    if m.locked:
        parts += ["--lock"] + sorted(m.locked)

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Exit / session report
# ---------------------------------------------------------------------------

def _group5(s: str) -> str:
    return " ".join(s[i : i + 5] for i in range(0, len(s), 5))


def build_report(session) -> str:
    """Full session report: config + plain + cipher for every message."""
    cols = 72
    sep  = "=" * cols
    msgs = list(session.finished)
    if session.msg.text or not msgs:
        cipher, _, _ = session.machine.replay(session.msg.text)
        msgs.append({
            "plain":  session.msg.text,
            "cipher": cipher,
            "snap":   session._machine_snapshot(),
        })

    lines = [sep, " ENIGMA SESSION REPORT", sep]
    for n, msg in enumerate(msgs, 1):
        if len(msgs) > 1:
            lines.append(f"\n--- MESSAGE {n} of {len(msgs)} ---")
        snap = msg["snap"]
        rotors = " ".join(r[0] for r in snap["rotors"])
        rings  = "/".join(f"{r[1]:02d}" for r in snap["rotors"])
        pos    = "/".join(r[2] for r in snap["rotors"])
        fourth = f"  4th={snap['fourth']}" if snap.get("fourth") else ""
        plug   = (("on: " + snap["plugs"]) if snap["plugboard_on"] and snap["plugs"]
                  else ("on" if snap["plugboard_on"] else "off"))
        lines += [
            "",
            "CONFIGURATION",
            f"  Model     : {snap['reflector']}{fourth}  etw {snap['etw']}",
            f"  Rotors    : {rotors}  ring {rings}  pos {pos}",
            f"  Plugboard : {plug}",
        ]
        plain  = msg["plain"].replace(" ", "")
        cipher = msg["cipher"].replace(" ", "")
        n_let  = len(plain)
        cli    = config_oneliner(session.machine)
        lines += [
            "",
            f"INPUT   ({n_let} letter{'s' if n_let != 1 else ''})",
            f"  typed  : {msg['plain'] or '(empty)'}",
            f"  groups : {_group5(plain) or '(empty)'}",
            "",
            f"OUTPUT  ({n_let} letter{'s' if n_let != 1 else ''})",
            f"  typed  : {msg['cipher'] or '(empty)'}",
            f"  groups : {_group5(cipher) or '(empty)'}",
            "",
            f"CLI COMMAND",
            f"  python3 -m termigma {cli} --text \"<your message>\"",
        ]
    lines.append("\n" + sep)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Vertical signal trace
# ---------------------------------------------------------------------------

def stage_kind(label: str) -> str:
    if label in ("Keyboard", "Input"):
        return "input"
    if label in ("Lamp", "Output"):
        return "output"
    if "Plugboard" in label:
        return "plug"
    if "Entry Wheel" in label:
        return "etw"
    if label.startswith("Reflector"):
        return "refl"
    return "back" if label.startswith("<-") else "fwd"


def _clean_label(raw: str) -> str:
    """Normalise an encode_letter() path label to a short display form."""
    raw = raw.replace(" ->", "").replace("Entry Wheel (ETW)", "ETW")
    if raw == "Keyboard":
        return "Input"
    if raw == "Lamp":
        return "Output"
    return raw


def build_trace(machine: "Enigma", text: str):
    """Replay *text* and collect per-stage letter paths without side-effects.

    Returns ``(labels, kinds, columns, positions)`` where *columns* is a list
    with one element per input character: either a list of per-stage letters or
    ``None`` for a space.  *positions* carries the 4-tuple snapshot after each
    character.  Labels and positions are derived from encode_letter() paths so
    they are always consistent with the encipherment.
    """
    start = machine.get_positions()
    labels: list[str] | None = None
    cols, poss = [], []
    try:
        for ch in text:
            if ch == " ":
                cols.append(None)
                poss.append(None)
                continue
            _out, path = machine.encode_letter(ch.upper())
            if labels is None:
                labels = [_clean_label(lab) for lab, _ in path]
            cols.append([letter for _, letter in path])
            poss.append(machine.get_positions())
    finally:
        machine.set_positions(start)
    if labels is None:
        labels = []
    kinds = [stage_kind(l) for l in labels]
    return labels, kinds, cols, poss


ANSI = {
    "input":  "1;97;44",   # bold white on blue
    "plug":   "33",         # yellow
    "etw":    "36",         # cyan
    "fwd":    "32",         # green
    "refl":   "1;35",       # bold magenta
    "back":   "94",         # light blue
    "output": "1;30;42",    # bold black on green
}
ANSI_LABEL = dict(ANSI, input="1;97", output="1;92")


def render_trace(machine: "Enigma", text: str, color: bool = False,
                 width: int = 100, positions: bool = False,
                 gap: str = ".") -> str:
    """Render the vertical trace as a plain-text (or ANSI-coloured) string.

    Rows run from Input at the top to Output at the bottom.  Each column is
    one letter of *text*; spaces appear as *gap* in the input/output rows.
    A **bold** letter changed at that stage; dim means it passed straight through.
    """
    labels, kinds, cols, poss = build_trace(machine, text)
    prow = ([(f"UKW pos", 3)] if machine.refl_thumb else []) + [
        ("Rotor L pos", 0), ("Rotor M pos", 1), ("Rotor R pos", 2),
    ] if positions else []
    g = max(len(x) for x in labels + ([r[0] for r in prow] if prow else [""])) + 2

    def paint(s: str, code: str) -> str:
        return f"\x1b[{code}m{s}\x1b[0m" if color and code else s

    per = max(4, (width - g - 1) // 2)
    lines: list[str] = []
    for b in range(0, max(1, len(cols)), per):
        chunk  = cols[b : b + per]
        pchunk = poss[b : b + per]
        if b:
            lines.append("")
        for r, (lab, kind) in enumerate(zip(labels, kinds)):
            cells = []
            for col in chunk:
                if col is None:
                    cells.append((paint(gap, "2") + " ") if kind in ("input", "output")
                                 else "  ")
                    continue
                changed = (r == 0) or (col[r - 1] != col[r])
                if kind in ("input", "output"):
                    code = ANSI[kind]
                else:
                    code = ("1;" if changed else "2;") + ANSI[kind]
                cells.append(paint(col[r], code) + " ")
            lines.append(paint(f"{lab:<{g}}", ANSI_LABEL[kind]) + "".join(cells).rstrip())
        if prow:
            lines.append(paint("-" * min(width - 1, g + 2 * len(chunk)), "2"))
            for lab, idx in prow:
                cells = ["  " if p is None else paint(ALPHA[p[idx]], "36") + " "
                         for p in pchunk]
                lines.append(paint(f"{lab:<{g}}", "36") + "".join(cells).rstrip())
    if color:
        lines += ["", paint("bold = letter changed at that stage   "
                            "dim = passed through unchanged", "2")]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Output file helpers
# ---------------------------------------------------------------------------

def auto_filename(machine: "Enigma", ext: str = "txt", tag: str = "") -> str:
    """Build a descriptive filename from the machine settings."""
    m = machine
    alias = ALIAS_BY_LABEL.get(m.model_label, "custom")
    wheels = ([m.fourth] if m.fourth else []) + [m.left, m.middle, m.right]
    parts = [
        "enigma", alias,
        "-".join(w.label for w in wheels),
        "ring" + "".join(f"{w.ring_setting:02d}" for w in wheels),
        "pos"  + "".join(w.position_letter       for w in wheels),
        "ukw"  + ("custom" if m.reflector_kind == "Custom"
                  else m.reflector_kind.replace("UKW-", "")),
    ]
    if m.refl_thumb:
        parts.append(f"ukwpos{m.reflector.position_letter}{m.reflector.ring_setting:02d}")
    if m.plugboard_enabled and m.plugboard.pairs_list():
        parts.append("plug" + "-".join(f"{a}{b}" for a, b in m.plugboard.pairs_list()))
    if m.locked:
        parts.append("lock" + "".join(sorted(m.locked)))
    if tag:
        parts.append(tag)
    parts.append(datetime.now().strftime("%Y%m%d-%H%M%S"))
    return re.sub(r"[^A-Za-z0-9._-]", "-", "_".join(parts)) + "." + ext


def resolve_out_path(spec: str | None, machine: "Enigma",
                     ext: str = "txt", tag: str = "") -> str | None:
    """Resolve an output path from the -o / --out flag value.

    - ``None``  → no file output
    - ``""``    → auto-name in the current directory
    - a directory path → auto-name in that directory
    - a file path → use exactly that path (no overwrite guard)
    """
    if spec is None:
        return None
    spec = os.path.expanduser(spec)
    if spec and not (spec.endswith(("/", os.sep)) or os.path.isdir(spec)):
        return spec
    directory = spec or "."
    os.makedirs(directory, exist_ok=True)
    name = auto_filename(machine, ext, tag)
    path = os.path.join(directory, name) if spec else name
    base, e = os.path.splitext(path)
    n = 1
    while os.path.exists(path):
        n += 1
        path = f"{base}-{n}{e}"
    return path


def write_file(path: str, body: str, header: list[str] | None = None) -> None:
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if header:
            f.write("\n".join(header) + "\n")
        f.write(body.rstrip("\n") + "\n")
