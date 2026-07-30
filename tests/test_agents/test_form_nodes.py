"""Test các node của graph điền form, dùng LLM giả."""

from datetime import date, timedelta

import pytest

from src.backend.agents.nodes.form_nodes import (
    MAX_CORRECTION_ROUNDS,
    ExtractedDraft,
    ask_missing_node,
    build_summary,
    classify_answer,
    direct_captures,
    extract_node,
    fill_node,
    mentioned_fields,
    patch_node,
    plan_node,
    route_after_extract,
    route_after_fill,
    route_after_patch,
    route_after_plan,
    summarize_node,
)
from src.backend.agents.state import FORM_FIELDS, empty_state

TOMORROW = (date.today() + timedelta(days=1)).isoformat()
NEXT_WEEK = (date.today() + timedelta(days=7)).isoformat()

FULL_DRAFT = {
    "name": "Trần Văn A",
    "phone": "0987654321",
    "email": "a.tran@example.com",
    "vehicle_id": "vf8",
    "test_drive_date": TOMORROW,
    "test_drive_time": "09:30",
    "ward": "Hoàn Kiếm",
    "note": "Muốn thử đường dài",
}


def state_with(**overrides):
    state = empty_state()
    state.update(overrides)
    return state


# ---------------------------------------------------------------- extract

class TestExtract:
    async def test_missing_fields_routes_to_ask_missing(self, fake_llm):
        fake_llm([ExtractedDraft(name="Nam", phone="0912345678")])

        result = await extract_node(state_with(query="Tôi là Nam, 0912345678"))

        assert result["draft"] == {"name": "Nam", "phone": "0912345678"}
        assert set(result["missing_fields"]) == {
            "vehicle_id",
            "test_drive_date",
            "test_drive_time",
            "ward",
        }
        assert route_after_extract(result) == "ask_missing"

    async def test_complete_input_routes_to_plan(self, fake_llm):
        fake_llm(
            [
                ExtractedDraft(
                    name="Trần Văn A",
                    phone="0987654321",
                    vehicle="VF 8",
                    test_drive_date=TOMORROW,
                    test_drive_time="09:30",
                    ward="Hoàn Kiếm",
                )
            ]
        )

        result = await extract_node(
            state_with(query="Tôi là Trần Văn A, 0987654321, lái thử VF 8 lúc 9 rưỡi sáng mai ở Hoàn Kiếm")
        )

        assert result["missing_fields"] == []
        assert result["draft"]["vehicle_id"] == "vf8"
        assert result["draft"]["ward"] == "Hoàn Kiếm"
        assert route_after_extract(result) == "plan"

    async def test_reads_from_messages_not_only_query(self, fake_llm):
        from langchain_core.messages import AIMessage, HumanMessage

        fake_llm([ExtractedDraft(name="Lan", phone="0912345678")])

        result = await extract_node(
            state_with(
                messages=[
                    HumanMessage(content="Chào bạn"),
                    AIMessage(content="Em nghe ạ"),
                    HumanMessage(content="Tôi là Lan, 0912345678"),
                ]
            )
        )

        assert result["draft"]["name"] == "Lan"

    async def test_merges_onto_previous_draft(self, fake_llm):
        fake_llm([ExtractedDraft(ward="Cầu Giấy")])

        result = await extract_node(
            state_with(draft={"name": "Nam", "phone": "0912345678"}, query="ở Cầu Giấy", status="collecting")
        )

        assert result["draft"] == {"name": "Nam", "phone": "0912345678", "ward": "Cầu Giấy"}

    @pytest.mark.parametrize("terminal_status", ["done", "manual_ready", "error"])
    async def test_starts_clean_draft_after_terminal_status(self, fake_llm, terminal_status):
        """Không được để dữ liệu khách trước rò sang khách sau trên cùng thread."""
        fake_llm([ExtractedDraft(name="Khách Mới")])

        result = await extract_node(
            state_with(draft=dict(FULL_DRAFT), status=terminal_status, query="Tôi là Khách Mới")
        )

        assert result["draft"] == {"name": "Khách Mới"}

    async def test_llm_failure_does_not_crash(self, monkeypatch):
        async def boom(_text):
            raise RuntimeError("openai down")

        monkeypatch.setattr("src.backend.agents.nodes.form_nodes._extract_with_llm", boom)

        result = await extract_node(state_with(query="Tôi là Nam"))

        assert result["status"] == "error"
        assert route_after_extract(result) == "end"

    async def test_ignores_past_date(self, fake_llm):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        fake_llm([ExtractedDraft(name="Nam", test_drive_date=yesterday)])

        result = await extract_node(state_with(query="lái thử hôm qua"))

        assert "test_drive_date" not in result["draft"]

    async def test_snaps_time_to_nearest_slot(self, fake_llm):
        fake_llm([ExtractedDraft(test_drive_time="09:20")])

        result = await extract_node(state_with(query="khoảng 9h20"))

        assert result["draft"]["test_drive_time"] == "09:30"

    async def test_rejects_fabricated_email(self, fake_llm):
        fake_llm([ExtractedDraft(name="Nam", email="không có")])

        result = await extract_node(state_with(query="Tôi là Nam"))

        assert "email" not in result["draft"]


