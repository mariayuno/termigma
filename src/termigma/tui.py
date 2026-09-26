"""Curses front-end for the termigma Enigma engine. All model logic lives
in engine.py; this module only draws things and reads the keyboard."""

import curses
import os

from .engine import (
    ALPHA, KB_ROWS, KB_INDENT, MAX_PLUGS, THIN_REFLECTORS,
    ROTOR_CHOICES, FOURTH_WHEEL_CHOICES, REFLECTOR_CHOICES,
    Rotor, FourthWheel, EntryWheel, Reflector, Plugboard, Enigma,
    FIELD_LABEL, build_field_order, adjust_field, fmt_val,
    parse_plug_pairs, parse_reflector_pairs,
)

ETW_CHOICES = ("military", "commercial")
PLUG_SUBS   = ("add", "remove", "clear", "on", "off")

CANCEL_KEYS    = frozenset({27, ord("`")})
BACKSPACE_KEYS = frozenset({curses.KEY_BACKSPACE, 127, 8})
ARROWS = {curses.KEY_LEFT: "h", curses.KEY_RIGHT: "l",
          curses.KEY_HOME: "0", curses.KEY_END: "$"}

COMMANDS = (
    "plug", "refl", "etw", "rotors", "ring", "pos", "wheel",
    "ukw", "show", "reset", "new", "help", "q", "q!",
)

MODE_HINT = {
    "INSERT":  "type A-Z / SPACE   BKSP delete   ESC or ` -> normal",
    "NORMAL":  ("i a I A insert   x X del   u undo   dd clear   "
                "yy/p yank/paste   v visual   : cmd   ? help"),
    "VISUAL":  "h l 0 $ w b extend   o other end   d delete   y yank   c change   ESC cancel",
    "COMMAND": "TAB complete   ENTER run   ESC cancel   :q to quit",
}


# ---------------------------------------------------------------------------
# Message — text buffer with cursor and undo stack
# ---------------------------------------------------------------------------
class Message:
    """An editable string of A-Z letters and spaces, with cursor and undo."""

    def __init__(self):
        self.text = ""
        self.cur  = 0
        self._hist = [("", 0)]   # (text, cursor) snapshots for undo

    def _push(self):
        self._hist.append((self.text, self.cur))
        del self._hist[:-500]

    def insert(self, s):
        """Insert *s* at the cursor and advance past it."""
        self._push()
        self.text = self.text[:self.cur] + s + self.text[self.cur:]
        self.cur += len(s)

    def delete(self, a, b):
        """Delete the half-open range [a, b) and place the cursor at *a*."""
        self._push()
        self.text = self.text[:a] + self.text[b:]
        self.cur  = max(0, min(a, len(self.text)))

    def undo(self):
        """Step back through history.  Returns True if a change was undone."""
        while self._hist:
            t, c = self._hist.pop()
            if t != self.text:
                self.text, self.cur = t, min(c, len(t))
                return True
        return False

    def move(self, k):
        """Move the cursor by vim motion key *k* (one of h l 0 $ w b)."""
        c, t = self.cur, self.text
        if k == "h":   c -= 1
        elif k == "l": c += 1
        elif k == "0": c = 0
        elif k == "$": c = len(t)
        elif k == "w":
            while c < len(t) and t[c] != " ": c += 1
            while c < len(t) and t[c] == " ": c += 1
        elif k == "b":
            while c > 0 and t[c - 1] == " ": c -= 1
            while c > 0 and t[c - 1] != " ": c -= 1
        self.cur = max(0, min(len(t), c))


