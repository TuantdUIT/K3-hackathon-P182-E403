"""Truy cập dữ liệu định giá xe cũ + toàn bộ phép tính A / B / C.

Cả form thủ công trong tab "Định giá xe" lẫn agent `swap_car` đều đi qua đây —
một đường ghi duy nhất, không có nhánh riêng cho bot. Nhờ vậy luật (cổng loại
trừ, công thức, chặn mềm checklist) chỉ cài MỘT chỗ là phủ cả hai đường, giống
cách `customer_repository.create_test_drive` đang làm với chặn trùng SĐT.

Mọi hàm tính toán ở đây là hàm THUẦN theo nghĩa không gọi LLM: chạy được khi
không có API key, và test không cần mock gì.
"""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..agents.shared.catalog import squash, vehicle_name, vehicle_price
from . import appraisal_rules as rules
from .tables import (
    AppraisalScore,
    Customer,
    TradeInAppraisal,
    TradeInQuote,
    UsedCarPrice,
    build_appraisal_code,
)
from .used_car_seed import USED_CAR_PRICES


class NoMarketPriceError(Exception):
    """Không có giá thị trường cho xe này — phải chuyển thẩm định thủ công."""

    def __init__(self, make: str, model: str, year: int):
        self.make = make
        self.model = model
        self.year = year
        super().__init__(f"Chưa có giá thị trường cho {make} {model} đời {year}.")


# --------------------------------------------------------------------------
# Bảng giá xe cũ
# --------------------------------------------------------------------------

def seed_used_car_prices(session: Session) -> int:
    """Nạp bảng giá còn thiếu. Chạy lại nhiều lần vẫn an toàn."""
    existing = {
        (row.make, row.model, row.year, row.trim)
        for row in session.scalars(select(UsedCarPrice))
    }

    created = 0
    for make, model, year, trim, price in USED_CAR_PRICES:
        if (make, model, year, trim) in existing:
            continue
        session.add(
            UsedCarPrice(
                make=make,
                model=model,
                year=year,
                trim=trim,
                lookup_key=squash(f"{make} {model}"),
                market_price=price,
            )
        )
        created += 1

    if created:
        session.commit()
    return created


def find_market_price(
    session: Session, *, make: str, model: str, year: int, trim: str = ""
) -> UsedCarPrice | None:
    """Tra giá theo (hãng, dòng, đời, phiên bản).

    Phiên bản khớp lỏng: sales nói "Honda City 2019" mà bảng chỉ có bản "G" thì
    vẫn dùng được. Đời xe thì KHÔNG nới — City 2019 và 2021 chênh cả trăm triệu,
    lấy nhầm đời là sai số lớn hơn cả phần chấm điểm.
    """
    key = squash(f"{make} {model}")
    rows = list(
        session.scalars(
            select(UsedCarPrice).where(
                UsedCarPrice.lookup_key == key, UsedCarPrice.year == int(year)
            )
        )
    )
    if not rows:
        return None

    wanted = squash(trim or "")
    if wanted:
        for row in rows:
            if squash(row.trim) == wanted:
                return row

    # Không nói phiên bản (hoặc phiên bản lạ) -> lấy bản rẻ nhất. Báo thấp rồi
    # điều chỉnh lên được, báo cao rồi hạ xuống là mất khách.
    return min(rows, key=lambda row: row.market_price)


def list_known_models(session: Session) -> list[dict[str, object]]:
    """Danh mục xe cũ tra được, gộp theo (hãng, dòng) để UI gợi ý."""
    rows = list(session.scalars(select(UsedCarPrice).order_by(UsedCarPrice.make, UsedCarPrice.model)))
    grouped: dict[tuple[str, str], list[int]] = {}
    for row in rows:
        grouped.setdefault((row.make, row.model), []).append(row.year)
    return [
        {"make": make, "model": model, "years": sorted(set(years))}
        for (make, model), years in grouped.items()
    ]


# --------------------------------------------------------------------------
# Bước 1 — tính A
# --------------------------------------------------------------------------

