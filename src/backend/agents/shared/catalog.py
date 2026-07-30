"""Chuẩn hoá dữ liệu tiếng Việt cho agent: mẫu xe, phường/xã, số điện thoại.

Quy tắc xuyên suốt: **thà trả None còn hơn đoán bừa**. Nếu một cách viết tắt
khớp nhiều ứng viên (ví dụ "Phú" khớp cả Phú Diễn / Phú Lương / Phú Cát) thì
hàm match trả None để agent quay lại hỏi khách, không tự chọn hộ.

Cặp (vehicle_id, name) ở đây phải khớp `src/frontend/src/data/vehicles.js` —
`tests/test_agents/test_catalog.py` đọc thẳng file JS để so.
"""

import re
import unicodedata

from .wards import HANOI_WARDS

VEHICLES: tuple[tuple[str, str], ...] = (
    ("vf2", "VF 2"),
    ("vf3", "VF 3"),
    ("vf5", "VF 5"),
    ("vf6", "VF 6"),
    ("vf7", "VF 7"),
    ("vf8", "VF 8"),
    ("vf8-allnew", "VF 8 All New (2026)"),
    ("vfmpv7", "VF MPV 7"),
    ("vf9", "VF 9"),
    ("minio-green", "Minio Green"),
    ("herio-green", "Herio Green"),
    ("nerio-green", "Nerio Green"),
    ("limo-green", "Limo Green"),
    ("ec-van", "EC Van"),
)

VEHICLE_NAME_BY_ID: dict[str, str] = dict(VEHICLES)

# (giá niêm yết, giá ưu đãi) — khớp `priceList` / `priceFrom` trong vehicles.js.
# Nghiệp vụ đổi xe cần cả hai ở backend: `priceList` là "Giá niêm yết xe mới" của
# bước 2, còn hiệu `priceList - priceFrom` chính là "Khuyến mãi xe mới" ở bước 3.
# `test_catalog.py` đọc file JS để so, nên sửa giá một bên là test đỏ ngay.
VEHICLE_PRICES: dict[str, tuple[int, int]] = {
    "vf2": (379_000_000, 359_000_000),
    "vf3": (322_000_000, 299_000_000),
    "vf5": (559_000_000, 529_000_000),
    "vf6": (729_000_000, 689_000_000),
    "vf7": (850_000_000, 799_000_000),
    "vf8": (1_089_000_000, 1_019_000_000),
    "vf8-allnew": (1_179_000_000, 1_099_000_000),
    "vfmpv7": (799_000_000, 749_000_000),
    "vf9": (1_591_000_000, 1_499_000_000),
    "minio-green": (285_000_000, 269_000_000),
    "herio-green": (526_000_000, 499_000_000),
    "nerio-green": (483_000_000, 459_000_000),
    "limo-green": (789_000_000, 749_000_000),
    "ec-van": (299_000_000, 285_000_000),
}


def vehicle_price(vehicle_id: str | None) -> tuple[int, int] | None:
    """(giá niêm yết, giá ưu đãi). None nếu không có xe trong danh mục."""
    if not vehicle_id:
        return None
    return VEHICLE_PRICES.get(vehicle_id)

# Cách khách hay gọi mà không suy ra được từ tên chính thức.
VEHICLE_ALIASES: dict[str, str] = {
    "vf8allnew": "vf8-allnew",
    "vf8allnew2026": "vf8-allnew",
    "vf8moi": "vf8-allnew",
    "vf8banmoi": "vf8-allnew",
    "mpv7": "vfmpv7",
    "vfmpv": "vfmpv7",
    "mpv": "vfmpv7",
    "minio": "minio-green",
    "herio": "herio-green",
    "nerio": "nerio-green",
    "limo": "limo-green",
    "ecvan": "ec-van",
    "van": "ec-van",
}


def strip_accents(text: str) -> str:
    """Bỏ dấu tiếng Việt và hạ chữ thường. `đ`/`Đ` phải xử lý riêng vì NFD không tách."""
    if not text:
        return ""
    lowered = text.lower().replace("đ", "d")
    decomposed = unicodedata.normalize("NFD", lowered)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _squash(text: str) -> str:
    """Bỏ dấu rồi bỏ luôn mọi ký tự không phải chữ/số: "VF 8" -> "vf8"."""
    return re.sub(r"[^a-z0-9]", "", strip_accents(text))


def squash(text: str) -> str:
    """Bản public của `_squash`, cho module ngoài dùng chung một quy tắc chuẩn hoá.

    Bảng giá xe cũ sinh `lookup_key` bằng đúng hàm này. Viết hàm bỏ dấu thứ hai
    ở nơi khác là hai bộ quy tắc sẽ trôi khỏi nhau, và tra giá trượt trong im lặng.
    """
    return _squash(text)


_VEHICLE_KEYS: dict[str, str] = {}
for _vehicle_id, _name in VEHICLES:
    _VEHICLE_KEYS[_squash(_vehicle_id)] = _vehicle_id
    _VEHICLE_KEYS[_squash(_name)] = _vehicle_id
