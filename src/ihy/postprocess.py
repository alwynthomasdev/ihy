"""Fixes applied to homr's recognised score before it is saved.

homr reads only the bottom number of a time signature. It guesses the top
number from the median bar length of the whole piece, so pieces that change
metre (or have a few misread note lengths) get wrong time signatures. homr also
labels every single-staff part "Voice". The functions here repair both.
"""

from __future__ import annotations

import re
from fractions import Fraction
from statistics import median

from music21 import instrument as m21instrument
from music21 import meter

# --instrument choices -> music21 instrument classes. Each class carries the
# MuseScore sound id (e.g. strings.cello) and General MIDI program.
INSTRUMENTS: dict[str, type[m21instrument.Instrument]] = {
    "cello": m21instrument.Violoncello,
    "violin": m21instrument.Violin,
    "viola": m21instrument.Viola,
    "bass": m21instrument.Contrabass,
    "piano": m21instrument.Piano,
    "voice": m21instrument.Vocalist,
}

_TIME_RE = re.compile(r"^\s*(\d{1,2})\s*/\s*(1|2|4|8|16|32)\s*$")

# Largest believable top number for each bottom number.
_MAX_BEATS = {1: 2, 2: 6, 4: 9, 8: 15, 16: 24, 32: 32}


def parse_time(text: str) -> str:
    """Validate one time signature like '6/8'. Returns it normalised."""
    match = _TIME_RE.match(text)
    if not match or int(match.group(1)) == 0:
        raise ValueError(
            f"'{text}' is not a time signature; use a form like 3/4 or 6/8 "
            "(bottom number 1, 2, 4, 8, 16 or 32)"
        )
    return f"{int(match.group(1))}/{int(match.group(2))}"


def parse_time_list(text: str) -> list[str]:
    """Parse '6/8,2/4' into ['6/8', '2/4']."""
    return [parse_time(part) for part in text.split(",") if part.strip()]


def _bar_lengths(measures: list) -> list[Fraction]:
    """Recognised length of each bar in quarter notes. Pickup and final
    bars are left out when there are enough others."""
    lengths = [Fraction(m.highestTime).limit_denominator(64) for m in measures]
    if len(lengths) > 3:
        lengths = lengths[1:-1]
    return [length for length in lengths if length > 0]


def _signature_for(length_quarters: Fraction, denominator: int) -> str | None:
    """Time signature with ``denominator`` matching a bar of the given length,
    or None if there is no believable one."""
    beats = length_quarters * denominator / 4
    if beats.denominator != 1 or not 1 <= beats <= _MAX_BEATS.get(denominator, 16):
        return None
    return f"{beats.numerator}/{denominator}"


def guess_time_signature(lengths: list[Fraction], homr_denominator: int) -> str | None:
    """Pick a time signature for a run of bars from their lengths."""
    if not lengths:
        return None
    length = Fraction(median(lengths)).limit_denominator(64)
    # Snap to the nearest whole unit of the bottom number (quaver for /8, ...).
    candidates = []
    for denominator in (homr_denominator, 4, 8, 2):
        if denominator >= 16 and denominator == homr_denominator:
            continue  # x/16 is almost always a misreading of x/4 or x/8
        unit = Fraction(4, denominator)
        snapped = round(length / unit) * unit
        sig = _signature_for(snapped, denominator)
        if sig:
            candidates.append(sig)
    return candidates[0] if candidates else None


def fix_time_signatures(score, override: list[str] | None = None) -> list[str]:
    """Correct time signatures in place. Returns the signatures now in the
    score, in order (empty if there are none).

    With ``override``, values are applied to the recognised signatures in
    order; the last value is reused for any extra ones. Without it, each run
    of bars between signatures gets a signature matching its typical length.
    """
    parts = list(score.parts)
    if not parts:
        return []
    part_measures = [list(p.getElementsByClass("Measure")) for p in parts]
    first = part_measures[0]

    # Where the time signatures are, by bar index in the first part.
    starts: list[tuple[int, meter.TimeSignature]] = []
    for index, measure in enumerate(first):
        found = measure.getElementsByClass("TimeSignature")
        if found:
            starts.append((index, found[0]))

    if not starts:
        if override and first:
            for measures in part_measures:
                if measures:
                    measures[0].insert(0, meter.TimeSignature(override[0]))
            return [override[0]]
        return []

    chosen: list[str] = []
    for n, (start, ts) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else len(first)
        if override:
            new = override[min(n, len(override) - 1)]
        else:
            lengths: list[Fraction] = []
            for measures in part_measures:
                lengths += _bar_lengths(measures[start:end])
            new = guess_time_signature(lengths, ts.denominator) or ts.ratioString
        chosen.append(new)
        for measures in part_measures:
            if start >= len(measures):
                continue
            measure = measures[start]
            for old in list(measure.getElementsByClass("TimeSignature")):
                measure.replace(old, meter.TimeSignature(new))
    return chosen


def _same(a, b) -> bool:
    """Whether two clefs / key signatures / time signatures say the same thing."""
    if a is None or b is None or type(a) is not type(b):
        return False
    if isinstance(a, meter.TimeSignature):
        return a.ratioString == b.ratioString
    if hasattr(a, "sharps"):
        return a.sharps == b.sharps
    if hasattr(a, "sign"):
        return (a.sign, a.line, a.octaveChange) == (b.sign, b.line, b.octaveChange)
    return False


def _last(part, class_name: str):
    found = list(part.recurse().getElementsByClass(class_name))
    return found[-1] if found else None


def merge_scores(scores: list) -> tuple[object, list[str]]:
    """Join the scores of several pages into one, in order.

    Each later page's bars are appended to the matching part (by position)
    of the first page and renumbered. Clefs, key and time signatures that
    homr repeats at the top of every page are dropped when they match what
    is already in force, so they don't appear as changes. Returns the merged
    score and any warnings.
    """
    if not scores:
        raise ValueError("no pages to merge")
    warnings: list[str] = []
    base = scores[0]
    base_parts = list(base.parts)
    for page_index, score in enumerate(scores[1:], start=2):
        parts = list(score.parts)
        if len(parts) != len(base_parts):
            warnings.append(
                f"page {page_index} has {len(parts)} part(s) but the first page has "
                f"{len(base_parts)}; parts were matched in order"
                + (" and the extra ones dropped" if len(parts) > len(base_parts) else "")
            )
        for base_part, part in zip(base_parts, parts):
            measures = list(part.getElementsByClass("Measure"))
            if not measures:
                continue
            first = measures[0]
            for class_name in ("Clef", "KeySignature", "TimeSignature"):
                current = _last(base_part, class_name)
                for element in list(first.getElementsByClass(class_name)):
                    if element.offset == 0 and _same(element, current):
                        first.remove(element)
            existing = list(base_part.getElementsByClass("Measure"))
            number = int(existing[-1].number) if existing else 0
            for measure in measures:
                part.remove(measure)
                number += 1
                measure.number = number
                base_part.append(measure)
    return base, warnings


def set_instrument(score, name: str) -> None:
    """Make every part use the named instrument (a key of INSTRUMENTS)."""
    cls = INSTRUMENTS[name]
    for part in score.parts:
        for old in list(part.recurse().getElementsByClass("Instrument")):
            old.activeSite.remove(old)
        new = cls()
        part.insert(0, new)
        part.partName = new.instrumentName
        part.partAbbreviation = new.instrumentAbbreviation
