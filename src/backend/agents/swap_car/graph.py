"""Graph agent đổi xe cũ lấy xe mới — nghiệp vụ 2.

Dựng đúng theo sơ đồ trong `agent-crm-flow.md` §2. Đối chiếu từng nút của sơ đồ
với node ở đây để sau này sửa sơ đồ là biết phải sửa chỗ nào:

    sơ đồ            node
    -------------    ----------------------------------------------------
    A                init + extract      (sales thuật lại xe cũ của khách)
    B                eligibility         (rule: ≥6 tháng, <7 năm, 4 cờ cứng)
    BX               rejected            (từ chối, KHÔNG tạo giao dịch)
    C                explain             (Ô XANH: giải thích vì sao, ngắn dần)
    D + E            appraise            (điều phối Smart Solution, chấm điểm)
    F                appraise            (đóng dấu hạn SLA để hệ thống nhắc)
    G                quote               (B = giá lăn bánh, C = tiền trả thêm)
    H                confirm_price       (khách đồng ý giá? — interrupt)
    H "Không" -> G   revise -> quote     (sửa chi phí/mức chấm/xe mới rồi tính lại)
    I + J            checklist           (4 việc bắt buộc — interrupt)
    K                checklist_blocked   (chặn MỀM, nêu mục còn thiếu)
    L                handover            (chốt ngày giao xe)

Ngoài sơ đồ: cặp `confirm_form` + `patch_form` chèn giữa `fill` và `appraise`,
mượn nguyên cặp `confirm_details` + `patch` của agent CRM. Sales soát hồ sơ con
trỏ vừa điền và gõ chỗ sai vào khung chat TRƯỚC khi `appraise` ghi vào DB —
`revise` ở nhánh H chỉ sửa được chi phí/xe mới/mức chấm, không sửa được đời xe
hay số km bóc tách nhầm.

START -> init -> extract
extract -> ask_missing -> END                 (thiếu field bắt buộc / chưa chọn khách)
extract -> eligibility
eligibility -> rejected -> END
eligibility -> market_check
market_check -> END                           (không có giá thị trường -> KHÔNG điền form)
market_check -> explain -> plan -> fill (tự lặp) -> confirm_form
confirm_form -> patch_form -> plan            (sửa -> điền lại -> soát lại)
patch_form -> confirm_form                    (không hiểu câu sửa, hỏi lại)
patch_form -> END                             (quá 3 vòng sửa)
confirm_form -> appraise
appraise -> END                               (không có giá thị trường -> thủ công)
appraise -> quote -> confirm_price
confirm_price -> revise -> quote | END        (quá 3 vòng sửa)
confirm_price -> checklist
checklist -> checklist_blocked -> END
checklist -> handover -> END
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .nodes import (
    appraise_node,
    ask_missing_node,
    checklist_blocked_node,
    checklist_node,
    confirm_form_node,
    confirm_price_node,
    eligibility_node,
    explain_node,
    extract_node,
    fill_node,
    handover_node,
    init_node,
    market_check_node,
    patch_form_node,
    plan_node,
    quote_node,
    rejected_node,
    revise_node,
    route_after_appraise,
    route_after_checklist,
    route_after_confirm_form,
    route_after_confirm_price,
    route_after_eligibility,
    route_after_extract,
    route_after_fill,
    route_after_market_check,
    route_after_patch_form,
    route_after_plan,
    route_after_revise,
)
from .state import SwapCarState

CHANNEL = "crm"
AGENT_NAME = "swap_car_agent"


def build_graph(*, checkpointer=None):
    builder = StateGraph(SwapCarState)

    builder.add_node("init", init_node)
    builder.add_node("extract", extract_node)
    builder.add_node("ask_missing", ask_missing_node)
    builder.add_node("eligibility", eligibility_node)
    builder.add_node("rejected", rejected_node)
    builder.add_node("market_check", market_check_node)
    builder.add_node("explain", explain_node)
    builder.add_node("plan", plan_node)
    builder.add_node("fill", fill_node)
    builder.add_node("confirm_form", confirm_form_node)
    builder.add_node("patch_form", patch_form_node)
    builder.add_node("appraise", appraise_node)
    builder.add_node("quote", quote_node)
    builder.add_node("confirm_price", confirm_price_node)
    builder.add_node("revise", revise_node)
    builder.add_node("checklist", checklist_node)
    builder.add_node("checklist_blocked", checklist_blocked_node)
    builder.add_node("handover", handover_node)

    builder.add_edge(START, "init")
    builder.add_edge("init", "extract")

    builder.add_conditional_edges(
        "extract",
        route_after_extract,
        {"ask_missing": "ask_missing", "eligibility": "eligibility", "end": END},
    )
    builder.add_edge("ask_missing", END)

    # Cổng loại trừ chạy TRƯỚC khi chấm điểm: chấm 8 tiêu chí cho một chiếc xe
    # ngập nước là làm việc thừa rồi vẫn phải vứt đi.
    builder.add_conditional_edges(
        "eligibility",
        route_after_eligibility,
        {"market_check": "market_check", "rejected": "rejected"},
    )
    builder.add_edge("rejected", END)

    # Không tra được giá thị trường thì dừng tại đây, KHÔNG cho con trỏ điền:
    # hồ sơ đó chắc chắn không tính ra tiền, diễn hoạt 14 ô chỉ để báo lỗi ở
    # cuối là bắt sales ngồi xem một việc vô ích.
    builder.add_conditional_edges(
        "market_check", route_after_market_check, {"explain": "explain", "end": END}
    )

    builder.add_edge("explain", "plan")
    builder.add_conditional_edges(
        "plan", route_after_plan, {"fill": "fill", "confirm_form": "confirm_form"}
    )
    builder.add_conditional_edges(
        "fill", route_after_fill, {"fill": "fill", "confirm_form": "confirm_form"}
    )

    # Chốt hồ sơ TRƯỚC khi ghi DB. Vòng `patch_form -> plan -> fill ->
    # confirm_form` lặp lại được, `MAX_CORRECTION_ROUNDS` là thứ cắt vòng.
    builder.add_conditional_edges(
        "confirm_form",
        route_after_confirm_form,
        {"appraise": "appraise", "patch_form": "patch_form"},
    )
    builder.add_conditional_edges(
        "patch_form",
        route_after_patch_form,
        {"plan": "plan", "confirm_form": "confirm_form", "end": END},
    )

    builder.add_conditional_edges(
        "appraise", route_after_appraise, {"quote": "quote", "end": END}
    )

    builder.add_edge("quote", "confirm_price")
    builder.add_conditional_edges(
        "confirm_price",
        route_after_confirm_price,
        {"checklist": "checklist", "revise": "revise"},
    )

    # Vòng sửa quay lại `quote`, KHÔNG quay lại `appraise`: hồ sơ đã tồn tại,
    # `revise` tự cập nhật A tại chỗ. Chạy lại `appraise` là đẻ thêm hồ sơ mới.
    builder.add_conditional_edges("revise", route_after_revise, {"quote": "quote", "end": END})

    builder.add_conditional_edges(
        "checklist",
        route_after_checklist,
        {
            "handover": "handover",
            "checklist_blocked": "checklist_blocked",
            "end": END,
        },
    )
    builder.add_edge("checklist_blocked", END)
    builder.add_edge("handover", END)

    # MemorySaver là bắt buộc: `interrupt()` cần checkpointer để đóng băng state,
    # frontend resume bằng cùng thread_id.
    return builder.compile(checkpointer=checkpointer or MemorySaver())


agent = build_graph()
