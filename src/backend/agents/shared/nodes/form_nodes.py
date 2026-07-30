"""Các node của graph điền form lái thử.

Nguyên tắc chung:
- Mọi câu agent nói với khách đều phát qua `messages` (AIMessage). Field
  `response` chỉ để debug/test, khung chat KHÔNG đọc nó.
- Node không bao giờ tự đoán thay khách: thiếu thì hỏi, khớp nhiều ứng viên thì
  hỏi lại, chứ không chọn hộ.
"""

import asyncio
import re
from datetime import date, datetime
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from ....models.schemas import TIME_SLOTS, TestDriveCreate
from ....services.customer_repository import DuplicatePhoneError, create_test_drive
from ....services.database import SessionLocal
from ....services.llm import get_llm
from ..catalog import match_vehicle, match_ward, normalize_phone, vehicle_name
from ..copy import CopyPack, get_copy
from ..state import FIELD_LABELS, FORM_FIELDS, REQUIRED_FIELDS, AgentState

HOTLINE = "1900 23 23 89"
MAX_CORRECTION_ROUNDS = 5

WEEKDAYS_VI = ("Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật")

# Trạng thái cho biết lượt trước đã đóng — lượt sau phải bắt đầu draft sạch,
# nếu không dữ liệu khách A rò sang phiên của khách B trên cùng thread.
# `duplicate_phone` cũng là trạng thái kết thúc: sales nhắn lại số mới thì phải
# bóc lại từ đầu, không đắp lên draft của khách đã bị từ chối.
TERMINAL_STATUSES = {"done", "manual_ready", "error", "duplicate_phone"}

TYPE_FIELDS = {"name", "phone", "email", "note"}
SELECT_FIELDS = {"vehicle_id", "test_drive_date", "test_drive_time"}


class ExtractedDraft(BaseModel):
    """Khung dữ liệu LLM phải trả về. Field nào khách không nói thì để null."""

    name: str | None = Field(default=None, description="Họ và tên khách, giữ nguyên dấu")
    phone: str | None = Field(default=None, description="Số điện thoại, chỉ chữ số")
    email: str | None = Field(default=None, description="Email nếu khách có nói")
    vehicle: str | None = Field(default=None, description="Mẫu xe khách nhắc, ví dụ 'VF 8'")
    test_drive_date: str | None = Field(default=None, description="Ngày lái thử, định dạng YYYY-MM-DD")
    test_drive_time: str | None = Field(default=None, description="Giờ lái thử, định dạng HH:MM")
    ward: str | None = Field(default=None, description="Tên phường/xã ở Hà Nội")
    note: str | None = Field(default=None, description="Yêu cầu khác của khách")


# --------------------------------------------------------------------------
# Helpers dùng chung
# --------------------------------------------------------------------------

def _today() -> date:
    return date.today()


def _today_hint() -> str:
    today = _today()
    return f"{today.isoformat()} ({WEEKDAYS_VI[today.weekday()]})"


def _message_text(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("content") or "")
    return str(getattr(message, "content", "") or "")


def _is_human(message: Any) -> bool:
    if isinstance(message, dict):
        return message.get("role") in {"user", "human"} or message.get("type") == "human"
    return getattr(message, "type", None) == "human" or isinstance(message, HumanMessage)


def _last_user_text(state: AgentState) -> str:
    """Lấy câu mới nhất của khách.

    Đọc cả `messages` (đường chạy thật qua AG-UI) lẫn `query` (để test gọi node
    trực tiếp không cần dựng message list).
    """
    for message in reversed(state.get("messages") or []):
        if _is_human(message):
            text = _message_text(message).strip()
            if text:
                return text
    return (state.get("query") or "").strip()


def _snap_time(hour: int, minute: int) -> str:
    """Ép về khung giờ gần nhất trong TIME_SLOTS."""
    target = hour * 60 + minute
    return min(
        TIME_SLOTS,
        key=lambda slot: abs(int(slot[:2]) * 60 + int(slot[3:]) - target),
    )


