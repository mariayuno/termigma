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
