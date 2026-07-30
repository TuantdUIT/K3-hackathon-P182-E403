"""Engine, session factory và khởi tạo DB (idempotent)."""

from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from ..config import get_settings
from .security import hash_password
from .tables import Base, Customer, SalesStaff, build_customer_code

# 3 nhân viên demo cho Admin Portal. Mật khẩu in ra ở README để chấm demo.
DEMO_STAFF = [
    {
        "name": "Nguyễn Lan Anh",
        "initials": "LA",
        "email": "lan.anh@vinfast.vn",
        "phone": "0901234501",
        "password": "LanAnh@2026",
    },
    {
        "name": "Trần Minh Quân",
        "initials": "MQ",
        "email": "minh.quan@vinfast.vn",
        "phone": "0901234502",
        "password": "MinhQuan@2026",
    },
    {
        "name": "Phạm Thanh Hà",
        "initials": "TH",
        "email": "thanh.ha@vinfast.vn",
        "phone": "0901234503",
        "password": "ThanhHa@2026",
    },
]


def _ensure_sqlite_dir(database_url: str) -> None:
    """SQLAlchemy không tự tạo thư mục chứa file .db — phải tự lo."""
    url = make_url(database_url)
    if url.drivername.startswith("sqlite") and url.database and url.database != ":memory:":
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)


def _build_engine() -> Engine:
    settings = get_settings()
    _ensure_sqlite_dir(settings.database_url)
    connect_args = (
        {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    )
    return create_engine(settings.database_url, connect_args=connect_args, future=True)


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_session() -> Iterator[Session]:
    """Dependency của FastAPI."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def seed_sales_staff(session: Session) -> None:
    """Thêm nhân viên demo còn thiếu. Chạy lại nhiều lần vẫn an toàn."""
    for staff in DEMO_STAFF:
        exists = session.scalar(select(SalesStaff).where(SalesStaff.email == staff["email"]))
        if exists:
            continue
        session.add(
            SalesStaff(
                name=staff["name"],
                initials=staff["initials"],
                email=staff["email"],
                phone=staff["phone"],
                password_hash=hash_password(staff["password"]),
                is_active=True,
            )
        )
    session.commit()


def seed_demo_customers(session: Session) -> int:
    """Tạo vài khách mẫu — CHỈ dùng khi demo thủ công, không gọi lúc khởi động.

    Bảng khách phải trống cho tới khi có đăng ký thật, nếu không phần nghiệm thu
    "bản ghi mới xuất hiện trong Admin Portal" sẽ lẫn với dữ liệu giả.
    """
    if session.scalar(select(Customer).limit(1)) is not None:
        return 0

    staff = list(session.scalars(select(SalesStaff).order_by(SalesStaff.id)))
    today = date.today()
    samples = [
        ("Lê Quốc Bảo", "0912345678", "vf8", "VF 8", 1, "09:30", "Cầu Giấy", "Đã liên hệ"),
        ("Đỗ Thu Trang", "0987654321", "vf3", "VF 3", 2, "13:30", "Hoàn Kiếm", "Mới"),
        ("Hoàng Văn Nam", "0977123456", "vf9", "VF 9", 3, "15:00", "Hà Đông", "Đặt lịch"),
    ]

    created = 0
    for index, (name, phone, vehicle_id, model, offset, slot, ward, status) in enumerate(samples):
        customer = Customer(
            name=name,
            phone=phone,
            email=None,
            vehicle_id=vehicle_id,
            model=model,
            test_drive_date=today + timedelta(days=offset),
            test_drive_time=slot,
            province="Hà Nội",
            ward=ward,
            note=None,
            status=status,
            source="Website",
            sales_staff_id=staff[index % len(staff)].id if staff else None,
        )
        session.add(customer)
        session.flush()
        customer.code = build_customer_code(customer.id)
        created += 1

    session.commit()
    return created


def init_db() -> None:
    """Tạo bảng + seed nhân viên. Gọi được nhiều lần, không hỏng dữ liệu cũ."""
    _ensure_sqlite_dir(get_settings().database_url)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        seed_sales_staff(session)