# ------------------------------------------------------------ ask_missing

class TestAskMissing:
    async def test_asks_for_all_missing_at_once(self):
        result = await ask_missing_node(
            state_with(missing_fields=["vehicle_id", "test_drive_date", "test_drive_time", "ward"])
        )

        content = result["messages"][0].content
        for label in ("Mẫu xe", "Ngày lái thử", "Giờ lái thử", "Phường/Xã"):
            assert label in content
        assert result["status"] == "collecting"

    async def test_never_asks_for_optional_fields(self):
        result = await ask_missing_node(state_with(missing_fields=["ward"]))
        content = result["messages"][0].content

        assert "Email" not in content
        assert "Yêu cầu khác" not in content


# ------------------------------------------------------------------- plan

class TestPlan:
    async def test_builds_actions_in_field_order(self):
        result = await plan_node(state_with(draft=dict(FULL_DRAFT)))

        fields = [action["field"] for action in result["action_queue"]]
        assert fields == [
            "name",
            "phone",
            "email",
            "vehicle_id",
            "test_drive_date",
            "test_drive_time",
            "ward",
            "note",
        ]
        assert result["run_kind"] == "full"
        assert result["status"] == "filling"
        assert route_after_plan(result) == "fill"

    async def test_action_types(self):
        result = await plan_node(state_with(draft=dict(FULL_DRAFT)))
        by_field = {action["field"]: action for action in result["action_queue"]}

        assert by_field["name"]["type"] == "type"
        assert by_field["phone"]["type"] == "type"
        assert by_field["email"]["type"] == "type"
        assert by_field["note"]["type"] == "type"
        assert by_field["vehicle_id"]["type"] == "select"
        assert by_field["test_drive_date"]["type"] == "select"
        assert by_field["test_drive_time"]["type"] == "select"
        assert by_field["ward"]["type"] == "pick_ward"

    async def test_selectors_point_at_data_attributes(self):
        result = await plan_node(state_with(draft=dict(FULL_DRAFT)))

        for action in result["action_queue"]:
            assert action["selector"] == f"[data-agent-field={action['field']}]"

    async def test_skips_empty_optional_fields(self):
        draft = {key: value for key, value in FULL_DRAFT.items() if key not in {"email", "note"}}

        result = await plan_node(state_with(draft=draft))

        fields = [action["field"] for action in result["action_queue"]]
        assert "email" not in fields
        assert "note" not in fields

    async def test_run_seq_increments_and_stamps_every_action(self):
        """BẪY #4: thiếu dấu run_seq trên từng action là lượt sau bị chặn."""
        result = await plan_node(state_with(draft=dict(FULL_DRAFT), run_seq=4))

        assert result["run_seq"] == 5
        assert {action["run_seq"] for action in result["action_queue"]} == {5}

    async def test_correction_run_only_plans_changed_fields(self):
        result = await plan_node(
            state_with(draft=dict(FULL_DRAFT), changed_fields=["test_drive_time"], run_seq=1)
        )

        assert [action["field"] for action in result["action_queue"]] == ["test_drive_time"]
        assert result["run_kind"] == "correction"
        assert result["run_seq"] == 2

    async def test_empty_correction_queue_goes_to_summarize(self):
        result = await plan_node(state_with(draft={}, changed_fields=["note"]))

        assert result["action_queue"] == []
        assert route_after_plan(result) == "summarize"


