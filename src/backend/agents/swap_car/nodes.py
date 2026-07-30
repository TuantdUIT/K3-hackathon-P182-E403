"""Các node của agent đổi xe cũ lấy xe mới (nghiệp vụ 2).

Bám đúng sơ đồ trong `agent-crm-flow.md` §2, giữ nguyên ranh giới AI / hệ thống:

- Ô XÁM (rule, không cần LLM): `eligibility`, `appraise`, `quote`, `checklist`.
  Toàn bộ phép tính nằm ở `services/appraisal_rules.py` và
  `services/appraisal_repository.py`, node ở đây chỉ gọi và kể lại.
- Ô XANH (cần LLM): `extract` (bóc thông tin từ lời sales) và `explain` (giải
  thích VÌ SAO từng điều kiện quan trọng, nói ngắn dần khi sales quen việc).

Nguyên tắc chung giống 2 agent kia: mọi câu nói với người dùng đi qua `messages`
(AIMessage), `response` chỉ để debug/test. Node không đoán thay người: thiếu thì
hỏi, không khớp danh mục thì chuyển thủ công, chứ không tự áng.
"""

import asyncio
import re
from datetime import date, datetime, timedelta
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from ...services import appraisal_repository as appraisal_repo
from ...services import appraisal_rules as rules
from ...services.appraisal_repository import NoMarketPriceError
from ...services.customer_repository import get_customer_by_code
from ...services.database import SessionLocal
from ...services.llm import get_llm
from ..shared.catalog import match_vehicle, vehicle_name
from ..shared.nodes.form_nodes import classify_answer
from . import copy as say
from .state import (
    FIELD_LABELS,
    FLAG_FIELDS,
    FORM_FIELDS,
    REQUIRED_FIELDS,
    SCORE_FIELDS,
    TYPE_FIELDS,
    SwapCarState,
)

MAX_REVISE_ROUNDS = 3

# Ngày hẹn giao xe mặc định. Đủ để làm thủ tục sang tên xe cũ, và luôn là một
# ngày cụ thể để sales có cái chốt với khách thay vì "khoảng tuần sau".
HANDOVER_LEAD_DAYS = 7

# Trạng thái báo hiệu lượt trước đã đóng — lượt sau phải bóc lại từ đầu, nếu
# không thông tin xe của khách A rò sang phiên của khách B trên cùng thread.
TERMINAL_STATUSES = {"rejected", "manual_appraisal", "accepted", "blocked", "error"}


class ExtractedSwapCar(BaseModel):
    """Khung dữ liệu LLM phải trả về. Field nào sales không nói thì để null."""

    make: str | None = Field(default=None, description="Hãng xe cũ, ví dụ 'Honda'")
    model: str | None = Field(default=None, description="Dòng xe cũ, ví dụ 'City'")
    year: int | None = Field(default=None, description="Đời xe, 4 chữ số")
    trim: str | None = Field(default=None, description="Phiên bản, ví dụ 'G', 'RS'")
    plate_no: str | None = Field(default=None, description="Biển số xe cũ")
    odo_km: int | None = Field(default=None, description="Số km đã đi, chỉ chữ số")
    first_registration_date: str | None = Field(
        default=None, description="Ngày đăng ký lần đầu, YYYY-MM-DD"
    )
    ownership_months: int | None = Field(
        default=None, description="Số tháng khách đã đứng tên xe"
    )
    repair_cost: int | None = Field(
        default=None, description="Chi phí dọn dẹp/sửa chữa dự kiến, đơn vị VND"
    )
    new_vehicle: str | None = Field(
        default=None, description="Mẫu VinFast khách muốn đổi, ví dụ 'VF 3'"
    )

    flood_damaged: bool | None = Field(default=None, description="Xe từng ngập nước")
    structural_damage: bool | None = Field(default=None, description="Đâm đụng ảnh hưởng kết cấu")
    odo_tampered: bool | None = Field(default=None, description="Có dấu hiệu tua công-tơ-mét")
    missing_papers: bool | None = Field(default=None, description="Thiếu giấy tờ gốc")

    condition_engine: str | None = Field(default=None, description="Động cơ & hộp số")
    condition_chassis: str | None = Field(default=None, description="Khung gầm & hệ thống treo")
    condition_electrical: str | None = Field(default=None, description="Hệ thống điện & tính năng")
    condition_exterior: str | None = Field(default=None, description="Sơn & vỏ xe")
    condition_interior: str | None = Field(default=None, description="Khoang cabin")
    condition_service: str | None = Field(default=None, description="Lịch sử bảo dưỡng")
    condition_extras: str | None = Field(default=None, description="Màu sắc & phụ kiện")


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _message_text(message: Any) -> str:
    content = getattr(message, "content", None)
    if content is None and isinstance(message, dict):
        content = message.get("content")
    return str(content or "")


def _is_human(message: Any) -> bool:
    if getattr(message, "type", None) == "human":
        return True
    role = message.get("role") if isinstance(message, dict) else None
    return role in {"user", "human"}


def _last_user_text(state: SwapCarState) -> str:
    if state.get("query"):
        return str(state["query"])
    for message in reversed(state.get("messages") or []):
        if _is_human(message):
            text = _message_text(message).strip()
            if text:
                return text
    return ""


