"""Chạy graph `swap_car` hết một lượt, có interrupt và resume.

`test_swap_car.py` kiểm từng node rời và cấu trúc graph; test này kiểm thứ hai
cái đó không bắt được: `interrupt()` có thật sự đóng băng đúng chỗ không, và
resume có chảy tiếp đúng nhánh không. Nối sai một router thì mọi test node vẫn
xanh mà luồng thật thì đứng.

LLM được thay bằng bản giả — toàn bộ phần còn lại (rule, DB, tính tiền) chạy thật.
"""

from datetime import date, timedelta

import pytest
from langgraph.types import Command

from src.backend.agents.swap_car import graph as swap_car
from src.backend.agents.swap_car import nodes

# Đổi tên khi import: pytest thấy class bắt đầu bằng "Test" ở scope module là cố
# thu thập nó như một test class rồi cảnh báo vì nó có `__init__`.
from src.backend.models.schemas import TestDriveCreate as TestDrivePayload
from src.backend.services import appraisal_repository as appraisal_repo
from src.backend.services import customer_repository as customer_repo
from src.backend.services.database import SessionLocal, engine, init_db
from src.backend.services.tables import Base

REGISTERED = (date.today() - timedelta(days=900)).isoformat()  # ~2,5 năm tuổi


@pytest.fixture
def customer_code():
    Base.metadata.drop_all(bind=engine)
    init_db()
    with SessionLocal() as session:
        customer = customer_repo.create_test_drive(
            session,
            TestDrivePayload(
                name="Nguyễn Văn Tuấn",
                phone="0912345678",
                vehicle_id="vf3",
                model="VF 3",
                test_drive_date=date.today() + timedelta(days=1),
                test_drive_time="09:30",
                ward="Cầu Giấy",
                source="Showroom",
            ),
        )
        return customer.code


class FakeExplainReply:
    content = "Em giải thích ngắn gọn từng điều kiện ạ."


class FakeStructuredLLM:
    """Nhánh `with_structured_output` — luôn trả về bản bóc dựng sẵn."""

    def __init__(self, extracted: nodes.ExtractedSwapCar):
        self.extracted = extracted

    async def ainvoke(self, messages):  # noqa: ARG002
        return self.extracted


class FakeLLM:
    def __init__(self, extracted: nodes.ExtractedSwapCar):
        self.structured = FakeStructuredLLM(extracted)

    def with_structured_output(self, schema):  # noqa: ARG002
        return self.structured

    async def ainvoke(self, messages):  # noqa: ARG002
        # Nhánh gọi thẳng, dùng bởi node `explain`.
        return FakeExplainReply()


@pytest.fixture
def run_agent(monkeypatch):
    """`run_agent(extracted, customer_code, thread)` -> (agent, config, state đầu vào)."""

    def install(extracted: nodes.ExtractedSwapCar, customer_code: str, thread: str):
        monkeypatch.setattr(nodes, "get_llm", lambda: FakeLLM(extracted))

        agent = swap_car.build_graph()
        config = {"configurable": {"thread_id": thread}}
        state = {
            "messages": [{"role": "user", "content": "Khách muốn đổi xe cũ"}],
            "customer_code": customer_code,
            "sales_staff_id": 1,
        }
        return agent, config, state

    return install


GOOD_CAR = nodes.ExtractedSwapCar(
    make="Honda",
    model="City",
    year=2022,
    trim="RS",
    odo_km=40_000,
    first_registration_date=REGISTERED,
    new_vehicle="VF 6",
    condition_engine="tot",
    condition_chassis="trung_binh",
)


def interrupt_kind(output) -> str | None:
    events = output.get("__interrupt__")
    return events[0].value.get("kind") if events else None


@pytest.mark.asyncio
class TestHappyPath:
    async def test_stops_at_the_price_card_with_a_full_quote(self, customer_code, run_agent):
        agent, config, state = run_agent(GOOD_CAR, customer_code, "happy-1")
        out = await agent.ainvoke(state, config)

        assert interrupt_kind(out) == "swap_confirm_price"
        assert out["status"] == "quoted"
        assert out["appraisal_code"].startswith("DG-")
        assert out["value_a"] > 0
        assert out["quote"]["amount_c"] == (
            out["quote"]["value_b"]
            - out["quote"]["value_a"]
            - out["quote"]["promo_new_car"]
            - out["quote"]["trade_in_bonus"]
        )

    async def test_agreeing_leads_to_the_checklist(self, customer_code, run_agent):
        agent, config, state = run_agent(GOOD_CAR, customer_code, "happy-2")
        await agent.ainvoke(state, config)
        out = await agent.ainvoke(Command(resume="Khách đồng ý"), config)
        assert interrupt_kind(out) == "swap_checklist"

    async def test_full_checklist_closes_the_deal(self, customer_code, run_agent):
        agent, config, state = run_agent(GOOD_CAR, customer_code, "happy-3")
        await agent.ainvoke(state, config)
        await agent.ainvoke(Command(resume="Khách đồng ý"), config)
        out = await agent.ainvoke(
            Command(resume={"done": ["contract", "deposit", "papers", "status"]}), config
        )

        assert out["status"] == "accepted"
        assert "Ngày hẹn giao xe" in out["response"]

        with SessionLocal() as session:
            row = appraisal_repo.get_appraisal(session, out["appraisal_code"])
            assert row.status == "accepted"
            assert row.quotes[0].status == "accepted"
            assert row.quotes[0].handover_date is not None


