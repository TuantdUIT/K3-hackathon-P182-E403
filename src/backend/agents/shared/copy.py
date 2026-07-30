"""Câu chữ agent phát ra, tách khỏi logic node.

Hai agent dùng CHUNG toàn bộ node ở `shared/nodes/form_nodes.py`; chỗ khác nhau
thật giữa chúng chỉ là giọng nói: agent lái thử nói VỚI KHÁCH, agent CRM nói VỚI
NHÂN VIÊN KINH DOANH về một khách thứ ba. Gom hết chuỗi vào đây để node không
phải biết mình đang phục vụ ai.

Mọi field đều bắt buộc (không có default) — thêm agent mới mà quên dịch một câu
thì vỡ ngay lúc import, chứ không âm thầm nói sai giọng lúc chạy.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CopyPack:
    # extract
    greeting: str
    extract_failed: str  # {hotline}

    # ask_missing — {need} là danh sách nhãn field còn thiếu, đã nối sẵn
    ask_missing: str

    # plan
    plan_full: str
    plan_correction: str

    # summarize
    summary_header: str
    summary_footer: str

    # ask_submit
    ask_submit: str

    # patch
    patch_applied: str  # {labels}
    patch_unclear: str
    patch_exhausted: str  # {rounds} {hotline}

    # submit / manual / report
    submit_invalid: str  # {error}
    submit_failed: str  # {hotline}
    manual_ready: str
    report: str  # {code} {date} {time} {vehicle} {ward}

    # check trùng (chỉ graph CRM đi qua, nhưng để cả 2 pack cho đồng nhất)
    duplicate_phone: str  # {code} {name}
    duplicate_name_warning: str  # {code}


def get_copy(state: Any) -> CopyPack:
    """Chọn bộ câu chữ theo `channel` mà node `init` của graph đã đóng dấu.

    Import NẰM TRONG HÀM là có chủ đích: `<agent>/copy.py` phải import `CopyPack`
    từ module này, nên import chúng ở module level sẽ tạo vòng tròn.
    """
    channel = (state or {}).get("channel") or "web"
    if channel == "crm":
        from ..crm_lead.copy import COPY

        return COPY

    from ..test_drive.copy import COPY

    return COPY
