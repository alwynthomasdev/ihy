from pathlib import Path

import pytest
from PIL import Image

from conftest import SAMPLES
from ihy.pdf import PdfError, page_count, parse_pages, render_pages


@pytest.fixture
def two_page_pdf(tmp_path: Path) -> Path:
    """A4-sized 2-page PDF made from the public-domain sample images."""
    pages = []
    for name in ["beware.png", "star-spangled-banner.png"]:
        img = Image.open(SAMPLES / name).convert("L")
        page = Image.new("L", (1240, 1754), 255)  # A4 at 150 dpi
        img.thumbnail((1100, 1600))
        page.paste(img, (70, 70))
        pages.append(page)
    pdf = tmp_path / "two pages é.pdf"
    pages[0].save(pdf, save_all=True, append_images=pages[1:], resolution=150)
    return pdf


def test_page_count(two_page_pdf: Path):
    assert page_count(two_page_pdf) == 2


def test_render_pages(two_page_pdf: Path, tmp_path: Path):
    paths = render_pages(two_page_pdf, [1, 2], tmp_path / "out")
    assert [p.name for p in paths] == ["page-001.png", "page-002.png"]
    for path in paths:
        img = Image.open(path)
        assert img.mode == "L"
        # A4 at 300 dpi is about 2480 x 3508 pixels.
        assert abs(img.width - 2480) < 10
        assert abs(img.height - 3508) < 10


def test_render_selected_page_only(two_page_pdf: Path, tmp_path: Path):
    paths = render_pages(two_page_pdf, [2], tmp_path / "out")
    assert [p.name for p in paths] == ["page-002.png"]


@pytest.mark.parametrize(
    "spec, expected",
    [(None, [1, 2, 3, 4, 5]), ("2", [2]), ("2-4", [2, 3, 4]), ("1,3", [1, 3]), ("4-5, 1", [4, 5, 1]), ("2,2-3", [2, 3])],
)
def test_parse_pages(spec, expected):
    assert parse_pages(spec, 5) == expected


@pytest.mark.parametrize("spec", ["0", "6", "3-2", "a", "1-", ",", "2-9"])
def test_parse_pages_rejects_bad_ranges(spec):
    with pytest.raises(ValueError):
        parse_pages(spec, 5)


def test_corrupt_pdf(tmp_path: Path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"%PDF-1.4 nonsense")
    with pytest.raises(PdfError):
        page_count(bad)