# ---------------------------------------------------------------------------
# Session — machine + message + vim-mode state machine
# ---------------------------------------------------------------------------
class Session:
    """Machine configuration, an editable message, and the editing mode.

    The machine's current positions are the *start key* — they are never
    mutated while typing.  Ciphertext is always derived by calling
    machine.replay(text), which re-enciphers from those fixed positions
    without advancing them.  Any edit just calls replay() again, so the
    displayed ciphertext stays consistent with the buffer and the key.
    """

    def __init__(self):
        self.machine  = Enigma()
        self.msg      = Message()
        self.finished: list = []   # snapshots of messages closed with :new
        self.mode     = "INSERT"
        self.anchor   = 0          # VISUAL mode: the stationary end
        self.cmd      = ""         # COMMAND mode: buffer being typed
        self.pending  = ""         # NORMAL: first key of dd / yy digraph
        self.reg      = ""         # yank register
        self.notice   = ""         # one-line message above the status bar

    # -- replay view ---------------------------------------------------------

    def view(self):
        """Return everything draw_all() needs for the current frame."""
        t, c = self.msg.text, self.msg.cur
        # INSERT cursor is between chars; the focused letter is the one left of it.
        focus = min(c - 1 if self.mode == "INSERT" else c, len(t) - 1)
        cipher, snaps, path = self.machine.replay(t)
        pos = snaps[focus] if focus >= 0 else self.machine.get_positions()
        lit = focus >= 0 and t[focus] != " "
        return {
            "cipher": cipher,
            "pos":    pos,
            "path":   path if lit else [],
            "key":    t[focus]      if lit else None,
            "out":    cipher[focus] if lit else None,
        }

    def selection(self):
        """(start, end) of the current VISUAL selection (half-open)."""
        a, b = sorted((self.anchor, self.msg.cur))
        return a, min(b + 1, len(self.msg.text))

    def start_new(self):
        """Finalise the current message and open a blank one."""
        if self.msg.text:
            cipher, _, _ = self.machine.replay(self.msg.text)
            self.finished.append({
                "plain":  self.msg.text,
                "cipher": cipher,
                "snap":   self._machine_snapshot(),
            })
        self.msg  = Message()
        self.mode = "INSERT"
        self.notice = "New message started."

    def _machine_snapshot(self):
        m = self.machine
        return {
            "reflector":    m.reflector_kind,
            "etw":          m.etw.mode,
            "rotors":       [(w.name, w.ring_setting, w.position_letter)
                             for w in (m.left, m.middle, m.right)],
            "fourth":       m.fourth.name if m.fourth else None,
            "plugboard_on": m.plugboard_enabled,
            "plugs":        " ".join(f"{a}{b}" for a, b in m.plugboard.pairs_list()),
        }

    # -- key handling --------------------------------------------------------

    def key(self, ch):
        """Process one raw curses keycode.

        Returns 'quit' or 'help' to tell the main loop what to do next,
        or None to continue normally.
        """
        self.notice = ""
        if self.mode == "COMMAND":
            return self._key_command(ch)
        cancel = ch in CANCEL_KEYS

        if self.mode == "INSERT":
            if cancel:
                self.mode = "NORMAL"
            elif ch in BACKSPACE_KEYS:
                if self.msg.cur:
                    self.msg.delete(self.msg.cur - 1, self.msg.cur)
                    self.msg._hist.pop()   # delete is its own undo unit
            elif ch == 32 or 65 <= ch <= 90 or 97 <= ch <= 122:
                self.msg.insert(" " if ch == 32 else chr(ch).upper())
            return None

        # NORMAL / VISUAL: backspace = move left
        if ch in BACKSPACE_KEYS:
            ch = ord("h")
        c = ARROWS.get(ch) or (chr(ch) if 0 < ch < 256 else "")

        if self.mode == "VISUAL":
            if cancel or c == "v":
                self.mode = "NORMAL"
            elif c in "hl0$wb":
                self.msg.move(c)
            elif c == "o":
                self.anchor, self.msg.cur = self.msg.cur, self.anchor
            elif c in "dxyc":
                a, b = self.selection()
                self.reg = self.msg.text[a:b]
                if c == "y":
                    self.msg.cur = a
                    self.mode = "NORMAL"
                    self.notice = f"Yanked {len(self.reg)} character(s)."
                else:
                    self.msg.delete(a, b)
                    self.mode = "INSERT" if c == "c" else "NORMAL"
            return None

        # NORMAL
        p, self.pending = self.pending, ""
        if p + c == "dd":
            self.msg._push()
            self.msg.text, self.msg.cur = "", 0
            self.notice = "Message cleared.  u to undo."
        elif p + c == "yy":
            self.reg = self.msg.text
            self.notice = f"Yanked {len(self.msg.text)} character(s)."
        elif c in "hl0$wb":
            self.msg.move(c)
        elif c == "i":
            self.msg._push(); self.mode = "INSERT"
        elif c == "a":
            self.msg.cur = min(len(self.msg.text), self.msg.cur + 1)
            self.msg._push(); self.mode = "INSERT"
        elif c == "I":
            self.msg.cur = 0; self.msg._push(); self.mode = "INSERT"
        elif c == "A":
            self.msg.cur = len(self.msg.text); self.msg._push(); self.mode = "INSERT"
        elif c == "x":
            if self.msg.cur < len(self.msg.text):
                self.msg.delete(self.msg.cur, self.msg.cur + 1)
        elif c == "X":
            if self.msg.cur > 0:
                self.msg.delete(self.msg.cur - 1, self.msg.cur)
        elif c == "u":
            if not self.msg.undo():
                self.notice = "Already at the oldest change."
        elif c in "dy":
            self.pending = c
        elif c == "p":
            if self.reg:
                self.msg._push()
                self.msg.insert(self.reg)
        elif c == "v":
            self.mode, self.anchor = "VISUAL", self.msg.cur
        elif c == ":":
            self.mode, self.cmd = "COMMAND", ""
        elif c == "?":
            return "help"
        return None

    def _key_command(self, ch):
        if ch in CANCEL_KEYS:
            self.mode, self.cmd = "NORMAL", ""
        elif ch in (10, 13, curses.KEY_ENTER):
            cmd = self.cmd.strip()
            self.cmd, self.mode = "", "NORMAL"
            return self._run(cmd)
        elif ch == 9:
            self._tab_complete()
        elif ch in BACKSPACE_KEYS:
            if self.cmd:
                self.cmd = self.cmd[:-1]
            else:
                self.mode = "NORMAL"
        elif 32 <= ch < 127:
            self.cmd += chr(ch)
        return None

    def _run(self, cmd):
        name, _, rest = cmd.partition(" ")
        name = name.lower()
        args = rest.split()
        if name in ("q", "q!", "quit", "exit", "wq"):
            return "quit"
        if name in ("help", "h", "?"):
            return "help"
        if name == "new":
            self.start_new()
        elif name == "reset":
            self.machine = Enigma()
            self.notice  = "Machine reset to defaults."
        elif name == "show":
            self.notice = self._fmt_summary()
        elif name in COMMANDS:
            try:
                self._configure(name, args)
                self.notice = self._fmt_summary()
            except (ValueError, IndexError) as e:
                self.notice = (f"{e}   " if isinstance(e, ValueError) else "") + f"usage: :{name}"
        elif name:
            self.notice = f"Unknown command {cmd!r}  (? for help)"
        return None

    def _configure(self, name, args):   # noqa: C901
        m = self.machine

        def need(n):
            if len(args) < n:
                raise IndexError

        def pick_letter(v):
            v = v.upper()
            if v not in ALPHA:
                raise ValueError(f"expected A-Z, got {v!r}")
            return v

        def pick_ring(v):
            try:
                n = int(v)
            except ValueError:
                n = ALPHA.index(v.upper()) + 1 if v.upper() in ALPHA else -1
            if not (1 <= n <= 26):
                raise ValueError(f"ring must be 1-26 or A-Z, got {v!r}")
            return n

        if name == "rotors":
            need(3)
            for v in args[:3]:
                if v.upper() not in ROTOR_CHOICES:
                    raise ValueError(f"unknown rotor {v!r}; choices: {', '.join(ROTOR_CHOICES)}")
            rings = (m.left.ring_setting, m.middle.ring_setting, m.right.ring_setting)
            pos   = (m.left.position_letter, m.middle.position_letter, m.right.position_letter)
            m.left   = Rotor(args[0].upper(), rings[0], pos[0])
            m.middle = Rotor(args[1].upper(), rings[1], pos[1])
            m.right  = Rotor(args[2].upper(), rings[2], pos[2])

        elif name == "ring":
            need(3)
            vals = [pick_ring(v) for v in args[:3]]
            m.left.ring_setting, m.middle.ring_setting, m.right.ring_setting = vals

        elif name == "pos":
            s = "".join(args).upper()
            if len(s) < 3:
                raise IndexError
            m.left.position   = ALPHA.index(pick_letter(s[0]))
            m.middle.position = ALPHA.index(pick_letter(s[1]))
            m.right.position  = ALPHA.index(pick_letter(s[2]))

        elif name == "refl":
            need(1)
            kind = next((r for r in REFLECTOR_CHOICES if r.lower() == args[0].lower()), None)
            if kind is None:
                raise ValueError(f"choices: {', '.join(REFLECTOR_CHOICES)}")
            m.reflector_kind = kind
            m.reflector = Reflector(kind, m.custom_reflector_pairs)
            if kind in THIN_REFLECTORS and not m.fourth:
                m.fourth = FourthWheel("Beta")
            elif kind not in THIN_REFLECTORS:
                m.fourth = None

        elif name == "wheel":
            if not m.fourth:
                raise ValueError("no 4th wheel active; use :refl B-thin first")
            need(1)
            wn = args[0].title()
            if wn not in FOURTH_WHEEL_CHOICES:
                raise ValueError(f"choices: {', '.join(FOURTH_WHEEL_CHOICES)}")
            m.fourth = FourthWheel(wn)

        elif name == "etw":
            need(1)
            em = args[0].lower()
            if em not in ETW_CHOICES:
                raise ValueError(f"choices: {', '.join(ETW_CHOICES)}")
            m.etw = EntryWheel(em)

        elif name == "ukw":
            need(1)
            ok, res = parse_reflector_pairs(" ".join(args).upper())
            if not ok:
                raise ValueError(res)
            m.custom_reflector_pairs = res
            m.reflector_kind = "Custom"
            m.reflector = Reflector("Custom", res)

        elif name == "plug":
            self._configure_plug(args)

        else:
            raise ValueError(f"unknown command {name!r}")

    def _configure_plug(self, args):
        m = self.machine
        if not args:
            raise ValueError
        sub  = args[0].lower()
        toks = [a.upper() for a in args[1:]]
        if sub == "on":
            m.plugboard_enabled = True
        elif sub == "off":
            m.plugboard_enabled = False
        elif sub == "clear":
            m.plugboard = Plugboard(None)
        elif sub == "add":
            if not toks:
                raise ValueError("add requires at least one pair")
            current = ["".join(sorted(p)) for p in m.plugboard.pairs_list()] + toks
            ok, res = parse_plug_pairs(" ".join(current))
            if not ok:
                raise ValueError(res)
            m.plugboard = Plugboard(res)
        elif sub == "remove":
            if not toks:
                raise ValueError("remove requires a pair or single letter")
            current = ["".join(sorted(p)) for p in m.plugboard.pairs_list()]
            for tok in toks:
                hit = [p for p in current
                       if (tok in p if len(tok) == 1 else set(p) == set(tok))]
                if not hit:
                    raise ValueError(f"cable {tok!r} not in plugboard")
                current.remove(hit[0])
            ok, res = parse_plug_pairs(" ".join(current))
            if not ok:
                raise ValueError(res)
            m.plugboard = Plugboard(res)
        else:
            raise ValueError(f"unknown sub-command {sub!r}; choices: {', '.join(PLUG_SUBS)}")

    def _tab_complete(self):
        words = self.cmd.split(" ")
        part, prev = words[-1], [w.lower() for w in words[:-1]]
        if not prev:
            opts = COMMANDS
        elif len(prev) == 1:
            opts = {
                "plug":  PLUG_SUBS,
                "refl":  REFLECTOR_CHOICES,
                "etw":   ETW_CHOICES,
                "wheel": FOURTH_WHEEL_CHOICES,
            }.get(prev[0], ())
        else:
            opts = ()
        hits = [o for o in opts if o.lower().startswith(part.lower())]
        if not hits:
            return
        new = hits[0] + " " if len(hits) == 1 else os.path.commonprefix(hits)
        if len(hits) > 1:
            self.notice = "  ".join(hits)
        if len(new) >= len(part):
            self.cmd = " ".join(words[:-1] + [new])

    def _fmt_summary(self):
        m = self.machine
        rotors = " ".join(w.name for w in (m.left, m.middle, m.right))
        rings  = "/".join(f"{w.ring_setting:02d}" for w in (m.left, m.middle, m.right))
        pos    = "/".join(w.position_letter for w in (m.left, m.middle, m.right))
        fourth = f"  4th={m.fourth.name}" if m.fourth else ""
        if m.plugboard_enabled:
            pairs = m.plugboard.pairs_list()
            plug  = ("on: " + " ".join(f"{a}{b}" for a, b in pairs)) if pairs else "on (no cables)"
        else:
            plug = "off"
        return (
            f"UKW {m.reflector_kind}{fourth}  etw {m.etw.mode}  "
            f"rotors {rotors}  ring {rings}  pos {pos}  plug {plug}"
        )


