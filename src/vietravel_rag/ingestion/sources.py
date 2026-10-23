"""Immutable inventory of official tour PDF sources."""

from vietravel_rag.models import TourSource

TOUR_SOURCES = (
    TourSource(
        tour_code="danang-central-5d4n",
        tour_name="Đà Nẵng – Hội An – Huế – Phong Nha",
        source_file="Đà Nẵng - Sơn Trà - KDL Bà Nà - Cầu Vàng - Hội An - La Vang - Động Phong Nha & Thiên Đường - Huế (Khách sạn 4_ trọn tour).pdf",
        aliases=["đà nẵng", "hội an", "huế", "bà nà", "phong nha"],
    ),
    TourSource(
        tour_code="mekong-my-tho-ben-tre-can-tho",
        tour_name="Miền Tây – Mỹ Tho – Bến Tre – Cần Thơ",
        source_file="Miền Tây_ Mỹ Tho - Bến Tre - Cần Thơ - Trải Nghiệm Tuyến Cao Tốc Mới Nhất Của Miền Tây.pdf",
        aliases=["miền tây", "mỹ tho", "bến tre", "cần thơ"],
    ),
    TourSource(
        tour_code="thailand-bangkok-pattaya",
        tour_name="Thái Lan – Bangkok – Pattaya",
        source_file="Thái Lan_ Bangkok - Pattaya (Tham quan Hoàng Cung, chùa Phật Ngọc, Vườn lan Nong Nooch, Đảo San Hô, Tặng Buffet Baiyoke Sky + vé xem Show Alcazar).pdf",
        aliases=["thái lan", "bangkok", "pattaya"],
    ),
    TourSource(
        tour_code="china-lijiang-dali-shangrila",
        tour_name="Trung Quốc – Lệ Giang – Đại Lý – Shangrila",
        source_file="Trung Quốc_ Lệ Giang - Đại Lý - Shangrila - Núi tuyết Ngọc Long - Lam Nguyệt Đàm - Hẻm núi Hổ Khiêu Hiệp - Tặng vé cáp treo lớn lên đỉnh Núi tuyết Ngọc Long _ 28 Tết.pdf",
        aliases=["trung quốc", "lệ giang", "đại lý", "shangrila", "núi tuyết ngọc long"],
    ),
)
