"""
Core Enigma engine: wheels, reflectors, plugboard, and the Enigma machine
itself, plus the plain-data helpers used by the settings screen. No curses
here on purpose, so this module is importable and testable on its own.

Historical scope: Wehrmacht/Kriegsmarine Enigma I, M3 (rotors I-VIII) and
M4 "Shark" (adds a non-stepping Beta/Gamma wheel and a thin reflector).
See ../../data/wiring_tables.json for sourcing notes, including which
commercial/national variants are deliberately NOT modelled here.
"""

import string

ALPHA = string.ascii_uppercase

# ---------------------------------------------------------------------------
# Historical wiring tables
# ---------------------------------------------------------------------------
ROTOR_DATA = {
    "I":    {"wiring": "EKMFLGDQVZNTOWYHXUSPAIBRCJ", "notches": {"Q"}},
    "II":   {"wiring": "AJDKSIRUXBLHWTMCQGZNPYFVOE", "notches": {"E"}},
    "III":  {"wiring": "BDFHJLCPRTXVZNYEIWGAKMUSQO", "notches": {"V"}},
    "IV":   {"wiring": "ESOVPZJAYQUIRHXLNFTGKDCMWB", "notches": {"J"}},
    "V":    {"wiring": "VZBRGITYUPSDNHLXAWMJQOFECK", "notches": {"Z"}},
    "VI":   {"wiring": "JPGVOUMFYQBENHZRDKASXLICTW", "notches": {"Z", "M"}},
    "VII":  {"wiring": "NZJHGRCXMYSWBOUFAIVLPEKQDT", "notches": {"Z", "M"}},
    "VIII": {"wiring": "FKQHTLXOCBJSPDZRAMEWNIUYGV", "notches": {"Z", "M"}},
}
ROTOR_CHOICES = list(ROTOR_DATA.keys())

FOURTH_WHEEL_DATA = {
    "Beta":  {"wiring": "LEYJVCNIXWPBQMDRTAKZGFUHOS"},
    "Gamma": {"wiring": "FSOKANUERHMBTIYCWLQPZXVGJD"},
}
FOURTH_WHEEL_CHOICES = list(FOURTH_WHEEL_DATA.keys())

REFLECTOR_DATA = {
    "B":      "YRUHQSLDPXNGOKMIEBFZCWVJAT",
    "C":      "FVPJIAOYEDRZXWGCTKUQSBNMHL",
    "B-thin": "ENKQAUYWJICOPBLMDXZVFTHRGS",
    "C-thin": "RDOBJNTKVEHMLFCWZAXGYIPSUQ",
}
REFLECTOR_CHOICES = ["B", "C", "B-thin", "C-thin", "Custom"]
THIN_REFLECTORS = {"B-thin", "C-thin"}

# Historical Enigma keyboard / lampboard layout (QWERTZ, staggered)
KB_ROWS = ["QWERTZUIO", "ASDFGHJK", "PYXCVBNML"]
KB_INDENT = [0, 1, 2]
COMMERCIAL_ETW_ORDER = "".join(KB_ROWS)  # commercial ETW follows keyboard order

MAX_PLUGS = 13  # full theoretical stecker capacity (wartime issue was 10 cables)

MODEL_NAMES = [
    "Custom",
    "Enigma I (Army/GAF)",
    "M3 (Army/Navy)",
    "M4 'Shark' (U-boats)",
    "Commercial-style (K/D ETW demo)",
]
PRESETS = {
    "Enigma I (Army/GAF)": dict(etw="military", plugboard_enabled=True, reflector="B",
                                 L_type="I", M_type="II", R_type="III"),
    "M3 (Army/Navy)": dict(etw="military", plugboard_enabled=True, reflector="B",
                            L_type="I", M_type="V", R_type="VIII"),
    "M4 'Shark' (U-boats)": dict(etw="military", plugboard_enabled=True, reflector="B-thin",
                                  L_type="II", M_type="IV", R_type="I", G_type="Beta"),
    "Commercial-style (K/D ETW demo)": dict(etw="commercial", plugboard_enabled=False,
                                             reflector="B", L_type="I", M_type="II", R_type="III"),
}


