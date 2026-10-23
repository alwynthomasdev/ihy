import shutil
from pathlib import Path

import pytest

from ihy import cli
from ihy.export import ExportResult
from ihy.pdf import page_count
from ihy.recognise import HomrFailed, models_downloaded


@pytest.fixture
def fake_pipeline(monkeypatch):
    """Replace homr and music21 with fakes. Recognition fails for any work
    folder whose name contains 'page-002' (page 2 of a PDF). Returns the list
    of folders recognise() was called with."""
    import music21

    calls: list[str] = []

    def fake_recognise(image: Path, workdir: Path) -> Path:
        calls.append(workdir.name)
        if "page-002" in workdir.name:
            raise HomrFailed("homr could not recognise the image (exit code 1).")
        xml = workdir / "page.musicxml"
        xml.parent.mkdir(parents=True, exist_ok=True)
        xml.write_text("<x/>")
        return xml

    def fake_load_score(musicxml: Path, output: Path):
        part = music21.stream.Part()
        measure = music21.stream.Measure(number=1)
        measure.append(music21.note.Note("C4", quarterLength=4))
        part.append(measure)
        score = music21.stream.Score()
        score.insert(0, part)
        return score

    def fake_finish_score(score, output: Path, **kwargs) -> ExportResult:
        output.write_bytes(b"PK")
        measures = len(score.parts[0].getElementsByClass("Measure"))
        return ExportResult(path=output, parts=1, measures=measures, notes=measures)

    monkeypatch.setattr(cli, "recognise", fake_recognise)
    monkeypatch.setattr(cli, "load_score", fake_load_score)
    monkeypatch.setattr(cli, "finish_score", fake_finish_score)
    monkeypatch.setattr(cli, "models_downloaded", lambda: True)
    return calls


@pytest.fixture
def three_page_pdf(tmp_path: Path, straight_page: Path) -> Path:
    from PIL import Image

    page = Image.open(straight_page).convert("L")
    pdf = tmp_path / "piece.pdf"
    page.save(pdf, save_all=True, append_images=[page, page], resolution=150)
    return pdf


def test_missing_file(tmp_path: Path, capsys):
    assert cli.main([str(tmp_path / "nope.png")]) == 2
    assert "does not exist" in capsys.readouterr().err


def test_unsupported_format(tmp_path: Path, capsys):
    f = tmp_path / "score.gif"
    f.write_bytes(b"GIF89a")
    assert cli.main([str(f)]) == 2
    assert "unsupported file type" in capsys.readouterr().err


def test_empty_folder(tmp_path: Path, capsys):
    assert cli.main([str(tmp_path)]) == 2
    assert "no .png" in capsys.readouterr().err


def test_output_paths(tmp_path: Path):
    img = tmp_path / "a.png"
    assert cli.output_path_for(img, None, False) == tmp_path / "a.mxl"
    assert cli.output_path_for(img, Path("out/score.mxl"), False) == Path("out/score.mxl")
    assert cli.output_path_for(img, Path("out"), True) == Path("out/a.mxl")


def test_collects_only_images(tmp_path: Path):
    for name in ["b.PNG", "a.jpg", "c.jpeg", "e.PDF", "notes.txt", "d.gif"]:
        (tmp_path / name).write_bytes(b"x")
    assert [p.name for p in cli.collect_images(tmp_path)] == ["a.jpg", "b.PNG", "c.jpeg", "e.PDF"]


def test_folder_batch_continues_after_failure(tmp_path: Path, fake_pipeline, capsys, straight_page):
    """One bad image must not stop the batch; the summary lists both."""
    batch = tmp_path / "batch"
    batch.mkdir()
    shutil.copy(straight_page, batch / "good.png")
    (batch / "broken.png").write_bytes(b"not an image")

    assert cli.main([str(batch)]) == 1
    out = capsys.readouterr().out
    assert "1 succeeded, 1 failed" in out
    assert "broken.png" in out
    assert (batch / "good.mxl").exists()


def test_homr_failure_is_reported(tmp_path: Path, monkeypatch, capsys, straight_page):
    def failing(image, workdir):
        raise HomrFailed("homr could not recognise the image (exit code 1).")

    monkeypatch.setattr(cli, "recognise", failing)
    monkeypatch.setattr(cli, "models_downloaded", lambda: True)
    assert cli.main([str(straight_page)]) == 1
    assert "homr could not recognise" in capsys.readouterr().err