def money(value: Any) -> str:
    """Định dạng tiền kiểu Việt Nam: 425000000 -> "425.000.000 đ"."""
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return str(value)
    return f"{number:,}".replace(",", ".") + " đ"


# KHÔNG có `\b` ở đầu đơn vị: giữa chữ số và chữ cái không tồn tại word boundary
# nên "15tr" sẽ không khớp `\btr\b`. Ranh giới CUỐI thì bắt buộc, nếu không "20
# trung bình" bị đọc thành 20 triệu.
_MONEY_UNITS = (
    (r"tri[eệ]u\b|tr\b", 1_000_000),
    (r"t[yỷ]\b", 1_000_000_000),
    (r"ng[aà]n\b|ngh[ìi]n\b|k\b", 1_000),
)


def parse_money(text: str | None) -> int | None:
    """Đọc số tiền trong câu nói: "20 triệu" -> 20000000, "1,5 tỷ" -> 1500000000."""
    if not text:
        return None
    lowered = str(text).lower().replace(",", ".")

    for pattern, factor in _MONEY_UNITS:
        match = re.search(rf"(\d+(?:\.\d+)?)\s*(?:{pattern})", lowered)
        if match:
            return int(round(float(match.group(1)) * factor))

    # Số viết đầy đủ, có thể có dấu chấm phân nhóm: "20.000.000".
    match = re.search(r"\b\d[\d.]{5,}\b", lowered)
    if match:
        digits = match.group(0).replace(".", "")
        return int(digits)
    return None


def _clean_text(raw: Any, *, limit: int = 60) -> str | None:
    if raw is None:
        return None
    text = " ".join(str(raw).split())
    return text[:limit] or None


def _to_int(raw: Any) -> int | None:
    if raw is None:
        return None
    digits = re.sub(r"\D", "", str(raw))
    return int(digits) if digits else None


def _to_iso_date(raw: Any) -> str | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw)[:10]).date()
    except ValueError:
        return None
    # Đăng ký lần đầu ở tương lai là dữ liệu hỏng, đừng để nó chảy vào công thức
    # tuổi xe rồi ra số tháng âm.
    if parsed > date.today():
        return None
    return parsed.isoformat()


_LEVEL_ALIASES: dict[str, str] = {
    "tot": "tot",
    "rat tot": "tot",
    "moi": "tot",
    "nguyen ban": "tot",
    "kha": "kha",
    "on": "kha",
    "binh thuong": "kha",
    "trung binh": "trung_binh",
    "trung_binh": "trung_binh",
    "kem": "kem",
    "hong": "kem",
    "xau": "kem",
}


def _to_level(raw: Any) -> str | None:
    """Map mô tả tình trạng về đúng 1 trong 4 mức. Không khớp -> None (chưa chấm)."""
    if not raw:
        return None
    from ..shared.catalog import strip_accents

    plain = re.sub(r"\s+", " ", strip_accents(str(raw))).strip()
    if plain in rules.LEVELS:
        return plain
    return _LEVEL_ALIASES.get(plain)


def _normalize(extracted: ExtractedSwapCar) -> tuple[dict[str, Any], dict[str, bool], dict[str, str]]:
    """Chuẩn hoá kết quả LLM thành (draft, flags, levels)."""
    draft: dict[str, Any] = {}

    for field in ("make", "model", "trim", "plate_no"):
        value = _clean_text(getattr(extracted, field))
        if value:
            draft[field] = value

    year = _to_int(extracted.year)
    if year and 1990 <= year <= date.today().year + 1:
        draft["year"] = year

    odo = _to_int(extracted.odo_km)
    if odo is not None:
        draft["odo_km"] = odo

    registered = _to_iso_date(extracted.first_registration_date)
    if registered:
        draft["first_registration_date"] = registered

    months = _to_int(extracted.ownership_months)
    if months is not None:
        draft["ownership_months"] = months

    repair = _to_int(extracted.repair_cost)
    if repair is not None:
        draft["repair_cost"] = repair

    vehicle_id = match_vehicle(extracted.new_vehicle)
    if vehicle_id:
        draft["vehicle_id"] = vehicle_id

    # Cờ loại trừ: chỉ ghi nhận khi LLM khẳng định True. `None` và `False` đều là
    # "sales không nói" — bật cờ hộ là tự tay loại xe của khách.
    flags = {code: True for code in rules.HARD_FLAGS if getattr(extracted, code, None) is True}

    levels: dict[str, str] = {}
    for code in rules.SCORED_CRITERIA:
        level = _to_level(getattr(extracted, f"condition_{code}", None))
        if level:
            levels[code] = level

    return draft, flags, levels


def _missing_fields(draft: dict[str, Any]) -> list[str]:
    return [
        field
        for field in REQUIRED_FIELDS
        if draft.get(field) in (None, "", []) and draft.get(field) != 0
    ]


def _join_labels(labels: list[str]) -> str:
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    return f"{', '.join(labels[:-1])} và {labels[-1]}"