def _normalize_time(raw: str | None) -> str | None:
    if not raw:
        return None
    text = str(raw).strip()
    if text in TIME_SLOTS:
        return text

    match = re.match(r"^(\d{1,2})\s*[:hg.]\s*(\d{1,2})$", text)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
    else:
        match = re.match(r"^(\d{1,2})$", text)
        if not match:
            return None
        hour, minute = int(match.group(1)), 0

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return _snap_time(hour, minute)


def _normalize_date(raw: str | None) -> str | None:
    """Chỉ nhận ISO date không ở quá khứ. Ngày tương đối do LLM quy đổi trước."""
    if not raw:
        return None
    text = str(raw).strip()
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if not match:
        return None
    try:
        parsed = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None
    if parsed < _today():
        return None
    return parsed.isoformat()


def _clean_text(raw: str | None, *, limit: int = 400) -> str | None:
    if not raw:
        return None
    text = " ".join(str(raw).split())
    return text[:limit] or None


def _normalize_email(raw: str | None) -> str | None:
    text = _clean_text(raw, limit=180)
    if not text:
        return None
    text = text.replace(" ", "").lower()
    if "@" not in text or "." not in text.split("@")[-1]:
        return None
    return text


def _normalize_extracted(extracted: ExtractedDraft) -> dict[str, Any]:
    """Đưa kết quả LLM qua catalog. Giá trị không chuẩn hoá được thì bỏ, không đoán."""
    normalized: dict[str, Any] = {}

    name = _clean_text(extracted.name, limit=120)
    if name and len(name) >= 2:
        normalized["name"] = name

    phone = normalize_phone(extracted.phone)
    if phone:
        normalized["phone"] = phone

    email = _normalize_email(extracted.email)
    if email:
        normalized["email"] = email

    vehicle_id = match_vehicle(extracted.vehicle)
    if vehicle_id:
        normalized["vehicle_id"] = vehicle_id

    test_drive_date = _normalize_date(extracted.test_drive_date)
    if test_drive_date:
        normalized["test_drive_date"] = test_drive_date

    test_drive_time = _normalize_time(extracted.test_drive_time)
    if test_drive_time:
        normalized["test_drive_time"] = test_drive_time

    ward = match_ward(extracted.ward)
    if ward:
        normalized["ward"] = ward

    note = _clean_text(extracted.note)
    if note:
        normalized["note"] = note

    return normalized


def _missing_fields(draft: dict[str, Any]) -> list[str]:
    return [field for field in REQUIRED_FIELDS if not draft.get(field)]


EXTRACT_SYSTEM_PROMPT = """Bạn là trợ lý bóc thông tin đăng ký lái thử xe điện VinFast tại Hà Nội.

Nhiệm vụ: đọc câu của khách và trích ra các field. Quy tắc bắt buộc:
- CHỈ điền field mà khách thực sự nói. Không suy diễn, không bịa, không điền giá trị mẫu. Field không có thông tin thì để null.
- Email KHÔNG bắt buộc. Khách không nói email thì để null, tuyệt đối không tự tạo email từ tên.
- Ngày: quy mọi cách nói tương đối về YYYY-MM-DD. Hôm nay là {today_hint}. "mai" = ngày kế tiếp, "ngày mốt" = 2 ngày sau, "thứ 5 tuần sau" = thứ Năm của tuần kế tiếp, "cuối tuần" = thứ Bảy gần nhất.
- Giờ: phải map về đúng MỘT trong các khung {slots}. "9 rưỡi" hoặc "9h30" -> 09:30; "sáng" -> 08:00 nếu khách không nói giờ cụ thể; "chiều" -> 13:30. Nếu khách nói giờ lệch khung thì chọn khung gần nhất.
- Số đứng sau "vào", "lúc", "khoảng" là GIỜ, không phải ngày. Ví dụ "lái thử vào 9 giờ" -> test_drive_time="09:00", test_drive_date=null.
- Mẫu xe: ghi lại đúng cách khách gọi (ví dụ "VF 8", "con VF9", "Limo Green"), hệ thống tự đối chiếu danh mục.
- Phường/xã: chỉ ghi tên phường/xã ở Hà Nội, bỏ tiền tố "Phường"/"Xã".
- "Yêu cầu khác" của khách (muốn lái đường dài, cần tư vấn trả góp, dẫn theo trẻ nhỏ...) ghi vào note. Ghi nhận nguyên văn ý khách, KHÔNG tự hứa hẹn thay showroom.
"""


