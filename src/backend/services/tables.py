"""Định nghĩa bảng SQLAlchemy 2.0."""

from datetime import UTC, date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Mã hiển thị cho khách: id 1 -> VF-24082
CODE_OFFSET = 24081

# Mã hồ sơ định giá xe cũ: id 1 -> DG-1001
APPRAISAL_CODE_OFFSET = 1000


class Base(DeclarativeBase):
    pass


class SalesStaff(Base):
    __tablename__ = "sales_staff"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    initials: Mapped[str] = mapped_column(String(8), nullable=False)
    email: Mapped[str] = mapped_column(String(180), nullable=False, unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    customers: Mapped[list["Customer"]] = relationship(back_populates="sales_staff")


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(16), nullable=True, unique=True, index=True)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(180), nullable=True)

    vehicle_id: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)

    test_drive_date: Mapped[date] = mapped_column(Date, nullable=False)
    test_drive_time: Mapped[str] = mapped_column(String(5), nullable=False)

    province: Mapped[str] = mapped_column(String(60), nullable=False, default="Hà Nội")
    ward: Mapped[str] = mapped_column(String(120), nullable=False)
    address_detail: Mapped[str | None] = mapped_column(String(255), nullable=True)

    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    marketing_opt_in: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="Mới", index=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="Website")

    sales_staff_id: Mapped[int | None] = mapped_column(
        ForeignKey("sales_staff.id"), nullable=True
    )
    sales_staff: Mapped[SalesStaff | None] = relationship(back_populates="customers")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )


class UsedCarPrice(Base):
    """Giá thị trường xe cũ cùng đời — vế trái của công thức A.

    Bảng TRA CỨU, không phải giao dịch. Không có xe trong bảng này thì không tính
    được A, hồ sơ phải chuyển thẩm định thủ công chứ không được đoán giá.
    """

    __tablename__ = "used_car_prices"
    __table_args__ = (UniqueConstraint("make", "model", "year", "trim"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    make: Mapped[str] = mapped_column(String(60), nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)

    # Chuỗi rỗng chứ KHÔNG phải NULL khi xe không phân bản: trong SQL NULL != NULL,
    # để NULL là UniqueConstraint mất tác dụng và cùng một xe nhập được nhiều lần
    # với nhiều giá khác nhau.
    trim: Mapped[str] = mapped_column(String(60), nullable=False, default="")

    # Khoá so khớp đã bỏ dấu/bỏ ký tự lạ, sinh bằng `catalog.squash("<make> <model>")`.
    # Sales gõ "honda city", "Honda  City" đều phải ra cùng một dòng.
    lookup_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)

    market_price: Mapped[int] = mapped_column(Integer, nullable=False)  # VND


class TradeInAppraisal(Base):
    """Hồ sơ định giá một xe cũ — BƯỚC 1 của công thức.

    Tách khỏi `trade_in_quotes` vì A không phụ thuộc xe mới: khách định giá một
    lần rồi so nhiều mẫu VinFast, mỗi mẫu là một quote trên cùng hồ sơ này.
    """

    __tablename__ = "trade_in_appraisals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(16), nullable=True, unique=True, index=True)

    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    customer: Mapped["Customer"] = relationship()

    sales_staff_id: Mapped[int | None] = mapped_column(
        ForeignKey("sales_staff.id"), nullable=True, index=True
    )
    sales_staff: Mapped[SalesStaff | None] = relationship()

    # --- xe cũ ---
    make: Mapped[str] = mapped_column(String(60), nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    trim: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    plate_no: Mapped[str | None] = mapped_column(String(20), nullable=True)
    odo_km: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Ngày ĐĂNG KÝ LẦN ĐẦU, không phải `year`: tiêu chí ODO chấm theo km/năm và
    # điều kiện "sở hữu ≥ 6 tháng, dưới 7 năm" đều cần tuổi xe theo tháng.
    first_registration_date: Mapped[date] = mapped_column(Date, nullable=False)

    # passed | rejected_age | rejected_ownership | rejected_flood_damaged | ...
    eligibility_status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)

    # --- kết quả bước 1 ---
    total_score_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    market_price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    repair_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # A = market_price × total_score_pct/100 − repair_cost.
    # Lưu lại dù suy ra được: đây là con số đã đọc cho khách, đối soát sau này
    # phải đọc đúng nó chứ không tính lại.
    value_a: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Tham chiếu phiếu thẩm định bên thứ ba + hạn SLA để hệ thống tự nhắc.
    smart_solution_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # draft | rejected | appraised | quoted | blocked | accepted
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    checklist_done: Mapped[str] = mapped_column(String(120), nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )

    scores: Mapped[list["AppraisalScore"]] = relationship(
        back_populates="appraisal", cascade="all, delete-orphan"
    )
    quotes: Mapped[list["TradeInQuote"]] = relationship(
        back_populates="appraisal", cascade="all, delete-orphan"
    )


class AppraisalScore(Base):
    """Điểm từng tiêu chí — 8 DÒNG mỗi hồ sơ, không phải 8 cột.

    Thêm tiêu chí là thêm dòng, không migrate. Trọng số KHÔNG lưu ở đây: nó là
    hằng số trong `appraisal_rules.CRITERIA_WEIGHT`, lưu lại chỉ tạo nguồn sự
    thật thứ hai để hai bên trôi khỏi nhau.
    """

    __tablename__ = "appraisal_scores"
    __table_args__ = (UniqueConstraint("appraisal_id", "criteria_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    appraisal_id: Mapped[int] = mapped_column(
        ForeignKey("trade_in_appraisals.id"), nullable=False, index=True
    )
    appraisal: Mapped["TradeInAppraisal"] = relationship(back_populates="scores")

    criteria_code: Mapped[str] = mapped_column(String(20), nullable=False)

    # Tỷ lệ đạt 0.0..1.0. Điểm thực = ratio × CRITERIA_WEIGHT[criteria_code].
    achieved_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # True = thẩm định viên chưa chấm, hệ thống tạm lấy mức mặc định. Phải hiện
    # rõ ở mọi chỗ đọc, nếu không con số ước lượng bị đọc như số đã thẩm định.
    estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    note: Mapped[str | None] = mapped_column(String(255), nullable=True)


class TradeInQuote(Base):
    """Báo giá cho khách — BƯỚC 2 và 3, gắn với một mẫu xe MỚI."""

    __tablename__ = "trade_in_quotes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    appraisal_id: Mapped[int] = mapped_column(
        ForeignKey("trade_in_appraisals.id"), nullable=False, index=True
    )
    appraisal: Mapped["TradeInAppraisal"] = relationship(back_populates="quotes")

    # Một trong 14 mẫu của `catalog.VEHICLES`, cùng không gian id với
    # `customers.vehicle_id`.
    vehicle_id: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)

    list_price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_fees: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    value_b: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    promo_new_car: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trade_in_bonus: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    value_a: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # C = B − A − khuyến mãi − ưu đãi đổi xe. Âm nghĩa là VinFast phải trả lại
    # tiền cho khách — hợp lệ về toán, chặn ở tầng nghiệp vụ chứ không ở đây.
    amount_c: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    handover_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )


def build_customer_code(customer_id: int) -> str:
    """Mã hiển thị cho khách. Chỉ gọi được sau `flush()` vì cần primary key."""
    return f"VF-{CODE_OFFSET + customer_id}"


def build_appraisal_code(appraisal_id: int) -> str:
    """Mã hồ sơ định giá. Cũng chỉ gọi được sau `flush()`."""
    return f"DG-{APPRAISAL_CODE_OFFSET + appraisal_id}"
