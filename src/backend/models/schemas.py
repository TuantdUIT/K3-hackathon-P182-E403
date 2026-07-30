"""Schemas pydantic v2 dùng chung cho API và agent."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

TIME_SLOTS: tuple[str, ...] = ("08:00", "09:30", "11:00", "13:30", "15:00", "16:30")
STATUSES: tuple[str, ...] = ("Mới", "Đã liên hệ", "Đặt lịch", "Không phù hợp")
SOURCES: tuple[str, ...] = ("Website", "Facebook", "Showroom", "Zalo")
PROVINCE = "Hà Nội"


class LoginRequest(BaseModel):
    email: str
    password: str


class SalesStaffOut(BaseModel):
    """Cố tình KHÔNG có `password_hash` — schema này đi ra ngoài qua HTTP."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    initials: str
    email: str
    phone: str
    is_active: bool


class LoginResponse(BaseModel):
    staff: SalesStaffOut
    message: str = "Đăng nhập thành công."


class TestDriveCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str
    email: str | None = None

    vehicle_id: str = Field(min_length=1, max_length=40)
    model: str = Field(min_length=1, max_length=80)

    test_drive_date: date
    test_drive_time: str

    province: str = PROVINCE
    ward: str = Field(min_length=1, max_length=120)
    address_detail: str | None = None

    note: str | None = None
    marketing_opt_in: bool = True
    source: str = "Website"

    @field_validator("name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("Họ tên quá ngắn.")
        return cleaned

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, value: str) -> str:
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) < 10:
            raise ValueError("Số điện thoại phải có ít nhất 10 chữ số.")
        if not digits.isdigit():
            raise ValueError("Số điện thoại chỉ được chứa chữ số.")
        return digits

    @field_validator("email", mode="before")
    @classmethod
    def _blank_email_is_none(cls, value):
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("email")
    @classmethod
    def _check_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError("Email không đúng định dạng.")
        return value

    @field_validator("test_drive_date")
    @classmethod
    def _not_in_the_past(cls, value: date) -> date:
        if value < date.today():
            raise ValueError("Ngày lái thử không được ở quá khứ.")
        return value

    @field_validator("test_drive_time")
    @classmethod
    def _known_slot(cls, value: str) -> str:
        if value not in TIME_SLOTS:
            raise ValueError(f"Giờ lái thử phải thuộc: {', '.join(TIME_SLOTS)}.")
        return value

    @field_validator("province")
    @classmethod
    def _hanoi_only(cls, value: str) -> str:
        if value.strip() != PROVINCE:
            raise ValueError('Chương trình lái thử hiện chỉ áp dụng tại "Hà Nội".')
        return PROVINCE

    @field_validator("source")
    @classmethod
    def _known_source(cls, value: str) -> str:
        if value not in SOURCES:
            raise ValueError(f"Nguồn phải thuộc: {', '.join(SOURCES)}.")
        return value


class StatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def _known_status(cls, value: str) -> str:
        if value not in STATUSES:
            raise ValueError(f"Trạng thái phải thuộc: {', '.join(STATUSES)}.")
        return value


class DuplicateCheckOut(BaseModel):
    """Kết quả tra trùng cho form CRM.

    `phone_match` là điều kiện CỨNG (UI chặn submit), `name_matches` là điều kiện
    MỀM (UI chỉ cảnh báo vàng, vẫn cho tạo).
    """

    phone_match: "CustomerOut | None" = None
    name_matches: list["CustomerOut"] = Field(default_factory=list)


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str | None
    name: str
    phone: str
    email: str | None
    vehicle_id: str
    model: str
    test_drive_date: date
    test_drive_time: str
    province: str
    ward: str
    address_detail: str | None
    note: str | None
    marketing_opt_in: bool
    status: str
    source: str
    created_at: datetime
    sales_staff: SalesStaffOut | None = None