_VEHICLE_KEYS.update({_squash(k): v for k, v in VEHICLE_ALIASES.items()})


def match_vehicle(text: str | None) -> str | None:
    """Tìm vehicle_id từ câu nói của khách ("con VF8", "vf 9", "xe Limo")."""
    if not text:
        return None

    squashed = _squash(text)
    if not squashed:
        return None

    # 1. Khớp tuyệt đối sau khi squash.
    if squashed in _VEHICLE_KEYS:
        return _VEHICLE_KEYS[squashed]

    # 2. Khoá nào xuất hiện trong câu — ưu tiên khoá dài nhất để "vf8allnew"
    #    không bị "vf8" giành trước.
    contained = sorted(
        (key for key in _VEHICLE_KEYS if len(key) >= 3 and key in squashed),
        key=len,
        reverse=True,
    )
    if contained:
        best = contained[0]
        winners = {_VEHICLE_KEYS[k] for k in contained if len(k) == len(best)}
        if len(winners) == 1:
            return winners.pop()
        return None

    # 3. Khớp một phần (câu là tiền tố của khoá) — chỉ nhận khi duy nhất 1 ứng viên.
    partial = {_VEHICLE_KEYS[key] for key in _VEHICLE_KEYS if key.startswith(squashed)}
    if len(partial) == 1:
        return partial.pop()
    return None


def vehicle_name(vehicle_id: str | None) -> str | None:
    if not vehicle_id:
        return None
    return VEHICLE_NAME_BY_ID.get(vehicle_id)


_WARD_PREFIX = re.compile(r"^(phuong|xa|p|x)\s+", re.IGNORECASE)


def _ward_key(text: str) -> str:
    """Khoá so khớp phường: bỏ dấu, bỏ ký tự lạ, gộp khoảng trắng.

    CỐ TÌNH không bỏ tiền tố "Phường/Xã" ở đây. Bỏ dấu biến "Phượng Dực" thành
    "phuong duc", nếu tiếp tục cắt tiền tố "phuong " thì phường đó chỉ còn khoá
    "duc" — và mọi câu chứa từ "duc" (kể cả "Thủ Đức") sẽ khớp sai vào nó.
    Việc cắt tiền tố chỉ áp cho CÂU CỦA KHÁCH, ở `match_ward`.
    """
    plain = strip_accents(text)
    plain = plain.replace("-", " ")
    plain = re.sub(r"[^a-z0-9\s]", " ", plain)
    return re.sub(r"\s+", " ", plain).strip()


_WARD_BY_KEY: dict[str, list[str]] = {}
for _ward in HANOI_WARDS:
    _WARD_BY_KEY.setdefault(_ward_key(_ward), []).append(_ward)


def _lookup_ward(key: str) -> str | None:
    """Thử khớp một khoá theo 3 mức: tuyệt đối -> nằm trong câu -> tiền tố."""
    exact = _WARD_BY_KEY.get(key)
    if exact:
        return exact[0] if len(exact) == 1 else None

    # Câu dài kiểu "ở Cầu Giấy Hà Nội": tìm tên phường nằm trong câu.
    contained = {
        wards[0]
        for ward_key, wards in _WARD_BY_KEY.items()
        if len(wards) == 1 and re.search(rf"\b{re.escape(ward_key)}\b", key)
    }
    if contained:
        return contained.pop() if len(contained) == 1 else None

    prefixed = {
        wards[0]
        for ward_key, wards in _WARD_BY_KEY.items()
        if len(wards) == 1 and ward_key.startswith(key)
    }
    return prefixed.pop() if len(prefixed) == 1 else None


def match_ward(text: str | None) -> str | None:
    """Tìm tên phường/xã chuẩn. Nhiều ứng viên -> None (agent sẽ nhờ khách tự chọn)."""
    if not text:
        return None

    key = _ward_key(text)
    if not key:
        return None

    found = _lookup_ward(key)
    if found:
        return found

    # Lượt 2: khách viết kèm tiền tố ("Phường Cầu Giấy", "Xã Bát Tràng").
    without_prefix = _WARD_PREFIX.sub("", key).strip()
    if without_prefix and without_prefix != key:
        return _lookup_ward(without_prefix)
    return None


def normalize_phone(text: str | None) -> str | None:
    """Bỏ ký tự trang trí, đổi +84/84 thành 0. Trả None nếu không đủ 10 chữ số."""
    if not text:
        return None

    digits = re.sub(r"\D", "", text)
    if not digits:
        return None

    # Dạng quốc tế viết kiểu "0084..." — bỏ tiền tố quay số quốc tế trước.
    if digits.startswith("00"):
        digits = digits[2:]

    if digits.startswith("840"):
        digits = digits[2:]
    elif digits.startswith("84") and len(digits) >= 11:
        digits = "0" + digits[2:]

    if not digits.startswith("0"):
        digits = "0" + digits

    if len(digits) < 10 or len(digits) > 11:
        return None
    return digits