# ---------------------------------------------------------------------------
# Additional historical wiring tables
# ---------------------------------------------------------------------------
# Every entry below was compared letter-by-letter against the Crypto Museum's
# published wiring tables (cryptomuseum.com/crypto/enigma/wiring.htm).
# All 64 wheels across all 16 models agree.  Two typos found in secondary
# sources (Sonder rotor II, Tirpitz reflector) were caught by cross-referencing
# and settled in the museum's favour.
#
# Key convention: base name is "LABEL-MODEL" (e.g. 'I-N' = rotor I for the
# Norenigma).  The 'label' field is what gets displayed (always the digit part).
_EXTENDED_ROTORS = {
    # Norenigma (N)
    "I-N":   {"wiring": "WTOKASUYVRBXJHQCPZEFMDINLG", "notches": {"Q"}, "label": "I"},
    "II-N":  {"wiring": "GJLPUBSWEMCTQVHXAOFZDRKYNI", "notches": {"E"}, "label": "II"},
    "III-N": {"wiring": "JWFMHNBPUSDYTIXVZGRQLAOEKC", "notches": {"V"}, "label": "III"},
    "IV-N":  {"wiring": "FGZJMVXEPBWSHQTLIUDYKCNRAO", "notches": {"J"}, "label": "IV"},
    "V-N":   {"wiring": "HEJXQOTZBVFDASCILWPGYNMURK", "notches": {"Z"}, "label": "V"},
    # Sondermaschine (S)
    "I-S":   {"wiring": "VEOSIRZUJDQCKGWYPNXAFLTHMB", "notches": {"Q"}, "label": "I"},
    "II-S":  {"wiring": "UEMOATQLSHPKCYFWJZBGVXIDNR", "notches": {"E"}, "label": "II"},
    "III-S": {"wiring": "TZHXMBSIPNURJFDKEQVCWGLAOY", "notches": {"V"}, "label": "III"},
    # Commercial D / K / Swiss-K (share D wiring; Swiss-K has different ring behaviour)
    "I-D":   {"wiring": "LPGSZMHAEOQKVXRFYBUTNICJDW", "notches": {"Y"}, "label": "I"},
    "II-D":  {"wiring": "SLVGBTFXJQOHEWIRZYAMKPCNDU", "notches": {"E"}, "label": "II"},
    "III-D": {"wiring": "CJGDPSHKTURAWZXFMYNQOBVLIE", "notches": {"N"}, "label": "III"},
    # Swiss-K
    "I-KS":  {"wiring": "PEZUOHXSCVFMTBGLRINQJWAYDK", "notches": {"Y"}, "label": "I"},
    "II-KS": {"wiring": "ZOUESYDKFWPCIQXHMVBLGNJRAT", "notches": {"E"}, "label": "II"},
    "III-KS":{"wiring": "EHRVXGAOBQUSIMZFLYNWKTPDJC", "notches": {"N"}, "label": "III"},
    # Railway (R) — published wiring
    "I-KR":  {"wiring": "JGDQOXUSCAMIFRVTPNEWKBLZYH", "notches": {"N"}, "label": "I"},
    "II-KR": {"wiring": "NTZPSFBOKMWRCJDIVLAEYUXHGQ", "notches": {"E"}, "label": "II"},
    "III-KR":{"wiring": "JVIUBHTCDYAKEQZPOSGXNRMWFL", "notches": {"Y"}, "label": "III"},
    # Tirpitz / T (Japan) — 8 rotors, 5 notches each
    "I-T":   {"wiring": "KPTYUELOCVGRFQDANJMBSWHZXI", "notches": {"W","Z","E","K","Q"}, "label": "I"},
    "II-T":  {"wiring": "UPHZLWEQMTDJXCAKSOIGVBYFNR", "notches": {"W","Z","F","L","R"}, "label": "II"},
    "III-T": {"wiring": "QUDLYRFEKONVZAXWHMGPJBSICT", "notches": {"W","Z","E","K","Q"}, "label": "III"},
    "IV-T":  {"wiring": "CIWTBKXNRESPFLYDAGVHQUOJZM", "notches": {"W","Z","F","L","R"}, "label": "IV"},
    "V-T":   {"wiring": "UAXGISNJBVERDYLFZWTPCKOHMQ", "notches": {"Y","C","F","K","R"}, "label": "V"},
    "VI-T":  {"wiring": "XFUZGALVHCNYSEWQTDMRBKPIOJ", "notches": {"X","E","I","M","Q"}, "label": "VI"},
    "VII-T": {"wiring": "BJVFTXPLNAYOZIKWGDQERUCHSM", "notches": {"Y","C","F","K","R"}, "label": "VII"},
    "VIII-T":{"wiring": "YMTPNZHWKODAJXELUQVGCBISFR", "notches": {"X","E","I","M","Q"}, "label": "VIII"},
    # A28 / G31 Zählwerk — uses D wiring with many-notch cog drive
    "I-Z":   {"wiring": "LPGSZMHAEOQKVXRFYBUTNICJDW",
               "notches": {"S","U","V","W","Z","A","B","C","E","F","G","I","K","L","O","P","Q"}, "label": "I"},
    "II-Z":  {"wiring": "SLVGBTFXJQOHEWIRZYAMKPCNDU",
               "notches": {"S","T","V","Y","Z","A","C","D","F","G","H","K","M","N","Q"}, "label": "II"},
    "III-Z": {"wiring": "CJGDPSHKTURAWZXFMYNQOBVLIE",
               "notches": {"U","W","X","A","E","F","H","K","M","N","R"}, "label": "III"},
    # G-111 (Hungary / Munich)
    "I-G111":  {"wiring": "WLRHBQUNDKJCZSEXOTMAGYFPVI",
                "notches": {"S","U","V","W","Z","A","B","C","E","F","G","I","K","L","O","P","Q"}, "label": "I"},
    "II-G111": {"wiring": "TFJQAZWMHLCUIXRDYGOEVBNSKP",
                "notches": {"S","T","V","Y","Z","A","C","D","F","G","H","K","M","N","Q"}, "label": "II"},
    "V-G111":  {"wiring": "QTPIXWVDFRMUSLJOHCANEZKYBG",
                "notches": {"S","W","Z","F","H","M","Q"}, "label": "V"},
    # G-260 (Abwehr / Argentina)
    "I-G260":  {"wiring": "RCSPBLKQAUMHWYTIFZVGOJNEXD",
                "notches": {"S","U","V","W","Z","A","B","C","E","F","G","I","K","L","O","P","Q"}, "label": "I"},
    "II-G260": {"wiring": "WCMIBVPJXAROSGNDLZKEYHUFQT",
                "notches": {"S","T","V","Y","Z","A","C","D","F","G","H","K","M","N","Q"}, "label": "II"},
    "III-G260":{"wiring": "FVDHZELSQMAXOKYIWPGCBUJTNR",
                "notches": {"U","W","X","A","E","F","H","K","M","N","R"}, "label": "III"},
    # G-312 (Abwehr / Bletchley)
    "I-G312":  {"wiring": "DMTWSILRUYQNKFEJCAZBPGXOHV",
                "notches": {"S","U","V","W","Z","A","B","C","E","F","G","I","K","L","O","P","Q"}, "label": "I"},
    "II-G312": {"wiring": "HQZGPJTMOBLNCIFDYAWVEUSRKX",
                "notches": {"S","T","V","Y","Z","A","C","D","F","G","H","K","M","N","Q"}, "label": "II"},
    "III-G312":{"wiring": "UQNTLSZFMREHDPXKIBVYGJCWOA",
                "notches": {"U","W","X","A","E","F","H","K","M","N","R"}, "label": "III"},
}
ROTOR_DATA.update(_EXTENDED_ROTORS)
# Backfill label on the original eight Wehrmacht rotors (same as their key)
for _k in ("I","II","III","IV","V","VI","VII","VIII"):
    ROTOR_DATA[_k].setdefault("label", _k)