def safe_addstr(win, y, x, text, attr=0):
    h, w = win.getmaxyx()
    if y < 0 or y >= h or x >= w or x < 0:
        return
    try:
        win.addstr(y, x, text[: max(0, w - x - 1)], attr)
    except curses.error:
        pass


def draw_box(win, y, x, h, w, title="", attr=0):
    safe_addstr(win, y, x, "+" + "-" * (w - 2) + "+", attr)
    for i in range(1, h - 1):
        safe_addstr(win, y + i, x, "|", attr)
        safe_addstr(win, y + i, x + w - 1, "|", attr)
    safe_addstr(win, y + h - 1, x, "+" + "-" * (w - 2) + "+", attr)
    if title:
        safe_addstr(win, y, x + 2, f" {title} ", attr | curses.A_BOLD)


def init_colors():
    curses.start_color()
    try:
        curses.use_default_colors()
        bg = -1
    except curses.error:
        bg = curses.COLOR_BLACK
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)   # pressed key
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_YELLOW)  # lit lamp
    curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_BLUE)    # title bar
    curses.init_pair(4, curses.COLOR_CYAN, bg)                    # box borders
    curses.init_pair(5, curses.COLOR_GREEN, bg)                   # signal path
    curses.init_pair(6, curses.COLOR_WHITE, curses.COLOR_RED)     # errors
    curses.init_pair(7, curses.COLOR_MAGENTA, bg)                 # plugboard