async def _extract_with_llm(text: str) -> ExtractedDraft:
    llm = get_llm().with_structured_output(ExtractedDraft)
    system = EXTRACT_SYSTEM_PROMPT.format(
        today_hint=_today_hint(), slots=", ".join(TIME_SLOTS)
    )
    result = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=text)])
    if isinstance(result, ExtractedDraft):
        return result
    if isinstance(result, dict):
        return ExtractedDraft(**result)
    return ExtractedDraft()


def _describe(draft: dict[str, Any], field: str) -> str:
    value = draft.get(field)
    if field == "vehicle_id":
        return vehicle_name(value) or str(value)
    if field == "test_drive_date":
        try:
            parsed = date.fromisoformat(str(value))
        except (TypeError, ValueError):
            return str(value)
        return f"{parsed.strftime('%d/%m/%Y')} ({WEEKDAYS_VI[parsed.weekday()]})"
    return str(value)


# --------------------------------------------------------------------------
# Node: extract
# --------------------------------------------------------------------------

async def extract_node(state: AgentState) -> dict[str, Any]:
    copy = get_copy(state)
    text = _last_user_text(state)
    if not text:
        return {
            "messages": [AIMessage(content=copy.greeting)],
            "status": "collecting",
            "missing_fields": list(REQUIRED_FIELDS),
        }

    previous_status = state.get("status") or "idle"
    base_draft: dict[str, Any] = {} if previous_status in TERMINAL_STATUSES else dict(
        state.get("draft") or {}
    )

    try:
        extracted = await _extract_with_llm(text)
    except Exception:  # noqa: BLE001 - lỗi LLM không được làm sập cả graph
        return {
            "messages": [AIMessage(content=copy.extract_failed.format(hotline=HOTLINE))],
            "status": "error",
            "error": "extract_failed",
        }

    normalized = _normalize_extracted(extracted)
    draft = {**base_draft, **normalized}

    return {
        "draft": draft,
        "missing_fields": _missing_fields(draft),
        "changed_fields": [],
        "correction_rounds": 0 if previous_status in TERMINAL_STATUSES else state.get(
            "correction_rounds", 0
        ),
        "submission_code": None,
        "filled_fields": [],
        "current_action": None,
        "action_queue": [],
        "awaiting": None,
        "error": None,
        "status": "extracted",
    }


def route_after_extract(state: AgentState) -> str:
    if state.get("status") == "error":
        return "end"
    return "ask_missing" if state.get("missing_fields") else "plan"


# --------------------------------------------------------------------------
# Node: ask_missing
# --------------------------------------------------------------------------

async def ask_missing_node(state: AgentState) -> dict[str, Any]:
    """Hỏi GỘP một lần tất cả field bắt buộc còn thiếu, không hỏi nhỏ giọt."""
    copy = get_copy(state)
    missing = state.get("missing_fields") or list(REQUIRED_FIELDS)
    labels = [FIELD_LABELS[field] for field in missing]

    need = labels[0] if len(labels) == 1 else f"{', '.join(labels[:-1])} và {labels[-1]}"

    hint_lines = []
    if "test_drive_time" in missing:
        hint_lines.append(f"Khung giờ đang nhận: {', '.join(TIME_SLOTS)}.")
    if "ward" in missing:
        hint_lines.append("Chương trình lái thử hiện chỉ áp dụng tại Hà Nội.")

    content = copy.ask_missing.format(need=need)
    if hint_lines:
        content += "\n" + "\n".join(hint_lines)

    return {
        "messages": [AIMessage(content=content)],
        "status": "collecting",
        "response": content,
    }


# --------------------------------------------------------------------------
# Node: plan
# --------------------------------------------------------------------------

