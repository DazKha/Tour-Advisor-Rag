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
    lines = [line for line in lines if line.casefold() != "xem chương trình tour" and not re.fullmatch(r"\d+", line)]
    # Remove exact adjacent duplicate extraction spans while preserving list boundaries.
    deduplicated: list[str] = []
    for line in lines:
        if line and (not deduplicated or deduplicated[-1] != line):
            deduplicated.append(line)
        elif not line and deduplicated and deduplicated[-1] != "":
            deduplicated.append("")
    while deduplicated and not deduplicated[-1]:
        deduplicated.pop()
    return "\n".join(deduplicated)


def extract_pdf_pages(path: Path) -> list[PageText]:
    """Extract each PDF page independently and retain its one-based page number."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    with pymupdf.open(path) as document:
        return [PageText(page_number=i + 1, text=_clean_page(page.get_text("text"))) for i, page in enumerate(document)]
