"""REST API cho trang khách hàng và Admin Portal."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..models.schemas import (
    CustomerOut,
    DuplicateCheckOut,
    LoginRequest,
    LoginResponse,
    SalesStaffOut,
    StatusUpdate,
    TestDriveCreate,
)
from ..services import customer_repository as repo
from ..services.customer_repository import DuplicatePhoneError
from ..services.database import get_session
from ..services.security import verify_password

router = APIRouter(prefix="/api/v1", tags=["vinfast"])


@router.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, session: Session = Depends(get_session)) -> LoginResponse:
    staff = repo.find_staff_by_email(session, payload.email)

    # Một thông báo chung cho cả 2 trường hợp sai — không tiết lộ email nào tồn tại.
    if staff is None or not staff.is_active or not verify_password(payload.password, staff.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng.",
        )

    return LoginResponse(staff=SalesStaffOut.model_validate(staff))


@router.post("/test-drives", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
def create_test_drive(
    payload: TestDriveCreate, session: Session = Depends(get_session)
) -> CustomerOut:
    try:
        customer = repo.create_test_drive(session, payload)
    except DuplicatePhoneError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Số điện thoại đã đăng ký cho khách {exc.code} — {exc.name}. "
                "Vui lòng kiểm tra lại."
            ),
        ) from exc
    return CustomerOut.model_validate(customer)


# PHẢI khai báo TRƯỚC "/customers/{code}/status": FastAPI match theo thứ tự đăng ký,
# để sau thì "check-duplicate" bị hiểu là giá trị của {code}.
@router.get("/customers/check-duplicate", response_model=DuplicateCheckOut)
def check_duplicate(
    phone: str | None = Query(default=None),
    name: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> DuplicateCheckOut:
    phone_match, name_matches = repo.find_duplicates(session, phone=phone, name=name)
    return DuplicateCheckOut(
        phone_match=CustomerOut.model_validate(phone_match) if phone_match else None,
        name_matches=[CustomerOut.model_validate(c) for c in name_matches],
    )


@router.get("/customers", response_model=list[CustomerOut])
def list_customers(
    search: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    session: Session = Depends(get_session),
) -> list[CustomerOut]:
    customers = repo.list_customers(session, search=search, status=status_filter)
    return [CustomerOut.model_validate(customer) for customer in customers]


@router.patch("/customers/{code}/status", response_model=CustomerOut)
def update_customer_status(
    code: str, payload: StatusUpdate, session: Session = Depends(get_session)
) -> CustomerOut:
    customer = repo.update_status(session, code, payload.status)
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy khách hàng có mã {code}.",
        )
    return CustomerOut.model_validate(customer)


@router.get("/sales-staff", response_model=list[SalesStaffOut])
def list_sales_staff(session: Session = Depends(get_session)) -> list[SalesStaffOut]:
    return [SalesStaffOut.model_validate(staff) for staff in repo.list_sales_staff(session)]


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