async def plan_node(state: AgentState) -> dict[str, Any]:
    copy = get_copy(state)
    draft = state.get("draft") or {}
    changed = state.get("changed_fields") or []
    run_kind = "correction" if changed else "full"

    # BẪY #4: mỗi lượt một run_seq mới, và run_seq được ĐÓNG DẤU lên từng action.
    # Không có nó, lượt sửa sinh ra action trùng chữ ký lượt trước và bị bộ lọc
    # chống lặp ở frontend chặn -> con trỏ không điền lại ô nào.
    run_seq = int(state.get("run_seq") or 0) + 1

    fields = [f for f in FORM_FIELDS if f in changed] if run_kind == "correction" else list(
        FORM_FIELDS
    )

    queue: list[dict[str, Any]] = []
    for field in fields:
        value = draft.get(field)
        if not value:
            continue
        if field in TYPE_FIELDS:
            action_type = "type"
        elif field in SELECT_FIELDS:
            action_type = "select"
        else:
            action_type = "pick_ward"

        queue.append(
            {
                "type": action_type,
                "field": field,
                "label": FIELD_LABELS[field],
                "selector": f"[data-agent-field={field}]",
                "value": str(value),
                "run_seq": run_seq,
            }
        )

    content = copy.plan_correction if run_kind == "correction" else copy.plan_full

    return {
        "messages": [AIMessage(content=content)],
        "action_queue": queue,
        "current_action": None,
        "filled_fields": [],
        "run_seq": run_seq,
        "run_kind": run_kind,
        "status": "filling",
        "response": content,
    }


def route_after_plan(state: AgentState) -> str:
    """Queue rỗng (lượt sửa mà không có field nào đổi) thì đi thẳng tóm tắt lại."""
    return "fill" if state.get("action_queue") else "summarize"


# --------------------------------------------------------------------------
# Node: fill (tự lặp)
# --------------------------------------------------------------------------

async def fill_node(state: AgentState) -> dict[str, Any]:
    """Pop ĐÚNG 1 action mỗi vòng.

    Mỗi vòng là một state-delta riêng được stream ra frontend, nhờ đó con trỏ
    chạy lần lượt từng ô. Nếu đẩy cả queue trong một lần, frontend chỉ thấy
    state cuối và con trỏ nhảy phát một tới ô cuối cùng.
    """
    queue = list(state.get("action_queue") or [])
    if not queue:
        return {"current_action": None}

    action = queue.pop(0)
    await asyncio.sleep(0.7)

    filled = list(state.get("filled_fields") or [])
    if action["field"] not in filled:
        filled.append(action["field"])

    return {
        "current_action": action,
        "action_queue": queue,
        "filled_fields": filled,
        "status": "filling",
    }


def route_after_fill(state: AgentState) -> str:
    return "fill" if state.get("action_queue") else "summarize"


# --------------------------------------------------------------------------
# Node: summarize
# --------------------------------------------------------------------------

def build_summary(draft: dict[str, Any], copy: CopyPack | None = None) -> str:
    """`copy=None` mặc định về giọng trang khách — tiện cho test gọi trực tiếp."""
    copy = copy or get_copy({})
    lines = [copy.summary_header]
    for field in FORM_FIELDS:
        if not draft.get(field):
            continue
        lines.append(f"• {FIELD_LABELS[field]}: {_describe(draft, field)}")
    lines.append("• Tỉnh/Thành phố: Hà Nội")
    lines.append("")
    lines.append(copy.summary_footer)
    return "\n".join(lines)


async def summarize_node(state: AgentState) -> dict[str, Any]:
    summary = build_summary(state.get("draft") or {}, get_copy(state))
    return {
        "messages": [AIMessage(content=summary)],
        "current_action": None,
        "status": "confirming",
        "awaiting": "confirm_details",
        "response": summary,
    }


# --------------------------------------------------------------------------
# Phân loại câu trả lời xác nhận — bằng từ khoá, không tốn lượt LLM
# --------------------------------------------------------------------------

AFFIRMATIVE = (
    "xac nhan",
    "dong y",
    "dung roi",
    "dung",
    "chinh xac",
    "chot",
    "ok",
    "oke",
    "okay",
    "duoc",
    "yes",
    "gui di",
    "gui luon",
    "tu dong gui",
    "cu gui",
)

NEGATIVE = (
    "khong",
    "ko",
    "chua",
    "sai",
    "doi",
    "sua",
    "thay",
    "tu gui",
    "de toi",
    "toi tu",
    "no",
)


def _plain(text: str) -> str:
    from ..catalog import strip_accents

    return re.sub(r"\s+", " ", strip_accents(text)).strip()


