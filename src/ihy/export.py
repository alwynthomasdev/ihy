"""Turn homr's MusicXML into a compressed .mxl file with music21."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


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


def _summarise(score) -> tuple[int, int, int]:
    parts = len(score.parts) if hasattr(score, "parts") else 0
    measures = 0
    if parts:
        measures = max(len(p.getElementsByClass("Measure")) for p in score.parts)
    notes = len(score.flatten().notes)
    return parts, measures, notes


def to_mxl(musicxml: Path, output: Path) -> ExportResult:
    """Parse ``musicxml`` and write it to ``output`` as compressed MusicXML.

    If parsing fails, the raw MusicXML is copied next to ``output`` (same
    name, ``.musicxml`` extension) and :class:`InvalidMusicXML` is raised.
    """
    # music21 is slow to import, so only pay for it when exporting.
    import music21

    output = output.with_suffix(".mxl")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        score = music21.converter.parse(str(musicxml), format="musicxml")
    except Exception as exc:  # music21 raises many different exception types
        raw_copy = output.with_suffix(".musicxml")
        try:
            shutil.copyfile(musicxml, raw_copy)
        except OSError:
            raw_copy = None
        where = f" Raw homr output saved to {raw_copy}." if raw_copy else ""
        raise InvalidMusicXML(f"music21 could not read the recognised MusicXML: {exc}.{where}", raw_copy) from exc

    written = Path(score.write("mxl", fp=str(output)))
    parts, measures, notes = _summarise(score)
    return ExportResult(path=written, parts=parts, measures=measures, notes=notes)
