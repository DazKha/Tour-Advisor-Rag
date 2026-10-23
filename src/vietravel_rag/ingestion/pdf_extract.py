"""Page-preserving extraction for official Vietravel PDFs."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pymupdf

from vietravel_rag.models import PageText


def _clean_page(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("\u00a0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line.casefold() != "xem chương trình tour"]
    return "\n".join(lines).strip()


def _page_text_from_blocks(blocks: list[tuple], page_number: int, page_height: float) -> str:
    """Keep repeated content; discard only same-text spans at the same position and confirmed footer labels."""
    seen_spans: set[tuple[str, tuple[float, float, float, float]]] = set()
    kept: list[tuple[float, float, str]] = []
    for block in blocks:
        if len(block) < 5:
            continue
        x0, y0, x1, y1, raw_text = block[:5]
        text = unicodedata.normalize("NFC", str(raw_text)).strip()
        if not text:
            continue
        normalized = _clean_page(text)
        if not normalized:
            continue
        if normalized == str(page_number) and y0 >= page_height * 0.94:
            continue
        bbox = tuple(round(float(value), 2) for value in (x0, y0, x1, y1))
        identity = (normalized, bbox)
        if identity in seen_spans:
            continue
        seen_spans.add(identity)
        kept.append((float(y0), float(x0), normalized))
    kept.sort(key=lambda item: (item[0], item[1]))
    return "\n".join(text for _, _, text in kept)


def extract_pdf_pages(path: Path) -> list[PageText]:
    """Extract each PDF page independently and retain its one-based page number."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    with pymupdf.open(path) as document:
        return [
            PageText(
                page_number=i + 1,
                text=_page_text_from_blocks(page.get_text("blocks", sort=True), i + 1, page.rect.height),
            )
            for i, page in enumerate(document)
        ]