EXTRACT_SYSTEM_PROMPT = """Bạn là trợ lý định giá xe cũ cho nhân viên kinh doanh VinFast.

Người nhắn là NHÂN VIÊN, đang thuật lại tình trạng xe cũ của một khách hàng thứ ba.
Nhiệm vụ: đọc câu của nhân viên và trích ra các field. Quy tắc bắt buộc:
- CHỈ điền field mà nhân viên thực sự nói. Không suy diễn, không bịa. Field không có thông tin thì để null.
- Hãng và dòng xe tách riêng: "Honda City 2019" -> make="Honda", model="City", year=2019.
- Số km: chỉ lấy chữ số. "8 vạn km" = 80000, "85 nghìn km" = 85000.
- Ngày đăng ký lần đầu về dạng YYYY-MM-DD. Hôm nay là {today}. Nhân viên chỉ nói năm thì lấy ngày 01 tháng 01 của năm đó.
- Chi phí sửa chữa quy về VND: "20 triệu" = 20000000.
- new_vehicle: ghi đúng cách nhân viên gọi mẫu VinFast khách muốn đổi ("VF 3", "con VF8"), hệ thống tự đối chiếu danh mục.
- 4 cờ ngập nước / đâm đụng kết cấu / tua công-tơ-mét / thiếu giấy tờ: chỉ đặt true khi nhân viên NÓI RÕ là có. Không chắc thì để null, tuyệt đối không đặt false hay true để đoán.
- Các field condition_*: chỉ nhận đúng một trong 4 giá trị "tot", "kha", "trung_binh", "kem". Nhân viên không nhắc tới bộ phận nào thì để null.
  Ví dụ: "máy êm, gầm hơi rỉ sét" -> condition_engine="tot", condition_chassis="trung_binh".
"""


async def _extract_with_llm(text: str) -> ExtractedSwapCar:
    llm = get_llm().with_structured_output(ExtractedSwapCar)
    system = EXTRACT_SYSTEM_PROMPT.format(today=date.today().isoformat())
    result = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=text)])
    if isinstance(result, ExtractedSwapCar):
        return result
    if isinstance(result, dict):
        return ExtractedSwapCar(**result)
    return ExtractedSwapCar()


# --------------------------------------------------------------------------
# Node: init — đóng dấu kênh + đo mức kinh nghiệm của sales
# --------------------------------------------------------------------------

def _lookup_experience(staff_id: int | None) -> str:
    with SessionLocal() as session:
        return appraisal_repo.experience_of(session, staff_id)


async def init_node(state: SwapCarState) -> dict[str, Any]:
    """Chốt `channel` và mức hướng dẫn ngay đầu lượt.

    Mức kinh nghiệm đọc từ SỐ HỒ SƠ ĐÃ XỬ LÝ trong DB, không nhờ frontend gửi
    lên: đây là thứ quyết định agent nói dài hay ngắn, để client tự khai thì mỗi
    máy một kiểu.
    """
    try:
        experience = await asyncio.to_thread(_lookup_experience, state.get("sales_staff_id"))
    except Exception:  # noqa: BLE001 - lỗi DB không được chặn cả lượt tư vấn
        experience = "novice"

    return {"channel": "crm", "experience": experience}


# --------------------------------------------------------------------------
# Node: extract
# --------------------------------------------------------------------------

async def extract_node(state: SwapCarState) -> dict[str, Any]:
    text = _last_user_text(state)
    if not text:
        return {
            "messages": [AIMessage(content=say.GREETING)],
            "status": "collecting",
            "missing_fields": list(REQUIRED_FIELDS),
            "response": say.GREETING,
        }

    if not state.get("customer_code"):
        return {
            "messages": [AIMessage(content=say.NO_CUSTOMER)],
            "status": "no_customer",
            "response": say.NO_CUSTOMER,
        }

    previous = state.get("status") or "idle"
    fresh = previous in TERMINAL_STATUSES
    base_draft: dict[str, Any] = {} if fresh else dict(state.get("draft") or {})
    base_flags: dict[str, bool] = {} if fresh else dict(state.get("flags") or {})
    base_levels: dict[str, str] = {} if fresh else dict(state.get("levels") or {})

    try:
        extracted = await _extract_with_llm(text)
    except Exception:  # noqa: BLE001 - lỗi LLM không được làm sập cả graph
        return {
            "messages": [AIMessage(content=say.EXTRACT_FAILED)],
            "status": "error",
            "error": "extract_failed",
            "response": say.EXTRACT_FAILED,
        }

    new_draft, new_flags, new_levels = _normalize(extracted)
    draft = {**base_draft, **new_draft}

    return {
        "draft": draft,
        "flags": {**base_flags, **new_flags},
        "levels": {**base_levels, **new_levels},
        "missing_fields": _missing_fields(draft),
        "appraisal_code": None if fresh else state.get("appraisal_code"),
        "revise_rounds": 0,
        "filled_fields": [],
        "current_action": None,
        "action_queue": [],
        "awaiting": None,
        "error": None,
        "status": "extracted",
    }


def route_after_extract(state: SwapCarState) -> str:
    if state.get("status") in {"error", "no_customer"}:
        return "end"
    return "ask_missing" if state.get("missing_fields") else "eligibility"


