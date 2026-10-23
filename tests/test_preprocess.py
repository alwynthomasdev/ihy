from pathlib import Path

import cv2
import numpy as np
import pytest

from conftest import SAMPLES, draw_staves, rotate
from ihy.preprocess import (
    TARGET_WIDTH,
    ImageReadError,
    estimate_skew,
    estimate_staff_spacing,
    preprocess,
    read_image,
)


def test_output_exists_and_original_untouched(straight_page: Path, tmp_path: Path):
    before = straight_page.read_bytes()
    out = tmp_path / "work" / "pre.png"
    result = preprocess(straight_page, out)
    assert out.exists()
    assert result.path == out
    assert straight_page.read_bytes() == before


def test_refuses_to_overwrite_original(straight_page: Path):
    with pytest.raises(ValueError):
        preprocess(straight_page, straight_page)


def test_output_is_greyscale_with_sensible_size(straight_page: Path, tmp_path: Path):
    out = tmp_path / "pre.png"
    preprocess(straight_page, out)
    img = cv2.imread(str(out), cv2.IMREAD_UNCHANGED)
    assert img.ndim == 2
    h, w = img.shape
    assert TARGET_WIDTH <= w <= 1600 * 4
    assert 0.4 < h / w < 0.7  # aspect ratio roughly preserved (900/1600)


def test_straight_image_is_not_rotated(straight_page: Path, tmp_path: Path):
    assert abs(estimate_skew(read_image(straight_page))) < 0.2
    result = preprocess(straight_page, tmp_path / "pre.png")
    assert result.angle == 0.0


@pytest.mark.parametrize("degrees", [-3.0, 2.0])
def test_tilted_staves_are_levelled(tmp_path: Path, degrees: float):
    page = tmp_path / "tilted.png"
    cv2.imwrite(str(page), rotate(draw_staves(), degrees))
    assert estimate_skew(read_image(page)) == pytest.approx(degrees, abs=0.3)

    out = tmp_path / "pre.png"
    preprocess(page, out)
    assert abs(estimate_skew(read_image(out))) < 0.3


def test_blank_image_does_not_crash(tmp_path: Path):
    page = tmp_path / "blank.png"
    cv2.imwrite(str(page), np.full((400, 600), 255, dtype=np.uint8))
    preprocess(page, tmp_path / "pre.png")


def test_small_image_is_upscaled():
    img = read_image(SAMPLES / "star-spangled-banner.png")
    assert img.shape[1] < TARGET_WIDTH
    from ihy.preprocess import upscale_factor

    assert upscale_factor(img) == pytest.approx(TARGET_WIDTH / img.shape[1], rel=0.01)


def test_staff_spacing_estimate():
    assert estimate_staff_spacing(draw_staves(spacing=16)) == pytest.approx(14, abs=2)


def test_binarise_gives_pure_black_and_white(straight_page: Path, tmp_path: Path):
    out = tmp_path / "pre.png"
    preprocess(straight_page, out, binarise_output=True)
    values = np.unique(cv2.imread(str(out), cv2.IMREAD_GRAYSCALE))
    assert set(values.tolist()) <= {0, 255}


def test_corrupt_image_raises_clear_error(tmp_path: Path):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"this is not a png")
    with pytest.raises(ImageReadError):
        preprocess(bad, tmp_path / "pre.png")


def test_non_ascii_path(tmp_path: Path):
    folder = tmp_path / "partitions été"
    folder.mkdir()
    page = folder / "page é.png"
    ok, buf = cv2.imencode(".png", draw_staves())
    buf.tofile(str(page))
    preprocess(page, folder / "pré.png")
    assert (folder / "pré.png").exists()