def draw_keyrow(win, y, x0, row, indent, highlight_letter, attr_on, attr_off):
    x = x0 + indent * 2
    for ch in row:
        attr = attr_on if ch == highlight_letter else attr_off
        safe_addstr(win, y, x, f"[{ch}]", attr)
        x += 4


def draw_wheel_panel(win, y, x, label, wheel, attr_border, attr_val):
    draw_box(win, y, x, 7, 14, label, attr_border)
    safe_addstr(win, y + 1, x + 2, f"Type:{wheel.name:<5}")
    safe_addstr(win, y + 2, x + 2, f"Ring:{wheel.ring_setting:02d}")
    eff = ALPHA[(wheel.position - (wheel.ring_setting - 1)) % 26]
    safe_addstr(win, y + 3, x + 2, f"Eff :{eff}")
    safe_addstr(win, y + 5, x + 4, f" {wheel.position_letter} ", attr_val | curses.A_BOLD)


def group5(s):
    return " ".join(s[i:i + 5] for i in range(0, len(s), 5))


def draw_all(stdscr, machine, state):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    if h < 34 or w < 108:
        safe_addstr(stdscr, 0, 0,
                    f"Terminal too small ({w}x{h}). Please resize to at least 108x34.")
        stdscr.refresh()
        return

    c_title = curses.color_pair(3)
    c_press = curses.color_pair(1) | curses.A_BOLD
    c_lamp = curses.color_pair(2) | curses.A_BOLD
    c_dim = curses.A_DIM
    c_border = curses.color_pair(4)
    c_sig = curses.color_pair(5)
    c_plug = curses.color_pair(7)

    safe_addstr(stdscr, 0, 0, " " * w, c_title)
    safe_addstr(stdscr, 0, 2, "T E R M I G M A  -  Interactive Enigma TUI", c_title | curses.A_BOLD)
    safe_addstr(stdscr, 0, w - 16, "F1 Help  ESC Quit", c_title)

    ry = 2
    draw_box(stdscr, ry, 2, 10, 60, "ROTORS", c_border)
    safe_addstr(stdscr, ry + 1, 4,
                f"Reflector: {machine.reflector_kind:<8}  ETW: {machine.etw.mode:<10}"
                f"Plugboard: {'ON' if machine.plugboard_enabled else 'OFF'}")
    row = ry + 2
    cols = []
    if machine.fourth:
        cols.append(("4TH", machine.fourth))
    cols += [("LEFT", machine.left), ("MID", machine.middle), ("RIGHT", machine.right)]
    for i, (label, wheel) in enumerate(cols):
        draw_wheel_panel(stdscr, row, 4 + i * 14, label, wheel, c_border, c_lamp)

    ky = 13
    draw_box(stdscr, ky, 2, 6, 46, "KEYBOARD (type A-Z)", c_border)
    pressed = state.get("last_key")
    for i, krow in enumerate(KB_ROWS):
        draw_keyrow(stdscr, ky + 1 + i, 4, krow, KB_INDENT[i], pressed, c_press, 0)

    ly = 20
    draw_box(stdscr, ly, 2, 6, 46, "LAMPBOARD (lit letter)", c_border)
    lit = state.get("last_out")
    for i, krow in enumerate(KB_ROWS):
        draw_keyrow(stdscr, ly + 1 + i, 4, krow, KB_INDENT[i], lit, c_lamp, c_dim)

    pby = 27
    draw_box(stdscr, pby, 2, 4, 46, "PLUGBOARD (F3 edit, F2 on/off)", c_border)
    if not machine.plugboard_enabled:
        safe_addstr(stdscr, pby + 1, 4, "DISABLED for this model", c_dim)
    else:
        pairs = machine.plugboard.pairs_list()
        ptxt = " ".join(f"{a}{b}" for a, b in pairs) if pairs else "(none)"
        safe_addstr(stdscr, pby + 1, 4, ptxt[:42], c_plug)
        safe_addstr(stdscr, pby + 2, 4, f"{len(pairs)}/{MAX_PLUGS} pairs used", c_dim)

    sx = 64
    sig_h = min(21, h - 3)
    draw_box(stdscr, 2, sx, sig_h, max(30, w - sx - 2), "SIGNAL PATH (this keypress)", c_border)
    path = state.get("last_path")
    if not path:
        safe_addstr(stdscr, 4, sx + 3, "Press a letter key to see the current flow", c_dim)
        safe_addstr(stdscr, 5, sx + 3, "through plugboard -> ETW -> rotors ->", c_dim)
        safe_addstr(stdscr, 6, sx + 3, "reflector -> rotors -> ETW -> plugboard -> lamp.", c_dim)
    else:
        for i, (label, val) in enumerate(path):
            r = 4 + i
            if r >= 2 + sig_h - 1:
                break
            safe_addstr(stdscr, r, sx + 3, f"{label:<24}", c_sig)
            safe_addstr(stdscr, r, sx + 29, val, c_lamp)

    logy = 2 + sig_h + 1
    draw_box(stdscr, logy, sx, 9, max(30, w - sx - 2), "MESSAGE LOG", c_border)
    plain = "".join(p for p, _ in state["log"])
    cipher = "".join(cp for _, cp in state["log"])
    inner_w = max(10, w - sx - 6)
    safe_addstr(stdscr, logy + 1, sx + 3, "Plain :")
    safe_addstr(stdscr, logy + 2, sx + 3, group5(plain)[-inner_w:])
    safe_addstr(stdscr, logy + 4, sx + 3, "Cipher:")
    safe_addstr(stdscr, logy + 5, sx + 3, group5(cipher)[-inner_w:], curses.A_BOLD)
    letters_only = sum(1 for p, _ in state["log"] if p != "/")
    safe_addstr(stdscr, logy + 7, sx + 3,
                f"Count: {letters_only}   Last input: {pressed or '-'}", c_dim)

    fy = h - 2
    safe_addstr(stdscr, fy, 0, "-" * w, c_dim)
    safe_addstr(stdscr, fy + 1, 2,
                "F1 Help  F2 Settings  F3 Plugboard  F4 Reset  F5 Custom UKW  ESC Quit")
    stdscr.refresh()


