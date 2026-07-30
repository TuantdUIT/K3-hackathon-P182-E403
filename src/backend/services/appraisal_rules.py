"""Luật định giá xe cũ theo `docs/CAR_PREDICT_FORMULA.md` và nghiệp vụ 2.

Cố định như `catalog.VEHICLES` / `wards.HANOI_WARDS` — sửa bảng tiêu chí là sửa
file này rồi chạy lại test, KHÔNG phải migrate DB. Giả định xuyên suốt của bản
này: **giá và phí không biến động**, nên không có versioning theo thời gian.

Ranh giới quan trọng, đúng nguyên tắc của `agent-crm-flow.md`:
- Mọi thứ ở đây là RULE — đúng/sai rõ ràng, không cần LLM. Điều kiện xe, công
  thức ODO, phép cộng A/B/C đều chạy được khi không có API key.
- Agent chỉ đóng góp ở chỗ diễn giải: bóc thông tin từ lời sales và GIẢI THÍCH
  vì sao từng điều kiện quan trọng. Nó không được sửa mấy con số dưới đây.
"""

from datetime import date

# --------------------------------------------------------------------------
# 8 tiêu chí chấm điểm — tổng đúng 100%
# --------------------------------------------------------------------------

# (code, nhóm, nhãn hiển thị, trọng số %)
APPRAISAL_CRITERIA: tuple[tuple[str, str, str, int], ...] = (
    ("odo", "Khấu hao sử dụng", "Số km đã đi (ODO)", 20),
    ("engine", "Tình trạng kỹ thuật", "Động cơ & hộp số", 20),
    ("chassis", "Tình trạng kỹ thuật", "Khung gầm & hệ thống treo", 20),
    ("electrical", "Tình trạng kỹ thuật", "Hệ thống điện & tính năng", 10),
    ("exterior", "Thẩm mỹ ngoại thất", "Sơn & vỏ xe", 10),
    ("interior", "Thẩm mỹ nội thất", "Khoang cabin", 10),
    ("service", "Yếu tố gia tăng", "Lịch sử bảo dưỡng", 5),
    ("extras", "Yếu tố gia tăng", "Màu sắc & phụ kiện", 5),
)

CRITERIA_WEIGHT: dict[str, int] = {code: weight for code, _, _, weight in APPRAISAL_CRITERIA}
CRITERIA_LABEL: dict[str, str] = {code: label for code, _, label, _ in APPRAISAL_CRITERIA}

# Bất biến của cả hệ thống: doc ghi rõ "tổng điểm hệ thống là 100%".
assert sum(CRITERIA_WEIGHT.values()) == 100, "Tổng trọng số 8 tiêu chí phải bằng 100"

# ODO tính bằng công thức từ ODO thực tế + tuổi xe, KHÔNG do người chấm nhập tay.
# 7 tiêu chí còn lại là quan sát của thẩm định viên.
ODO_CODE = "odo"
SCORED_CRITERIA: tuple[str, ...] = tuple(
    code for code in CRITERIA_WEIGHT if code != ODO_CODE
)

# --------------------------------------------------------------------------
# Thang chấm 4 mức
# --------------------------------------------------------------------------

# Doc mô tả tiêu chí kỹ thuật bằng lời ("máy êm", "chuyển số mượt mà") — không
# quy ra số được nhất quán, hai thẩm định viên sẽ cho hai kết quả. Ép về 4 mức
# rời rạc để mọi người chấm cùng một thước.
LEVELS: dict[str, float] = {
    "tot": 1.0,
    "kha": 0.75,
    "trung_binh": 0.5,
    "kem": 0.0,
}

LEVEL_LABELS: dict[str, str] = {
    "tot": "Tốt — đúng như mô tả tiêu chí",
    "kha": "Khá — hao mòn nhẹ, không ảnh hưởng sử dụng",
    "trung_binh": "Trung bình — cần sửa/làm lại",
    "kem": "Kém — hỏng hoặc phải thay thế",
}

# Tiêu chí thẩm định viên chưa đánh giá thì tạm tính mức "Khá" và PHẢI được đánh
# dấu là ước lượng ở mọi chỗ hiển thị. Không im lặng cho điểm tối đa: đó là tự
# đoán có lợi cho một bên, đúng thứ nguyên tắc "thà hỏi còn hơn đoán bừa" cấm.
DEFAULT_LEVEL = "kha"


def level_ratio(level: str | None) -> float:
    return LEVELS.get(str(level or DEFAULT_LEVEL), LEVELS[DEFAULT_LEVEL])


# --------------------------------------------------------------------------
# Tiêu chí ODO — "vượt mức sẽ bị hạ điểm tịnh tiến"
# --------------------------------------------------------------------------

# Doc ghi "trung bình 15.000 - 20.000 km/năm đối với xe gia đình". Lấy mốc giữa
# làm chuẩn: chạy tới 18.000 km/năm vẫn giữ nguyên điểm.
STANDARD_KM_PER_YEAR = 18_000