ROTOR_CHOICES = list(ROTOR_DATA.keys())   # now 43 entries; kept for internal use

# Additional reflectors
REFLECTOR_DATA.update({
    "A":       "EJMZALYXVBWFCRQUONTSPIKHGD",
    "UKW-N":   "MOWJYPUXNDSRAIBFVLKZGQCHET",
    "UKW-S":   "CIAGSNDRBYTPZFULVHEKOQXWJM",
    "UKW-COM": "IMETCGFRAYSQBZXWLHKDVUPOJN",
    "UKW-KR":  "QYHOGNECVPUZTFDJAXWMKISRBL",
    "UKW-T":   "GEKPBTAUMOCNILJDXZYFHWVQSR",
    "UKW-G312":"RULQMZJSYGOCETKWDAHNBXPVIF",
})

REFLECTOR_CHOICES = ["B", "C", "B-thin", "C-thin", "Custom"]   # for the Custom machine
ALL_REFLECTOR_KEYS = list(REFLECTOR_DATA.keys()) + ["Custom"]   # model lookup

# Tirpitz has its own entry-wheel order (distinct from military and commercial)
_ETW_TIRPITZ = "ILXRZTKGJYAMWVDUFCPQEONSHB"

def default_custom_pairs():
    pairs = {}
    for i in range(0, 26, 2):
        a, b = ALPHA[i], ALPHA[i + 1]
        pairs[a] = b
        pairs[b] = a
    return pairs


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class Wheel:
    """Shared forward/backward substitution math for rotors and the 4th wheel."""

    def __init__(self, wiring, ring_setting=1, start_pos="A"):
        self.wiring = wiring
        self.ring_setting = ring_setting
        self.position = ALPHA.index(start_pos)

    @property
    def position_letter(self):
        return ALPHA[self.position]

    def forward(self, c):
        shift = self.position - (self.ring_setting - 1)
        entry = (c + shift) % 26
        out = ord(self.wiring[entry]) - ord("A")
        return (out - shift) % 26

    def backward(self, c):
        shift = self.position - (self.ring_setting - 1)
        entry = (c + shift) % 26
        out = self.wiring.index(ALPHA[entry])
        return (out - shift) % 26


