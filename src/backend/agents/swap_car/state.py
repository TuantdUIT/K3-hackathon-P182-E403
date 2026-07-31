"""State của agent đổi xe (nghiệp vụ 2).

Cố tình KHÔNG dùng lại `shared/state.py`. Hai agent kia là bài toán ĐIỀN FORM
(bóc field -> điền -> gửi), còn agent này là CHẨN ĐOÁN (kiểm tra điều kiện ->
chấm điểm -> tính tiền -> gate checklist). Nhét chung một TypedDict thì `draft`
mang hai nghĩa khác nhau tuỳ agent, và `plan_node` dùng chung sẽ sinh action cho
những ô không tồn tại ở form bên kia.

Phần DÙNG LẠI thật sự là giao thức con trỏ ảo — `action_queue` / `current_action`
/ `run_seq` giữ nguyên tên và hình dạng để `useAgentActionRunner.js` ở frontend
chạy được với cả ba agent mà không phải sửa dòng nào.

BẪY #1 vẫn áp dụng: `TypedDict` PHẢI lấy từ `typing_extensions`, không phải
`typing` — Python 3.11 trong container thiếu metadata mà `ag_ui_langgraph` cần.
"""

from typing import Annotated, Any, Literal

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from ...services.appraisal_rules import SCORED_CRITERIA

RunKind = Literal["full", "correction"]

# Form gồm 4 khối, xếp trên màn hình theo đúng thứ tự này:
#   1. Thông tin xe cũ   2. Điều kiện loại trừ cứng
#   3. Chấm điểm thẩm định   4. Xe mới khách muốn đổi
# Hai khối ô nhập nằm ở hai ĐẦU form nên phải tách ra: gộp chung một tuple thì
# `plan_node` nạp cả `vehicle_id`/`repair_cost` ngay từ đầu hàng đợi, con trỏ
# nhảy thẳng xuống khối cuối rồi mới ngược lên bảng chấm điểm.
OLD_CAR_FIELDS: tuple[str, ...] = (
    "make",
    "model",
    "year",
    "trim",
    "plate_no",
    "odo_km",
    "first_registration_date",
)

NEW_CAR_FIELDS: tuple[str, ...] = (
    "vehicle_id",
    "repair_cost",
)

# Toàn bộ ô nhập của form, dùng khi cần duyệt draft mà không quan tâm khối nào.
FORM_FIELDS: tuple[str, ...] = OLD_CAR_FIELDS + NEW_CAR_FIELDS

# Thiếu một trong số này thì không chạy được cổng loại trừ lẫn công thức A.
# `trim`, `plate_no`, `repair_cost` cố tình KHÔNG bắt buộc: xe không phân bản là
# chuyện thường, và chi phí sửa chữa chỉ biết sau khi thẩm định.
REQUIRED_FIELDS: tuple[str, ...] = (
    "make",
    "model",
    "year",
    "odo_km",
    "first_registration_date",
    "vehicle_id",
)

FIELD_LABELS: dict[str, str] = {
    "make": "Hãng xe cũ",
    "model": "Dòng xe cũ",
    "year": "Đời xe",
    "trim": "Phiên bản",
    "plate_no": "Biển số",
    "odo_km": "Số km đã đi",
    "first_registration_date": "Ngày đăng ký lần đầu",
    "repair_cost": "Chi phí dọn dẹp/sửa chữa",
    "vehicle_id": "Xe mới muốn đổi",
}

# Ô nhập chữ -> gõ từng ký tự; ô chọn/ngày -> set thẳng giá trị.
TYPE_FIELDS: set[str] = {"make", "model", "trim", "plate_no", "odo_km", "repair_cost"}
SELECT_FIELDS: set[str] = {"year", "first_registration_date", "vehicle_id"}

# 7 ô chấm điểm (ODO do hệ thống tự tính nên không có ô nhập).
SCORE_FIELDS: tuple[str, ...] = tuple(f"score_{code}" for code in SCORED_CRITERIA)

# 4 cờ loại trừ cứng. Agent CHỈ bật cờ khi sales nói rõ, không tự suy diễn.
FLAG_FIELDS: tuple[str, ...] = (
    "flag_flood_damaged",
    "flag_structural_damage",
    "flag_odo_tampered",
    "flag_missing_papers",
)


class SwapCarState(TypedDict, total=False):
    messages: Annotated[list[Any], add_messages]

    # Kênh cố định "crm": agent này chỉ chạy trong Admin Portal, không phơi ra
    # trang khách. Node `init` tự đóng dấu, không nhờ frontend set.
    channel: Literal["crm"]

    # Khách đang định giá — sales chọn ở bảng bên trái, frontend đẩy vào bằng
    # `setState`. Không có mã khách thì không ghi được hồ sơ.
    customer_code: str | None
    customer_name: str | None
    sales_staff_id: int | None

    # Mức hướng dẫn của nhân viên này (novice | familiar | expert). Quyết định
    # node `explain` nói dài hay ngắn — đây là phần cá nhân hoá của nghiệp vụ 2.
    experience: str

    # Thông tin xe cũ đang gom
    draft: dict[str, Any]
    missing_fields: list[str]
    flags: dict[str, bool]
    levels: dict[str, str]

    # Con trỏ ảo — cùng giao thức với 2 agent kia
    action_queue: list[dict[str, Any]]
    current_action: dict[str, Any] | None
    filled_fields: list[str]
    run_seq: int
    run_kind: RunKind

    # Cổng loại trừ
    eligibility_status: str
    eligibility_checks: list[dict[str, Any]]

    # Kết quả thẩm định (bước 1)
    appraisal_code: str | None
    market_price: int
    total_score_pct: float
    repair_cost: int
    value_a: int
    estimated_criteria: list[str]
    sla_hours: int

    # Báo giá (bước 2 & 3)
    quote: dict[str, Any]

    # Checklist 4 việc
    checklist_done: list[str]
    checklist_missing: list[str]
    handover_date: str | None

    # Điều phối
    awaiting: str | None
    revise_rounds: int

    # Vòng sửa HỒ SƠ (khác `revise_rounds` — vòng sửa GIÁ). Sales soát lại thông
    # tin xe cũ sau khi con trỏ điền xong, gõ chỗ sai vào khung chat.
    # `changed_fields` là danh sách ô thật sự đổi, để `plan_node` chỉ điền lại
    # đúng mấy ô đó thay vì diễn lại cả form từ đầu.
    correction_rounds: int
    changed_fields: list[str]

    status: str

    # Dùng cho test gọi node trực tiếp, không đi qua messages
    query: str | None
    response: str | None
    error: str | None


def empty_state() -> SwapCarState:
    return SwapCarState(
        messages=[],
        channel="crm",
        customer_code=None,
        customer_name=None,
        sales_staff_id=None,
        experience="novice",
        draft={},
        missing_fields=[],
        flags={},
        levels={},
        action_queue=[],
        current_action=None,
        filled_fields=[],
        run_seq=0,
        run_kind="full",
        eligibility_status="",
        eligibility_checks=[],
        appraisal_code=None,
        market_price=0,
        total_score_pct=0.0,
        repair_cost=0,
        value_a=0,
        estimated_criteria=[],
        sla_hours=0,
        quote={},
        checklist_done=[],
        checklist_missing=[],
        handover_date=None,
        awaiting=None,
        revise_rounds=0,
        correction_rounds=0,
        changed_fields=[],
        status="idle",
        query=None,
        response=None,
        error=None,
    )