# ------------------------------------------------------------------- fill

class TestFill:
    async def test_pops_exactly_one_action_per_pass(self):
        planned = await plan_node(state_with(draft=dict(FULL_DRAFT)))
        state = state_with(**planned)

        first = await fill_node(state)

        assert first["current_action"]["field"] == "name"
        assert len(first["action_queue"]) == 7
        assert first["filled_fields"] == ["name"]
        assert route_after_fill(first) == "fill"

    async def test_drains_queue_in_order_then_summarizes(self):
        planned = await plan_node(state_with(draft=dict(FULL_DRAFT)))
        state = state_with(**planned)

        order = []
        for _ in range(len(planned["action_queue"])):
            delta = await fill_node(state)
            state.update(delta)
            order.append(delta["current_action"]["field"])

        assert order == [action["field"] for action in planned["action_queue"]]
        assert state["action_queue"] == []
        assert route_after_fill(state) == "summarize"

    async def test_empty_queue_is_a_noop(self):
        result = await fill_node(state_with(action_queue=[]))
        assert result == {"current_action": None}


# -------------------------------------------------------------- summarize

class TestSummarize:
    async def test_lists_every_filled_field(self):
        result = await summarize_node(state_with(draft=dict(FULL_DRAFT)))
        content = result["messages"][0].content

        assert "Trần Văn A" in content
        assert "0987654321" in content
        assert "VF 8" in content  # hiện tên xe, không phải id "vf8"
        assert "09:30" in content
        assert "Hoàn Kiếm" in content
        assert "Hà Nội" in content
        assert result["awaiting"] == "confirm_details"
        assert result["current_action"] is None

    def test_summary_shows_vehicle_name_not_id(self):
        summary = build_summary({"vehicle_id": "vf8-allnew"})
        assert "VF 8 All New (2026)" in summary
        assert "vf8-allnew" not in summary


# ------------------------------------------------------- classify_answer

class TestClassifyAnswer:
    @pytest.mark.parametrize(
        "text",
        ["Thông tin chính xác", "xác nhận", "đồng ý", "ok em", "chốt luôn", "Tự động gửi", "đúng rồi"],
    )
    def test_affirmative(self, text):
        assert classify_answer(text) == "yes"

    @pytest.mark.parametrize(
        "text",
        ["không đúng", "chưa đúng", "sai số điện thoại", "đổi giờ thành 15:00", "Tôi tự gửi", "sửa tên"],
    )
    def test_negative(self, text):
        assert classify_answer(text) == "no"

    def test_unknown(self):
        assert classify_answer("") == "unknown"
        assert classify_answer("hmm") == "unknown"


# ------------------------------------------------------------------ patch

class TestMentionedFields:
    def test_time_only(self):
        assert mentioned_fields("đổi giờ thành 15:00") == {"test_drive_time"}

    def test_email_does_not_trigger_date(self):
        """"email" chứa "mai" — nếu dùng `in` thay vì `\\b` sẽ hiểu nhầm là sửa ngày."""
        assert "test_drive_date" not in mentioned_fields("đổi email thành a@b.com")

    def test_vehicle(self):
        assert "vehicle_id" in mentioned_fields("đổi xe sang VF 9")

    def test_ward(self):
        assert "ward" in mentioned_fields("đổi phường thành Cầu Giấy")


class TestDirectCaptures:
    def test_time_with_colon(self):
        assert direct_captures("đổi giờ thành 15:00")["test_drive_time"] == "15:00"

    def test_time_with_h(self):
        assert direct_captures("cho tôi 13h30 nhé")["test_drive_time"] == "13:30"

    def test_half_past(self):
        assert direct_captures("9 rưỡi sáng")["test_drive_time"] == "09:30"

    def test_iso_date(self):
        assert direct_captures(f"đổi ngày thành {NEXT_WEEK}")["test_drive_date"] == NEXT_WEEK

    def test_phone_is_not_read_as_time(self):
        captured = direct_captures("số mới là 0912345678")
        assert captured["phone"] == "0912345678"
        assert "test_drive_time" not in captured

    def test_vehicle(self):
        assert direct_captures("đổi sang VF 9")["vehicle_id"] == "vf9"

    def test_multiword_ward(self):
        assert direct_captures("chuyển sang Cầu Giấy")["ward"] == "Cầu Giấy"


