"""Node chỉ riêng graph CRM có: kiểm tra trùng khách trước khi hỏi xác nhận.

Đặt thành node riêng thay vì nhét `if` vào `summarize_node` dùng chung, để graph
trang khách không phải gánh nhánh nó không dùng, và 2 luồng test được độc lập.
"""

import asyncio
from typing import Any

from langchain_core.messages import AIMessage

from ...services.customer_repository import find_duplicates
from ...services.database import SessionLocal
from ..shared.copy import get_copy
from ..shared.state import AgentState


def _lookup(phone: str, name: str) -> tuple[tuple[str, str] | None, list[str]]:
    """Tra DB trong thread riêng. Trả về ((code, name) trùng SĐT, [code trùng tên]).

    Cố tình KHÔNG trả về ORM object: session đóng lại là instance detach, đọc
    thuộc tính sau đó sẽ nổ `DetachedInstanceError`.
    """
    with SessionLocal() as session:
        phone_match, name_matches = find_duplicates(session, phone=phone, name=name)
        hard = (phone_match.code or "", phone_match.name) if phone_match else None
        # Trùng tên nhưng cùng số điện thoại thì đã bị chặn cứng ở trên rồi, không
        # cần cảnh báo mềm thêm lần nữa.
        soft = [
            c.code or ""
            for c in name_matches
            if not phone_match or c.id != phone_match.id
        ]
        return hard, soft


async def check_duplicate_node(state: AgentState) -> dict[str, Any]:
    copy = get_copy(state)
    draft = state.get("draft") or {}
    phone = str(draft.get("phone") or "")
    name = str(draft.get("name") or "")

    if not phone and not name:
        return {"duplicate_warning": ""}

    try:
        hard, soft = await asyncio.to_thread(_lookup, phone, name)
    except Exception:  # noqa: BLE001 - lỗi tra DB không được chặn luồng nhập lead
        return {"duplicate_warning": ""}

    if hard is not None:
        code, existing_name = hard
        content = copy.duplicate_phone.format(
            code=code, name=existing_name, phone=phone, hotline=""
        )
        return {
            "messages": [AIMessage(content=content)],
            "current_action": None,
            "duplicate_warning": "",
            "awaiting": None,
            "status": "duplicate_phone",
            "response": content,
        }

    if soft:
        warning = copy.duplicate_name_warning.format(code=", ".join(soft))
        return {
            "messages": [AIMessage(content=warning)],
            "duplicate_warning": warning,
            "response": warning,
        }

    return {"duplicate_warning": ""}


def route_after_check_duplicate(state: AgentState) -> str:
    if state.get("status") == "duplicate_phone":
        return "duplicate_blocked"
    return "confirm_details"


async def duplicate_blocked_node(state: AgentState) -> dict[str, Any]:  # noqa: ARG001
    """Kết thúc lượt sau khi báo trùng.

    Không phát thêm message: `check_duplicate_node` đã nói rồi. Lượt chat sau sales
    nhắn số mới sẽ chạy lại từ `extract`, và vì `duplicate_phone` nằm trong
    `TERMINAL_STATUSES` nên draft được bóc lại từ đầu chứ không đắp lên số cũ.
    """
    return {"current_action": None, "action_queue": []}
