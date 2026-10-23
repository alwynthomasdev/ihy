"""OpenCV clean-up applied to a scan before it is handed to homr."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

# homr resizes every page to this width before recognition, so upscaling
# beyond it gains nothing. Smaller images are upscaled here with a better
# interpolation than homr's default.
TARGET_WIDTH = 1920
# Staff spacing (pixels between staff lines) below which recognition suffers.
MIN_STAFF_SPACING = 14
MAX_UPSCALE = 4.0
# Ignore skew estimates larger than this; they are almost certainly wrong.
MAX_SKEW_DEGREES = 15.0


class ImageReadError(Exception):
    """The file could not be decoded as an image."""


@dataclass
class PreprocessResult:
    path: Path
    angle: float = 0.0
    scale: float = 1.0
    steps: list[str] = field(default_factory=list)


def read_image(path: Path) -> np.ndarray:
    """Read an image as greyscale. Works with non-ASCII paths on Windows."""
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE) if data.size else None
    if image is None:
        raise ImageReadError(f"could not read '{path}' as an image (corrupt or not a PNG/JPG?)")
    return image


def write_image(path: Path, image: np.ndarray) -> None:
    ok, buffer = cv2.imencode(path.suffix or ".png", image)
    if not ok:
        raise OSError(f"could not encode image for '{path}'")
    buffer.tofile(str(path))


def _dark_mask(grey: np.ndarray) -> np.ndarray:
    """White-on-black mask of the ink in the image."""
    _, mask = cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    return mask


def estimate_skew(grey: np.ndarray) -> float:
    """Angle in degrees of the staff lines (positive = counter-clockwise).

    Returns 0.0 when no staff lines are found.
    """
    h, w = grey.shape
    mask = _dark_mask(grey)
    # Keep only long horizontal strokes, which on a score are the staff lines.
    kernel_width = max(15, w // 30)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_width, 1))
    lines_only = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    lines = cv2.HoughLinesP(
        lines_only,
        rho=1,
        theta=np.pi / 1800,
        threshold=max(50, w // 8),
        minLineLength=max(30, w // 4),
        maxLineGap=max(5, w // 100),
    )
    if lines is None:
        return 0.0
    angles = []
    for x1, y1, x2, y2 in lines[:, 0]:
        if x2 == x1:
            continue
        # Image y grows downwards, so negate to get a conventional angle.
        angle = -np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if abs(angle) <= MAX_SKEW_DEGREES:
            angles.append(angle)
    if not angles:
        return 0.0
    return float(np.median(angles))


def deskew(grey: np.ndarray, angle: float) -> np.ndarray:
    """Rotate so the staff lines are level, padding with white."""
    if abs(angle) < 0.05:
        return grey
    h, w = grey.shape
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), -angle, 1.0)
    # Grow the canvas so rotated corners are not cut off.
    cos, sin = abs(matrix[0, 0]), abs(matrix[0, 1])
    new_w = int(h * sin + w * cos)
    new_h = int(h * cos + w * sin)
    matrix[0, 2] += new_w / 2 - w / 2
    matrix[1, 2] += new_h / 2 - h / 2
    return cv2.warpAffine(
        grey,
        matrix,
        (new_w, new_h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=255,
    )


def estimate_staff_spacing(grey: np.ndarray) -> float | None:
    """Most common vertical gap between ink runs, i.e. the staff spacing.

    Uses the classic OMR run-length method on a sample of columns.
    Returns None if the image has no clear staff structure.
    """
    mask = _dark_mask(grey) > 0
    h, w = mask.shape
    columns = np.linspace(0, w - 1, num=min(w, 200), dtype=int)
    gaps: list[int] = []
    for x in columns:
        col = mask[:, x].astype(np.int8)
        edges = np.flatnonzero(np.diff(col))
        # Pairs of (ink ends, next ink starts) give the white gaps.
        ends = edges[col[edges] == 1]
        starts = edges[col[edges] == 0]
        for end in ends:
            nxt = starts[starts > end]
            if nxt.size:
                gaps.append(int(nxt[0] - end))
    gaps = [g for g in gaps if 2 <= g <= h // 4]
    if len(gaps) < 20:
        return None
    counts = np.bincount(gaps)
    return float(np.argmax(counts))


def upscale_factor(grey: np.ndarray) -> float:
    """How much to enlarge the image (1.0 = leave as is)."""
    h, w = grey.shape
    factors = [1.0]
    if w < TARGET_WIDTH:
        factors.append(TARGET_WIDTH / w)
    spacing = estimate_staff_spacing(grey)
    if spacing and spacing < MIN_STAFF_SPACING:
        factors.append(MIN_STAFF_SPACING / spacing)
    return min(max(factors), MAX_UPSCALE)


def denoise(grey: np.ndarray) -> np.ndarray:
    """Light denoise that keeps thin staff lines and stems intact."""
    return cv2.fastNlMeansDenoising(grey, None, h=7, templateWindowSize=7, searchWindowSize=21)


def binarise(grey: np.ndarray) -> np.ndarray:
    """Adaptive threshold to pure black and white (copes with uneven lighting)."""
    block = max(15, (min(grey.shape) // 40) | 1)  # must be odd
    return cv2.adaptiveThreshold(
        grey, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block, 15
    )


def preprocess(src: Path, dest: Path, *, binarise_output: bool = False) -> PreprocessResult:
    """Clean up ``src`` and write the result to ``dest`` (never overwrites ``src``)."""
    if src.resolve() == dest.resolve():
        raise ValueError("preprocess output must not overwrite the original image")
    result = PreprocessResult(path=dest)
    grey = read_image(src)
    result.steps.append("greyscale")

    angle = estimate_skew(grey)
    if abs(angle) >= 0.05:
        grey = deskew(grey, angle)
        result.angle = angle
        result.steps.append(f"deskew {angle:+.2f} deg")

    scale = upscale_factor(grey)
    if scale > 1.01:
        grey = cv2.resize(grey, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        result.scale = scale
        result.steps.append(f"upscale x{scale:.2f}")

    grey = denoise(grey)
    result.steps.append("denoise")

    if binarise_output:
        grey = binarise(grey)
        result.steps.append("binarise")

    dest.parent.mkdir(parents=True, exist_ok=True)
    write_image(dest, grey)
    return result