def flash_error(stdscr, msg):
    h, w = stdscr.getmaxyx()
    y = min(h - 4, 32)
    safe_addstr(stdscr, y, 2, " " * min(len(msg) + 4, max(1, w - 4)))
    safe_addstr(stdscr, y, 2, f" {msg} ", curses.color_pair(6) | curses.A_BOLD)
    stdscr.refresh()
    curses.napms(1200)


def draw_help(stdscr):
    stdscr.erase()
    lines = [
        "TERMIGMA - HELP",
        "",
        "Simulates the Wehrmacht/Kriegsmarine Enigma family: Enigma I (3 rotors",
        "from I-V), M3 (3 rotors from I-VIII), and M4 'Shark' (3 rotors from",
        "I-VIII plus a non-stepping Beta/Gamma 4th wheel and a thin reflector).",
        "",
        "Type a letter A-Z to encipher it; the SIGNAL PATH panel shows every",
        "stage: plugboard -> entry wheel (ETW) -> 3 (or 4) rotors -> reflector",
        "-> back through the rotors -> ETW -> plugboard -> lamp.",
        "",
        "Rotors step automatically every keypress (including the middle-rotor",
        "double-step) and this cannot be undone, exactly like the real machine.",
        "",
        "Controls:",
        "  A-Z    encipher a letter          SPACE  visual separator only",
        "  F2     settings: model preset, ETW (military/commercial), plugboard",
        "         on/off, reflector (B/C/B-thin/C-thin/Custom), movable notches,",
        "         4th wheel (when a thin reflector is chosen), and all 3 rotors",
        "         (type / ring / start position). UP/DOWN move, LEFT/RIGHT",
        "         change, ENTER apply, ESC cancel.",
        "  F3     plugboard editor - pairs like 'AB CD EF', up to 13 pairs",
        "  F5     custom (rewirable) reflector editor - needs exactly 13 pairs",
        "         covering all 26 letters (only used when Reflector = Custom)",
        "  F4     reset to default settings          ESC  quit",
        "",
        "Note: exact wirings for the more exotic commercial/national variants",
        "(K, D, Swiss-K, Railway, Tirpitz, Norenigma, Sonder, Abwehr G-machines)",
        "are not included - see data/wiring_tables.json for why. The",
        "'commercial-style' preset demonstrates the real QWERTZU entry wiring",
        "and no-plugboard quirk of commercial machines using the Enigma I",
        "rotor set as a stand-in.",
        "",
        "Press any key to return...",
    ]
    for i, line in enumerate(lines):
        safe_addstr(stdscr, 1 + i, 4, line)
    stdscr.refresh()
    stdscr.getch()


