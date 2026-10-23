import zipfile
from pathlib import Path

import music21
import pytest

from ihy.export import InvalidMusicXML, to_mxl

# One bar of 3/4 in E-flat major: three crotchets.
SIMPLE_MUSICXML = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN"
  "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="4.0">
  <part-list>
    <score-part id="P1"><part-name>Voice</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <key><fifths>-3</fifths></key>
        <time><beats>3</beats><beat-type>4</beat-type></time>
        <clef><sign>G</sign><line>2</line></clef>
      </attributes>
      <note><pitch><step>A</step><alter>-1</alter><octave>4</octave></pitch><duration>1</duration><type>quarter</type></note>
      <note><pitch><step>G</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type></note>
      <note><pitch><step>F</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type></note>
    </measure>
  </part>
</score-partwise>
"""


@pytest.fixture
def simple_xml(tmp_path: Path) -> Path:
    path = tmp_path / "simple.musicxml"
    path.write_text(SIMPLE_MUSICXML, encoding="utf-8")
    return path


def test_writes_valid_mxl(simple_xml: Path, tmp_path: Path):
    out = tmp_path / "out" / "score.mxl"
    result = to_mxl(simple_xml, out)

    assert result.path == out
    assert out.exists()
    assert zipfile.is_zipfile(out)
    with zipfile.ZipFile(out) as z:
        assert "META-INF/container.xml" in z.namelist()
    assert (result.parts, result.measures, result.notes) == (1, 1, 3)


def test_mxl_round_trips_through_music21(simple_xml: Path, tmp_path: Path):
    out = to_mxl(simple_xml, tmp_path / "score.mxl").path
    score = music21.converter.parse(str(out))

    notes = list(score.flatten().notes)
    assert [n.nameWithOctave for n in notes] == ["A-4", "G4", "F4"]
    assert score.flatten().getElementsByClass("KeySignature")[0].sharps == -3
    ts = score.flatten().getElementsByClass("TimeSignature")[0]
    assert ts.ratioString == "3/4"
    assert score.flatten().getElementsByClass("Clef")[0].sign == "G"


def test_extension_forced_to_mxl(simple_xml: Path, tmp_path: Path):
    result = to_mxl(simple_xml, tmp_path / "score.xml")
    assert result.path.suffix == ".mxl"


def test_invalid_musicxml_keeps_raw_copy(tmp_path: Path):
    bad = tmp_path / "bad.musicxml"
    bad.write_text("<score-partwise><part id='P1'><measure", encoding="utf-8")
    with pytest.raises(InvalidMusicXML) as excinfo:
        to_mxl(bad, tmp_path / "out" / "score.mxl")
    raw = excinfo.value.raw_copy
    assert raw is not None and raw.exists()
    assert raw.read_text(encoding="utf-8") == bad.read_text(encoding="utf-8")
    assert not (tmp_path / "out" / "score.mxl").exists()


def test_instrument_written_for_musescore(simple_xml: Path, tmp_path: Path):
    out = to_mxl(simple_xml, tmp_path / "score.mxl", instrument="cello").path
    with zipfile.ZipFile(out) as z:
        xml = z.read("score.xml").decode("utf-8")
    assert "<part-name>Violoncello</part-name>" in xml
    assert "<instrument-sound>strings.cello</instrument-sound>" in xml
    assert "<midi-program>43</midi-program>" in xml
    inst = music21.converter.parse(str(out)).parts[0].getInstrument()
    assert isinstance(inst, music21.instrument.Violoncello)


def test_time_override(simple_xml: Path, tmp_path: Path):
    result = to_mxl(simple_xml, tmp_path / "score.mxl", time=["6/8"])
    assert result.time_signatures == ["6/8"]
    ts = music21.converter.parse(str(result.path)).flatten().getElementsByClass("TimeSignature")[0]
    assert ts.ratioString == "6/8"


def test_overfull_bar_is_not_rebarred(tmp_path: Path):
    """A bar homr over-filled must stay one bar, not spill into the next one.

    music21's default export re-bars such measures, which shifted every later
    note and garbled v0.1.0 output.
    """
    xml = SIMPLE_MUSICXML.replace(
        '<note><pitch><step>F</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type></note>',
        '<note><pitch><step>F</step><octave>4</octave></pitch><duration>2</duration><type>half</type></note>',
    ).replace(
        "</measure>\n  </part>",
        '</measure>\n    <measure number="2"><note><pitch><step>C</step><octave>5</octave></pitch>'
        "<duration>3</duration><type>half</type><dot/></note></measure>\n  </part>",
    )
    src = tmp_path / "overfull.musicxml"
    src.write_text(xml, encoding="utf-8")
    out = to_mxl(src, tmp_path / "score.mxl", time=["3/4"]).path
    measures = music21.converter.parse(str(out)).parts[0].getElementsByClass("Measure")
    assert len(measures) == 2
    assert [n.nameWithOctave for n in measures[0].notes] == ["A-4", "G4", "F4"]
    assert [n.nameWithOctave for n in measures[1].notes] == ["C5"]
