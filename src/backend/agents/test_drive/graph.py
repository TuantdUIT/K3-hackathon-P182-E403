"""Graph agent lái thử — khách tự đăng ký trên trang showcase.

START -> init -> extract
extract -> ask_missing -> END            (còn field bắt buộc bị thiếu)
extract -> plan -> fill (tự lặp) -> summarize -> confirm_details
confirm_details -> patch -> plan          (khách muốn sửa)
confirm_details -> ask_submit -> confirm_submit
confirm_submit -> submit -> report -> END (khách cho gửi hộ)
confirm_submit -> manual_ready -> END     (khách tự bấm gửi)
patch -> END                              (quá 5 vòng sửa)
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

CHANNEL = "web"
AGENT_NAME = "test_drive_agent"


def build_graph(*, checkpointer=None):
    builder = StateGraph(AgentState)

    builder.add_node("init", make_init_node(CHANNEL))
    builder.add_node("extract", extract_node)
    builder.add_node("ask_missing", ask_missing_node)
    builder.add_node("plan", plan_node)
    builder.add_node("fill", fill_node)
    builder.add_node("summarize", summarize_node)
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

    # Queue rỗng thì bỏ qua fill — xảy ra ở lượt sửa mà không field nào đổi.
    builder.add_conditional_edges(
        "plan", route_after_plan, {"fill": "fill", "summarize": "summarize"}
    )

    # fill tự lặp: mỗi vòng pop 1 action để frontend nhận từng state-delta.
    builder.add_conditional_edges(
        "fill", route_after_fill, {"fill": "fill", "summarize": "summarize"}
    )

    builder.add_edge("summarize", "confirm_details")
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

    # MemorySaver là bắt buộc: interrupt() cần checkpointer để đóng băng state,
    # frontend resume bằng cùng thread_id.
    return builder.compile(checkpointer=checkpointer or MemorySaver())


agent = build_graph()