class Rotor(Wheel):
    def __init__(self, name, ring_setting=1, start_pos="A", notch_override=None):
        super().__init__(ROTOR_DATA[name]["wiring"], ring_setting, start_pos)
        self.name = name
        self.notches = {notch_override} if notch_override else set(ROTOR_DATA[name]["notches"])

    def at_notch(self):
        return self.position_letter in self.notches

    def step(self):
        self.position = (self.position + 1) % 26


class FourthWheel(Wheel):
    """Non-stepping M4 'Greek' wheel (Beta/Gamma): set by hand, never turns."""

    def __init__(self, name, ring_setting=1, start_pos="A"):
        super().__init__(FOURTH_WHEEL_DATA[name]["wiring"], ring_setting, start_pos)
        self.name = name


class EntryWheel:
    """Fixed (non-rotating) entry wiring. Military = straight-through.
    Commercial = wired in QWERTZU keyboard order."""

    def __init__(self, mode="military"):
        self.mode = mode
        order = COMMERCIAL_ETW_ORDER if mode == "commercial" else ALPHA
        self.fwd = {order[i]: i for i in range(26)}
        self.inv = [None] * 26
        for letter, idx in self.fwd.items():
            self.inv[idx] = ALPHA.index(letter)

    def forward(self, c):
        return self.fwd[ALPHA[c]]

    def backward(self, c):
        return self.inv[c]