async def ask_missing_node(state: SwapCarState) -> dict[str, Any]:
    """Hỏi GỘP một lần tất cả field còn thiếu, không hỏi nhỏ giọt."""
    missing = state.get("missing_fields") or list(REQUIRED_FIELDS)
    need = _join_labels([FIELD_LABELS[field] for field in missing])
    content = say.ASK_MISSING.format(need=need)
    return {
        "messages": [AIMessage(content=content)],
        "status": "collecting",
        "response": content,
    }


# --------------------------------------------------------------------------
# Node: eligibility — Ô XÁM, rule thuần
# --------------------------------------------------------------------------

async def eligibility_node(state: SwapCarState) -> dict[str, Any]:
    draft = state.get("draft") or {}
    registered = date.fromisoformat(str(draft["first_registration_date"]))

    status_code, checks = rules.check_eligibility(
        first_registration_date=registered,
        ownership_months=draft.get("ownership_months"),
        flags=state.get("flags") or {},
    )

    return {
        "eligibility_status": status_code,
        "eligibility_checks": checks,
        "status": "eligible" if status_code == "passed" else "not_eligible",
    }


def route_after_eligibility(state: SwapCarState) -> str:
    return "explain" if state.get("eligibility_status") == "passed" else "rejected"


def _persist_rejected(payload: dict[str, Any]) -> str:
    """Ghi lại cả hồ sơ bị từ chối — không ghi thì quản lý mất số liệu loại xe."""
    with SessionLocal() as session:
        customer = get_customer_by_code(session, str(payload["customer_code"]))
        if customer is None:
            return ""
        appraisal = appraisal_repo.create_appraisal(
            session,
            customer_id=customer.id,
            make=str(payload["make"]),
            model=str(payload["model"]),
            year=int(payload["year"]),
            trim=str(payload.get("trim") or ""),
            plate_no=payload.get("plate_no"),
            odo_km=int(payload.get("odo_km") or 0),
            first_registration_date=date.fromisoformat(str(payload["first_registration_date"])),
            ownership_months=payload.get("ownership_months"),
            flags=payload.get("flags") or {},
            sales_staff_id=payload.get("sales_staff_id"),
        )
        return appraisal.code or ""


async def rejected_node(state: SwapCarState) -> dict[str, Any]:
    """Từ chối thẳng, KHÔNG tạo giao dịch — đúng nhánh BX của sơ đồ."""
    draft = state.get("draft") or {}
    reason = rules.REJECTION_LABELS.get(
        str(state.get("eligibility_status")), "chưa đạt điều kiện đầu vào"
    )

    payload = {**draft, "customer_code": state.get("customer_code"),
               "flags": state.get("flags") or {},
               "sales_staff_id": state.get("sales_staff_id")}

    try:
        code = await asyncio.to_thread(_persist_rejected, payload)
    except Exception:  # noqa: BLE001
        code = ""

    content = (
        say.REJECTED.format(reason=reason, code=code)
        if code
        else say.REJECTED_NO_RECORD.format(reason=reason)
    )
    return {
        "messages": [AIMessage(content=content)],
        "appraisal_code": code or None,
        "current_action": None,
        "action_queue": [],
        "status": "rejected",
        "response": content,
    }


# --------------------------------------------------------------------------
# Node: explain — Ô XANH, chỗ AI thực sự tạo giá trị
# --------------------------------------------------------------------------

EXPLAIN_SYSTEM_PROMPT = """Bạn là trợ lý nội bộ của VinFast, đang hướng dẫn một nhân viên kinh doanh {level_hint}.

Nhân viên vừa nhập một xe cũ ĐÃ ĐẠT tất cả điều kiện đầu vào để đổi xe. Nhiệm vụ của bạn:
viết lại phần giải thích dưới đây cho dễ đọc, giữ NGUYÊN ý nghĩa và KHÔNG thêm điều kiện mới,
KHÔNG bịa số liệu, KHÔNG hứa hẹn gì về giá.

Yêu cầu văn phong: tiếng Việt, xưng "em", gọi nhân viên là "anh/chị". {length_hint}

Nội dung gốc:
{material}
"""

LEVEL_HINTS: dict[str, tuple[str, str]] = {
    "novice": (
        "mới vào nghề, lần đầu xử lý hồ sơ đổi xe",
        "Viết đủ ý từng điều kiện, mỗi điều kiện 1-2 câu, có gạch đầu dòng.",
    ),
    "familiar": (
        "đã xử lý vài hồ sơ đổi xe",
        "Viết gọn, mỗi điều kiện đúng 1 câu ngắn, chỉ giữ lý do cốt lõi.",
    ),
}


