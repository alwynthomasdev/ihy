from fractions import Fraction

import pytest
from music21 import meter, note, stream

from ihy.postprocess import (
    fix_time_signatures,
    guess_time_signature,
    parse_time,
    parse_time_list,
    set_instrument,
)


def make_score(bars: list[list[float]], signatures: dict[int, str]) -> stream.Score:
    """One-part score. ``bars`` lists note lengths (in crotchets) per bar;
    ``signatures`` maps bar index -> time signature as homr wrote it."""
    part = stream.Part()
    for i, lengths in enumerate(bars):
        m = stream.Measure(number=i + 1)
        if i in signatures:
            m.insert(0, meter.TimeSignature(signatures[i]))
        for ql in lengths:
            m.append(note.Note("C3", quarterLength=ql))
        part.append(m)
    score = stream.Score()
    score.insert(0, part)
    return score


def signatures_in(score) -> list[tuple[int, str]]:
    part = score.parts[0]
    return [
        (i, m.getElementsByClass("TimeSignature")[0].ratioString)
        for i, m in enumerate(part.getElementsByClass("Measure"))
        if m.getElementsByClass("TimeSignature")
    ]


def test_12_16_becomes_3_4():
    score = make_score([[1, 1, 1]] * 6, {0: "12/16"})
    assert fix_time_signatures(score) == ["3/4"]
    assert signatures_in(score) == [(0, "3/4")]


def test_metre_change_gets_one_signature_per_section():
    # Like the Delibes cello part: 6 bars of 6/8, then 2/4, both wrongly
    # numbered by homr's single whole-piece median.
    six_eight = [[3.0], [0.5, 0.5, 0.5, 1.0, 0.5]] * 3
    two_four = [[0.5, 0.5, 0.5, 0.5]] * 8
    score = make_score(six_eight + two_four, {0: "4/8", 6: "2/4"})
    assert fix_time_signatures(score) == ["6/8", "2/4"]
    assert signatures_in(score) == [(0, "6/8"), (6, "2/4")]


def test_a_few_misread_bars_do_not_change_the_result():
    bars = [[1, 1, 1]] * 7 + [[1, 1]] + [[1, 1, 1, 1]] + [[1, 1, 1]]
    score = make_score(bars, {0: "4/4"})
    assert fix_time_signatures(score) == ["3/4"]


def test_override_list_applies_in_order():
    score = make_score([[1, 1, 1]] * 4 + [[1, 1]] * 4, {0: "2/4", 4: "2/4"})
    assert fix_time_signatures(score, ["3/4", "2/4"]) == ["3/4", "2/4"]
    assert signatures_in(score) == [(0, "3/4"), (4, "2/4")]


def test_single_override_applies_to_every_signature():
    score = make_score([[1, 1, 1]] * 8, {0: "2/4", 4: "4/4"})
    assert fix_time_signatures(score, ["3/4"]) == ["3/4", "3/4"]


def test_override_inserts_signature_when_none_recognised():
    score = make_score([[1, 1, 1]] * 3, {})
    assert fix_time_signatures(score, ["3/4"]) == ["3/4"]
    assert signatures_in(score) == [(0, "3/4")]


def test_no_signature_and_no_override_leaves_score_alone():
    score = make_score([[1, 1, 1]] * 3, {})
    assert fix_time_signatures(score) == []
    assert signatures_in(score) == []


def test_unbelievable_length_keeps_homr_value():
    # 20 crotchets per bar is not a plausible x/4 or x/8 time signature here.
    score = make_score([[4, 4, 4, 4, 4]] * 4, {0: "4/4"})
    assert fix_time_signatures(score) == ["4/4"]


def test_guess_prefers_homr_denominator():
    assert guess_time_signature([Fraction(3)] * 4, 8) == "6/8"
    assert guess_time_signature([Fraction(3)] * 4, 4) == "3/4"
    assert guess_time_signature([Fraction(3)] * 4, 16) == "3/4"
    assert guess_time_signature([], 4) is None


@pytest.mark.parametrize("text, expected", [("3/4", "3/4"), (" 6 / 8 ", "6/8"), ("12/8", "12/8")])
def test_parse_time(text, expected):
    assert parse_time(text) == expected


@pytest.mark.parametrize("bad", ["3", "3/5", "0/4", "x/4", "3/4/4", ""])
def test_parse_time_rejects_bad_values(bad):
    with pytest.raises(ValueError):
        parse_time(bad)


def test_parse_time_list():
    assert parse_time_list("6/8,2/4") == ["6/8", "2/4"]


def test_set_instrument_replaces_existing():
    from music21 import instrument

    score = make_score([[1, 1, 1]], {0: "3/4"})
    score.parts[0].insert(0, instrument.Vocalist())
    set_instrument(score, "cello")
    part = score.parts[0]
    found = list(part.recurse().getElementsByClass("Instrument"))
    assert len(found) == 1
    assert isinstance(found[0], instrument.Violoncello)
    assert part.partName == "Violoncello"
