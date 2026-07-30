"""Graph agent CRM — sales nhập lead hộ khách trong Admin Portal.

Giống graph lái thử, KHÁC ĐÚNG MỘT CHỖ: chèn `check_duplicate` giữa `summarize`
và `confirm_details`.

START -> init -> extract
extract -> ask_missing -> END
extract -> plan -> fill (tự lặp) -> summarize -> check_duplicate
check_duplicate -> duplicate_blocked -> END   (trùng SĐT: chặn cứng)
check_duplicate -> confirm_details            (sạch, hoặc chỉ trùng tên)
confirm_details -> patch -> plan | ask_submit -> confirm_submit
confirm_submit -> submit -> report -> END | manual_ready -> END
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from ..shared.nodes.form_nodes import (
    ask_missing_node,
    ask_submit_node,
    confirm_details_node,
    confirm_submit_node,
    extract_node,
    fill_node,
    manual_ready_node,
    patch_node,
    plan_node,
    report_node,
    route_after_confirm_details,
    route_after_confirm_submit,
    route_after_extract,
    route_after_fill,
    route_after_patch,
    route_after_plan,
    submit_node,
    summarize_node,
)
from ..shared.nodes.init_node import make_init_node
from ..shared.state import AgentState
from .nodes import (
    check_duplicate_node,
    duplicate_blocked_node,
    route_after_check_duplicate,
)

CHANNEL = "crm"
AGENT_NAME = "crm_lead_agent"


def build_graph(*, checkpointer=None):
    builder = StateGraph(AgentState)

    builder.add_node("init", make_init_node(CHANNEL))
    builder.add_node("extract", extract_node)
    builder.add_node("ask_missing", ask_missing_node)
    builder.add_node("plan", plan_node)
    builder.add_node("fill", fill_node)
    builder.add_node("summarize", summarize_node)
    builder.add_node("check_duplicate", check_duplicate_node)
    builder.add_node("duplicate_blocked", duplicate_blocked_node)
    builder.add_node("confirm_details", confirm_details_node)
    builder.add_node("patch", patch_node)
    builder.add_node("ask_submit", ask_submit_node)
    builder.add_node("confirm_submit", confirm_submit_node)
    builder.add_node("submit", submit_node)
    builder.add_node("manual_ready", manual_ready_node)
    builder.add_node("report", report_node)

    builder.add_edge(START, "init")
    builder.add_edge("init", "extract")

    builder.add_conditional_edges(
        "extract",
        route_after_extract,
        {"ask_missing": "ask_missing", "plan": "plan", "end": END},
    )
    builder.add_edge("ask_missing", END)

    builder.add_conditional_edges(
        "plan", route_after_plan, {"fill": "fill", "summarize": "summarize"}
    )
    builder.add_conditional_edges(
        "fill", route_after_fill, {"fill": "fill", "summarize": "summarize"}
    )

    # Chỗ duy nhất khác graph lái thử.
    builder.add_edge("summarize", "check_duplicate")
    builder.add_conditional_edges(
        "check_duplicate",
        route_after_check_duplicate,
        {"duplicate_blocked": "duplicate_blocked", "confirm_details": "confirm_details"},
    )
    builder.add_edge("duplicate_blocked", END)

    builder.add_conditional_edges(
        "confirm_details",
        route_after_confirm_details,
        {"patch": "patch", "ask_submit": "ask_submit"},
    )

    builder.add_conditional_edges("patch", route_after_patch, {"plan": "plan", "end": END})

    builder.add_edge("ask_submit", "confirm_submit")
    builder.add_conditional_edges(
        "confirm_submit",
        route_after_confirm_submit,
        {"submit": "submit", "manual_ready": "manual_ready"},
    )

    builder.add_edge("submit", "report")
    builder.add_edge("report", END)
    builder.add_edge("manual_ready", END)

    return builder.compile(checkpointer=checkpointer or MemorySaver())


agent = build_graph()