async def explain_node(state: SwapCarState) -> dict[str, Any]:
    """Giải thích VÌ SAO từng điều kiện quan trọng, nói ngắn dần khi sales quen việc.

    Phần "vì sao" là chuỗi cố định trong `appraisal_rules.HARD_FLAGS` — LLM chỉ
    được diễn đạt lại, không được tự sinh lý do. Nhờ vậy nội dung nghiệp vụ
    không đổi giữa hai lần chạy, và LLM hỏng thì rơi về đúng bản gốc.
    """
    experience = str(state.get("experience") or "novice")
    checks = state.get("eligibility_checks") or []
    passed = [check for check in checks if check.get("passed")]

    # Sales đã quen việc thì không giảng lại — đúng tinh thần progressive autonomy.
    if experience == "expert":
        content = say.EXPLAIN_SHORT.format(total=len(passed))
        return {
            "messages": [AIMessage(content=content)],
            "status": "explained",
            "response": content,
        }

    material = "\n".join(f"- {check['label']}: {check['why']}" for check in passed)
    fallback = f"{say.EXPLAIN_HEADER}\n{material}"

    level_hint, length_hint = LEVEL_HINTS.get(experience, LEVEL_HINTS["novice"])
    prompt = EXPLAIN_SYSTEM_PROMPT.format(
        level_hint=level_hint, length_hint=length_hint, material=material
    )

    try:
        result = await get_llm().ainvoke(
            [SystemMessage(content=prompt), HumanMessage(content=say.EXPLAIN_HEADER)]
        )
        content = _message_text(result).strip() or fallback
    except Exception:  # noqa: BLE001 - mất phần diễn giải thì dùng bản gốc, không chặn luồng
        content = fallback

    return {
        "messages": [AIMessage(content=content)],
        "status": "explained",
        "response": content,
    }


# --------------------------------------------------------------------------
# Node: plan / fill — con trỏ ảo điền hồ sơ, cùng giao thức 2 agent kia
# --------------------------------------------------------------------------

async def plan_node(state: SwapCarState) -> dict[str, Any]:
    draft = state.get("draft") or {}
    levels = state.get("levels") or {}
    flags = state.get("flags") or {}

    # BẪY #4: mỗi lượt một run_seq mới, đóng dấu lên TỪNG action. Không có nó,
    # lượt sửa sinh action trùng chữ ký lượt trước và bị bộ lọc chống lặp ở
    # frontend nuốt mất -> con trỏ không điền lại ô nào.
    run_seq = int(state.get("run_seq") or 0) + 1
    queue: list[dict[str, Any]] = []

    for field in FORM_FIELDS:
        value = draft.get(field)
        if value in (None, ""):
            continue
        action_type = "type" if field in TYPE_FIELDS else "select"
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

    for field in SCORE_FIELDS:
        code = field.removeprefix("score_")
        if code not in levels:
            continue
        queue.append(
            {
                "type": "select",
                "field": field,
                "label": rules.CRITERIA_LABEL[code],
                "selector": f"[data-agent-field={field}]",
                "value": levels[code],
                "run_seq": run_seq,
            }
        )

    for field in FLAG_FIELDS:
        code = field.removeprefix("flag_")
        if not flags.get(code):
            continue
        queue.append(
            {
                "type": "select",
                "field": field,
                "label": rules.HARD_FLAGS[code][0],
                "selector": f"[data-agent-field={field}]",
                "value": "1",
                "run_seq": run_seq,
            }
        )

    run_kind = "correction" if state.get("revise_rounds") else "full"
    content = say.PLAN_CORRECTION if run_kind == "correction" else say.PLAN_FULL

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


def route_after_plan(state: SwapCarState) -> str:
    return "fill" if state.get("action_queue") else "appraise"


async def fill_node(state: SwapCarState) -> dict[str, Any]:
    """Pop ĐÚNG 1 action mỗi vòng — mỗi vòng là một state-delta stream ra frontend."""
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


def route_after_fill(state: SwapCarState) -> str:
    return "fill" if state.get("action_queue") else "appraise"


# --------------------------------------------------------------------------
# Node: appraise — Smart Solution + bước 1 của công thức
# --------------------------------------------------------------------------

def _persist_appraisal(payload: dict[str, Any]) -> dict[str, Any]:
    """Ghi hồ sơ qua ĐÚNG repository mà form thủ công dùng.

    Trả về dict chứ không trả ORM object: session đóng là instance detach, đọc
    thuộc tính sau đó nổ `DetachedInstanceError`.
    """
    with SessionLocal() as session:
        customer = get_customer_by_code(session, str(payload["customer_code"]))
        if customer is None:
            raise ValueError("customer_not_found")

        appraisal = appraisal_repo.create_appraisal(
            session,
            customer_id=customer.id,
            make=str(payload["make"]),
            model=str(payload["model"]),
            year=int(payload["year"]),
            trim=str(payload.get("trim") or ""),
            plate_no=payload.get("plate_no"),
            odo_km=int(payload.get("odo_km") or 0),
            first_registration_date=date.fromisoformat(str(payload["first_registration_date"])),
            ownership_months=payload.get("ownership_months"),
            flags=payload.get("flags") or {},
            levels=payload.get("levels") or {},
            repair_cost=int(payload.get("repair_cost") or 0),
            sales_staff_id=payload.get("sales_staff_id"),
        )
        return {
            "code": appraisal.code or "",
            "market_price": appraisal.market_price,
            "total_score_pct": appraisal.total_score_pct,
            "repair_cost": appraisal.repair_cost,
            "value_a": appraisal.value_a,
            "estimated": [
                rules.CRITERIA_LABEL[score.criteria_code]
                for score in appraisal.scores
                if score.estimated
            ],
        }


