"""Test agent `swap_car` — nghiệp vụ 2 (đổi xe cũ lấy xe mới).

Chia 3 phần: cấu trúc graph, các node RULE (chạy được không cần LLM), và phần
bóc thông tin có LLM (dùng LLM giả).
"""

from datetime import date, timedelta

import pytest

from src.backend.agents.swap_car import graph as swap_car
from src.backend.agents.swap_car import nodes
from src.backend.agents.swap_car.state import (
    FIELD_LABELS,
    FLAG_FIELDS,
    FORM_FIELDS,
    REQUIRED_FIELDS,
    SCORE_FIELDS,
    empty_state,
)
from src.backend.services import appraisal_rules as rules

EXPECTED_NODES = {
    "init",
    "extract",
    "ask_missing",
    "eligibility",
    "rejected",
    "explain",
    "plan",
    "fill",
    "appraise",
    "quote",
    "confirm_price",
    "revise",
    "checklist",
    "checklist_blocked",
    "handover",
}


def node_names(compiled) -> set[str]:
    return {name for name in compiled.get_graph().nodes if name not in {"__start__", "__end__"}}


def edge_pairs(compiled) -> set[tuple[str, str]]:
    return {(edge.source, edge.target) for edge in compiled.get_graph().edges}


class TestAgentIdentity:
    def test_name_matches_the_frontend_contract(self):
        # Ba chỗ phải khớp: hằng số này, key trong `agents__unsafe_dev_only` ở
        # main.jsx, và tham số `useCoAgent` trong AppraisalBoard.jsx.
        assert swap_car.AGENT_NAME == "swap_car_agent"

    def test_runs_only_inside_the_admin_portal(self):
        assert swap_car.CHANNEL == "crm"

    def test_is_a_separate_graph_from_the_form_agents(self):
        from src.backend.agents.crm_lead import graph as crm_lead

        assert swap_car.agent is not crm_lead.agent
        assert node_names(swap_car.agent) != node_names(crm_lead.agent)


class TestGraphTopology:
    """Khoá đúng sơ đồ `agent-crm-flow.md` §2 — nối sai edge thì graph vẫn compile."""

    def test_has_exactly_the_expected_nodes(self):
        assert node_names(swap_car.agent) == EXPECTED_NODES

    def test_starts_at_init_then_extract(self):
        edges = edge_pairs(swap_car.agent)
        assert ("__start__", "init") in edges
        assert ("init", "extract") in edges

    def test_eligibility_gate_runs_before_scoring(self):
        edges = edge_pairs(swap_car.agent)
        assert ("extract", "eligibility") in edges
        assert ("eligibility", "explain") in edges
        assert ("eligibility", "rejected") in edges
        # Không có đường tắt từ extract thẳng tới chấm điểm.
        assert ("extract", "appraise") not in edges
        assert ("extract", "plan") not in edges

    def test_rejected_ends_without_creating_a_deal(self):
        edges = edge_pairs(swap_car.agent)
        assert ("rejected", "__end__") in edges
        assert not [target for source, target in edges if source == "rejected" and target != "__end__"]

    def test_explain_then_fills_the_form(self):
        edges = edge_pairs(swap_car.agent)
        assert ("explain", "plan") in edges
        assert ("plan", "fill") in edges
        assert ("fill", "fill") in edges  # tự lặp, mỗi vòng 1 action

    def test_appraise_leads_to_quote_then_confirmation(self):
        edges = edge_pairs(swap_car.agent)
        assert ("appraise", "quote") in edges
        assert ("quote", "confirm_price") in edges

    def test_price_rejection_loops_back_to_quote_not_appraise(self):
        # Nhánh H -> G của sơ đồ. Quay lại `appraise` sẽ đẻ thêm hồ sơ mới mỗi
        # vòng sửa, đúng thứ `update_valuation` sinh ra để tránh.
        edges = edge_pairs(swap_car.agent)
        assert ("confirm_price", "revise") in edges
        assert ("revise", "quote") in edges
        assert ("revise", "appraise") not in edges

    def test_checklist_gate_before_handover(self):
        edges = edge_pairs(swap_car.agent)
        assert ("confirm_price", "checklist") in edges
        assert ("checklist", "handover") in edges
        assert ("checklist", "checklist_blocked") in edges
        assert ("checklist_blocked", "__end__") in edges
        assert ("handover", "__end__") in edges

    def test_cannot_reach_handover_without_the_checklist(self):
        edges = edge_pairs(swap_car.agent)
        into_handover = {source for source, target in edges if target == "handover"}
        assert into_handover == {"checklist"}


