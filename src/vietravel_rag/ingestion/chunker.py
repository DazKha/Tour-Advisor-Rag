"""Conservative, source-page-aware semantic splitting for tour PDFs."""

from __future__ import annotations

import re
from collections import defaultdict

from vietravel_rag.models import ChunkRecord, PageText, TourSource

SECTION_HEADINGS = {
    "included": ("giá tour bao gồm",),
    "excluded": ("giá tour không bao gồm",),
    "child_price": ("giá vé trẻ em",),
    "payment": ("điều kiện thanh toán",),
    "cancellation_standard": ("các điều kiện hủy tour đối với ngày thường", "các điều kiện hủy tour ngày thường"),
    "cancellation_holiday": ("các điều kiện hủy tour đối với ngày lễ", "các điều kiện hủy tour ngày lễ"),
    "force_majeure": ("trường hợp bất khả kháng",),
}
_DAY = re.compile(r"^Ngày\s+(\d+)\s*:\s*(.*)$", re.I)
_HEADING_ALIASES = {phrase.casefold(): kind for kind, phrases in SECTION_HEADINGS.items() for phrase in phrases}


def _kind(line: str) -> str | None:
    value = line.strip().casefold().rstrip(":")
    if value == "giá dịch vụ":
        return "price"
    return next((kind for phrase, kind in _HEADING_ALIASES.items() if value.startswith(phrase)), None)


def chunk_tour(source: TourSource, pages: list[PageText]) -> list[ChunkRecord]:
    rows = [(page.page_number, line.strip()) for page in pages for line in page.text.splitlines() if line.strip()]
    chunks_data: list[tuple[str, str, int, int, str]] = []

    # The first-page commercial table ends before itinerary begins; keep it whole.
    first_day = next((i for i, (_, line) in enumerate(rows) if _DAY.match(line)), len(rows))
    price_start = next((i for i, (_, line) in enumerate(rows[:first_day]) if _kind(line) == "price"), None)
    if price_start is not None:
        title_start = first_day
        while title_start > price_start:
            candidate = rows[title_start - 1][1]
            if candidate.isupper() and any(character.isalpha() for character in candidate):
                title_start -= 1
            else:
                break
        price_rows = rows[price_start:title_start]
        chunks_data.append(("price", "Giá dịch vụ", price_rows[0][0], price_rows[-1][0], "\n".join(x[1] for x in price_rows)))
        rows = rows[:price_start] + rows[title_start:]

    current_kind = "tour_overview"
    current_title = "Thông tin tour"
    current: list[tuple[int, str]] = []

    def flush() -> None:
        nonlocal current
        if current:
            chunks_data.append((current_kind, current_title, current[0][0], current[-1][0], "\n".join(line for _, line in current)))
            current = []

    for page_no, line in rows:
        if line.casefold() in {"xem chương trình tour"} or re.fullmatch(r"\d+", line):
            continue
        day = _DAY.match(line)
        kind = _kind(line)
        if day:
            flush()
            current_kind = "itinerary"
            current_title = line
            current = [(page_no, line)]
            continue
        if line.casefold() == "những thông tin cần lưu ý":
            flush()
            current_kind, current_title = "registration_notes", line
            continue
        if kind:
            flush()
            current_kind, current_title = kind, line.rstrip(":")
            continue
        if re.match(r"^các điều kiện khi đăng ký tour", line, re.I):
            flush()
            current_kind, current_title = "registration_notes", line
            continue
        if re.match(r"^lưu ý khi chuyển/hủy tour", line, re.I):
            # Retain registration and cancellation context together until a defined cancellation heading.
            current.append((page_no, line))
            continue
        if re.match(r"^thông tin (?:giá|tour|chuyến bay|phương tiện)", line, re.I):
            if current_kind not in {"tour_overview", "price"}:
                flush()
                current_kind, current_title = "tour_overview", line
        current.append((page_no, line))
    flush()

    counters: defaultdict[str, int] = defaultdict(int)
    records: list[ChunkRecord] = []
    for kind, title, page_start, page_end, content in chunks_data:
        if kind == "itinerary":
            counters[kind] += 1
            index = counters[kind]
        else:
            counters[kind] += 1
            index = counters[kind]
        chunk_id = f"{source.tour_code}_{kind}_{index:02d}"
        records.append(ChunkRecord(
            chunk_id=chunk_id,
            tour_code=source.tour_code,
            tour_name=source.tour_name,
            section_type=kind,
            section_title=title,
            page_start=page_start,
            page_end=page_end,
            chunk_index=index,
            source_file=source.source_file,
            content=content,
            embedding_text=f"{source.tour_name} ({source.tour_code})\n{title}\n{content}",
        ))
    return records