async def appraise_node(state: SwapCarState) -> dict[str, Any]:
    """Điều phối Smart Solution (D+E), nhắc SLA (F) và chốt giá trị A."""
    draft = state.get("draft") or {}
    payload = {
        **draft,
        "customer_code": state.get("customer_code"),
        "flags": state.get("flags") or {},
        "levels": state.get("levels") or {},
        "sales_staff_id": state.get("sales_staff_id"),
    }

    try:
        result = await asyncio.to_thread(_persist_appraisal, payload)
    except NoMarketPriceError as exc:
        content = say.NO_MARKET_PRICE.format(make=exc.make, model=exc.model, year=exc.year)
        return {
            "messages": [AIMessage(content=content)],
            "current_action": None,
            "status": "manual_appraisal",
            "error": "no_market_price",
            "response": content,
        }
    except Exception:  # noqa: BLE001
        return {
            "messages": [AIMessage(content=say.APPRAISE_FAILED)],
            "current_action": None,
            "status": "error",
            "error": "persist_failed",
            "response": say.APPRAISE_FAILED,
        }

    lines = [
        say.SMART_SOLUTION.format(
            code=result["code"],
            steps=rules.SMART_SOLUTION_STEPS,
            items=rules.SMART_SOLUTION_ITEMS,
            sla=rules.SMART_SOLUTION_SLA_HOURS,
        ),
        "",
        say.APPRAISAL_SUMMARY.format(
            make=draft.get("make"),
            model=draft.get("model"),
            year=draft.get("year"),
            market_price=money(result["market_price"]),
            score=result["total_score_pct"],
            repair_cost=money(result["repair_cost"]),
            value_a=money(result["value_a"]),
        ),
    ]
    if result["estimated"]:
        lines += [
            "",
            say.ESTIMATED_WARNING.format(
                count=len(result["estimated"]), labels=", ".join(result["estimated"])
            ),
        ]

    content = "\n".join(lines)
    return {
        "messages": [AIMessage(content=content)],
        "current_action": None,
        "appraisal_code": result["code"],
        "market_price": result["market_price"],
        "total_score_pct": result["total_score_pct"],
        "repair_cost": result["repair_cost"],
        "value_a": result["value_a"],
        "estimated_criteria": result["estimated"],
        "sla_hours": rules.SMART_SOLUTION_SLA_HOURS,
        "status": "appraised",
        "response": content,
    }


def route_after_appraise(state: SwapCarState) -> str:
    return "quote" if state.get("status") == "appraised" else "end"


# --------------------------------------------------------------------------
# Node: quote — bước 2 & 3
# --------------------------------------------------------------------------

def _persist_quote(code: str, vehicle_id: str) -> dict[str, Any]:
    with SessionLocal() as session:
        quote = appraisal_repo.add_quote(session, appraisal_code=code, vehicle_id=vehicle_id)
        if quote is None:
            raise ValueError("appraisal_not_found")
        return {
            "vehicle_id": quote.vehicle_id,
            "model": quote.model,
            "list_price": quote.list_price,
            "total_fees": quote.total_fees,
            "value_b": quote.value_b,
            "promo_new_car": quote.promo_new_car,
            "trade_in_bonus": quote.trade_in_bonus,
            "value_a": quote.value_a,
            "amount_c": quote.amount_c,
        }


async def quote_node(state: SwapCarState) -> dict[str, Any]:
    draft = state.get("draft") or {}
    vehicle_id = str(draft.get("vehicle_id") or "")

    try:
        quote = await asyncio.to_thread(
            _persist_quote, str(state.get("appraisal_code") or ""), vehicle_id
        )
    except Exception:  # noqa: BLE001
        return {
            "messages": [AIMessage(content=say.APPRAISE_FAILED)],
            "status": "error",
            "error": "quote_failed",
            "response": say.APPRAISE_FAILED,
        }

    lines = [
        say.QUOTE_SUMMARY.format(
            model=quote["model"],
            list_price=money(quote["list_price"]),
            total_fees=money(quote["total_fees"]),
            value_b=money(quote["value_b"]),
            value_a=money(quote["value_a"]),
            promo=money(quote["promo_new_car"]),
            bonus=money(quote["trade_in_bonus"]),
            amount_c=money(quote["amount_c"]),
        )
    ]
    if quote["amount_c"] < 0:
        lines += ["", say.QUOTE_NEGATIVE.format(amount_c=money(quote["amount_c"]))]
    lines += ["", say.ASK_PRICE_OK]

    content = "\n".join(lines)
    return {
        "messages": [AIMessage(content=content)],
        "quote": quote,
        "status": "quoted",
        "awaiting": "confirm_price",
        "response": content,
    }


# --------------------------------------------------------------------------
# Node: confirm_price — nhánh H của sơ đồ, dùng interrupt()
# --------------------------------------------------------------------------

async def confirm_price_node(state: SwapCarState) -> dict[str, Any]:
    """Đóng băng graph chờ sales trả lời thay khách."""
    answer = interrupt(
        {
            "kind": "swap_confirm_price",
            "appraisal_code": state.get("appraisal_code"),
            "quote": state.get("quote") or {},
            "value_a": state.get("value_a"),
            "total_score_pct": state.get("total_score_pct"),
            "estimated_criteria": state.get("estimated_criteria") or [],
        }
    )
    text = str(answer or "")

    if classify_answer(text) == "yes":
        return {"awaiting": None, "status": "price_agreed", "query": None}
    return {"awaiting": None, "status": "price_rejected", "query": text}