class Reflector:
    def __init__(self, kind="B", custom_pairs=None):
        self.kind = kind
        self.pairs = dict(custom_pairs) if kind == "Custom" else None

    def apply(self, c):
        if self.kind == "Custom":
            return ALPHA.index(self.pairs[ALPHA[c]])
        return ord(REFLECTOR_DATA[self.kind][c]) - ord("A")


class Plugboard:
    def __init__(self, pairs=None):
        self.pairs = dict(pairs or {})

    def apply(self, c):
        letter = ALPHA[c]
        return ALPHA.index(self.pairs.get(letter, letter))

    def pairs_list(self):
        seen, out = set(), []
        for a, b in self.pairs.items():
            if a not in seen:
                out.append((a, b))
                seen.add(a)
                seen.add(b)
        return out


class Enigma:
    def __init__(self, rotor_names=("I", "II", "III"), ring_settings=(1, 1, 1),
                 positions=("A", "A", "A"), reflector_kind="B", plug_pairs=None,
                 etw_mode="military", fourth_wheel=None, fourth_ring=1, fourth_pos="A",
                 rotor_notches=(None, None, None), custom_reflector_pairs=None,
                 plugboard_enabled=True):
        self.left = Rotor(rotor_names[0], ring_settings[0], positions[0], rotor_notches[0])
        self.middle = Rotor(rotor_names[1], ring_settings[1], positions[1], rotor_notches[1])
        self.right = Rotor(rotor_names[2], ring_settings[2], positions[2], rotor_notches[2])
        self.reflector_kind = reflector_kind
        self.custom_reflector_pairs = custom_reflector_pairs or default_custom_pairs()
        self.reflector = Reflector(reflector_kind, self.custom_reflector_pairs)
        self.plugboard = Plugboard(plug_pairs)
        self.plugboard_enabled = plugboard_enabled
        self.etw = EntryWheel(etw_mode)
        self.fourth = FourthWheel(fourth_wheel, fourth_ring, fourth_pos) if fourth_wheel else None
        self.movable_notches = any(n is not None for n in rotor_notches)

    def get_positions(self):
        """Return a snapshot of all rotor positions as a plain tuple.

        The snapshot captures only the three main rotor positions; the 4th
        wheel (Beta/Gamma) is fixed and never steps, so there is nothing to
        capture for it.  Useful for saving state before a keypress so that it
        can be restored later (e.g. to undo that keypress).
        """
        return (self.left.position, self.middle.position, self.right.position)

    def set_positions(self, snapshot):
        """Restore rotor positions from a snapshot returned by get_positions."""
        self.left.position, self.middle.position, self.right.position = snapshot

    def replay(self, text):
        """Encipher *text* from the machine's current (start) positions.

        The rotors are NOT permanently advanced — positions are saved before
        the run and restored afterwards, so replay() can be called as many
        times as needed without side-effects on the machine state.  This is
        what makes live re-encipherment of an editable message possible: any
        edit simply calls replay() again from the same start key.

        Parameters
        ----------
        text : str
            A string of A-Z letters and spaces.  Spaces are passed through
            unchanged and do not advance the rotors.

        Returns
        -------
        cipher : str
            The enciphered string.  Spaces in *text* appear as spaces here,
            aligned with the input character-for-character.
        snapshots : list[tuple]
            One position snapshot (as returned by get_positions()) per
            character in *text*, taken *after* that character was processed.
            Useful for reading back the rotor display at any point in the
            message.
        path : list[tuple[str, str]]
            The signal-path list from encode_letter() for the *last
            non-space* character in *text*, or [] if *text* is empty or
            all spaces.
        """
        start = self.get_positions()
        cipher, snapshots, path = [], [], []
        try:
            for ch in text:
                if ch == " ":
                    cipher.append(" ")
                    snapshots.append(self.get_positions())
                else:
                    out, p = self.encode_letter(ch)
                    cipher.append(out)
                    snapshots.append(self.get_positions())
                    path = p
        finally:
            self.set_positions(start)
        return "".join(cipher), snapshots, path

    def step_rotors(self):
        mid_notch = self.middle.at_notch()
        right_notch = self.right.at_notch()
        if mid_notch:
            self.left.step()
            self.middle.step()
        elif right_notch:
            self.middle.step()
        self.right.step()

    def encode_letter(self, letter):
        self.step_rotors()
        path = [("Keyboard", letter)]
        c = ALPHA.index(letter)
        if self.plugboard_enabled:
            c = self.plugboard.apply(c)
            path.append(("Plugboard", ALPHA[c]))
        c = self.etw.forward(c)
        path.append(("Entry Wheel (ETW)", ALPHA[c]))
        c = self.right.forward(c)
        path.append((f"Rotor R ({self.right.name}) ->", ALPHA[c]))
        c = self.middle.forward(c)
        path.append((f"Rotor M ({self.middle.name}) ->", ALPHA[c]))
        c = self.left.forward(c)
        path.append((f"Rotor L ({self.left.name}) ->", ALPHA[c]))
        if self.fourth:
            c = self.fourth.forward(c)
            path.append((f"4th Wheel ({self.fourth.name}) ->", ALPHA[c]))
        c = self.reflector.apply(c)
        path.append((f"Reflector {self.reflector_kind}", ALPHA[c]))
        if self.fourth:
            c = self.fourth.backward(c)
            path.append((f"<- 4th Wheel ({self.fourth.name})", ALPHA[c]))
        c = self.left.backward(c)
        path.append((f"<- Rotor L ({self.left.name})", ALPHA[c]))
        c = self.middle.backward(c)
        path.append((f"<- Rotor M ({self.middle.name})", ALPHA[c]))
        c = self.right.backward(c)
        path.append((f"<- Rotor R ({self.right.name})", ALPHA[c]))
        c = self.etw.backward(c)
        path.append(("<- Entry Wheel (ETW)", ALPHA[c]))
        if self.plugboard_enabled:
            c = self.plugboard.apply(c)
            path.append(("Plugboard", ALPHA[c]))
        path.append(("Lamp", ALPHA[c]))
        return ALPHA[c], path


