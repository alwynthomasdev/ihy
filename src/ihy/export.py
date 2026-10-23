"""Turn homr's MusicXML into a compressed .mxl file with music21."""

from __future__ import annotations

import re
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .postprocess import fix_time_signatures, set_instrument

_CONTAINER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<container>
  <rootfiles>
    <rootfile full-path="score.xml" media-type="application/vnd.recordare.musicxml+xml"/>
  </rootfiles>
</container>
"""


class InvalidMusicXML(Exception):
    """music21 could not parse the recognised MusicXML.

    ``raw_copy`` is where the unparsed homr output was saved instead.
    """

    def __init__(self, message: str, raw_copy: Path | None):
        super().__init__(message)
        self.raw_copy = raw_copy


@dataclass
class ExportResult:
    path: Path
    parts: int
    measures: int
    notes: int
    time_signatures: list[str] = field(default_factory=list)
    instrument: str | None = None


def _summarise(score) -> tuple[int, int, int]:
    parts = len(score.parts) if hasattr(score, "parts") else 0
    measures = 0
    if parts:
        measures = max(len(p.getElementsByClass("Measure")) for p in score.parts)
    notes = len(score.flatten().notes)
    return parts, measures, notes


def _instrument_sounds(score) -> dict[str, str]:
    """Instrument name -> MuseScore sound id (e.g. 'Violoncello' -> 'strings.cello')."""
    sounds: dict[str, str] = {}
    for inst in score.recurse().getElementsByClass("Instrument"):
        name, sound = inst.instrumentName, getattr(inst, "instrumentSound", None)
        if name and sound:
            sounds.setdefault(name, sound)
    return sounds


def add_instrument_sounds(xml: str, sounds: dict[str, str]) -> str:
    """Add <instrument-sound> to each <score-instrument>.

    music21 leaves it out, but MuseScore 4 uses it to pick the instrument;
    without it a cello can open as a generic or wrong instrument.
    """

    def patch(match: re.Match) -> str:
        block = match.group(0)
        if "<instrument-sound>" in block:
            return block
        name = re.search(r"<instrument-name>(.*?)</instrument-name>", block, re.S)
        sound = sounds.get(name.group(1).strip()) if name else None
        if not sound:
            return block
        # instrument-sound comes after instrument-name and instrument-abbreviation.
        anchor = "</instrument-abbreviation>" if "</instrument-abbreviation>" in block else "</instrument-name>"
        return block.replace(anchor, f"{anchor}\n        <instrument-sound>{sound}</instrument-sound>", 1)

    return re.sub(r"<score-instrument\b.*?</score-instrument>", patch, xml, flags=re.S)


def write_mxl(score, output: Path) -> None:
    """Write ``score`` as compressed MusicXML, keeping instrument sounds."""
    from music21.musicxml.m21ToXml import GeneralObjectExporter

    exporter = GeneralObjectExporter(score)
    # Keep the bars exactly as recognised. With makeNotation on, music21
    # re-bars any measure whose notes don't fit the time signature, which
    # moves notes into neighbouring bars and corrupts the whole passage.
    # An over- or under-full bar is much easier to fix by hand in MuseScore.
    exporter.makeNotation = False
    xml = exporter.parse().decode("utf-8")
    xml = add_instrument_sounds(xml, _instrument_sounds(score))
    with zipfile.ZipFile(output, "w") as z:
        # The MusicXML spec asks for an uncompressed mimetype entry first.
        z.writestr("mimetype", "application/vnd.recordare.musicxml", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", _CONTAINER_XML, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("score.xml", xml, compress_type=zipfile.ZIP_DEFLATED)


def load_score(musicxml: Path, output: Path):
    """Parse homr's MusicXML with music21.

    If parsing fails, the raw MusicXML is copied next to ``output`` (same
    name, ``.musicxml`` extension) and :class:`InvalidMusicXML` is raised.
    """
    # music21 is slow to import, so only pay for it when exporting.
    import music21

    try:
        return music21.converter.parse(str(musicxml), format="musicxml")
    except Exception as exc:  # music21 raises many different exception types
        raw_copy = output.with_suffix(".musicxml")
        try:
            raw_copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(musicxml, raw_copy)
        except OSError:
            raw_copy = None
        where = f" Raw homr output saved to {raw_copy}." if raw_copy else ""
        raise InvalidMusicXML(f"music21 could not read the recognised MusicXML: {exc}.{where}", raw_copy) from exc


def to_mxl(
    musicxml: Path,
    output: Path,
    *,
    instrument: str | None = None,
    time: list[str] | None = None,
) -> ExportResult:
    """Parse ``musicxml``, apply fixes and write ``output`` as compressed MusicXML.

    ``instrument`` is a key of ``postprocess.INSTRUMENTS``; ``time`` is a list of
    time signatures to apply in order (None = tidy homr's guess automatically).
    """
    output = output.with_suffix(".mxl")
    score = load_score(musicxml, output)
    return finish_score(score, output, instrument=instrument, time=time)


def finish_score(
    score,
    output: Path,
    *,
    instrument: str | None = None,
    time: list[str] | None = None,
) -> ExportResult:
    """Apply time-signature and instrument fixes, then write ``output``."""
    output = output.with_suffix(".mxl")
    output.parent.mkdir(parents=True, exist_ok=True)
    signatures = fix_time_signatures(score, time)
    if instrument:
        set_instrument(score, instrument)

    write_mxl(score, output)
    parts, measures, notes = _summarise(score)
    return ExportResult(
        path=output,
        parts=parts,
        measures=measures,
        notes=notes,
        time_signatures=signatures,
        instrument=instrument,
    )
