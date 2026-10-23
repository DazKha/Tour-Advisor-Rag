# Markdown Response Presentation Design

## Goal

Render generated tour answers as clean CommonMark and replace technical phrasing/status labels with natural customer-facing Vietnamese, without adding model calls or changing grounding behavior.

## Generated answer format

The answer-generation prompt must require CommonMark for structured content:

- Never use the Unicode bullet `•`.
- Put a blank line before each list.
- Put every list item on its own line and start it with `- `.
- Format itinerary items as `- **Ngày N – route:** concise description`.
- Keep paragraphs short and do not compress a multi-day itinerary into one line.

Few-shot examples must use this exact layout so the model sees literal newlines and Markdown list markers.

## Natural language

Normal answers should lead with the useful fact, for example “Dạ, tour Bangkok – Pattaya kéo dài 5 ngày…” rather than “Dạ, theo tài liệu…”. Source-oriented phrases are reserved for genuine uncertainty or conflict.

When most of an itinerary is supported but one detail conflicts, answer the itinerary first and then add a short section:

```markdown
**Điểm anh/chị nên lưu ý**

Tên ngôi chùa trong ngày cuối chưa được ghi thống nhất: phần giới thiệu nhắc đến **Chùa Phật Ngọc**, còn lịch trình chi tiết ghi **Chùa Phật Vàng**. Anh/chị nên xác nhận lại điểm tham quan này với Vietravel trước ngày khởi hành ạ.
```

Avoid robotic constructions such as “Lưu ý: tài liệu tour có hai cách ghi…” and avoid repeatedly saying “theo tài liệu”.

## Streamlit presentation

Keep `st.markdown` as the renderer. Add a small presentation normalizer as defense in depth: Unicode bullet markers produced at the beginning of a line are converted to Markdown `- ` markers, with a blank line before the list. The helper must not rewrite ordinary prose or citations.

Map internal response statuses to friendly display labels:

- `answered` → `Đã tìm thấy thông tin`
- `conflict` → `Có thông tin cần xác nhận`
- `unsupported` → `Chưa đủ thông tin`
- `escalate` → `Cần Vietravel hỗ trợ`
- `clarification_needed` → `Cần thêm thông tin`

Internal status values in graph state and evaluation output remain unchanged.

## Verification

Tests cover prompt rules and examples, Markdown normalization, every status label, and rendering behavior. A live smoke query for the Bangkok–Pattaya itinerary must produce a readable multi-line answer and retain citations. Full tests and lint must pass.