def route_after_confirm_price(state: SwapCarState) -> str:
    return "checklist" if state.get("status") == "price_agreed" else "revise"


# --------------------------------------------------------------------------
# Node: revise — khách chưa đồng ý giá, quay lại tính lại (nhánh H -> G)
# --------------------------------------------------------------------------

FIELD_KEYWORDS: dict[str, tuple[str, ...]] = {
    "repair_cost": ("sua chua", "sua", "don dep", "chi phi", "tan trang"),
    "vehicle_id": ("doi sang", "chuyen sang", "xe moi", "vf", "minio", "herio", "nerio", "limo"),
}

CRITERIA_KEYWORDS: dict[str, tuple[str, ...]] = {
    "engine": ("may", "dong co", "hop so"),
    "chassis": ("gam", "khung gam", "giam xoc", "treo"),
    "electrical": ("dien", "dieu hoa", "man hinh", "cam bien"),
    "exterior": ("son", "vo xe", "ngoai that", "lop"),
    "interior": ("noi that", "cabin", "ghe", "vo lang"),
    "service": ("bao duong", "so bao duong"),
    "extras": ("mau", "phu kien", "phim", "camera"),
}


def _plain(text: str) -> str:
    from ..shared.catalog import strip_accents

    return re.sub(r"\s+", " ", strip_accents(text or "")).strip()


def parse_revision(text: str) -> tuple[dict[str, Any], dict[str, str]]:
    """Đọc yêu cầu sửa bằng TỪ KHOÁ, không tốn thêm một lượt LLM.

    Trả `(thay đổi ở draft, mức chấm mới)`. Không nhận ra gì thì trả rỗng để
    node hỏi lại — đoán bừa ở đây là tính sai tiền cho khách.
    """
    plain = _plain(text)
    changes: dict[str, Any] = {}
    levels: dict[str, str] = {}

    vehicle_id = match_vehicle(text)
    if vehicle_id:
        changes["vehicle_id"] = vehicle_id

    if any(keyword in plain for keyword in FIELD_KEYWORDS["repair_cost"]):
        amount = parse_money(text)
        if amount is not None:
            changes["repair_cost"] = amount

    level = None
    for alias, code in _LEVEL_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", plain):
            level = code
            break
    if level:
        for criteria, keywords in CRITERIA_KEYWORDS.items():
            if any(re.search(rf"\b{re.escape(word)}\b", plain) for word in keywords):
                levels[criteria] = level

    return changes, levels


def _update_valuation(code: str, repair_cost: int | None, levels: dict[str, str]) -> dict[str, Any]:
    with SessionLocal() as session:
        updated = appraisal_repo.update_valuation(
            session, code=code, repair_cost=repair_cost, levels=levels
        )
        if updated is None:
            raise ValueError("appraisal_not_found")
        return updated


async def revise_node(state: SwapCarState) -> dict[str, Any]:
    rounds = int(state.get("revise_rounds") or 0) + 1
    if rounds > MAX_REVISE_ROUNDS:
        content = say.REVISE_EXHAUSTED.format(rounds=MAX_REVISE_ROUNDS)
        return {
            "messages": [AIMessage(content=content)],
            "revise_rounds": rounds,
            "status": "manual_pending",
            "response": content,
        }

    changes, new_levels = parse_revision(str(state.get("query") or ""))
    if not changes and not new_levels:
        content = say.REVISE_UNCLEAR
        return {
            "messages": [AIMessage(content=content)],
            "revise_rounds": rounds,
            "status": "needs_revision",
            "response": content,
        }

    draft = {**(state.get("draft") or {}), **changes}
    levels = {**(state.get("levels") or {}), **new_levels}

    labels: list[str] = []
    if "vehicle_id" in changes:
        labels.append(f"xe mới {vehicle_name(changes['vehicle_id'])}")
    if "repair_cost" in changes:
        labels.append(f"chi phí sửa chữa {money(changes['repair_cost'])}")
    labels += [rules.CRITERIA_LABEL[code] for code in new_levels]

    update: dict[str, Any] = {
        "draft": draft,
        "levels": levels,
        "revise_rounds": rounds,
        "status": "revised",
    }

    # Đổi chi phí sửa chữa hoặc mức chấm là A đổi theo -> phải cập nhật bước 1
    # trước khi tính lại B/C, nếu không báo giá mới vẫn trừ đi giá thu xe cũ cũ.
    if "repair_cost" in changes or new_levels:
        try:
            recomputed = await asyncio.to_thread(
                _update_valuation,
                str(state.get("appraisal_code") or ""),
                changes.get("repair_cost"),
                levels,
            )
            update |= {
                "total_score_pct": recomputed["total_score_pct"],
                "repair_cost": recomputed["repair_cost"],
                "value_a": recomputed["value_a"],
                "estimated_criteria": recomputed["estimated"],
            }
            labels.append(f"giá thu xe cũ {money(recomputed['value_a'])}")
        except Exception:  # noqa: BLE001
            return {
                "messages": [AIMessage(content=say.APPRAISE_FAILED)],
                "revise_rounds": rounds,
                "status": "error",
                "error": "revise_failed",
                "response": say.APPRAISE_FAILED,
            }

    content = say.REVISE_APPLIED.format(labels=_join_labels(labels))
    update["messages"] = [AIMessage(content=content)]
    update["response"] = content
    return update