class TestStateContract:
    def test_required_fields_are_a_subset_of_form_fields(self):
        assert set(REQUIRED_FIELDS) <= set(FORM_FIELDS)

    def test_every_form_field_has_a_label(self):
        assert set(FIELD_LABELS) == set(FORM_FIELDS)

    def test_score_fields_cover_the_seven_manual_criteria(self):
        assert set(SCORE_FIELDS) == {f"score_{code}" for code in rules.SCORED_CRITERIA}
        assert "score_odo" not in SCORE_FIELDS

    def test_flag_fields_cover_the_four_hard_conditions(self):
        assert set(FLAG_FIELDS) == {f"flag_{code}" for code in rules.HARD_FLAGS}


class TestMoneyHelpers:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("20 triệu", 20_000_000),
            ("chi phí sửa 15tr", 15_000_000),
            ("1.5 tỷ", 1_500_000_000),
            ("20.000.000", 20_000_000),
            ("500 nghìn", 500_000),
        ],
    )
    def test_parse_money(self, raw, expected):
        assert nodes.parse_money(raw) == expected

    @pytest.mark.parametrize("raw", [None, "", "không có số"])
    def test_parse_money_gives_up_quietly(self, raw):
        assert nodes.parse_money(raw) is None

    def test_money_formats_vietnamese_style(self):
        assert nodes.money(425_000_000) == "425.000.000 đ"


class TestParseRevision:
    def test_switching_the_new_car(self):
        changes, levels = nodes.parse_revision("khách muốn đổi sang VF 5")
        assert changes["vehicle_id"] == "vf5"
        assert levels == {}

    def test_changing_repair_cost(self):
        changes, _ = nodes.parse_revision("chi phí sửa chữa 20 triệu")
        assert changes["repair_cost"] == 20_000_000

    def test_rescoring_a_criteria(self):
        _changes, levels = nodes.parse_revision("gầm chấm mức trung bình")
        assert levels == {"chassis": "trung_binh"}

    def test_unrecognised_text_changes_nothing(self):
        # Đoán bừa ở đây là tính sai tiền cho khách -> phải trả rỗng để hỏi lại.
        assert nodes.parse_revision("ừ thì cũng được") == ({}, {})

    def test_bare_number_without_context_is_ignored(self):
        assert nodes.parse_revision("20 triệu")[0] == {}


class TestChecklistResume:
    def test_card_sends_a_dict(self):
        assert nodes._resume_to_codes({"done": ["contract", "deposit"]}) == ["contract", "deposit"]

    def test_typing_yes_ticks_everything(self):
        assert len(nodes._resume_to_codes("xong hết rồi")) == 4

    def test_empty_answer_ticks_nothing(self):
        assert nodes._resume_to_codes("") == []