# Sàn 30%: xe chạy gấp đôi mức chuẩn vẫn còn giá trị sử dụng, cho 0 điểm cả
# tiêu chí 20% là phạt nặng tới mức khách bỏ đi.
ODO_FLOOR_RATIO = 0.30


def months_between(start: date, end: date) -> int:
    """Số tháng tròn giữa 2 mốc. Dùng cho cả tuổi xe lẫn thời gian sở hữu."""
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return max(months, 0)


def odo_ratio(odo_km: int, first_registration_date: date, today: date | None = None) -> float:
    """Tỷ lệ đạt của tiêu chí ODO, tịnh tiến theo mức vượt chuẩn.

    Xe mới đăng ký dưới 1 năm vẫn quy về mốc 1 năm, nếu không một chiếc chạy
    5.000 km trong 2 tháng sẽ ra 30.000 km/năm và bị trừ oan.
    """
    today = today or date.today()
    years = max(months_between(first_registration_date, today) / 12, 1.0)
    km_per_year = max(int(odo_km), 0) / years

    if km_per_year <= STANDARD_KM_PER_YEAR:
        return 1.0

    over = (km_per_year - STANDARD_KM_PER_YEAR) / STANDARD_KM_PER_YEAR
    return max(ODO_FLOOR_RATIO, round(1.0 - over, 4))


# --------------------------------------------------------------------------
# Cổng loại trừ — chạy TRƯỚC khi chấm điểm
# --------------------------------------------------------------------------

MIN_OWNERSHIP_MONTHS = 6
MAX_AGE_YEARS = 7

# code -> (nhãn, câu giải thích VÌ SAO). Phần "vì sao" chính là thứ node
# `explain` đọc cho sales mới nghe — nội dung ở đây, không nằm trong prompt LLM,
# để câu trả lời không đổi giữa hai lần chạy.
HARD_FLAGS: dict[str, tuple[str, str]] = {
    "flood_damaged": (
        "Xe từng ngập nước",
        "Nước vào khoang máy và hệ thống điện gây ăn mòn ngầm, lỗi phát sinh dần "
        "nhiều tháng sau khi thu xe. Không định giá được rủi ro đó nên loại thẳng.",
    ),
    "structural_damage": (
        "Đâm đụng ảnh hưởng kết cấu",
        "Khung xe đã biến dạng thì độ an toàn khi va chạm tiếp theo không còn như "
        "thiết kế, và không thể phục hồi về nguyên bản bằng sửa chữa thông thường.",
    ),
    "odo_tampered": (
        "Có dấu hiệu tua công-tơ-mét",
        "ODO là gốc của tiêu chí khấu hao 20%. Số đã bị can thiệp thì toàn bộ "
        "phần định giá phía sau mất căn cứ.",
    ),
    "missing_papers": (
        "Không đủ giấy tờ gốc",
        "Thiếu đăng ký gốc thì không sang tên được cho người mua tiếp theo, xe "
        "thu về không bán lại được.",
    ),
}

OWNERSHIP_REASON = (
    f"Khách phải đứng tên xe tối thiểu {MIN_OWNERSHIP_MONTHS} tháng. Mốc này chặn "
    "việc mua đi bán lại lấy ưu đãi đổi xe, không phải nhu cầu dùng xe thật."
)
AGE_REASON = (
    f"Xe dưới {MAX_AGE_YEARS} năm sử dụng mới đủ điều kiện. Quá mốc này chi phí "
    "tân trang và rủi ro tồn kho vượt phần giá trị thu về."
)


def check_eligibility(
    *,
    first_registration_date: date,
    ownership_months: int | None = None,
    flags: dict[str, bool] | None = None,
    today: date | None = None,
) -> tuple[str, list[dict[str, object]]]:
    """Trả `(status, checks)`.

    `status` = "passed" hoặc "rejected_<code>" của điều kiện trượt ĐẦU TIÊN.
    `checks` luôn đủ 6 dòng để UI hiện được cả mục đạt lẫn mục trượt — sales cần
    thấy xe qua được những gì, không chỉ thấy chỗ bị chặn.
    """
    today = today or date.today()
    flags = flags or {}
    checks: list[dict[str, object]] = []

    age_months = months_between(first_registration_date, today)
    age_ok = age_months < MAX_AGE_YEARS * 12
    checks.append(
        {
            "code": "age",
            "label": f"Dưới {MAX_AGE_YEARS} năm sử dụng",
            "passed": age_ok,
            "detail": f"Xe đã dùng {age_months // 12} năm {age_months % 12} tháng.",
            "why": AGE_REASON,
        }
    )

    # Không khai thời gian sở hữu thì lấy tuổi xe làm cận trên: khách không thể
    # sở hữu lâu hơn tuổi của chính chiếc xe.
    owned = age_months if ownership_months is None else int(ownership_months)
    ownership_ok = owned >= MIN_OWNERSHIP_MONTHS
    checks.append(
        {
            "code": "ownership",
            "label": f"Sở hữu tối thiểu {MIN_OWNERSHIP_MONTHS} tháng",
            "passed": ownership_ok,
            "detail": f"Khách đứng tên {owned} tháng.",
            "why": OWNERSHIP_REASON,
        }
    )

    for code, (label, why) in HARD_FLAGS.items():
        raised = bool(flags.get(code))
        checks.append(
            {
                "code": code,
                "label": f"Không {label.lower()}" if code != "missing_papers" else "Đủ giấy tờ gốc",
                "passed": not raised,
                "detail": "Đạt." if not raised else f"{label} — loại.",
                "why": why,
            }
        )

    if not age_ok:
        return "rejected_age", checks
    if not ownership_ok:
        return "rejected_ownership", checks
    for code in HARD_FLAGS:
        if flags.get(code):
            return f"rejected_{code}", checks

    return "passed", checks