def route_after_revise(state: SwapCarState) -> str:
    return "quote" if state.get("status") == "revised" else "end"


# --------------------------------------------------------------------------
# Node: checklist — workflow gate, chặn MỀM (nhánh I/J/K)
# --------------------------------------------------------------------------

# Cách sales xác nhận đã làm xong checklist. Để riêng chứ không nhét vào
# `AFFIRMATIVE` dùng chung: "xong hết" là câu trả lời cho một danh sách việc, còn
# `AFFIRMATIVE` đang phục vụ câu hỏi "thông tin đúng chưa" của 2 agent kia — nới
# từ vựng chung ra là đổi hành vi của chúng theo.
CHECKLIST_DONE_PHRASES = ("xong het", "xong roi", "xong ca", "du roi", "day du", "lam xong")


def _resume_to_codes(answer: Any) -> list[str]:
    """Nhận cả `{"done": [...]}` từ thẻ tích chọn lẫn chuỗi tự do từ ô chat."""
    if isinstance(answer, dict):
        return [str(code) for code in answer.get("done") or []]
    if isinstance(answer, list):
        return [str(code) for code in answer]

    plain = _plain(str(answer or ""))
    if not plain:
        return []

    # Sales gõ tay "xong hết" thì coi như tích đủ — vẫn phải là câu khẳng định rõ,
    # im lặng hoặc câu lấp lửng thì không tích hộ mục nào.
    if classify_answer(str(answer)) == "yes" or any(
        phrase in plain for phrase in CHECKLIST_DONE_PHRASES
    ):
        return [code for code, _ in rules.CHECKLIST_ITEMS]
    return [code for code, _ in rules.CHECKLIST_ITEMS if code in plain]


def _persist_checklist(code: str, done: list[str], handover: date) -> dict[str, Any]:
    with SessionLocal() as session:
        appraisal, missing = appraisal_repo.complete_checklist(
            session, appraisal_code=code, done=done, handover_date=handover
        )
        if appraisal is None:
            raise ValueError("appraisal_not_found")
        return {"missing": missing, "status": appraisal.status}


async def checklist_node(state: SwapCarState) -> dict[str, Any]:
    answer = interrupt(
        {
            "kind": "swap_checklist",
            "appraisal_code": state.get("appraisal_code"),
            "items": [
                {"code": code, "label": label} for code, label in rules.CHECKLIST_ITEMS
            ],
        }
    )
    done = _resume_to_codes(answer)
    handover = date.today() + timedelta(days=HANDOVER_LEAD_DAYS)

    try:
        result = await asyncio.to_thread(
            _persist_checklist, str(state.get("appraisal_code") or ""), done, handover
        )
    except Exception:  # noqa: BLE001
        return {
            "messages": [AIMessage(content=say.HANDOVER_FAILED)],
            "awaiting": None,
            "status": "error",
            "error": "checklist_failed",
            "response": say.HANDOVER_FAILED,
        }

    return {
        "awaiting": None,
        "checklist_done": done,
        "checklist_missing": result["missing"],
        "handover_date": handover.isoformat(),
        "status": "checklist_blocked" if result["missing"] else "checklist_passed",
    }


def route_after_checklist(state: SwapCarState) -> str:
    if state.get("status") == "checklist_passed":
        return "handover"
    return "end" if state.get("status") == "error" else "checklist_blocked"


async def checklist_blocked_node(state: SwapCarState) -> dict[str, Any]:
    """Chặn MỀM: nêu mục còn thiếu và dừng lượt, không huỷ hồ sơ."""
    missing = state.get("checklist_missing") or []
    content = say.CHECKLIST_BLOCKED.format(
        count=len(missing),
        labels=_join_labels([rules.CHECKLIST_LABEL[code] for code in missing]),
        code=state.get("appraisal_code") or "",
    )
    return {
        "messages": [AIMessage(content=content)],
        "current_action": None,
        "status": "blocked",
        "response": content,
    }


async def handover_node(state: SwapCarState) -> dict[str, Any]:
    """Đủ checklist -> hẹn ngày giao xe (nhánh L, kết thúc quy trình)."""
    quote = state.get("quote") or {}
    handover_date = str(state.get("handover_date") or "")
    try:
        pretty = datetime.fromisoformat(handover_date).strftime("%d/%m/%Y")
    except ValueError:
        pretty = handover_date

    content = say.HANDOVER.format(
        code=state.get("appraisal_code") or "",
        model=quote.get("model") or "",
        amount_c=money(quote.get("amount_c")),
        handover_date=pretty,
    )
    return {
        "messages": [AIMessage(content=content)],
        "current_action": None,
        "status": "accepted",
        "response": content,
    }