def build_scores(
    *,
    odo_km: int,
    first_registration_date: date,
    levels: dict[str, str] | None = None,
    today: date | None = None,
) -> list[dict[str, object]]:
    """Dựng đủ 8 dòng điểm.

    ODO tính bằng công thức, 7 tiêu chí còn lại lấy mức thẩm định viên chọn.
    Tiêu chí chưa chấm được đánh dấu `estimated=True` — con số ước lượng phải đi
    kèm nhãn tới tận màn hình, không được đọc như số đã thẩm định.
    """
    levels = levels or {}
    rows: list[dict[str, object]] = []

    for code, _group, label, weight in rules.APPRAISAL_CRITERIA:
        if code == rules.ODO_CODE:
            ratio = rules.odo_ratio(odo_km, first_registration_date, today)
            estimated = False
            level = None
        else:
            level = levels.get(code)
            ratio = rules.level_ratio(level)
            estimated = level is None

        rows.append(
            {
                "criteria_code": code,
                "label": label,
                "weight_pct": weight,
                "level": level or (rules.DEFAULT_LEVEL if estimated else None),
                "achieved_ratio": round(float(ratio), 4),
                "achieved_pct": round(weight * float(ratio), 2),
                "estimated": estimated,
            }
        )

    return rows


def total_score_pct(scores: list[dict[str, object]]) -> float:
    return round(sum(float(row["achieved_pct"]) for row in scores), 2)


def compute_value_a(market_price: int, score_pct: float, repair_cost: int = 0) -> int:
    """A = giá thị trường × tổng điểm − chi phí sửa chữa. Không cho xuống dưới 0."""
    raw = market_price * (score_pct / 100.0) - max(int(repair_cost), 0)
    return max(int(round(raw)), 0)


# --------------------------------------------------------------------------
# Bước 2 & 3 — tính B và C
# --------------------------------------------------------------------------

def compute_quote(vehicle_id: str, value_a: int) -> dict[str, object]:
    """B = giá niêm yết + phí lăn bánh; C = B − A − khuyến mãi − ưu đãi đổi xe."""
    prices = vehicle_price(vehicle_id)
    if prices is None:
        raise ValueError(f"Mẫu xe mới không có trong danh mục: {vehicle_id}")

    list_price, price_from = prices
    fees = rules.rolling_fees(list_price)
    total_fees = sum(fees.values())
    value_b = list_price + total_fees

    promo = max(list_price - price_from, 0)
    bonus = rules.TRADE_IN_BONUS
    amount_c = value_b - value_a - promo - bonus

    return {
        "vehicle_id": vehicle_id,
        "model": vehicle_name(vehicle_id) or vehicle_id,
        "list_price": list_price,
        "fees": fees,
        "total_fees": total_fees,
        "value_b": value_b,
        "promo_new_car": promo,
        "trade_in_bonus": bonus,
        "value_a": value_a,
        "amount_c": amount_c,
    }


# --------------------------------------------------------------------------
# Ghi hồ sơ
# --------------------------------------------------------------------------

def _staff_case_count(session: Session, staff_id: int | None) -> int:
    if staff_id is None:
        return 0
    stmt = select(TradeInAppraisal.id).where(TradeInAppraisal.sales_staff_id == staff_id)
    return len(list(session.scalars(stmt)))


def experience_of(session: Session, staff_id: int | None) -> str:
    """Mức hướng dẫn cho nhân viên này — cơ sở của progressive autonomy."""
    return rules.experience_level(_staff_case_count(session, staff_id))


