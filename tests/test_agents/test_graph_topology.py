"""Khoá cấu trúc 2 graph.

Các node và router đã được test riêng lẻ ở `test_form_nodes.py`, nhưng việc chúng
được NỐI ĐÚNG vào StateGraph thì không có gì bảo vệ: nối sai một edge (ví dụ
`summarize -> END` thay vì `summarize -> confirm_details`) thì graph vẫn compile
và toàn bộ test node vẫn xanh. Test này là lưới an toàn cho việc đó.
"""

from src.backend.agents.crm_lead import graph as crm_lead
from src.backend.agents.test_drive import graph as test_drive

SHARED_NODES = {
    "init",
    "extract",
    "ask_missing",
    "plan",
    "fill",
    "summarize",
    "confirm_details",
    "patch",
    "ask_submit",
    "confirm_submit",
    "submit",
    "manual_ready",
    "report",
}


def node_names(compiled) -> set[str]:
    return {name for name in compiled.get_graph().nodes if name not in {"__start__", "__end__"}}


def edge_pairs(compiled) -> set[tuple[str, str]]:
    return {(edge.source, edge.target) for edge in compiled.get_graph().edges}


class TestAgentIdentity:
    def test_names_match_the_frontend_contract(self):
        # Ba chỗ phải khớp: hằng số này, key trong `agents__unsafe_dev_only` ở
        # main.jsx, và tham số của `useCoAgent`. Lệch một ký tự thì chat im lặng.
        assert test_drive.AGENT_NAME == "test_drive_agent"
        assert crm_lead.AGENT_NAME == "crm_lead_agent"

    def test_channels_are_distinct(self):
        assert test_drive.CHANNEL == "web"
        assert crm_lead.CHANNEL == "crm"

    def test_each_agent_compiles_its_own_graph(self):
        assert test_drive.agent is not crm_lead.agent


class TestTestDriveGraph:
    def test_has_exactly_the_shared_nodes(self):
        assert node_names(test_drive.agent) == SHARED_NODES

    def test_starts_at_init_then_extract(self):
        edges = edge_pairs(test_drive.agent)
        assert ("__start__", "init") in edges
        assert ("init", "extract") in edges

    def test_summarize_goes_straight_to_confirm_details(self):
        assert ("summarize", "confirm_details") in edge_pairs(test_drive.agent)

    def test_has_no_duplicate_check(self):
        assert "check_duplicate" not in node_names(test_drive.agent)

    def test_fill_loops_back_onto_itself(self):
        """Mỗi vòng `fill` pop 1 action — mất self-loop là con trỏ nhảy phát một."""
        assert ("fill", "fill") in edge_pairs(test_drive.agent)

    def test_submit_reports_before_ending(self):
        edges = edge_pairs(test_drive.agent)
        assert ("submit", "report") in edges
        assert ("report", "__end__") in edges


class TestCrmLeadGraph:
    def test_adds_duplicate_nodes_on_top_of_the_shared_set(self):
        assert node_names(crm_lead.agent) == SHARED_NODES | {
            "check_duplicate",
            "duplicate_blocked",
        }

    def test_duplicate_check_sits_between_summarize_and_confirm(self):
        edges = edge_pairs(crm_lead.agent)

        assert ("summarize", "check_duplicate") in edges
        assert ("check_duplicate", "confirm_details") in edges
        assert ("check_duplicate", "duplicate_blocked") in edges
        # Không được còn đường tắt bỏ qua bước kiểm trùng.
        assert ("summarize", "confirm_details") not in edges

    def test_duplicate_blocked_ends_the_turn(self):
        assert ("duplicate_blocked", "__end__") in edge_pairs(crm_lead.agent)

    def test_everything_else_matches_the_test_drive_graph(self):
        """Hai graph chỉ được khác nhau ở đúng nhánh kiểm trùng."""
        only_in_crm = edge_pairs(crm_lead.agent) - edge_pairs(test_drive.agent)
        only_in_web = edge_pairs(test_drive.agent) - edge_pairs(crm_lead.agent)

        assert only_in_crm == {
            ("summarize", "check_duplicate"),
            ("check_duplicate", "confirm_details"),
            ("check_duplicate", "duplicate_blocked"),
            ("duplicate_blocked", "__end__"),
        }
        assert only_in_web == {("summarize", "confirm_details")}
