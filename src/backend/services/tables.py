"""Định nghĩa bảng SQLAlchemy 2.0."""

from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Mã hiển thị cho khách: id 1 -> VF-24082
CODE_OFFSET = 24081


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


def build_customer_code(customer_id: int) -> str:
    """Mã hiển thị cho khách. Chỉ gọi được sau `flush()` vì cần primary key."""
    return f"VF-{CODE_OFFSET + customer_id}"