def draw_rotor_settings(stdscr, settings, active_field, field_order):
    stdscr.erase()
    safe_addstr(stdscr, 1, 2, "SETTINGS", curses.A_BOLD)
    safe_addstr(stdscr, 2, 2, "UP/DOWN move   LEFT/RIGHT change   ENTER apply   ESC cancel")
    for i, field in enumerate(field_order):
        y = 4 + i
        attr = curses.A_REVERSE if field == active_field else 0
        label = FIELD_LABEL[field]
        val = fmt_val(settings[field])
        safe_addstr(stdscr, y, 4, f"{label:<20}: < {val:<30} >", attr)
    safe_addstr(stdscr, 5 + len(field_order), 4,
                "Note: the three main rotors must all be different types.")
    stdscr.refresh()


def rotor_settings_screen(stdscr, machine):
    settings = {
        "model": "Custom",
        "etw": machine.etw.mode,
        "plugboard_enabled": machine.plugboard_enabled,
        "movable_notches": machine.movable_notches,
        "reflector": machine.reflector_kind,
        "L_type": machine.left.name, "L_ring": machine.left.ring_setting, "L_pos": machine.left.position_letter,
        "M_type": machine.middle.name, "M_ring": machine.middle.ring_setting, "M_pos": machine.middle.position_letter,
        "R_type": machine.right.name, "R_ring": machine.right.ring_setting, "R_pos": machine.right.position_letter,
        "G_type": machine.fourth.name if machine.fourth else "Beta",
        "G_ring": machine.fourth.ring_setting if machine.fourth else 1,
        "G_pos": machine.fourth.position_letter if machine.fourth else "A",
    }
    if machine.movable_notches:
        settings["L_notch"] = sorted(machine.left.notches)[0]
        settings["M_notch"] = sorted(machine.middle.notches)[0]
        settings["R_notch"] = sorted(machine.right.notches)[0]
    else:
        from .engine import ROTOR_DATA
        settings["L_notch"] = sorted(ROTOR_DATA[settings["L_type"]]["notches"])[0]
        settings["M_notch"] = sorted(ROTOR_DATA[settings["M_type"]]["notches"])[0]
        settings["R_notch"] = sorted(ROTOR_DATA[settings["R_type"]]["notches"])[0]

    idx = 0
    while True:
        field_order = build_field_order(settings)
        idx = idx % len(field_order)
        draw_rotor_settings(stdscr, settings, field_order[idx], field_order)
        ch = stdscr.getch()
        if ch == 27:
            return
        elif ch in (10, 13, curses.KEY_ENTER):
            types = [settings["L_type"], settings["M_type"], settings["R_type"]]
            if len(set(types)) < 3:
                flash_error(stdscr, "The three main rotors must be different!")
                continue
            notch_over = (None, None, None)
            if settings["movable_notches"]:
                notch_over = (settings["L_notch"], settings["M_notch"], settings["R_notch"])
            machine.left = Rotor(settings["L_type"], settings["L_ring"], settings["L_pos"], notch_over[0])
            machine.middle = Rotor(settings["M_type"], settings["M_ring"], settings["M_pos"], notch_over[1])
            machine.right = Rotor(settings["R_type"], settings["R_ring"], settings["R_pos"], notch_over[2])
            machine.reflector_kind = settings["reflector"]
            machine.reflector = Reflector(settings["reflector"], machine.custom_reflector_pairs)
            from .engine import EntryWheel
            machine.etw = EntryWheel(settings["etw"])
            machine.plugboard_enabled = settings["plugboard_enabled"]
            machine.movable_notches = settings["movable_notches"]
            if settings["reflector"] in THIN_REFLECTORS:
                machine.fourth = FourthWheel(settings["G_type"], settings["G_ring"], settings["G_pos"])
            else:
                machine.fourth = None
            return
        elif ch == curses.KEY_UP:
            idx = (idx - 1) % len(field_order)
        elif ch == curses.KEY_DOWN:
            idx = (idx + 1) % len(field_order)
        elif ch == curses.KEY_LEFT:
            adjust_field(settings, field_order[idx], -1)
        elif ch == curses.KEY_RIGHT:
            adjust_field(settings, field_order[idx], 1)