def classify_answer(text: str) -> str:
    """Trả "yes" | "no" | "unknown". NEGATIVE được ưu tiên xét trước."""
    plain = _plain(text or "")
    if not plain:
        return "unknown"

    for keyword in NEGATIVE:
        if re.search(rf"\b{re.escape(keyword)}\b", plain):
            return "no"
    for keyword in AFFIRMATIVE:
        if re.search(rf"\b{re.escape(keyword)}\b", plain):
            return "yes"
    return "unknown"


# --------------------------------------------------------------------------
# Node: confirm_details / confirm_submit — dùng interrupt() của LangGraph
# --------------------------------------------------------------------------

async def confirm_details_node(state: AgentState) -> dict[str, Any]:
    """Đóng băng graph chờ khách xác nhận.

    `interrupt()` khiến LangGraph dừng và ghi state vào checkpointer; frontend
    resume bằng cùng `thread_id`, giá trị resume trở thành kết quả của lời gọi này.
    """
    answer = interrupt(
        {
            "kind": "confirm_details",
            "summary": build_summary(state.get("draft") or {}, get_copy(state)),
            "draft": state.get("draft") or {},
            "warning": state.get("duplicate_warning") or "",
        }
    )
    text = str(answer or "")

    if classify_answer(text) == "yes":
        return {"awaiting": None, "status": "details_confirmed", "query": None}

    return {"awaiting": None, "status": "needs_correction", "query": text}


def route_after_confirm_details(state: AgentState) -> str:
    return "patch" if state.get("status") == "needs_correction" else "ask_submit"


async def ask_submit_node(state: AgentState) -> dict[str, Any]:
    content = get_copy(state).ask_submit
    return {
        "messages": [AIMessage(content=content)],
        "status": "awaiting_submit",
        "awaiting": "confirm_submit",
        "response": content,
    }


async def confirm_submit_node(state: AgentState) -> dict[str, Any]:
    answer = interrupt(
        {
            "kind": "confirm_submit",
            "draft": state.get("draft") or {},
        }
    )
    text = str(answer or "")

    if classify_answer(text) == "yes":
        return {"awaiting": None, "status": "submitting"}
    return {"awaiting": None, "status": "manual_pending"}


def route_after_confirm_submit(state: AgentState) -> str:
    return "submit" if state.get("status") == "submitting" else "manual_ready"


# --------------------------------------------------------------------------
# Node: patch
# --------------------------------------------------------------------------

FIELD_KEYWORDS: dict[str, tuple[str, ...]] = {
    "test_drive_time": ("gio", "ruoi", "sang", "trua", "chieu", "toi", "khung", "slot"),
    "test_drive_date": ("ngay", "mai", "mot", "hom", "thu", "tuan", "cuoi tuan", "date"),
    "phone": ("sdt", "so dien thoai", "dien thoai", "so may", "so lien lac", "phone"),
    "email": ("email", "mail", "gmail", "hom thu"),
    "vehicle_id": ("xe", "mau", "mau xe", "doi xe", "vf", "minio", "herio", "nerio", "limo", "van", "mpv"),
    "ward": ("phuong", "xa", "quan", "dia diem", "khu vuc", "showroom", "diem hen", "cho"),
    "note": ("ghi chu", "yeu cau", "luu y", "note", "them"),
    "name": ("ten", "ho ten", "ho va ten"),
}

WARD_HINT_WORDS = ("phuong", "xa", "quan", "dia diem", "khu vuc", "showroom", "diem hen", "o ")


def mentioned_fields(text: str) -> set[str]:
    """Đoán khách đang nhắc tới field nào, bằng từ khoá không dấu + biên từ.

    Cần dùng `\\b` chứ không phải `in`: "email" chứa "mai" sẽ khiến câu sửa email
    bị hiểu là sửa ngày.
    """
    plain = _plain(text)
    found: set[str] = set()
    for field, keywords in FIELD_KEYWORDS.items():
        for keyword in keywords:
            if re.search(rf"\b{re.escape(keyword)}\b", plain):
                found.add(field)
                break
    return found


