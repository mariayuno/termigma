from termigma.engine import ALPHA, Enigma, Rotor, ROTOR_DATA, default_custom_pairs


def test_reference_vector():
    """Published reference vector: rotors I-II-III, rings 01-01-01, start AAA,
    reflector B, no plugboard -> 'AAAAA' encodes to 'BDZGO'."""
    m = Enigma(rotor_names=("I", "II", "III"), ring_settings=(1, 1, 1),
               positions=("A", "A", "A"), reflector_kind="B")
    out = "".join(m.encode_letter(c)[0] for c in "AAAAA")
    assert out == "BDZGO"


def test_three_rotor_reciprocity():
    settings = dict(rotor_names=("III", "II", "I"), ring_settings=(5, 3, 1),
                     positions=("Q", "E", "R"), reflector_kind="C")
    forward = Enigma(**settings).encode_letter("X")[0]
    back = Enigma(**settings).encode_letter(forward)[0]
    assert back == "X"


def test_double_notch_rotor():
    assert Rotor("VI", 1, "Z").at_notch()
    assert Rotor("VI", 1, "M").at_notch()
    assert not Rotor("VI", 1, "A").at_notch()


def test_m4_four_rotor_reciprocity():
    settings = dict(rotor_names=("II", "IV", "I"), ring_settings=(1, 1, 1),
                     positions=("A", "A", "A"), reflector_kind="B-thin",
                     fourth_wheel="Beta", fourth_ring=1, fourth_pos="A")
    forward = Enigma(**settings).encode_letter("H")[0]
    back = Enigma(**settings).encode_letter(forward)[0]
    assert back == "H"


def test_commercial_etw_is_valid_bijection_and_differs_from_military():
    mil = Enigma(etw_mode="military")
    com = Enigma(etw_mode="commercial")
    assert set(com.etw.fwd.values()) == set(range(26))
    assert mil.etw.forward(ALPHA.index("Q")) != com.etw.forward(ALPHA.index("Q"))


def test_commercial_style_no_plugboard_reciprocity():
    settings = dict(rotor_names=("I", "II", "III"), ring_settings=(1, 1, 1),
                     positions=("A", "A", "A"), reflector_kind="B",
                     etw_mode="commercial", plugboard_enabled=False)
    forward = Enigma(**settings).encode_letter("P")[0]
    back = Enigma(**settings).encode_letter(forward)[0]
    assert back == "P"


def test_custom_reflector_default_is_valid_involution():
    pairs = default_custom_pairs()
    assert len(pairs) == 26
    assert all(pairs[k] != k for k in pairs)


def test_custom_reflector_reciprocity():
    pairs = default_custom_pairs()
    forward = Enigma(reflector_kind="Custom", custom_reflector_pairs=pairs).encode_letter("Z")[0]
    back = Enigma(reflector_kind="Custom", custom_reflector_pairs=pairs).encode_letter(forward)[0]
    assert back == "Z"


def test_movable_notch_override():
    m = Enigma(rotor_names=("I", "II", "III"), rotor_notches=(None, None, "A"))
    assert m.right.notches == {"A"}
    assert m.left.notches == {"Q"}  # unmodified rotors keep their historical notch(es)


def test_all_rotor_notches_present():
    for name, data in ROTOR_DATA.items():
        assert data["notches"], f"{name} should have at least one notch"


def test_get_set_positions_roundtrip():
    """get_positions / set_positions should save and restore exactly."""
    m = Enigma(rotor_names=("I", "II", "III"), positions=("A", "D", "V"))
    snap = m.get_positions()
    # step once, changing the positions
    m.encode_letter("A")
    m.set_positions(snap)
    assert m.get_positions() == snap


def test_backspace_restores_output():
    """Encoding X, then undoing (set_positions), then encoding X again
    must produce the same ciphertext both times — the rotor positions
    before each keypress were identical."""
    m = Enigma(rotor_names=("I", "II", "III"), positions=("A", "A", "A"))
    before = m.get_positions()
    out1, _ = m.encode_letter("X")
    # rewind to the saved snapshot
    m.set_positions(before)
    out2, _ = m.encode_letter("X")
    assert out1 == out2


def test_backspace_across_double_step():
    """The double-step anomaly affects both M and L rotors at once.  A
    snapshot taken before the keypress that triggers it must restore both."""
    # Rotor III notch is V, so right rotor at V will advance middle.
    # Middle rotor II notch is E, so at E a double-step fires.
    m = Enigma(rotor_names=("I", "II", "III"), positions=("A", "E", "U"))
    before = m.get_positions()
    m.encode_letter("A")
    after_step = m.get_positions()
    # Double-step means both middle AND left advanced.
    assert after_step != before
    # Restoring must bring all three back.
    m.set_positions(before)
    assert m.get_positions() == before


def test_replay_is_idempotent():
    """replay() must not change machine state — calling it twice returns the same cipher."""
    m = Enigma(rotor_names=("I", "II", "III"), positions=("A", "D", "F"))
    before = m.get_positions()
    c1, _, _ = m.replay("HELLO")
    c2, _, _ = m.replay("HELLO")
    assert c1 == c2
    assert m.get_positions() == before


def test_replay_matches_sequential_encode():
    """replay() must produce the same cipher as encoding letters one by one."""
    m1 = Enigma(rotor_names=("I", "II", "III"), positions=("Q", "E", "V"))
    m2 = Enigma(rotor_names=("I", "II", "III"), positions=("Q", "E", "V"))
    text = "ATTACKATDAWN"
    cipher_replay, _, _ = m1.replay(text)
    cipher_seq = "".join(m2.encode_letter(ch)[0] for ch in text)
    assert cipher_replay == cipher_seq


def test_replay_spaces_do_not_step_rotors():
    """A space in the text must be passed through as-is without advancing the rotors."""
    m = Enigma(rotor_names=("I", "II", "III"), positions=("A", "A", "A"))
    before = m.get_positions()
    # Replay a space-only string — nothing should step
    cipher, snaps, _ = m.replay("   ")
    assert cipher == "   "
    assert m.get_positions() == before
    # Positions after each space should be the same start position
    assert all(s == before for s in snaps)


def test_replay_snapshot_count():
    """replay() returns one snapshot per character in the input."""
    m = Enigma(rotor_names=("I", "II", "III"), positions=("A", "A", "A"))
    text = "HELLO WORLD"
    _, snaps, _ = m.replay(text)
    assert len(snaps) == len(text)
