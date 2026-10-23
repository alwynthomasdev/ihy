"""Render PDF pages to images so homr can read them."""

from __future__ import annotations

import re
from pathlib import Path

RENDER_DPI = 300
# Keep very large pages (posters, A2 scans) to a size homr can cope with.
MAX_SIDE_PX = 7000


class PdfError(Exception):
    """The PDF could not be opened or rendered."""


def _open(pdf: Path):
    import pypdfium2 as pdfium

    try:
        return pdfium.PdfDocument(str(pdf))
    except pdfium.PdfiumError as exc:
        text = str(exc).lower()
        if "password" in text or "security" in text:
            raise PdfError(f"'{pdf}' is password-protected; remove the password and try again") from exc
        raise PdfError(f"could not open '{pdf}' as a PDF (corrupt or not a PDF?): {exc}") from exc


def page_count(pdf: Path) -> int:
    doc = _open(pdf)
    try:
        return len(doc)
    finally:
        doc.close()


def parse_pages(spec: str | None, total: int) -> list[int]:
    """Turn '2-4,7' into [2, 3, 4, 7] (1-based). None means every page."""
    if total < 1:
        raise PdfError("the PDF has no pages")
    if spec is None:
        return list(range(1, total + 1))
    pages: list[int] = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        match = re.fullmatch(r"(\d+)\s*(?:-\s*(\d+))?", chunk)
        if not match:
            raise ValueError(f"'{chunk}' is not a page or page range; use a form like 2, 2-4 or 1,3")
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if start < 1 or end < start:
            raise ValueError(f"'{chunk}' is not a valid page range")
        if end > total:
            raise ValueError(f"page {end} doesn't exist; the PDF has {total} page(s)")
        pages.extend(p for p in range(start, end + 1) if p not in pages)
    if not pages:
        raise ValueError("no pages selected")
    return pages


def render_pages(pdf: Path, pages: list[int], out_dir: Path) -> list[Path]:
    """Render the given 1-based pages to greyscale PNGs in ``out_dir``."""
    doc = _open(pdf)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    try:
        for number in pages:
            page = doc[number - 1]
            try:
                width_pt, height_pt = page.get_size()
                scale = RENDER_DPI / 72
                longest = max(width_pt, height_pt) * scale
                if longest > MAX_SIDE_PX:
                    scale *= MAX_SIDE_PX / longest
                image = page.render(scale=scale, grayscale=True).to_pil()
            except Exception as exc:
                raise PdfError(f"could not render page {number} of '{pdf}': {exc}") from exc
            finally:
                page.close()
            path = out_dir / f"page-{number:03d}.png"
            image.save(path)
            paths.append(path)
    finally:
        doc.close()
    return paths