def create_appraisal(
    session: Session,
    *,
    customer_id: int,
    make: str,
    model: str,
    year: int,
    trim: str = "",
    plate_no: str | None = None,
    odo_km: int = 0,
    first_registration_date: date,
    ownership_months: int | None = None,
    flags: dict[str, bool] | None = None,
    levels: dict[str, str] | None = None,
    repair_cost: int = 0,
    sales_staff_id: int | None = None,
    today: date | None = None,
) -> TradeInAppraisal:
    """Chạy cổng loại trừ -> chấm điểm -> tính A, rồi ghi hồ sơ.

    Xe trượt cổng vẫn được GHI LẠI với `status="rejected"`. Không ghi thì hồ sơ
    bị từ chối biến mất khỏi hệ thống, quản lý không đếm được đã loại bao nhiêu
    xe vì lý do gì.
    """
    status_code, checks = rules.check_eligibility(
        first_registration_date=first_registration_date,
        ownership_months=ownership_months,
        flags=flags,
        today=today,
    )

    appraisal = TradeInAppraisal(
        customer_id=customer_id,
        sales_staff_id=sales_staff_id,
        make=make.strip(),
        model=model.strip(),
        year=int(year),
        trim=(trim or "").strip(),
        plate_no=plate_no,
        odo_km=max(int(odo_km), 0),
        first_registration_date=first_registration_date,
        eligibility_status=status_code,
        repair_cost=max(int(repair_cost), 0),
    )

    # `checks` KHÔNG gắn lên object trả về: nó không phải cột, gắn vào thì lần
    # đọc lại từ DB là mất. Ai cần bảng chi tiết thì gọi lại `check_eligibility`
    # — hàm thuần, chạy lại cho đúng kết quả cũ.
    del checks

    if status_code != "passed":
        appraisal.status = "rejected"
        session.add(appraisal)
        session.flush()
        appraisal.code = build_appraisal_code(appraisal.id)
        session.commit()
        return appraisal

    price_row = find_market_price(session, make=make, model=model, year=year, trim=trim)
    if price_row is None:
        raise NoMarketPriceError(make, model, int(year))

    scores = build_scores(
        odo_km=odo_km,
        first_registration_date=first_registration_date,
        levels=levels,
        today=today,
    )
    score_pct = total_score_pct(scores)

    appraisal.market_price = price_row.market_price
    appraisal.total_score_pct = score_pct
    appraisal.value_a = compute_value_a(price_row.market_price, score_pct, repair_cost)
    appraisal.status = "appraised"
    appraisal.sla_due_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(
        hours=rules.SMART_SOLUTION_SLA_HOURS
    )

    session.add(appraisal)
    session.flush()
    appraisal.code = build_appraisal_code(appraisal.id)
    appraisal.smart_solution_ref = f"SS-{appraisal.code}"

    for row in scores:
        session.add(
            AppraisalScore(
                appraisal_id=appraisal.id,
                criteria_code=str(row["criteria_code"]),
                achieved_ratio=float(row["achieved_ratio"]),
                estimated=bool(row["estimated"]),
                note=None if row["level"] is None else rules.LEVEL_LABELS.get(str(row["level"])),
            )
        )

    session.commit()
    return get_appraisal(session, appraisal.code or "") or appraisal


def update_valuation(
    session: Session,
    *,
    code: str,
    repair_cost: int | None = None,
    levels: dict[str, str] | None = None,
) -> dict[str, object] | None:
    """Chấm lại điểm / đổi chi phí sửa chữa rồi tính lại A trên hồ sơ ĐÃ CÓ.

    Cập nhật tại chỗ chứ không tạo hồ sơ mới: vòng "khách chưa đồng ý giá" của
    nghiệp vụ 2 có thể lặp nhiều lần, mỗi lần đẻ một hồ sơ thì bảng đầy bản nháp
    và không biết cái nào là giá đã báo.
    """
    appraisal = get_appraisal(session, code)
    if appraisal is None:
        return None

    if repair_cost is not None:
        appraisal.repair_cost = max(int(repair_cost), 0)

    # Mức chấm cũ đọc ngược từ tỷ lệ đã lưu, để lần sửa này chỉ đụng tiêu chí
    # được nhắc tới và giữ nguyên phần thẩm định viên đã chấm trước đó.
    merged: dict[str, str] = {}
    for score in appraisal.scores:
        if score.criteria_code == rules.ODO_CODE or score.estimated:
            continue
        for level, ratio in rules.LEVELS.items():
            if abs(ratio - score.achieved_ratio) < 1e-6:
                merged[score.criteria_code] = level
                break
    merged.update(levels or {})

    scores = build_scores(
        odo_km=appraisal.odo_km,
        first_registration_date=appraisal.first_registration_date,
        levels=merged,
    )
    appraisal.total_score_pct = total_score_pct(scores)
    appraisal.value_a = compute_value_a(
        appraisal.market_price, appraisal.total_score_pct, appraisal.repair_cost
    )

    by_code = {score.criteria_code: score for score in appraisal.scores}
    for row in scores:
        existing = by_code.get(str(row["criteria_code"]))
        if existing is None:
            continue
        existing.achieved_ratio = float(row["achieved_ratio"])
        existing.estimated = bool(row["estimated"])
        existing.note = None if row["level"] is None else rules.LEVEL_LABELS.get(str(row["level"]))

    session.commit()
    return {
        "code": appraisal.code or "",
        "total_score_pct": appraisal.total_score_pct,
        "repair_cost": appraisal.repair_cost,
        "value_a": appraisal.value_a,
        "estimated": [
            rules.CRITERIA_LABEL[row["criteria_code"]]  # type: ignore[index]
            for row in scores
            if row["estimated"]
        ],
    }