def draw_plugboard_editor(stdscr, buf):
    stdscr.erase()
    safe_addstr(stdscr, 1, 2, "PLUGBOARD EDITOR", curses.A_BOLD)
    safe_addstr(stdscr, 3, 2, "Type letter pairs separated by spaces, e.g.:  AB CD EF")
    safe_addstr(stdscr, 4, 2, f"(max {MAX_PLUGS} pairs, each letter used at most once)")
    safe_addstr(stdscr, 6, 2, "> " + buf, curses.A_REVERSE)
    safe_addstr(stdscr, 8, 2, "ENTER: apply   ESC: cancel   BACKSPACE: delete")
    stdscr.refresh()


def plugboard_screen(stdscr, machine):
    if not machine.plugboard_enabled:
        flash_error(stdscr, "This model's plugboard is off - enable it in F2 first.")
        return
    buf = " ".join(f"{a}{b}" for a, b in machine.plugboard.pairs_list())
    curses.curs_set(1)
    while True:
        draw_plugboard_editor(stdscr, buf)
        ch = stdscr.getch()
        if ch == 27:
            break
        elif ch in (10, 13, curses.KEY_ENTER):
            ok, result = parse_plug_pairs(buf.upper())
            if ok:
                machine.plugboard = Plugboard(result)
                break
            else:
                flash_error(stdscr, result)
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            buf = buf[:-1]
        elif 32 <= ch < 127:
            c = chr(ch).upper()
            if c.isalpha() or c == " ":
                if len(buf) < 45:
                    buf += c
    curses.curs_set(0)


def draw_reflector_editor(stdscr, buf):
    stdscr.erase()
    safe_addstr(stdscr, 1, 2, "CUSTOM REFLECTOR EDITOR (rewirable, like UKW-D)", curses.A_BOLD)
    safe_addstr(stdscr, 3, 2, "Type exactly 13 pairs covering all 26 letters, e.g.:")
    safe_addstr(stdscr, 4, 2, "AB CD EF GH IJ KL MN OP QR ST UV WX YZ")
    safe_addstr(stdscr, 6, 2, "> " + buf, curses.A_REVERSE)
    safe_addstr(stdscr, 8, 2, "ENTER: apply   ESC: cancel   BACKSPACE: delete")
    stdscr.refresh()


