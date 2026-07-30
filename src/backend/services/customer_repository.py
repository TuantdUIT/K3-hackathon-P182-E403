"""Truy cập bảng Customer.

Cả form thủ công (POST /test-drives) và node `submit` của agent đều đi qua
`create_test_drive` ở đây — một đường ghi duy nhất, không có nhánh riêng cho bot.
"""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from ..models.schemas import TestDriveCreate
from .tables import Customer, SalesStaff, build_customer_code


def _next_staff_id(session: Session) -> int | None:
    """Chia khách cho nhân viên theo vòng tròn dựa trên số khách đã có."""
    staff_ids = list(session.scalars(select(SalesStaff.id).order_by(SalesStaff.id)))
    if not staff_ids:
        return None
    total = session.scalar(select(Customer.id).order_by(Customer.id.desc()).limit(1)) or 0
    return staff_ids[total % len(staff_ids)]


def create_test_drive(session: Session, payload: TestDriveCreate) -> Customer:
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