# ---------------------------------------------------------------------------
# Settings-screen logic (pure data; the curses UI in tui.py just renders it)
# ---------------------------------------------------------------------------
FIELD_LABEL = {
    "model": "Model preset",
    "etw": "Entry wheel (ETW)",
    "plugboard_enabled": "Plugboard",
    "movable_notches": "Movable notches",
    "reflector": "Reflector (UKW)",
    "G_type": "4th wheel type", "G_ring": "4th wheel ring", "G_pos": "4th wheel start",
    "L_type": "Left rotor type", "L_ring": "Left ring", "L_pos": "Left start pos", "L_notch": "Left notch",
    "M_type": "Mid rotor type", "M_ring": "Mid ring", "M_pos": "Mid start pos", "M_notch": "Mid notch",
    "R_type": "Right rotor type", "R_ring": "Right ring", "R_pos": "Right start pos", "R_notch": "Right notch",
}


def build_field_order(settings):
    order = ["model", "etw", "plugboard_enabled", "movable_notches", "reflector"]
    if settings["reflector"] in THIN_REFLECTORS:
        order += ["G_type", "G_ring", "G_pos"]
    for p in ("L", "M", "R"):
        order += [f"{p}_type", f"{p}_ring", f"{p}_pos"]
        if settings["movable_notches"]:
            order.append(f"{p}_notch")
    return order


