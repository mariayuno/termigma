"""Command-line interface for termigma.

Every setting is a flag; the TUI opens when no text is supplied on a real
terminal.  Enigma is reciprocal, so decrypting is the same command on the
ciphertext.  Examples::

    # one-shot
    python3 -m termigma -m m3 -r III II I -p A B C -s AB CD -t "HELLO WORLD"

    # pipe a file
    cat message.txt | python3 -m termigma -m m4 --refl B-thin -w Beta -r II IV I

    # write an auto-named file and print the vertical trace
    python3 -m termigma -m i -r I II III -s AB -t "TEST" -o -V
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from .engine import (
    ALPHA, MODELS, MODEL_ALIASES, REFLECTOR_CHOICES,
    ROTOR_CHOICES, FOURTH_WHEEL_CHOICES, ETW_CHOICES,
    Enigma, Rotor, Reflector, FourthWheel, EntryWheel, Plugboard,
    apply_model, parse_plug_pairs, parse_reflector_pairs,
)
from .utils import (
    normalize_text, encipher_text, format_output,
    render_trace, config_oneliner, resolve_out_path, write_file,
)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python3 -m termigma",
        description="Enigma machine simulator — TUI and CLI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Machine selection
    m = p.add_argument_group("machine")
    m.add_argument("-m", "--model", metavar="KEY",
                   choices=MODEL_ALIASES, default=None,
                   help=f"model preset key; choices: {', '.join(MODEL_ALIASES)}")
    m.add_argument("-r", "--rotors", nargs=3, metavar="ROTOR",
                   help="three main rotors (left middle right)")
    m.add_argument("-g", "--ring", nargs="+", metavar="N",
                   help="ring settings 1-26 (one per wheel; include 4th wheel first if present)")
    m.add_argument("-p", "--pos", nargs="+", metavar="LETTER",
                   help="start positions A-Z (same order as --ring)")
    m.add_argument("-u", "--refl", metavar="UKW",
                   help=f"reflector; choices: {', '.join(REFLECTOR_CHOICES)}")
    m.add_argument("--ukw", nargs="+", metavar="PAIR",
                   help="custom rewirable reflector — 13 letter pairs e.g. AB CD EF …")
    m.add_argument("--ukwpos", metavar="LETTER",
                   help="UKW start position (thumbwheel machines)")
    m.add_argument("--ukwring", metavar="N", type=int,
                   help="UKW ring setting 1-26 (thumbwheel machines)")
    m.add_argument("-w", "--wheel", metavar="NAME",
                   choices=FOURTH_WHEEL_CHOICES,
                   help="4th wheel name (Beta or Gamma; requires a thin reflector)")
    m.add_argument("-s", "--plug", nargs="+", metavar="PAIR",
                   help="plugboard pairs e.g. AB CD EF  (or 'off' to disable)")
    m.add_argument("--etw", metavar="MODE",
                   choices=ETW_CHOICES,
                   help=f"entry-wheel mode; choices: {', '.join(ETW_CHOICES)}")
    m.add_argument("--notch", nargs=3, metavar="LETTER",
                   help="override notch letters for left, middle, right rotor")
    m.add_argument("--lock", nargs="+", metavar="WHEEL",
                   help="lock wheels from advancing: L M R UKW (or 'off')")

    # Input
    i = p.add_argument_group("input")
    src = i.add_mutually_exclusive_group()
    src.add_argument("-t", "--text", metavar="TEXT",
                     help="encipher TEXT directly")
    src.add_argument("-f", "--file", metavar="PATH",
                     help="read plaintext from PATH (- = stdin)")

    # Output shaping
    o = p.add_argument_group("output shaping")
    o.add_argument("--group", type=int, metavar="N", default=0,
                   help="group output in blocks of N letters")
    o.add_argument("--letters", action="store_true",
                   help="strip spaces — output one continuous letter run")
    o.add_argument("--keep-other", action="store_true",
                   help="pass non-letter characters through unchanged")
    o.add_argument("--json", action="store_true",
                   help="output as JSON {plain, cipher, config, cli}")

    # File output
    fo = p.add_argument_group("file output")
    fo.add_argument("-o", "--out", nargs="?", const="", metavar="PATH",
                    help="write output to a file; no PATH = auto-named in cwd")

    # Views
    v = p.add_argument_group("views")
    v.add_argument("-V", "--vertical", action="store_true",
                   help="print vertical signal trace after the cipher output")
    v.add_argument("-P", "--positions", action="store_true",
                   help="include rotor positions beneath each trace block")
    v.add_argument("--color", choices=("auto", "always", "never"), default="auto",
                   help="ANSI colour in the trace (default: auto)")

    # Utility
    u = p.add_argument_group("utility")
    u.add_argument("-c", "--show-config", action="store_true",
                   help="print the machine configuration and exit (no message needed)")
    u.add_argument("--list-models", action="store_true",
                   help="list all model keys and labels then exit")
    u.add_argument("--tui", action="store_true",
                   help="force the TUI even when text is provided")
    u.add_argument("--live", action="store_true",
                   help="force the TUI and open in live-trace mode")

    return p


# ---------------------------------------------------------------------------
# Machine setup from parsed args
# ---------------------------------------------------------------------------

def _letter(v: str, name: str) -> str:
    v = v.upper()
    if v not in ALPHA:
        raise SystemExit(f"error: {name}: expected A-Z, got {v!r}")
    return v


def _ring(v: str, name: str) -> int:
    try:
        n = int(v)
    except ValueError:
        n = ALPHA.index(v.upper()) + 1 if v.upper() in ALPHA else -1
    if not 1 <= n <= 26:
        raise SystemExit(f"error: {name}: expected 1-26, got {v!r}")
    return n


def configure_machine(args: argparse.Namespace) -> Enigma:
    """Build and return an Enigma from the parsed CLI arguments."""
    m = Enigma()

    # 1. Apply model preset (sets rotors, refl, etw, mechanism, thumb flags)
    if args.model:
        apply_model(m, args.model)

    # 2. Override individual settings
    if args.refl:
        kind = next((r for r in REFLECTOR_CHOICES if r.lower() == args.refl.lower()), None)
        if kind is None:
            raise SystemExit(f"error: --refl: unknown reflector {args.refl!r}")
        m.reflector_kind = kind
        m.reflector = Reflector(kind, m.custom_reflector_pairs)
        from .engine import THIN_REFLECTORS
        if kind in THIN_REFLECTORS and not m.fourth:
            m.fourth = FourthWheel("Beta")
        elif kind not in THIN_REFLECTORS:
            m.fourth = None

    if args.ukw:
        raw = " ".join(args.ukw).upper()
        ok, res = parse_reflector_pairs(raw)
        if not ok:
            raise SystemExit(f"error: --ukw: {res}")
        m.custom_reflector_pairs = res
        m.reflector_kind = "Custom"
        m.reflector = Reflector("Custom", res)

    if args.wheel:
        m.fourth = FourthWheel(args.wheel.title())

    notch_ov = [None, None, None]
    if args.notch:
        notch_ov = [_letter(x, "--notch") for x in args.notch]

    if args.rotors:
        keys = [r.upper() for r in args.rotors]
        for k in keys:
            if k not in ROTOR_CHOICES:
                raise SystemExit(f"error: --rotors: unknown rotor {k!r}")
        rings = [m.left.ring_setting, m.middle.ring_setting, m.right.ring_setting]
        pos   = [m.left.position_letter, m.middle.position_letter, m.right.position_letter]
        m.left   = Rotor(keys[0], rings[0], pos[0], notch_ov[0])
        m.middle = Rotor(keys[1], rings[1], pos[1], notch_ov[1])
        m.right  = Rotor(keys[2], rings[2], pos[2], notch_ov[2])
    elif any(notch_ov):
        m.left   = Rotor(m.left.name,   m.left.ring_setting,   m.left.position_letter,   notch_ov[0])
        m.middle = Rotor(m.middle.name, m.middle.ring_setting, m.middle.position_letter, notch_ov[1])
        m.right  = Rotor(m.right.name,  m.right.ring_setting,  m.right.position_letter,  notch_ov[2])

    if args.etw:
        m.etw = EntryWheel(args.etw)

    # Ring and position (4th wheel is first when present)
    wheels = ([m.fourth] if m.fourth else []) + [m.left, m.middle, m.right]
    if args.ring:
        rings = [_ring(v, "--ring") for v in args.ring]
        if len(rings) != len(wheels):
            raise SystemExit(
                f"error: --ring: got {len(rings)} values, expected {len(wheels)}"
            )
        for w, r in zip(wheels, rings):
            w.ring_setting = r

    if args.pos:
        pos = [_letter(v, "--pos") for v in args.pos]
        if len(pos) != len(wheels):
            raise SystemExit(
                f"error: --pos: got {len(pos)} values, expected {len(wheels)}"
            )
        for w, p in zip(wheels, pos):
            w.position = ALPHA.index(p)

    if args.ukwpos:
        if not m.refl_thumb:
            raise SystemExit("error: --ukwpos: this model's UKW is not settable")
        m.reflector.pos = ALPHA.index(_letter(args.ukwpos, "--ukwpos"))

    if args.ukwring:
        if not m.refl_thumb:
            raise SystemExit("error: --ukwring: this model's UKW is not settable")
        m.reflector.ring_setting = _ring(str(args.ukwring), "--ukwring")

    if args.plug:
        plug_str = " ".join(args.plug).upper()
        if plug_str == "OFF":
            m.plugboard_enabled = False
        else:
            ok, res = parse_plug_pairs(plug_str)
            if not ok:
                raise SystemExit(f"error: --plug: {res}")
            m.plugboard = Plugboard(res)
            m.plugboard_enabled = True

    if args.lock:
        valid = {"L", "M", "R", "UKW", "OFF"}
        for tok in args.lock:
            t = tok.upper()
            if t not in valid:
                raise SystemExit(f"error: --lock: unknown wheel {tok!r}; choices: L M R UKW off")
            if t == "OFF":
                m.locked.clear()
            else:
                m.locked.add(t)

    return m


# ---------------------------------------------------------------------------
# Reading input text
# ---------------------------------------------------------------------------

def read_input(args: argparse.Namespace) -> str | None:
    """Return the input text from --text, --file, or stdin; None if interactive."""
    if args.text is not None:
        return args.text
    if args.file:
        path = args.file
        if path == "-":
            return sys.stdin.read()
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return None  # interactive — caller should open TUI


# ---------------------------------------------------------------------------
# Main CLI entry point
# ---------------------------------------------------------------------------

def run_cli(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Utility-only flags
    if args.list_models:
        for key, info in MODELS.items():
            print(f"  {key:<10} {info['label']}")
        return

    machine = configure_machine(args)

    if args.show_config:
        print(config_oneliner(machine))
        return

    # Decide: CLI or TUI
    text = read_input(args)
    if text is None or args.tui or args.live:
        from .tui import main as tui_main
        tui_main(machine=machine, live=args.live)
        return

    # --- CLI path ---
    want_color = (
        args.color == "always"
        or (args.color == "auto" and sys.stdout.isatty()
            and os.environ.get("NO_COLOR") is None)
    )

    cipher, dropped = encipher_text(machine, text, keep_other=args.keep_other)
    output = format_output(cipher, group=args.group, letters=args.letters)

    if args.json:
        doc = {
            "plain":  text,
            "cipher": cipher,
            "output": output,
            "config": config_oneliner(machine),
            "dropped": dropped,
        }
        print(json.dumps(doc, ensure_ascii=False, indent=2))
    else:
        print(output)

    if args.vertical:
        cols = os.get_terminal_size().columns if sys.stdout.isatty() else 100
        # Use raw letters only for the trace (spaces break column alignment)
        trace_text = "".join(c for c in text if c.isascii() and c.isalpha()).upper()
        if trace_text:
            print()
            print(render_trace(machine, trace_text, color=want_color,
                               width=cols, positions=args.positions))

    if args.out is not None:
        cli_cmd = config_oneliner(machine)
        header = [f"# config: python3 -m termigma {cli_cmd} --text <message>"]
        path = resolve_out_path(args.out, machine)
        if path:
            write_file(path, output, header=header)
            print(f"# written: {path}", file=sys.stderr)
