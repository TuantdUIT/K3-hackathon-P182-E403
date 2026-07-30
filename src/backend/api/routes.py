"""REST API cho trang khách hàng và Admin Portal."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..models.schemas import (
    AppraisalCreate,
    AppraisalOut,
    ChecklistUpdate,
    CriteriaOut,
    CustomerOut,
    DuplicateCheckOut,
    EligibilityCheckOut,
    LoginRequest,
    LoginResponse,
    QuoteCreate,
    SalesStaffOut,
    StatusUpdate,
    TestDriveCreate,
    TradeInQuoteOut,
)
from ..services import appraisal_repository as appraisal_repo
from ..services import appraisal_rules as rules
from ..services import customer_repository as repo
from ..services.appraisal_repository import NoMarketPriceError
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


# --------------------------------------------------------------------------
# Nghiệp vụ 2 — định giá xe cũ
# --------------------------------------------------------------------------

@router.get("/appraisals/criteria", response_model=list[CriteriaOut])
def list_criteria() -> list[CriteriaOut]:
    """Bảng 8 tiêu chí. UI dựng form chấm điểm từ đây, không hardcode lại trọng số."""
    return [
        CriteriaOut(
            code=code,
            group=group,
            label=label,
            weight_pct=weight,
            auto=code == rules.ODO_CODE,
        )
        for code, group, label, weight in rules.APPRAISAL_CRITERIA
    ]


@router.get("/appraisals/used-car-models")
def list_used_car_models(session: Session = Depends(get_session)) -> list[dict]:
    """Danh mục xe cũ tra được giá — ngoài danh sách này phải thẩm định thủ công."""
    return appraisal_repo.list_known_models(session)


# PHẢI đứng TRƯỚC "/appraisals/{code}" — cùng lý do với "/customers/check-duplicate".
@router.get("/appraisals", response_model=list[AppraisalOut])
def list_appraisals(
    customer_code: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[AppraisalOut]:
    rows = appraisal_repo.list_appraisals(session, customer_code=customer_code)
    return [AppraisalOut.model_validate(row) for row in rows]


@router.post("/appraisals", response_model=AppraisalOut, status_code=status.HTTP_201_CREATED)
def create_appraisal(
    payload: AppraisalCreate, session: Session = Depends(get_session)
) -> AppraisalOut:
    customer = repo.get_customer_by_code(session, payload.customer_code)
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy khách hàng có mã {payload.customer_code}.",
        )

    try:
        appraisal = appraisal_repo.create_appraisal(
            session,
            customer_id=customer.id,
            make=payload.make,
            model=payload.model,
            year=payload.year,
            trim=payload.trim,
            plate_no=payload.plate_no,
            odo_km=payload.odo_km,
            first_registration_date=payload.first_registration_date,
            ownership_months=payload.ownership_months,
            flags=payload.flags,
            levels=payload.levels,
            repair_cost=payload.repair_cost,
            sales_staff_id=payload.sales_staff_id,
        )
    except NoMarketPriceError as exc:
        # 422 chứ không phải 500: dữ liệu gửi lên hợp lệ, chỉ là hệ thống chưa có
        # giá tham chiếu cho xe đó nên phải chuyển thẩm định thủ công.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Chưa có giá thị trường cho {exc.make} {exc.model} đời {exc.year}. "
                "Hồ sơ cần thẩm định viên định giá thủ công."
            ),
        ) from exc

    return AppraisalOut.model_validate(appraisal)


@router.post("/appraisals/eligibility", response_model=list[EligibilityCheckOut])
def preview_eligibility(
    payload: AppraisalCreate, session: Session = Depends(get_session)  # noqa: ARG001
) -> list[EligibilityCheckOut]:
    """Chạy thử cổng loại trừ mà KHÔNG ghi hồ sơ — cho UI hiện đèn xanh/đỏ ngay."""
    _status, checks = rules.check_eligibility(
        first_registration_date=payload.first_registration_date,
        ownership_months=payload.ownership_months,
        flags=payload.flags,
    )
    return [EligibilityCheckOut(**check) for check in checks]


@router.get("/appraisals/{code}", response_model=AppraisalOut)
def get_appraisal(code: str, session: Session = Depends(get_session)) -> AppraisalOut:
    appraisal = appraisal_repo.get_appraisal(session, code)
    if appraisal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy hồ sơ định giá có mã {code}.",
        )
    return AppraisalOut.model_validate(appraisal)


@router.post(
    "/appraisals/{code}/quotes",
    response_model=TradeInQuoteOut,
    status_code=status.HTTP_201_CREATED,
)
def create_quote(
    code: str, payload: QuoteCreate, session: Session = Depends(get_session)
) -> TradeInQuoteOut:
    try:
        quote = appraisal_repo.add_quote(session, appraisal_code=code, vehicle_id=payload.vehicle_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    if quote is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy hồ sơ định giá có mã {code}.",
        )
    return TradeInQuoteOut.model_validate(quote)


@router.patch("/appraisals/{code}/checklist", response_model=AppraisalOut)
def update_checklist(
    code: str, payload: ChecklistUpdate, session: Session = Depends(get_session)
) -> AppraisalOut:
    """Chặn MỀM: thiếu mục vẫn trả 200 kèm hồ sơ ở trạng thái `blocked`.

    Không dùng 4xx vì đây không phải lỗi của người gửi — sales đang làm dở,
    thiếu giấy tờ giữa chừng là chuyện bình thường.
    """
    appraisal, _missing = appraisal_repo.complete_checklist(
        session, appraisal_code=code, done=payload.done, handover_date=payload.handover_date
    )
    if appraisal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy hồ sơ định giá có mã {code}.",
        )
    return AppraisalOut.model_validate(appraisal)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
