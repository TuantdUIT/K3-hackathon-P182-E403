"""Truy cập bảng Customer.

Cả form thủ công (POST /test-drives), form CRM và node `submit` của agent đều đi
qua `create_test_drive` ở đây — một đường ghi duy nhất, không có nhánh riêng cho
bot. Nhờ vậy việc chặn trùng số điện thoại chỉ cần cài MỘT chỗ là phủ cả 3 đường.
"""

import re
import unicodedata

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from ..models.schemas import TestDriveCreate
from .tables import Customer, SalesStaff, build_customer_code


class DuplicatePhoneError(Exception):
    """Số điện thoại đã có khách khác dùng. Mang theo mã + tên khách cũ để báo lại."""

    def __init__(self, customer: Customer):
        self.customer = customer
        self.code = customer.code or ""
        self.name = customer.name
        super().__init__(f"Số điện thoại đã đăng ký cho khách {self.code} — {self.name}.")


def normalize_phone(value: str | None) -> str:
    """Chỉ giữ chữ số: "0987 654 321" và "0987-654-321" ra cùng một khoá."""
    return re.sub(r"\D", "", value or "")


def normalize_name(value: str | None) -> str:
    """Khoá so khớp MỀM cho họ tên: bỏ dấu, hạ chữ thường, gộp khoảng trắng.

    "Trần Văn Tuấn", "tran van tuan" và "TRẦN  VĂN   TUẤN" phải cho cùng một khoá.
    `đ` phải xử lý riêng vì NFD không tách được dấu gạch của nó.
    """
    lowered = (value or "").casefold().replace("đ", "d")
    decomposed = unicodedata.normalize("NFD", lowered)
    plain = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return " ".join(plain.split())


def find_duplicates(
    session: Session, *, phone: str | None = None, name: str | None = None
) -> tuple[Customer | None, list[Customer]]:
    """Trả về (khách trùng SĐT, danh sách khách trùng tên).

    Trùng SĐT là điều kiện CỨNG nên so khớp tuyệt đối sau khi chuẩn hoá. Trùng tên
    là điều kiện MỀM, phải bỏ dấu nên không thể so trong SQL (SQLite không có
    unaccent) — lọc trong Python. Dữ liệu demo cỡ vài trăm dòng, chấp nhận quét hết.
    """
    phone_key = normalize_phone(phone)
    name_key = normalize_name(name)
    if not phone_key and not name_key:
        return None, []

    stmt = select(Customer).options(selectinload(Customer.sales_staff))
    stmt = stmt.order_by(Customer.id)
    everyone = list(session.scalars(stmt))

    phone_match = None
    if phone_key:
        phone_match = next(
            (c for c in everyone if normalize_phone(c.phone) == phone_key), None
        )

    name_matches: list[Customer] = []
    if name_key:
        name_matches = [c for c in everyone if normalize_name(c.name) == name_key]

    return phone_match, name_matches


def _next_staff_id(session: Session) -> int | None:
    """Chia khách cho nhân viên theo vòng tròn dựa trên số khách đã có."""
    staff_ids = list(session.scalars(select(SalesStaff.id).order_by(SalesStaff.id)))
    if not staff_ids:
        return None
    total = session.scalar(select(Customer.id).order_by(Customer.id.desc()).limit(1)) or 0
    return staff_ids[total % len(staff_ids)]


def create_test_drive(session: Session, payload: TestDriveCreate) -> Customer:
    # Chặn CỨNG trùng số điện thoại. Đặt ở đây thay vì ở route để cả agent và
    # form CRM cũng bị chặn — chỉ một chỗ cài luật, không thể lách.
    phone_match, _ = find_duplicates(session, phone=payload.phone)
    if phone_match is not None:
        raise DuplicatePhoneError(phone_match)

    customer = Customer(
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        vehicle_id=payload.vehicle_id,
        model=payload.model,
        test_drive_date=payload.test_drive_date,
        test_drive_time=payload.test_drive_time,
        province=payload.province,
        ward=payload.ward,
        address_detail=payload.address_detail,
        note=payload.note,
        marketing_opt_in=payload.marketing_opt_in,
        status="Mới",
        source=payload.source,
        sales_staff_id=_next_staff_id(session),
    )
    session.add(customer)
    session.flush()  # cần id để sinh code
    customer.code = build_customer_code(customer.id)
    session.commit()

    return get_customer_by_code(session, customer.code) or customer


def list_customers(
    session: Session, *, search: str | None = None, status: str | None = None
) -> list[Customer]:
    stmt = select(Customer).options(selectinload(Customer.sales_staff))

    if search:
        needle = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Customer.code.ilike(needle),
                Customer.name.ilike(needle),
                Customer.phone.ilike(needle),
                Customer.model.ilike(needle),
                Customer.ward.ilike(needle),
                Customer.province.ilike(needle),
            )
        )

    if status:
        stmt = stmt.where(Customer.status == status)

    stmt = stmt.order_by(Customer.created_at.desc(), Customer.id.desc())
    return list(session.scalars(stmt))


def get_customer_by_code(session: Session, code: str) -> Customer | None:
    stmt = (
        select(Customer)
        .options(selectinload(Customer.sales_staff))
        .where(Customer.code == code)
    )
    return session.scalar(stmt)


def update_status(session: Session, code: str, status: str) -> Customer | None:
    customer = get_customer_by_code(session, code)
    if customer is None:
        return None
    customer.status = status
    session.commit()
    return get_customer_by_code(session, code)


def list_sales_staff(session: Session) -> list[SalesStaff]:
    return list(session.scalars(select(SalesStaff).order_by(SalesStaff.id)))


def find_staff_by_email(session: Session, email: str) -> SalesStaff | None:
    normalized = email.strip().lower()
    return session.scalar(select(SalesStaff).where(SalesStaff.email == normalized))
