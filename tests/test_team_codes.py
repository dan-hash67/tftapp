import pytest

from pygooey.domain.team_codes import (
    TeamCodeFormat,
    TeamCodeError,
    build_reverse_planner_codes,
    decode_team_code,
    encode_unit_ids,
)


SAMPLE_CODE = "0240743042A42840F4183E9429000000TFTSet18"
UNIT_CODES = {
    "TFT18_Karma": 0x407,
    "TFT18_Taric": 0x430,
    "TFT18_Sett": 0x42A,
    "TFT18_AncientSentinel": 0x428,
    "TFT18_Krug": 0x40F,
    "TFT18_Morgana": 0x418,
    "TFT18_Ahri": 0x3E9,
    "TFT18_Pebbles": 0x429,
}


def test_decode_and_encode_round_trip() -> None:
    reverse = build_reverse_planner_codes(UNIT_CODES)
    team = decode_team_code(SAMPLE_CODE, reverse)

    assert [slot.unit_id for slot in team.slots[:8]] == [
        "TFT18_Karma",
        "TFT18_Taric",
        "TFT18_Sett",
        "TFT18_AncientSentinel",
        "TFT18_Krug",
        "TFT18_Morgana",
        "TFT18_Ahri",
        "TFT18_Pebbles",
    ]
    assert team.slots[8].is_empty
    assert team.slots[9].is_empty
    assert team.encode(UNIT_CODES) == SAMPLE_CODE


def test_editing_a_slot_changes_only_that_slot() -> None:
    reverse = build_reverse_planner_codes(UNIT_CODES)
    team = decode_team_code(SAMPLE_CODE, reverse)
    edited = team.replace_slot(8, "TFT18_Sett", UNIT_CODES)

    assert edited.encode(UNIT_CODES) == "0240743042A42840F4183E942942A000TFTSet18"
    assert team.encode(UNIT_CODES) == SAMPLE_CODE


def test_shared_planner_id_is_preserved_until_resolved() -> None:
    unit_codes = {"TFT18_LuxBlossom": 0x405, "TFT18_LuxInferno": 0x405}
    reverse = build_reverse_planner_codes(unit_codes)
    ambiguous_code = "02" + ("000" * 8) + "405" + "000" + "TFTSet18"
    team = decode_team_code(ambiguous_code, reverse)

    assert team.slots[8].is_ambiguous
    assert team.slots[8].candidates == ("TFT18_LuxBlossom", "TFT18_LuxInferno")
    assert team.encode(unit_codes) == ambiguous_code


def test_short_or_wrong_set_codes_are_rejected() -> None:
    with pytest.raises(TeamCodeError):
        decode_team_code("02407TFTSet18", {})
    with pytest.raises(TeamCodeError):
        decode_team_code("020000000000000000000000000000TFTSet17", {})


def test_encode_unit_ids_pads_to_ten_slots() -> None:
    assert encode_unit_ids(["TFT18_Ahri"], {"TFT18_Ahri": 0x3E9}) == (
        "02" + "3E9" + ("000" * 9) + "TFTSet18"
    )


def test_future_set_format_is_data_driven() -> None:
    future_format = TeamCodeFormat("03", "TFTSet19", 2)
    mapping = {"future_a": 0x123}
    reverse = build_reverse_planner_codes(mapping)
    code = encode_unit_ids(["future_a"], mapping, code_format=future_format)

    decoded = decode_team_code(code, reverse, code_format=future_format)
    assert code == "03123000TFTSet19"
    assert decoded.slots[0].unit_id == "future_a"
    assert decoded.slots[1].is_empty
