"""State của graph điền form.

BẪY #1 — `TypedDict` PHẢI lấy từ `typing_extensions`, không phải `typing`.
Trên Python 3.11, `ag_ui_langgraph` gọi `get_input_jsonschema()` để mô tả state
cho client; `typing.TypedDict` của 3.11 không mang đủ metadata
(`__required_keys__` / `__orig_bases__` khác nhau) nên hàm đó vỡ ngay ở request
đầu tiên. Máy dev chạy 3.12 sẽ KHÔNG lộ lỗi này, chỉ container 3.11 chết.
"""

from typing import Annotated, Any, Literal

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

RunKind = Literal["full", "correction"]

# Các field của form theo đúng thứ tự con trỏ sẽ đi qua.
FORM_FIELDS: tuple[str, ...] = (
    "name",
    "phone",
    "email",
    "vehicle_id",
    "test_drive_date",
    "test_drive_time",
    "ward",
    "note",
)

REQUIRED_FIELDS: tuple[str, ...] = (
    "name",
    "phone",
    "vehicle_id",
    "test_drive_date",
    "test_drive_time",
    "ward",
)

FIELD_LABELS: dict[str, str] = {
    "name": "Họ và tên",
    "phone": "Số điện thoại",
    "email": "Email",
    "vehicle_id": "Mẫu xe",
    "test_drive_date": "Ngày lái thử",
    "test_drive_time": "Giờ lái thử",
    "ward": "Phường/Xã",
    "note": "Yêu cầu khác",
}


class AgentState(TypedDict, total=False):
    messages: Annotated[list[Any], add_messages]

    # Dữ liệu form đang gom
    draft: dict[str, Any]
    missing_fields: list[str]

    # Hàng đợi hành động cho con trỏ ảo ở frontend
    action_queue: list[dict[str, Any]]
    current_action: dict[str, Any] | None
    filled_fields: list[str]

    # BẪY #4: run_seq tăng mỗi lượt và được đóng dấu lên TỪNG action, nhờ đó
    # frontend phân biệt được lượt 1 và lượt 2 dù nội dung action giống nhau.
    run_seq: int
    run_kind: RunKind

    # Luồng xác nhận 2 bước
    awaiting: str | None
    changed_fields: list[str]
    correction_rounds: int

    # Kết quả
    submission_code: str | None
    status: str

    # Dùng cho test gọi node trực tiếp, không đi qua messages
    query: str | None
    response: str | None
    error: str | None


def empty_state() -> AgentState:
    return AgentState(
        messages=[],
        draft={},
        missing_fields=[],
        action_queue=[],
        current_action=None,
        filled_fields=[],
        run_seq=0,
        run_kind="full",
        awaiting=None,
        changed_fields=[],
        correction_rounds=0,
        submission_code=None,
        status="idle",
        query=None,
        response=None,
        error=None,
    )
