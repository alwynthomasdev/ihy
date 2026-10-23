from pathlib import Path

import cv2
import numpy as np
import pytest

SAMPLES = Path(__file__).parent / "samples"


def draw_staves(width: int = 1600, height: int = 900, spacing: int = 16, staves: int = 4) -> np.ndarray:
    """Synthetic score page: a few five-line staves with some note heads."""
    img = np.full((height, width), 255, dtype=np.uint8)
    margin = width // 16
    top = height // (staves + 1)
    for s in range(staves):
        y0 = top * (s + 1) - 2 * spacing
        for line in range(5):
            y = y0 + line * spacing
            cv2.line(img, (margin, y), (width - margin, y), 0, 2)
        for i, x in enumerate(range(margin + 80, width - margin - 40, 90)):
            y = y0 + (i % 8) * spacing // 2
            cv2.ellipse(img, (x, y), (spacing // 2 + 2, spacing // 2 - 1), -20, 0, 360, 0, -1)
            cv2.line(img, (x + spacing // 2, y), (x + spacing // 2, y - 3 * spacing), 0, 2)
    return img


def rotate(img: np.ndarray, degrees: float) -> np.ndarray:
    h, w = img.shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), degrees, 1.0)
    return cv2.warpAffine(img, m, (w, h), borderValue=255)


@pytest.fixture
def straight_page(tmp_path: Path) -> Path:
    path = tmp_path / "straight.png"
    cv2.imwrite(str(path), draw_staves())
    return path


@pytest.fixture
def samples() -> Path:
    return SAMPLES