@pytest.mark.asyncio
class TestRevisionLoop:
    async def test_raising_repair_cost_lowers_a_and_raises_c(self, customer_code, run_agent):
        agent, config, state = run_agent(GOOD_CAR, customer_code, "revise-1")
        first = await agent.ainvoke(state, config)

        second = await agent.ainvoke(Command(resume="chi phí sửa chữa 20 triệu"), config)

        # Quay lại đúng thẻ giá, không đi tiếp sang checklist.
        assert interrupt_kind(second) == "swap_confirm_price"
        assert second["value_a"] == first["value_a"] - 20_000_000
        assert second["quote"]["amount_c"] == first["quote"]["amount_c"] + 20_000_000

    async def test_revision_updates_the_same_record(self, customer_code, run_agent):
        # Vòng sửa KHÔNG được đẻ hồ sơ mới mỗi lần, nếu không bảng đầy bản nháp
        # và không biết cái nào là giá đã báo cho khách.
        agent, config, state = run_agent(GOOD_CAR, customer_code, "revise-2")
        first = await agent.ainvoke(state, config)
        second = await agent.ainvoke(Command(resume="chi phí sửa chữa 20 triệu"), config)

        assert second["appraisal_code"] == first["appraisal_code"]
        with SessionLocal() as session:
            assert len(appraisal_repo.list_appraisals(session)) == 1

    async def test_switching_the_new_car_requotes(self, customer_code, run_agent):
        agent, config, state = run_agent(GOOD_CAR, customer_code, "revise-3")
        first = await agent.ainvoke(state, config)
        second = await agent.ainvoke(Command(resume="đổi sang VF 9"), config)

        assert second["quote"]["vehicle_id"] == "vf9"
        assert second["quote"]["value_b"] > first["quote"]["value_b"]
        # A không đổi vì chỉ đổi xe mới.
        assert second["value_a"] == first["value_a"]


@pytest.mark.asyncio
class TestSoftBlock:
    async def test_partial_checklist_blocks_without_cancelling(self, customer_code, run_agent):
        agent, config, state = run_agent(GOOD_CAR, customer_code, "blocked-1")
        await agent.ainvoke(state, config)
        await agent.ainvoke(Command(resume="Khách đồng ý"), config)
        out = await agent.ainvoke(Command(resume={"done": ["contract", "deposit"]}), config)

        assert out["status"] == "blocked"
        assert out["checklist_missing"] == ["papers", "status"]
        assert "Thu đủ giấy tờ gốc xe cũ" in out["response"]

        with SessionLocal() as session:
            row = appraisal_repo.get_appraisal(session, out["appraisal_code"])
            # Chặn MỀM: hồ sơ vẫn còn, chỉ đứng chờ.
            assert row.status == "blocked"
            assert row.quotes


@pytest.mark.asyncio
class TestRejectionPath:
    async def test_old_car_is_rejected_before_any_scoring(self, customer_code, run_agent):
        old_car = nodes.ExtractedSwapCar(
            make="Toyota",
            model="Vios",
            year=2018,
            odo_km=200_000,
            first_registration_date="2018-01-01",
            new_vehicle="VF 3",
        )
        agent, config, state = run_agent(old_car, customer_code, "reject-1")
        out = await agent.ainvoke(state, config)

        assert out["status"] == "rejected"
        assert out["eligibility_status"] == "rejected_age"
        assert interrupt_kind(out) is None  # dừng hẳn, không hỏi gì thêm

        with SessionLocal() as session:
            row = appraisal_repo.get_appraisal(session, out["appraisal_code"])
            # Vẫn lưu để quản lý đếm được xe bị loại, nhưng không chấm điểm,
            # không định giá, không tạo báo giá.
            assert row.status == "rejected"
            assert row.scores == []
            assert row.quotes == []
            assert row.value_a == 0

    async def test_missing_fields_stop_at_the_question(self, customer_code, run_agent):
        agent, config, state = run_agent(
            nodes.ExtractedSwapCar(make="Honda"), customer_code, "reject-2"
        )
        out = await agent.ainvoke(state, config)

        assert out["status"] == "collecting"
        assert "Dòng xe cũ" in out["response"]
        assert out.get("appraisal_code") is None

    async def test_unknown_car_needs_manual_appraisal(self, customer_code, run_agent):
        unknown = nodes.ExtractedSwapCar(
            make="Tesla",
            model="Model 3",
            year=2022,
            odo_km=30_000,
            first_registration_date=REGISTERED,
            new_vehicle="VF 8",
        )
        agent, config, state = run_agent(unknown, customer_code, "reject-3")
        out = await agent.ainvoke(state, config)

        assert out["status"] == "manual_appraisal"
        assert "thẩm định viên" in out["response"]
        assert interrupt_kind(out) is None