def custom_reflector_screen(stdscr, machine):
    if machine.reflector_kind != "Custom":
        flash_error(stdscr, "Set Reflector to 'Custom' in F2 settings first.")
        return
    buf = " ".join(f"{a}{b}" for a, b in sorted(machine.custom_reflector_pairs.items()) if a < b)
    curses.curs_set(1)
    while True:
        draw_reflector_editor(stdscr, buf)
        ch = stdscr.getch()
        if ch == 27:
            break
        elif ch in (10, 13, curses.KEY_ENTER):
            ok, result = parse_reflector_pairs(buf.upper())
            if ok:
                machine.custom_reflector_pairs = result
                machine.reflector = Reflector("Custom", result)
                break
            else:
                flash_error(stdscr, result)
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            buf = buf[:-1]
        elif 32 <= ch < 127:
            c = chr(ch).upper()
            if c.isalpha() or c == " ":
                if len(buf) < 60:
                    buf += c
    curses.curs_set(0)


def _fmt_config(machine):
    """Return a human-readable block summarising the current machine settings."""
    lines = [
        "  Reflector  : " + machine.reflector_kind,
        "  ETW        : " + (
            "military (straight-through)" if machine.etw.mode == "military"
            else "commercial (QWERTZU)"
        ),
    ]
    wheels = []
    if machine.fourth:
        wheels.append(("4th (fixed)", machine.fourth))
    for label, w in (("Left", machine.left), ("Middle", machine.middle), ("Right", machine.right)):
        wheels.append((label, w))
    for label, w in wheels:
        lines.append(f"  {label:<12}: {w.name}  ring {w.ring_setting:02d}  start {w.position_letter}")
    if machine.plugboard_enabled:
        pairs = machine.plugboard.pairs_list()
        plug_str = " ".join(f"{a}{b}" for a, b in pairs) if pairs else "(none)"
        lines.append(f"  Plugboard  : {plug_str}")
    else:
        lines.append("  Plugboard  : disabled")
    return "\n".join(lines)


def run(stdscr, out):
    """Run the TUI.  Populates *out* with session data before returning."""
    curses.curs_set(0)
    stdscr.keypad(True)
    init_colors()

    machine = Enigma()
    state = {
        "log": [],
        "last_path": [],
        "last_key": None,
        "last_out": None,
        # Stack of rotor-position snapshots, one entry pushed *before* each
        # letter keypress.  On backspace we pop the top snapshot and restore
        # the machine to the state it was in before that letter was typed,
        # which is how the real Enigma would behave if you could rewind it.
        "position_stack": [],
    }

    while True:
        draw_all(stdscr, machine, state)
        ch = stdscr.getch()

        if ch == 27:   # ESC
            break
        elif ch == curses.KEY_F1:
            draw_help(stdscr)
        elif ch == curses.KEY_F2:
            rotor_settings_screen(stdscr, machine)
        elif ch == curses.KEY_F3:
            plugboard_screen(stdscr, machine)
        elif ch == curses.KEY_F4:
            machine = Enigma()
            state = {"log": [], "last_path": [], "last_key": None, "last_out": None}
        elif ch == curses.KEY_F5:
            custom_reflector_screen(stdscr, machine)
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            # Walk the last log entry back.  Spaces don't move the rotors, so
            # only letter entries have a matching position snapshot to restore.
            if state["log"]:
                last_plain, _ = state["log"][-1]
                state["log"].pop()
                if last_plain != "/":
                    # Restore the exact rotor positions that existed before
                    # that keypress — including any carries or double-steps
                    # that occurred — so the next letter typed enciphers as
                    # though the deleted letter was never pressed.
                    if state["position_stack"]:
                        machine.set_positions(state["position_stack"].pop())
                state["last_key"] = None
                state["last_out"] = None
                state["last_path"] = []
        elif ch == 32:
            state["log"].append(("/", "/"))
            state["last_key"] = None
            state["last_out"] = None
        elif 65 <= ch <= 90 or 97 <= ch <= 122:
            letter = chr(ch).upper()
            # Save positions *before* the step so backspace can undo exactly.
            state["position_stack"].append(machine.get_positions())
            out, path = machine.encode_letter(letter)
            state["last_key"] = letter
            state["last_out"] = out
            state["last_path"] = path
            state["log"].append((letter, out))
            if len(state["log"]) > 500:
                state["log"] = state["log"][-500:]
                state["position_stack"] = state["position_stack"][-500:]

    # Populate the summary so main() can print it after curses closes.
    plain = "".join(p for p, _ in state["log"] if p != "/")
    cipher = "".join(c for _, c in state["log"] if c != "/")
    out["config"] = _fmt_config(machine)
    out["plain"] = plain
    out["cipher"] = cipher


def main():
    out = {}
    curses.wrapper(run, out)
    if not out:
        return
    plain = out["plain"]
    cipher = out["cipher"]
    if not plain:
        return
    sep = "-" * 60
    print()
    print(sep)
    print("CONFIGURATION")
    print(out["config"])
    print(sep)
    print(f"  Plaintext  ({len(plain):>4} letters): {plain}")
    print(f"  Ciphertext ({len(cipher):>4} letters): {cipher}")
    print(sep)


if __name__ == "__main__":
    main()