def add_quote(
    session: Session, *, appraisal_code: str, vehicle_id: str
) -> TradeInQuote | None:
    """Tạo báo giá B/C cho một mẫu xe mới trên hồ sơ đã định giá."""
    appraisal = get_appraisal(session, appraisal_code)
    if appraisal is None:
        return None
    if appraisal.eligibility_status != "passed":
        raise ValueError("Hồ sơ đã bị từ chối ở khâu kiểm tra điều kiện, không báo giá được.")

    computed = compute_quote(vehicle_id, appraisal.value_a)

    quote = TradeInQuote(
        appraisal_id=appraisal.id,
        vehicle_id=vehicle_id,
        model=str(computed["model"]),
        list_price=int(computed["list_price"]),
        total_fees=int(computed["total_fees"]),
        value_b=int(computed["value_b"]),
        promo_new_car=int(computed["promo_new_car"]),
        trade_in_bonus=int(computed["trade_in_bonus"]),
        value_a=appraisal.value_a,
        amount_c=int(computed["amount_c"]),
        status="draft",
    )
    session.add(quote)
    appraisal.status = "quoted"
    session.commit()
    return quote


def missing_checklist(done: list[str] | None) -> list[str]:
    """Mục còn thiếu trong checklist 4 việc. Thứ tự giữ đúng như luật."""
    picked = set(done or [])
    return [code for code, _ in rules.CHECKLIST_ITEMS if code not in picked]


def complete_checklist(
    session: Session,
    *,
    appraisal_code: str,
    done: list[str],
    handover_date: date | None = None,
) -> tuple[TradeInAppraisal | None, list[str]]:
    """Chặn MỀM: thiếu mục thì trả về danh sách thiếu và KHÔNG chốt hồ sơ.

    Khác chặn cứng ở `create_test_drive` (raise): ở đây sales vẫn đang làm dở,
    thiếu giấy tờ là chuyện bình thường giữa chừng, không phải lỗi cần ném ra.
    """
    appraisal = get_appraisal(session, appraisal_code)
    if appraisal is None:
        return None, []

    missing = missing_checklist(done)
    appraisal.checklist_done = ",".join(sorted(set(done or [])))

    if missing:
        appraisal.status = "blocked"
        session.commit()
        return appraisal, missing

    appraisal.status = "accepted"
    for quote in appraisal.quotes:
        quote.status = "accepted"
        quote.handover_date = handover_date
    session.commit()
    return get_appraisal(session, appraisal_code), []


# --------------------------------------------------------------------------
# Đọc
# --------------------------------------------------------------------------

def _with_relations():
    return (
        selectinload(TradeInAppraisal.scores),
        selectinload(TradeInAppraisal.quotes),
        selectinload(TradeInAppraisal.customer),
        selectinload(TradeInAppraisal.sales_staff),
    )


def get_appraisal(session: Session, code: str) -> TradeInAppraisal | None:
    stmt = (
        select(TradeInAppraisal)
        .options(*_with_relations())
        .where(TradeInAppraisal.code == code)
    )
    return session.scalar(stmt)


def list_appraisals(
    session: Session, *, customer_code: str | None = None
) -> list[TradeInAppraisal]:
    stmt = select(TradeInAppraisal).options(*_with_relations())
    if customer_code:
        stmt = stmt.join(Customer).where(Customer.code == customer_code)
    stmt = stmt.order_by(TradeInAppraisal.created_at.desc(), TradeInAppraisal.id.desc())
    return list(session.scalars(stmt))