@pytest.mark.asyncio
class TestRuleNodes:
    async def test_extract_without_a_customer_stops_early(self):
        state = empty_state()
        state["query"] = "Honda City 2022"
        result = await nodes.extract_node(state)
        assert result["status"] == "no_customer"
        assert nodes.route_after_extract(result) == "end"

    async def test_missing_fields_route_to_ask_missing(self):
        state = empty_state()
        state["draft"] = {"make": "Honda"}
        state["missing_fields"] = ["model", "year"]
        assert nodes.route_after_extract(state) == "ask_missing"

        asked = await nodes.ask_missing_node(state)
        assert "Dòng xe cũ" in asked["response"]
        assert "Đời xe" in asked["response"]

    async def test_eligibility_passes_a_recent_clean_car(self):
        state = empty_state()
        state["draft"] = {
            "first_registration_date": (date.today() - timedelta(days=800)).isoformat()
        }
        result = await nodes.eligibility_node(state)
        assert result["eligibility_status"] == "passed"
        assert nodes.route_after_eligibility(result) == "explain"

    async def test_eligibility_rejects_a_flooded_car(self):
        state = empty_state()
        state["draft"] = {
            "first_registration_date": (date.today() - timedelta(days=800)).isoformat()
        }
        state["flags"] = {"flood_damaged": True}
        result = await nodes.eligibility_node(state)
        assert result["eligibility_status"] == "rejected_flood_damaged"
        assert nodes.route_after_eligibility(result) == "rejected"

    async def test_expert_gets_the_short_explanation(self):
        state = empty_state()
        state["experience"] = "expert"
        state["eligibility_checks"] = [{"label": "x", "why": "y", "passed": True}]
        result = await nodes.explain_node(state)
        # Không gọi LLM, không giảng lại — progressive autonomy.
        assert "chuyển sang thẩm định" in result["response"]

    async def test_plan_queues_form_scores_and_raised_flags(self):
        state = empty_state()
        state["draft"] = {"make": "Honda", "model": "City", "year": 2022, "vehicle_id": "vf3"}
        state["levels"] = {"engine": "tot"}
        state["flags"] = {"flood_damaged": True}

        result = await nodes.plan_node(state)
        fields = [action["field"] for action in result["action_queue"]]

        assert fields == ["make", "model", "year", "vehicle_id", "score_engine", "flag_flood_damaged"]
        assert result["run_seq"] == 1
        # BẪY #4: run_seq đóng dấu lên TỪNG action.
        assert all(action["run_seq"] == 1 for action in result["action_queue"])
        assert result["action_queue"][0]["type"] == "type"  # ô chữ -> gõ từng ký tự
        assert result["action_queue"][2]["type"] == "select"  # đời xe -> set thẳng

    async def test_plan_skips_empty_fields(self):
        state = empty_state()
        state["draft"] = {"make": "Honda", "trim": "", "plate_no": None}
        result = await nodes.plan_node(state)
        assert [action["field"] for action in result["action_queue"]] == ["make"]

    async def test_fill_pops_exactly_one_action_per_round(self):
        state = empty_state()
        state["action_queue"] = [
            {"field": "make", "type": "type", "value": "Honda"},
            {"field": "model", "type": "type", "value": "City"},
        ]
        result = await nodes.fill_node(state)
        assert result["current_action"]["field"] == "make"
        assert len(result["action_queue"]) == 1
        assert nodes.route_after_fill(result) == "fill"

    async def test_revise_gives_up_after_the_round_limit(self):
        state = empty_state()
        state["revise_rounds"] = nodes.MAX_REVISE_ROUNDS
        state["query"] = "đổi sang VF 5"
        result = await nodes.revise_node(state)
        assert result["status"] == "manual_pending"
        assert nodes.route_after_revise(result) == "end"

    async def test_revise_asks_again_when_the_request_is_unclear(self):
        state = empty_state()
        state["query"] = "chưa ưng lắm"
        result = await nodes.revise_node(state)
        assert result["status"] == "needs_revision"
        assert nodes.route_after_revise(result) == "end"

    async def test_blocked_checklist_names_the_missing_items(self):
        state = empty_state()
        state["checklist_missing"] = ["papers", "status"]
        state["appraisal_code"] = "DG-1001"
        result = await nodes.checklist_blocked_node(state)
        assert result["status"] == "blocked"
        assert "Thu đủ giấy tờ gốc xe cũ" in result["response"]
        assert "DG-1001" in result["response"]


class TestExtractNormalisation:
    def test_only_true_flags_are_recorded(self):
        # `None` và `False` đều là "sales không nói" — bật cờ hộ là tự loại xe.
        extracted = nodes.ExtractedSwapCar(flood_damaged=True, odo_tampered=False)
        _draft, flags, _levels = nodes._normalize(extracted)
        assert flags == {"flood_damaged": True}

    def test_condition_words_map_to_levels(self):
        extracted = nodes.ExtractedSwapCar(condition_engine="tot", condition_chassis="lạ hoắc")
        _draft, _flags, levels = nodes._normalize(extracted)
        assert levels == {"engine": "tot"}

    def test_vehicle_is_resolved_against_the_catalog(self):
        extracted = nodes.ExtractedSwapCar(new_vehicle="con VF8 all new")
        draft, _flags, _levels = nodes._normalize(extracted)
        assert draft["vehicle_id"] == "vf8-allnew"

    def test_future_registration_date_is_dropped(self):
        future = (date.today() + timedelta(days=30)).isoformat()
        extracted = nodes.ExtractedSwapCar(first_registration_date=future)
        draft, _flags, _levels = nodes._normalize(extracted)
        assert "first_registration_date" not in draft

    def test_implausible_year_is_dropped(self):
        extracted = nodes.ExtractedSwapCar(year=1899)
        draft, _flags, _levels = nodes._normalize(extracted)
        assert "year" not in draft