class TestPatch:
    async def test_only_changes_the_mentioned_field(self, fake_llm):
        # LLM "nhiệt tình" điền lại cả form — bộ lọc phải chặn mọi field
        # khách không nhắc tới.
        fake_llm(
            [
                ExtractedDraft(
                    name="Người Khác",
                    phone="0900000000",
                    vehicle="VF 3",
                    test_drive_time="15:00",
                    ward="Cầu Giấy",
                )
            ]
        )

        result = await patch_node(state_with(draft=dict(FULL_DRAFT), query="đổi giờ thành 15:00"))

        assert result["changed_fields"] == ["test_drive_time"]
        assert result["draft"]["test_drive_time"] == "15:00"
        assert result["draft"]["name"] == FULL_DRAFT["name"]
        assert result["draft"]["phone"] == FULL_DRAFT["phone"]
        assert result["draft"]["vehicle_id"] == "vf8"
        assert result["draft"]["ward"] == "Hoàn Kiếm"
        assert route_after_patch(result) == "plan"

    async def test_regex_wins_over_wrong_llm_answer(self, fake_llm):
        fake_llm([ExtractedDraft(test_drive_time="08:00")])

        result = await patch_node(state_with(draft=dict(FULL_DRAFT), query="đổi giờ thành 15:00"))

        assert result["draft"]["test_drive_time"] == "15:00"

    async def test_changes_vehicle(self, fake_llm):
        fake_llm([ExtractedDraft(vehicle="VF 9")])

        result = await patch_node(state_with(draft=dict(FULL_DRAFT), query="đổi xe sang VF 9"))

        assert result["changed_fields"] == ["vehicle_id"]
        assert result["draft"]["vehicle_id"] == "vf9"

    async def test_no_recognisable_change_asks_again(self, fake_llm):
        fake_llm([ExtractedDraft()])

        result = await patch_node(state_with(draft=dict(FULL_DRAFT), query="ừ thì sửa đi"))

        assert result["changed_fields"] == []
        assert result["status"] == "needs_correction_retry"
        assert route_after_patch(result) == "plan"

    async def test_counts_rounds(self, fake_llm):
        fake_llm([ExtractedDraft(test_drive_time="15:00")])

        result = await patch_node(
            state_with(draft=dict(FULL_DRAFT), query="đổi giờ thành 15:00", correction_rounds=2)
        )

        assert result["correction_rounds"] == 3

    async def test_stops_after_max_rounds(self, fake_llm):
        fake_llm([ExtractedDraft(test_drive_time="15:00")])

        result = await patch_node(
            state_with(
                draft=dict(FULL_DRAFT),
                query="đổi giờ thành 15:00",
                correction_rounds=MAX_CORRECTION_ROUNDS,
            )
        )

        assert result["status"] == "error"
        assert result["error"] == "too_many_corrections"
        assert "1900 23 23 89" in result["messages"][0].content
        assert route_after_patch(result) == "end"

    async def test_survives_llm_failure_using_regex(self, monkeypatch):
        async def boom(_text):
            raise RuntimeError("openai down")

        monkeypatch.setattr("src.backend.agents.nodes.form_nodes._extract_with_llm", boom)

        result = await patch_node(state_with(draft=dict(FULL_DRAFT), query="đổi giờ thành 15:00"))

        assert result["draft"]["test_drive_time"] == "15:00"
        assert result["changed_fields"] == ["test_drive_time"]


# --------------------------------------------------------- mọi câu qua messages

class TestAgentSpeaksThroughMessages:
    async def test_every_speaking_node_emits_ai_message(self):
        nodes = [
            await ask_missing_node(state_with(missing_fields=["ward"])),
            await plan_node(state_with(draft=dict(FULL_DRAFT))),
            await summarize_node(state_with(draft=dict(FULL_DRAFT))),
        ]

        for result in nodes:
            assert result["messages"], "node nói với khách nhưng không phát AIMessage"
            assert result["messages"][0].content.strip()


def test_form_fields_cover_every_label():
    from src.backend.agents.state import FIELD_LABELS

    assert set(FORM_FIELDS) == set(FIELD_LABELS)