def direct_captures(text: str) -> dict[str, Any]:
    """Bắt trực tiếp các giá trị có định dạng cứng.

    Ưu tiên hơn kết quả LLM: khách gõ "15:00" thì phải ra đúng 15:00, không phụ
    thuộc việc LLM có bóc đúng hay không.
    """
    captured: dict[str, Any] = {}
    plain = _plain(text)

    # Ngày ISO (bắt trước để chuỗi ngày không bị hiểu thành số điện thoại).
    iso = _normalize_date(text)
    if iso:
        captured["test_drive_date"] = iso

    # Giờ: bắt buộc có dấu phân tách nên không đụng vào dãy số điện thoại.
    time_match = re.search(r"\b(\d{1,2})\s*(?::|h|g|gio)\s*(\d{2})\b", plain)
    if time_match:
        snapped = _normalize_time(f"{time_match.group(1)}:{time_match.group(2)}")
        if snapped:
            captured["test_drive_time"] = snapped
    else:
        half = re.search(r"\b(\d{1,2})\s*(?:h|gio)?\s*ruoi\b", plain)
        whole = re.search(r"\b(\d{1,2})\s*(?:h|gio)\b", plain)
        if half:
            captured["test_drive_time"] = _snap_time(int(half.group(1)), 30)
        elif whole:
            captured["test_drive_time"] = _snap_time(int(whole.group(1)), 0)

    # Xoá ngày ISO và giờ HH:MM trước khi tìm số điện thoại: gộp khoảng trắng
    # giữa các chữ số sẽ dán "2026-08-01 15:00" thành một dãy 10 số trông y như
    # số điện thoại. Không dùng `\b` ở đầu vì số có thể dính liền chữ có dấu
    # ("là0912345678"), lúc đó `\b` không tồn tại.
    scrubbed = re.sub(r"\d{4}-\d{2}-\d{2}", " ", text)
    scrubbed = re.sub(r"\d{1,2}\s*[:h]\s*\d{2}", " ", scrubbed)
    compact = re.sub(r"(?<=\d)[.\s-]+(?=\d)", "", scrubbed)

    phone_match = re.search(r"(?<!\d)(?:\+?84\d{9}|0\d{9,10})(?!\d)", compact)
    if phone_match:
        phone = normalize_phone(phone_match.group(0))
        if phone:
            captured["phone"] = phone

    email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    if email_match:
        email = _normalize_email(email_match.group(0))
        if email:
            captured["email"] = email

    vehicle_id = match_vehicle(text)
    if vehicle_id:
        captured["vehicle_id"] = vehicle_id

    # Phường chỉ bắt trực tiếp khi câu có dấu hiệu nói về địa điểm, hoặc tên
    # phường là cụm nhiều từ — tránh nuốt một từ đơn trùng tên phường.
    ward = match_ward(text)
    if ward:
        has_hint = any(hint.strip() in plain.split() or hint in plain for hint in WARD_HINT_WORDS)
        if has_hint or len(ward.split()) > 1:
            captured["ward"] = ward

    return captured


async def patch_node(state: AgentState) -> dict[str, Any]:
    copy = get_copy(state)
    rounds = int(state.get("correction_rounds") or 0) + 1
    old_draft = dict(state.get("draft") or {})
    text = (state.get("query") or "").strip()

    if rounds > MAX_CORRECTION_ROUNDS:
        content = copy.patch_exhausted.format(
            rounds=MAX_CORRECTION_ROUNDS, hotline=HOTLINE
        )
        return {
            "messages": [AIMessage(content=content)],
            "correction_rounds": rounds,
            "changed_fields": [],
            "status": "error",
            "error": "too_many_corrections",
            "response": content,
        }

    try:
        extracted = await _extract_with_llm(text) if text else ExtractedDraft()
        normalized = _normalize_extracted(extracted)
    except Exception:  # noqa: BLE001 - vẫn còn regex để cứu
        normalized = {}

    mentioned = mentioned_fields(text)
    new_draft = dict(old_draft)

    # Chỉ áp kết quả LLM cho field khách THỰC SỰ nhắc tới. Không có bước lọc này,
    # LLM hay "điền lại" cả form theo trí nhớ và ghi đè field khách không hề sửa.
    for field in FORM_FIELDS:
        if field in mentioned and normalized.get(field):
            new_draft[field] = normalized[field]

    new_draft.update(direct_captures(text))

    changed = [f for f in FORM_FIELDS if new_draft.get(f) != old_draft.get(f)]

    if not changed:
        content = copy.patch_unclear
        return {
            "messages": [AIMessage(content=content)],
            "draft": new_draft,
            "changed_fields": [],
            "correction_rounds": rounds,
            "status": "needs_correction_retry",
            "response": content,
        }

    labels = ", ".join(FIELD_LABELS[field] for field in changed)
    content = copy.patch_applied.format(labels=labels)

    return {
        "messages": [AIMessage(content=content)],
        "draft": new_draft,
        "missing_fields": _missing_fields(new_draft),
        "changed_fields": changed,
        "correction_rounds": rounds,
        "status": "patched",
        "query": None,
        "response": content,
    }


