"""Conservative, source-page-aware semantic splitting for tour PDFs."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable

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
_ADDITIONAL_HEADINGS = {
    "visa": (
        "điều kiện xin visa",
        "điều kiện xin visa đoàn",
        "điều kiện xin visa du lịch trung quốc",
        "hồ sơ chi tiết cá nhân",
        "visa du lịch trung quốc nộp tại trung tâm tiếp nhận hồ sơ",
    ),
    "tour_notes": ("ghi chú",),
    "contact": ("thông tin liên lạc",),
}
_ADDITIONAL_ALIASES = {phrase.casefold(): kind for kind, phrases in _ADDITIONAL_HEADINGS.items() for phrase in phrases}
MAX_REGISTRATION_CHARS = 1800


def _kind(line: str) -> str | None:
    value = line.strip().casefold().rstrip(":")
    if value == "giá dịch vụ":
        return "price"
    result = next((kind for phrase, kind in _HEADING_ALIASES.items() if value == phrase), None)
    if result:
        return result
    return next((kind for phrase, kind in _ADDITIONAL_ALIASES.items()
                 if value == phrase or (kind == "visa" and value.startswith(phrase + " "))), None)


def _page_texts(rows: Iterable[tuple[int, str]]) -> dict[int, str]:
    grouped: defaultdict[int, list[str]] = defaultdict(list)
    for page_number, line in rows:
        grouped[page_number].append(line)
    return {page: "\n".join(lines) for page, lines in grouped.items()}


def _semantic_groups(kind: str, rows: list[tuple[int, str]]) -> list[list[tuple[int, str]]]:
    if kind not in {"registration_notes", "visa"}:
        return [rows]
    items: list[list[tuple[int, str]]] = []
    item: list[tuple[int, str]] = []
    for row in rows:
        starts_list_item = bool(re.match(r"^[-•·]\s+", row[1]))
        starts_subsection = bool(re.match(r"^Lưu ý khi chuyển/hủy tour\b", row[1], re.I))
        if item and (starts_list_item or starts_subsection):
            items.append(item)
            item = []
        item.append(row)
    if item:
        items.append(item)

    groups: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    current_chars = 0
    for semantic_item in items:
        item_chars = sum(len(line) + 1 for _, line in semantic_item)
        if current and current_chars + item_chars > MAX_REGISTRATION_CHARS:
            groups.append(current)
            current = []
            current_chars = 0
        current.extend(semantic_item)
        current_chars += item_chars
    if current:
        groups.append(current)
    return groups


def chunk_tour(source: TourSource, pages: list[PageText]) -> list[ChunkRecord]:
    rows = [(page.page_number, line.strip()) for page in pages for line in page.text.splitlines() if line.strip()]
    chunks_data: list[tuple[str, str, int, int, str, dict[int, str]]] = []

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
        chunks_data.append(("price", "Giá dịch vụ", price_rows[0][0], price_rows[-1][0], "\n".join(x[1] for x in price_rows), _page_texts(price_rows)))
        rows = rows[:price_start] + rows[title_start:]

    current_kind = "tour_overview"
    current_title = "Thông tin tour"
    current: list[tuple[int, str]] = []

    def flush() -> None:
        nonlocal current
        if current:
            for group in _semantic_groups(current_kind, current):
                chunks_data.append((
                    current_kind,
                    current_title,
                    group[0][0],
                    group[-1][0],
                    "\n".join(line for _, line in group),
                    _page_texts(group),
                ))
            current = []

    for page_no, line in rows:
        if line.casefold() in {"xem chương trình tour"}:
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
    for kind, title, page_start, page_end, content, page_texts in chunks_data:
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
            page_texts=page_texts,
        ))
    return records
