import shutil
from pathlib import Path

import pytest

from ihy import cli
from ihy.export import ExportResult
from ihy.recognise import HomrFailed, models_downloaded


def test_missing_file(tmp_path: Path, capsys):
    assert cli.main([str(tmp_path / "nope.png")]) == 2
    assert "does not exist" in capsys.readouterr().err


def test_unsupported_format(tmp_path: Path, capsys):
    f = tmp_path / "score.pdf"
    f.write_bytes(b"%PDF")
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
    for name in ["b.PNG", "a.jpg", "c.jpeg", "notes.txt", "d.gif"]:
        (tmp_path / name).write_bytes(b"x")
    assert [p.name for p in cli.collect_images(tmp_path)] == ["a.jpg", "b.PNG", "c.jpeg"]


def test_folder_batch_continues_after_failure(tmp_path: Path, monkeypatch, capsys, straight_page):
    """One bad image must not stop the batch; the summary lists both."""
    batch = tmp_path / "batch"
    batch.mkdir()
    shutil.copy(straight_page, batch / "good.png")
    (batch / "broken.png").write_bytes(b"not an image")

    def fake_recognise(image: Path, workdir: Path) -> Path:
        xml = workdir / "page.musicxml"
        xml.write_text("<x/>")
        return xml

    def fake_to_mxl(musicxml: Path, output: Path) -> ExportResult:
        output.write_bytes(b"PK")
        return ExportResult(path=output, parts=1, measures=1, notes=3)

    monkeypatch.setattr(cli, "recognise", fake_recognise)
    monkeypatch.setattr(cli, "to_mxl", fake_to_mxl)
    monkeypatch.setattr(cli, "models_downloaded", lambda: True)

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