def route_after_patch(state: AgentState) -> str:
    if state.get("status") == "error":
        return "end"
    return "plan"


# --------------------------------------------------------------------------
# Node: submit / manual_ready / report
# --------------------------------------------------------------------------

def _persist(payload: TestDriveCreate) -> str:
    """Ghi qua ĐÚNG repository mà form thủ công dùng — một đường ghi duy nhất."""
    with SessionLocal() as session:
        customer = create_test_drive(session, payload)
        return customer.code or ""


async def submit_node(state: AgentState) -> dict[str, Any]:
    copy = get_copy(state)
    draft = state.get("draft") or {}

    try:
        payload = TestDriveCreate(
            name=draft["name"],
            phone=draft["phone"],
            email=draft.get("email"),
            vehicle_id=draft["vehicle_id"],
            model=vehicle_name(draft["vehicle_id"]) or draft["vehicle_id"],
            test_drive_date=datetime.fromisoformat(str(draft["test_drive_date"])).date(),
            test_drive_time=draft["test_drive_time"],
            province="Hà Nội",
            ward=draft["ward"],
            note=draft.get("note"),
            source=state.get("source") or "Website",
        )
    except (KeyError, ValueError) as exc:
        content = copy.submit_invalid.format(error=exc)
        return {
            "messages": [AIMessage(content=content)],
            "status": "error",
            "error": "invalid_draft",
            "response": content,
        }

    try:
        code = await asyncio.to_thread(_persist, payload)
    except DuplicatePhoneError as exc:
        # Chốt chặn CUỐI. Graph CRM đã kiểm ở `check_duplicate` trước khi hỏi xác
        # nhận, nhưng giữa lúc đó và lúc ghi có thể có sales khác vừa tạo cùng số.
        # Bắt ở đây để exception không xé graph giữa chừng.
        content = copy.duplicate_phone.format(
            code=exc.code, name=exc.name, phone=payload.phone, hotline=HOTLINE
        )
        return {
            "messages": [AIMessage(content=content)],
            "status": "duplicate_phone",
            "error": "duplicate_phone",
            "response": content,
        }
    except Exception:  # noqa: BLE001
        content = copy.submit_failed.format(hotline=HOTLINE)
        return {
            "messages": [AIMessage(content=content)],
            "status": "error",
            "error": "persist_failed",
            "response": content,
        }

    return {"submission_code": code, "status": "submitted"}


async def manual_ready_node(state: AgentState) -> dict[str, Any]:
    """Không tạo bản ghi, giữ nguyên form đã điền cho người dùng tự bấm gửi."""
    content = get_copy(state).manual_ready
    return {
        "messages": [AIMessage(content=content)],
        "current_action": None,
        "status": "manual_ready",
        "response": content,
    }


async def report_node(state: AgentState) -> dict[str, Any]:
    draft = state.get("draft") or {}
    code = state.get("submission_code") or ""

    content = get_copy(state).report.format(
        code=code,
        date=_describe(draft, "test_drive_date"),
        time=draft.get("test_drive_time"),
        vehicle=vehicle_name(draft.get("vehicle_id")) or "",
        ward=draft.get("ward"),
        hotline=HOTLINE,
    )
    return {
        "messages": [AIMessage(content=content)],
        "current_action": None,
        "status": "done",
        "response": content,
    }