REJECTION_LABELS: dict[str, str] = {
    "rejected_age": f"xe đã quá {MAX_AGE_YEARS} năm sử dụng",
    "rejected_ownership": f"khách chưa sở hữu đủ {MIN_OWNERSHIP_MONTHS} tháng",
    **{f"rejected_{code}": label.lower() for code, (label, _) in HARD_FLAGS.items()},
}


# --------------------------------------------------------------------------
# Bước 2 — phí lăn bánh xe mới (B)
# --------------------------------------------------------------------------

# LƯU Ý CẦN XÁC NHẬN: để 0% là đang giả định ô tô điện chạy pin vẫn trong thời
# gian miễn lệ phí trước bạ. Sai mức này thì B lệch hàng chục triệu.
REGISTRATION_TAX_PCT: float = 0.0
PLATE_FEE: int = 20_000_000  # biển Hà Nội
ROAD_FEE: int = 1_560_000  # phí đường bộ 1 năm
INSPECTION_FEE: int = 340_000
INSURANCE_FEE: int = 530_000  # TNDS bắt buộc

FEE_BREAKDOWN_LABELS: tuple[tuple[str, str], ...] = (
    ("registration_tax", "Thuế trước bạ"),
    ("plate_fee", "Phí biển số"),
    ("road_fee", "Phí đường bộ"),
    ("inspection_fee", "Phí đăng kiểm"),
    ("insurance_fee", "Bảo hiểm TNDS"),
)


def rolling_fees(list_price: int) -> dict[str, int]:
    """Các khoản cộng vào giá niêm yết để ra tổng chi phí lăn bánh."""
    return {
        "registration_tax": int(round(list_price * REGISTRATION_TAX_PCT)),
        "plate_fee": PLATE_FEE,
        "road_fee": ROAD_FEE,
        "inspection_fee": INSPECTION_FEE,
        "insurance_fee": INSURANCE_FEE,
    }


# --------------------------------------------------------------------------
# Bước 3 — ưu đãi độc quyền cho khách đổi xe
# --------------------------------------------------------------------------

TRADE_IN_BONUS: int = 10_000_000


# --------------------------------------------------------------------------
# Checklist 4 việc bắt buộc trước khi hẹn giao xe (workflow gate, chặn MỀM)
# --------------------------------------------------------------------------

CHECKLIST_ITEMS: tuple[tuple[str, str], ...] = (
    ("contract", "Ký hợp đồng mua xe mới"),
    ("deposit", "Khách đã đặt cọc"),
    ("papers", "Thu đủ giấy tờ gốc xe cũ"),
    ("status", "Cập nhật trạng thái khách trên CRM"),
)

CHECKLIST_LABEL: dict[str, str] = dict(CHECKLIST_ITEMS)


# --------------------------------------------------------------------------
# SLA thẩm định Smart Solution — timer, không phải phán đoán
# --------------------------------------------------------------------------

SMART_SOLUTION_SLA_HOURS = 48
SMART_SOLUTION_STEPS = 7
SMART_SOLUTION_ITEMS = 100


# --------------------------------------------------------------------------
# Progressive autonomy — mức giải thích giảm dần khi sales quen việc
# --------------------------------------------------------------------------

# Ngưỡng tạm đặt. `agent-crm-flow.md` mục 9 ghi rõ con số thật phải lấy từ vài
# tuần chạy thực tế, nên đừng coi 3/10 là kết luận.
NOVICE_MAX_CASES = 3
FAMILIAR_MAX_CASES = 10


def experience_level(handled_cases: int) -> str:
    """"novice" | "familiar" | "expert" theo số hồ sơ nhân viên đã xử lý."""
    if handled_cases < NOVICE_MAX_CASES:
        return "novice"
    if handled_cases < FAMILIAR_MAX_CASES:
        return "familiar"
    return "expert"