# `DuplicateCheckOut` khai báo trước `CustomerOut` nên phải build lại model sau khi
# `CustomerOut` đã tồn tại, nếu không forward-ref trong annotation vẫn là chuỗi.
DuplicateCheckOut.model_rebuild()


# --------------------------------------------------------------------------
# Nghiệp vụ 2 — đổi xe cũ lấy xe mới
# --------------------------------------------------------------------------

class AppraisalCreate(BaseModel):
    """Hồ sơ định giá xe cũ do sales gửi lên (hoặc agent `swap_car` gửi hộ)."""

    customer_code: str = Field(min_length=1, max_length=16)

    make: str = Field(min_length=1, max_length=60)
    model: str = Field(min_length=1, max_length=80)
    year: int = Field(ge=1990, le=2100)
    trim: str = ""
    plate_no: str | None = None
    odo_km: int = Field(default=0, ge=0)
    first_registration_date: date

    # Không khai thì `check_eligibility` lấy tuổi xe làm cận trên.
    ownership_months: int | None = Field(default=None, ge=0)

    # 4 cờ loại trừ CỨNG: ngập nước, tua km, đâm đụng kết cấu, thiếu giấy tờ.
    flags: dict[str, bool] = Field(default_factory=dict)

    # criteria_code -> mức chấm ("tot" | "kha" | "trung_binh" | "kem").
    # Thiếu tiêu chí nào thì tiêu chí đó bị đánh dấu là ước lượng, không im lặng
    # cho điểm tối đa.
    levels: dict[str, str] = Field(default_factory=dict)

    repair_cost: int = Field(default=0, ge=0)
    sales_staff_id: int | None = None

    @field_validator("first_registration_date")
    @classmethod
    def _not_in_the_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Ngày đăng ký lần đầu không được ở tương lai.")
        return value

    @field_validator("levels")
    @classmethod
    def _known_levels(cls, value: dict[str, str]) -> dict[str, str]:
        from ..services.appraisal_rules import LEVELS, SCORED_CRITERIA

        for code, level in value.items():
            if code not in SCORED_CRITERIA:
                raise ValueError(f"Tiêu chí không hợp lệ: {code}.")
            if level not in LEVELS:
                raise ValueError(f"Mức chấm phải thuộc: {', '.join(LEVELS)}.")
        return value


class QuoteCreate(BaseModel):
    vehicle_id: str = Field(min_length=1, max_length=40)


class ChecklistUpdate(BaseModel):
    done: list[str] = Field(default_factory=list)
    handover_date: date | None = None


class AppraisalScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    criteria_code: str
    achieved_ratio: float
    estimated: bool
    note: str | None = None


class TradeInQuoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    vehicle_id: str
    model: str
    list_price: int
    total_fees: int
    value_b: int
    promo_new_car: int
    trade_in_bonus: int
    value_a: int
    amount_c: int
    status: str
    handover_date: date | None = None
    created_at: datetime


class AppraisalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str | None
    make: str
    model: str
    year: int
    trim: str
    plate_no: str | None
    odo_km: int
    first_registration_date: date
    eligibility_status: str
    total_score_pct: float
    market_price: int
    repair_cost: int
    value_a: int
    smart_solution_ref: str | None
    sla_due_at: datetime | None
    status: str
    checklist_done: str
    created_at: datetime
    customer: CustomerOut | None = None
    sales_staff: SalesStaffOut | None = None
    scores: list[AppraisalScoreOut] = Field(default_factory=list)
    quotes: list[TradeInQuoteOut] = Field(default_factory=list)


class EligibilityCheckOut(BaseModel):
    code: str
    label: str
    passed: bool
    detail: str
    why: str


class CriteriaOut(BaseModel):
    """Bảng tiêu chí cho UI dựng form chấm điểm — nguồn sự thật ở backend."""

    code: str
    group: str
    label: str
    weight_pct: int
    auto: bool  # True = hệ thống tự tính (ODO), người chấm không sửa được