def test_help_mentions_every_option(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--help"])
    text = capsys.readouterr().out
    for opt in ["-o", "--no-preprocess", "--binarise", "--keep-temp", "--download-models"]:
        assert opt in text


@pytest.mark.e2e
@pytest.mark.skipif(not models_downloaded(), reason="homr models not downloaded (run: ihy --download-models)")
def test_end_to_end_sample(tmp_path: Path, samples: Path):
    import music21

    image = tmp_path / "beware.png"
    shutil.copy(samples / "beware.png", image)
    assert cli.main([str(image)]) == 0

    out = tmp_path / "beware.mxl"
    assert out.exists()
    score = music21.converter.parse(str(out))
    flat = score.flatten()
    assert len(flat.notes) >= 10
    assert flat.getElementsByClass("Clef")
    assert flat.getElementsByClass("TimeSignature")
    # Nothing but the .mxl should appear next to the input.
    assert sorted(p.name for p in tmp_path.iterdir()) == ["beware.mxl", "beware.png"]


def test_readme_matches_help(capsys, monkeypatch):
    """The README embeds `ihy --help` verbatim; keep them in sync."""
    monkeypatch.setenv("COLUMNS", "100")
    with pytest.raises(SystemExit):
        cli.main(["--help"])
    help_text = capsys.readouterr().out.strip()
    readme = (Path(__file__).parent.parent / "README.md").read_text(encoding="utf-8")
    assert help_text in readme


def test_bad_time_value_is_usage_error(straight_page: Path, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main([str(straight_page), "--time", "3/5"])
    assert exc.value.code == 2
    assert "not a time signature" in capsys.readouterr().err


def test_bad_instrument_is_usage_error(straight_page: Path, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main([str(straight_page), "--instrument", "kazoo"])
    assert exc.value.code == 2


def test_pdf_pages_merged_and_failed_page_skipped(three_page_pdf: Path, fake_pipeline, capsys):
    assert cli.main([str(three_page_pdf)]) == 0
    captured = capsys.readouterr()
    assert fake_pipeline == ["page-001", "page-002", "page-003"]
    assert "page 2 skipped" in captured.err
    assert "2 measure(s)" in captured.out  # pages 1 and 3, one bar each
    assert (three_page_pdf.parent / "piece.mxl").exists()


def test_pdf_page_selection(three_page_pdf: Path, fake_pipeline):
    assert cli.main([str(three_page_pdf), "--pages", "1,3"]) == 0
    assert fake_pipeline == ["page-001", "page-003"]


def test_pdf_with_no_readable_page_fails(three_page_pdf: Path, fake_pipeline, capsys):
    assert cli.main([str(three_page_pdf), "--pages", "2"]) == 1
    assert "no music was recognised" in capsys.readouterr().err


@pytest.mark.parametrize("pages", ["4", "0", "3-1", "x"])
def test_bad_page_range_is_usage_error(three_page_pdf: Path, pages: str, capsys):
    assert page_count(three_page_pdf) == 3
    assert cli.main([str(three_page_pdf), "--pages", pages]) == 2
    assert "error:" in capsys.readouterr().err


def test_pages_with_image_is_usage_error(straight_page: Path, capsys):
    assert cli.main([str(straight_page), "--pages", "1"]) == 2
    assert "only works with a single PDF" in capsys.readouterr().err


def test_corrupt_pdf_is_reported(tmp_path: Path, fake_pipeline, capsys):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"%PDF-1.4 this is not really a pdf")
    assert cli.main([str(bad)]) == 1
    assert "could not open" in capsys.readouterr().err


@pytest.mark.e2e
@pytest.mark.skipif(not models_downloaded(), reason="homr models not downloaded (run: ihy --download-models)")
def test_end_to_end_pdf(tmp_path: Path, samples: Path):
    """Two pages of the same piece come out as one score with twice the bars."""
    import music21
    from PIL import Image

    img = Image.open(samples / "beware.png").convert("L")
    pdf = tmp_path / "beware.pdf"
    img.save(pdf, save_all=True, append_images=[img], resolution=300)
    assert cli.main([str(pdf), "--instrument", "cello"]) == 0

    score = music21.converter.parse(str(tmp_path / "beware.mxl"))
    measures = score.parts[0].getElementsByClass("Measure")
    assert len(measures) >= 20
    assert [m.number for m in measures] == list(range(1, len(measures) + 1))
    assert isinstance(score.parts[0].getInstrument(), music21.instrument.Violoncello)
