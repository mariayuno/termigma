"""Curses front-end for the termigma Enigma engine. All model logic lives
in engine.py; this module only draws things and reads the keyboard."""

import curses
import os

from .engine import (
    ALPHA, KB_ROWS, KB_INDENT, MAX_PLUGS, THIN_REFLECTORS,
    ROTOR_CHOICES, FOURTH_WHEEL_CHOICES, REFLECTOR_CHOICES, ETW_CHOICES, MODEL_ALIASES,
    Rotor, FourthWheel, EntryWheel, Reflector, Plugboard, Enigma,
    parse_plug_pairs, parse_reflector_pairs, apply_model,
)

PLUG_SUBS   = ("add", "remove", "clear", "on", "off")

CANCEL_KEYS    = frozenset({27, ord("`")})
BACKSPACE_KEYS = frozenset({curses.KEY_BACKSPACE, 127, 8})
ARROWS = {curses.KEY_LEFT: "h", curses.KEY_RIGHT: "l",
          curses.KEY_HOME: "0", curses.KEY_END: "$"}

COMMANDS = (
    "model", "plug", "refl", "etw", "rotors", "ring", "pos", "wheel",
    "ukw", "ukwpos", "ukwring", "lock", "live", "show", "reset", "new", "help", "q", "q!",
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

    def __init__(self, machine=None):
        self.machine  = machine if machine is not None else Enigma()
        self.msg      = Message()
        self.finished: list = []   # snapshots of messages closed with :new
        self.mode     = "INSERT"
        self.anchor   = 0          # VISUAL mode: the stationary end
        self.cmd      = ""         # COMMAND mode: buffer being typed
        self.pending  = ""         # NORMAL: first key of dd / yy digraph
        self.reg      = ""         # yank register
        self.notice   = ""         # one-line message above the status bar
        self.live     = False      # show live vertical trace panel

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
        elif c == "t":
            self.live = not self.live
            self.notice = ("Live trace ON  (t to toggle)"
                           if self.live else "Live trace OFF  (t to toggle)")
        elif c == ":live" or c == "?":
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

        def locked(what):
            raise ValueError(
                f":{what} is not available on a locked model; use :model custom to unlock"
            )

        if name == "model":
            need(1)
            key = args[0].lower()
            if key not in MODEL_ALIASES:
                raise ValueError(f"unknown model {args[0]!r}; choices: {', '.join(MODEL_ALIASES)}")
            apply_model(m, key)
            return  # summary already shows the new model

        elif name == "rotors":
            if m.model_locked:
                locked("rotors")
            need(3)
            for v in args[:3]:
                if v.upper() not in ROTOR_CHOICES:
                    raise ValueError(f"unknown rotor {v!r}")
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
            if m.model_locked:
                locked("refl")
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
            if m.model_locked:
                locked("etw")
            need(1)
            em = args[0].lower()
            if em not in ETW_CHOICES:
                raise ValueError(f"choices: {', '.join(ETW_CHOICES)}")
            m.etw = EntryWheel(em)

        elif name == "ukwpos":
            if not m.refl_thumb:
                raise ValueError("this model's UKW is not settable; use :model t|a28|g111|g260|g312")
            need(1)
            m.reflector.pos = ALPHA.index(pick_letter(args[0]))

        elif name == "ukwring":
            if not m.refl_thumb:
                raise ValueError("this model's UKW is not settable; use :model t|a28|g111|g260|g312")
            need(1)
            m.reflector.ring_setting = pick_ring(args[0])

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

    def _lock(self, args):
        """Toggle or clear wheel locks.  :lock L|M|R|UKW toggles; :lock off clears all."""
        m = self.machine
        if not args:
            raise ValueError("usage: :lock L|M|R|UKW  or  :lock off")
        tok = args[0].upper()
        if tok == "OFF":
            m.locked.clear()
            self.notice = "All wheels unlocked."
            return
        if tok not in ("L", "M", "R", "UKW"):
            raise ValueError("choices: L  M  R  UKW  off")
        if tok == "UKW" and not m.refl_rotating:
            raise ValueError("UKW lock only applies to rotating-reflector models (G-series)")
        m.locked.symmetric_difference_update({tok})
        state = "locked" if tok in m.locked else "unlocked"
        self.notice = f"Rotor {tok} {state}."

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
                "model": MODEL_ALIASES,
                "plug":  PLUG_SUBS,
                "refl":  REFLECTOR_CHOICES,
                "etw":   ETW_CHOICES,
                "wheel": FOURTH_WHEEL_CHOICES,
                "lock":  ("L", "M", "R", "UKW", "off"),
            }.get(prev[0], ())
        else:
            opts = ()
        hits = [o for o in opts if o.lower().startswith(part.lower())]
        if not hits:
            return
        new = hits[0] + " " if len(hits) == 1 else os.path.commonprefix(hits)
        if len(hits) > 1:
            if prev and prev[0] == "model":
                from .engine import MODELS as _M
                self.notice = "  ".join(
                    f"{o}={_M[o]['label']}" if o in _M else o for o in hits
                )
            else:
                self.notice = "  ".join(hits)
        if len(new) >= len(part):
            self.cmd = " ".join(words[:-1] + [new])

    def _fmt_summary(self):
        m = self.machine
        rotors = " ".join(w.label for w in (m.left, m.middle, m.right))
        rings  = "/".join(f"{w.ring_setting:02d}" for w in (m.left, m.middle, m.right))
        pos    = "/".join(w.position_letter for w in (m.left, m.middle, m.right))
        fourth = f"  4th={m.fourth.name}" if m.fourth else ""
        ukw_extra = ""
        if m.refl_thumb:
            ukw_extra = f" pos={m.reflector.position_letter} ring={m.reflector.ring_setting:02d}"
        if m.plugboard_enabled:
            pairs = m.plugboard.pairs_list()
            plug  = ("on: " + " ".join(f"{a}{b}" for a, b in pairs)) if pairs else "on (no cables)"
        else:
            plug = "off"
        model_tag = f"[{m.model_label}]  " if m.model_label != "Custom" else ""
        lock_str = ("  locked " + " ".join(sorted(m.locked))) if m.locked else ""
        return (
            f"{model_tag}UKW {m.reflector.label}{ukw_extra}{fourth}  "
            f"etw {m.etw.mode}  rotors {rotors}  ring {rings}  pos {pos}  plug {plug}{lock_str}"
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


def draw_text_line(win, y, x, n, text, start, cur, sel, attr, cur_attr):
    """Render one scrolled line of the message with cursor and selection."""
    safe_addstr(win, y, x, text[start:start + n], attr)
    if sel:
        a = max(sel[0], start)
        b = min(sel[1], start + n)
        if a < b:
            safe_addstr(win, y, x + a - start, text[a:b], attr | curses.A_REVERSE)
    if start <= cur < start + n:
        ch = text[cur] if cur < len(text) else " "
        safe_addstr(win, y, x + cur - start, ch, cur_attr)


def draw_all(stdscr, session):
    """Redraw the whole screen from the current Session state."""
    v = session.view()
    stdscr.erase()
    h, w = stdscr.getmaxyx()

    if h < 34 or w < 108:
        safe_addstr(stdscr, 0, 0,
                    f"Terminal too small ({w}x{h}). Please resize to at least 108x34.")
        stdscr.refresh()
        return

    c_title = curses.color_pair(3)
    c_press  = curses.color_pair(1) | curses.A_BOLD
    c_lamp   = curses.color_pair(2) | curses.A_BOLD
    c_dim    = curses.A_DIM
    c_border = curses.color_pair(4)
    c_sig    = curses.color_pair(5)
    c_plug   = curses.color_pair(7)

    machine = session.machine

    # title bar
    safe_addstr(stdscr, 0, 0, " " * w, c_title)
    safe_addstr(stdscr, 0, 2, "E N I G M A  -  Interactive TUI Simulator",
                c_title | curses.A_BOLD)
    safe_addstr(stdscr, 0, w - 16, ":q quit   ? help", c_title)

    # rotor panel
    ry = 2
    model_tag = f"  [{machine.model_label}]" if machine.model_label != "Custom" else ""
    panel_title = f"ROTORS{model_tag}"
    draw_box(stdscr, ry, 2, 11, 60, panel_title, c_border)
    ukw_label = machine.reflector.label
    ukw_extra = ""
    if machine.refl_thumb:
        ukw_extra = (f" pos={machine.reflector.position_letter}"
                     f" ring={machine.reflector.ring_setting:02d}"
                     f"{'  rotating' if machine.refl_rotating else ''}")
    mech_tag = "  cog drive" if machine.mechanism == "cog" else ""
    safe_addstr(stdscr, ry + 1, 4,
                f"UKW: {ukw_label}{ukw_extra:<18}"
                f"ETW: {machine.etw.mode:<14}"
                f"Plug: {'on' if machine.plugboard_enabled else 'off'}{mech_tag}")
    _lock_key = {"LEFT": "L", "MID": "M", "RIGHT": "R"}
    cols = []
    if machine.fourth:
        cols.append(("4TH", machine.fourth, machine.fourth.position))
    for lb, wh in zip(("LEFT", "MID", "RIGHT"),
                       (machine.left, machine.middle, machine.right)):
        pos = {"LEFT": v["pos"][0], "MID": v["pos"][1], "RIGHT": v["pos"][2]}[lb]
        cols.append((lb, wh, pos))
    for i, (label, wheel, pos) in enumerate(cols):
        disp = label + ("*" if _lock_key.get(label) in machine.locked else "")
        draw_wheel_panel(stdscr, ry + 2, 4 + i * 14, disp, wheel, c_border, c_lamp)

    # keyboard
    ky = 13
    draw_box(stdscr, ky, 2, 6, 46, "KEYBOARD", c_border)
    for i, row in enumerate(KB_ROWS):
        draw_keyrow(stdscr, ky + 1 + i, 4, row, KB_INDENT[i], v["key"], c_press, 0)

    # lampboard
    ly = 20
    draw_box(stdscr, ly, 2, 6, 46, "LAMPBOARD", c_border)
    for i, row in enumerate(KB_ROWS):
        draw_keyrow(stdscr, ly + 1 + i, 4, row, KB_INDENT[i], v["out"], c_lamp, c_dim)

    # plugboard summary
    pby = 27
    draw_box(stdscr, pby, 2, 4, 46, "PLUGBOARD (:plug add/remove/clear)", c_border)
    if not machine.plugboard_enabled:
        safe_addstr(stdscr, pby + 1, 4, "DISABLED for this model", c_dim)
    else:
        pairs = machine.plugboard.pairs_list()
        ptxt = " ".join(f"{a}{b}" for a, b in pairs) if pairs else "(no cables)"
        safe_addstr(stdscr, pby + 1, 4, ptxt[:42], c_plug)
        safe_addstr(stdscr, pby + 2, 4, f"{len(pairs)}/{MAX_PLUGS} pairs", c_dim)

    # signal path
    sx = 64
    sig_h = min(21, h - 3)
    draw_box(stdscr, 2, sx, sig_h, max(30, w - sx - 2), "SIGNAL PATH", c_border)
    if not v["path"]:
        safe_addstr(stdscr, 4, sx + 3, "Move the cursor to a letter to see the", c_dim)
        safe_addstr(stdscr, 5, sx + 3, "signal path through plugboard, ETW,", c_dim)
        safe_addstr(stdscr, 6, sx + 3, "rotors, reflector and back.", c_dim)
    else:
        for i, (label, val) in enumerate(v["path"]):
            row = 4 + i
            if row >= 2 + sig_h - 1:
                break
            safe_addstr(stdscr, row, sx + 3, f"{label:<24}", c_sig)
            safe_addstr(stdscr, row, sx + 29, val, c_lamp)

    # live trace panel
    if session.live:
        from .utils import render_trace
        trace_text = session.msg.text.replace(" ", "")
        if trace_text:
            want_color = True
            trace_w = max(30, w - sx - 2)
            ty = 2 + sig_h + 1
            draw_box(stdscr, ty, sx, 12, trace_w, "LIVE TRACE  (t to toggle)", c_border)
            rendered = render_trace(session.machine, trace_text[-20:],
                                    color=False, width=trace_w - 4)
            for ti, tline in enumerate(rendered.split("\n")[:10]):
                safe_addstr(stdscr, ty + 1 + ti, sx + 2, tline[:trace_w - 4], c_sig)
            logy = ty + 13
        else:
            logy = 2 + sig_h + 1
    else:
        logy = 2 + sig_h + 1

    # message area
    draw_box(stdscr, logy, sx, 9, max(30, w - sx - 2), "MESSAGE", c_border)
    t   = session.msg.text
    cur = session.msg.cur
    inner_w = max(10, w - sx - 6)
    start   = max(0, cur - (inner_w - 6))
    sel     = session.selection() if session.mode == "VISUAL" else None
    cur_attr = (curses.A_UNDERLINE if session.mode == "INSERT" else curses.A_REVERSE) | curses.A_BOLD
    disp_plain  = t.replace(" ", "/")
    disp_cipher = v["cipher"].replace(" ", "/")
    safe_addstr(stdscr, logy + 1, sx + 3, "Plain :")
    draw_text_line(stdscr, logy + 2, sx + 3, inner_w, disp_plain, start, cur, sel, 0, cur_attr)
    safe_addstr(stdscr, logy + 4, sx + 3, "Cipher:")
    draw_text_line(stdscr, logy + 5, sx + 3, inner_w, disp_cipher, start, cur, sel,
                   curses.A_BOLD, cur_attr)
    letters = len(t.replace(" ", ""))
    status = f"Letters: {letters}   Cursor: {cur}/{len(t)}"
    if session.finished:
        status += f"   Message #{len(session.finished) + 1}"
    safe_addstr(stdscr, logy + 7, sx + 3, status, c_dim)

    # footer
    fy = h - 2
    if session.notice:
        import textwrap as _tw
        _lines = _tw.wrap(session.notice, max(20, w - 4)) or [session.notice]
        _cap = 3
        if len(_lines) > _cap:
            _lines = _lines[:_cap - 1] + [f"... ({len(_lines) - _cap + 1} more)"]
        for _i, _ln in enumerate(_lines):
            safe_addstr(stdscr, fy - len(_lines) + _i, 2, _ln, curses.A_BOLD)
    safe_addstr(stdscr, fy, 0, "-" * w, c_dim)
    if session.mode == "COMMAND":
        safe_addstr(stdscr, fy + 1, 2, ":" + session.cmd, curses.A_BOLD)
        safe_addstr(stdscr, fy + 1, 3 + len(session.cmd), " ", curses.A_REVERSE)
    else:
        badge = f" {session.mode} "
        safe_addstr(stdscr, fy + 1, 2, badge, c_press)
        safe_addstr(stdscr, fy + 1, 2 + len(badge) + 2,
                    MODE_HINT.get(session.mode, "")[:w - len(badge) - 6], c_dim)
    stdscr.refresh()


def draw_help(stdscr):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    lines = [
        "ENIGMA  -  help  (press any key to return)",
        "",
        "Modes (shown bottom-left in a badge)",
        "  INSERT   Type A-Z / SPACE to encipher at the cursor.",
        "           BACKSPACE deletes the character to the left.",
        "           ESC or ` exits to NORMAL mode.",
        "  NORMAL   Navigate and edit without typing ciphertext.",
        "  VISUAL   Make a selection; act on it with d y c.",
        "  COMMAND  Colon command line.  TAB completes.  ENTER runs.  ESC cancels.",
        "",
        "NORMAL mode keys",
        "  h l         move left / right one character",
        "  0 $         jump to start / end of message",
        "  w b         jump forward / backward one word",
        "  i a         insert before / after cursor    I A  insert at start / end",
        "  x X         delete character under / before cursor",
        "  u           undo last change",
        "  dd          clear the entire message  (u undoes)",
        "  yy          yank (copy) the whole message into the register",
        "  p           paste the register at the cursor",
        "  v           enter VISUAL mode (then use motion keys to select)",
        "  :           open the COMMAND line",
        "  t           toggle live vertical signal trace",
        "  ?           this help screen",
        "",
        "Commands  (TAB completes each word)",
        "  :rotors I II III     choose the three main rotors",
        "  :ring 1 2 3          set ring settings (1-26 or A-Z)",
        "  :pos A A A           set start positions (also: :pos AAA)",
        "  :refl B|C|B-thin|C-thin|Custom    choose reflector",
        "  :wheel Beta|Gamma    choose the 4th wheel (M4, when using a thin reflector)",
        "  :etw military|commercial           choose entry wheel mode",
        "  :ukw AB CD EF ...    set a custom rewirable reflector (13 pairs)",
        "  :plug add AB CD      add plugboard cables",
        "  :plug remove AB      remove a cable (letter or pair)",
        "  :plug clear          remove all cables",
        "  :plug on / off       enable or disable the plugboard",
        "  :show                print current settings in the notice line",
        "  :reset               restore factory defaults",
        "  :new                 start a new message (keeps the current one for the report)",
        "  :q                   quit and print the session report",
        "",
        "Editing anywhere, or changing a setting, re-enciphers the entire message",
        "from the start position automatically.",
    ]
    for i, line in enumerate(lines[:h - 2]):
        safe_addstr(stdscr, 1 + i, 4, line[:w - 8])
    stdscr.refresh()
    stdscr.getch()


# ---------------------------------------------------------------------------
# Exit report
# ---------------------------------------------------------------------------
def _group5(s):
    return " ".join(s[i:i + 5] for i in range(0, len(s), 5))


def _machine_config_block(snap):
    m = snap
    fourth = f"  4th={m['fourth']}" if m["fourth"] else ""
    rotors = " ".join(r[0] for r in m["rotors"])
    rings  = "/".join(f"{r[1]:02d}" for r in m["rotors"])
    pos    = "/".join(r[2] for r in m["rotors"])
    plug   = (("on: " + m["plugs"]) if m["plugboard_on"] and m["plugs"]
              else ("on (no cables)" if m["plugboard_on"] else "off"))
    return [
        f"  Reflector : {m['reflector']}{fourth}",
        f"  ETW       : {m['etw']}",
        f"  Rotors    : {rotors}  (left to right)",
        f"  Ring      : {rings}",
        f"  Pos       : {pos}",
        f"  Plugboard : {plug}",
    ]


def build_exit_report(session):
    """Full session report: config + plain + cipher for every message."""
    cols = 72
    sep  = "=" * cols
    msgs = list(session.finished)
    # Include the current (possibly empty) last message
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
        lines += ["", "CONFIGURATION"] + _machine_config_block(msg["snap"])
        plain  = msg["plain"].replace(" ", "")
        cipher = msg["cipher"].replace(" ", "")
        n_let  = len(plain)
        lines += [
            "",
            f"INPUT   ({n_let} letter{'s' if n_let != 1 else ''})",
            f"  typed  : {msg['plain'] or '(empty)'}",
            f"  groups : {_group5(plain) or '(empty)'}",
            "",
            f"OUTPUT  ({n_let} letter{'s' if n_let != 1 else ''})",
            f"  typed  : {msg['cipher'] or '(empty)'}",
            f"  groups : {_group5(cipher) or '(empty)'}",
        ]
    lines.append("\n" + sep)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main curses loop
# ---------------------------------------------------------------------------
def run(stdscr):
    curses.curs_set(0)
    stdscr.keypad(True)
    init_colors()

    session = Session()

    while True:
        draw_all(stdscr, session)
        ch = stdscr.getch()
        action = session.key(ch)
        if action == "quit":
            break
        if action == "help":
            draw_help(stdscr)


def main(machine=None, live: bool = False) -> None:
    """Start the TUI.

    Parameters
    ----------
    machine : Enigma, optional
        Pre-configured machine from the CLI layer.  When None a default
        machine is created.
    live : bool
        Open with the live signal-trace panel visible.
    """
    from .utils import build_report
    session = Session(machine=machine)
    if live:
        session.live = True
    curses.wrapper(lambda scr: _run_with_session(scr, session))
    report = build_report(session)
    if any(m["plain"] for m in ([{"plain": session.msg.text}] + session.finished)):
        print()
        print(report)


def _run_with_session(stdscr, session):
    curses.curs_set(0)
    stdscr.keypad(True)
    init_colors()
    while True:
        draw_all(stdscr, session)
        ch = stdscr.getch()
        action = session.key(ch)
        if action == "quit":
            break
        if action == "help":
            draw_help(stdscr)