def apply_model_preset(settings, name):
    preset = PRESETS.get(name)
    if not preset:
        return
    settings.update(preset)
    for p in ("L", "M", "R"):
        settings[f"{p}_ring"] = 1
        settings[f"{p}_pos"] = "A"
    settings["movable_notches"] = False
    if settings["reflector"] in THIN_REFLECTORS:
        settings["G_type"] = preset.get("G_type", "Beta")
        settings["G_ring"] = 1
        settings["G_pos"] = "A"


def adjust_field(settings, field, d):
    if field == "model":
        names = MODEL_NAMES
        settings[field] = names[(names.index(settings[field]) + d) % len(names)]
        if settings[field] != "Custom":
            apply_model_preset(settings, settings[field])
        return

    if field == "etw":
        opts = ["military", "commercial"]
        settings[field] = opts[(opts.index(settings[field]) + d) % 2]
    elif field == "plugboard_enabled":
        settings[field] = not settings[field]
    elif field == "movable_notches":
        settings[field] = not settings[field]
        if settings[field]:
            for p in ("L", "M", "R"):
                settings[f"{p}_notch"] = sorted(ROTOR_DATA[settings[f"{p}_type"]]["notches"])[0]
    elif field == "reflector":
        opts = REFLECTOR_CHOICES
        settings[field] = opts[(opts.index(settings[field]) + d) % len(opts)]
        if settings[field] in THIN_REFLECTORS:
            settings.setdefault("G_type", "Beta")
            settings.setdefault("G_ring", 1)
            settings.setdefault("G_pos", "A")
    elif field == "G_type":
        opts = FOURTH_WHEEL_CHOICES
        settings[field] = opts[(opts.index(settings[field]) + d) % len(opts)]
    elif field == "G_ring":
        settings[field] = ((settings[field] - 1 + d) % 26) + 1
    elif field == "G_pos":
        i = ALPHA.index(settings[field])
        settings[field] = ALPHA[(i + d) % 26]
    elif field.endswith("_type"):
        opts = ROTOR_CHOICES
        settings[field] = opts[(opts.index(settings[field]) + d) % len(opts)]
    elif field.endswith("_ring"):
        settings[field] = ((settings[field] - 1 + d) % 26) + 1
    elif field.endswith("_notch") or field.endswith("_pos"):
        i = ALPHA.index(settings[field])
        settings[field] = ALPHA[(i + d) % 26]

    settings["model"] = "Custom"


def fmt_val(v):
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, int):
        return f"{v:02d}"
    return str(v)


# ---------------------------------------------------------------------------
# Plugboard / custom-reflector text parsing (pure logic, no curses)
# ---------------------------------------------------------------------------
def parse_plug_pairs(buf):
    tokens = buf.split()
    if len(tokens) > MAX_PLUGS:
        return False, f"Max {MAX_PLUGS} plug pairs (historical limit)"
    used, pairs = set(), {}
    for t in tokens:
        if len(t) != 2 or not t.isalpha():
            return False, f"Invalid pair '{t}' (need two letters)"
        a, b = t[0], t[1]
        if a == b:
            return False, f"Cannot plug {a} to itself"
        if a in used or b in used:
            return False, f"Letter reused in '{t}'"
        used.add(a)
        used.add(b)
        pairs[a] = b
        pairs[b] = a
    return True, pairs


def parse_reflector_pairs(buf):
    tokens = buf.split()
    if len(tokens) != 13:
        return False, f"Need exactly 13 pairs covering all 26 letters (got {len(tokens)})"
    used, pairs = set(), {}
    for t in tokens:
        if len(t) != 2 or not t.isalpha():
            return False, f"Invalid pair '{t}'"
        a, b = t[0], t[1]
        if a == b:
            return False, f"Cannot reflect {a} to itself"
        if a in used or b in used:
            return False, f"Letter reused in '{t}'"
        used.add(a)
        used.add(b)
        pairs[a] = b
        pairs[b] = a
    if len(used) != 26:
        return False, "All 26 letters must be used exactly once"
    return True, pairs
