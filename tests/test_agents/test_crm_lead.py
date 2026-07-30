"""Test agent CRM: check trùng, copy pack theo channel, source ghi vào DB."""

from datetime import date, timedelta

import pytest

from src.backend.agents.crm_lead.nodes import (
    check_duplicate_node,
    duplicate_blocked_node,
    route_after_check_duplicate,
)
from src.backend.agents.shared.copy import get_copy
from src.backend.agents.shared.nodes.form_nodes import submit_node
from src.backend.agents.shared.nodes.init_node import make_init_node
from src.backend.agents.shared.state import empty_state

# Alias KHÔNG bắt đầu bằng "Test": pytest thu gom mọi tên `Test*` trong module
# nên `TestDriveCreate` (và cả `TestDrivePayload`) sẽ bị hiểu là test class.
from src.backend.models.schemas import TestDriveCreate as DrivePayload
from src.backend.services import customer_repository as repo
from src.backend.services.database import SessionLocal, init_db
from src.backend.services.tables import Base

TOMORROW = (date.today() + timedelta(days=1)).isoformat()

CRM_DRAFT = {
    "name": "Trần Văn A",
    "phone": "0987654321",
    "vehicle_id": "vf8",
    "test_drive_date": TOMORROW,
    "test_drive_time": "09:30",
    "ward": "Hoàn Kiếm",
}


def crm_state(**overrides):
    state = empty_state()
    state["channel"] = "crm"
    state.update(overrides)
    return state


@pytest.fixture
def clean_db():
    """DB trắng cho mỗi test — các node CRM đọc DB thật qua SessionLocal."""
    from src.backend.services.database import engine

    Base.metadata.drop_all(bind=engine)
    init_db()
    yield


def seed_customer(**overrides):
    payload = {
        "name": "Trần Văn A",
        "phone": "0987654321",
        "vehicle_id": "vf8",
        "model": "VF 8",
        "test_drive_date": date.fromisoformat(TOMORROW),
        "test_drive_time": "09:30",
        "province": "Hà Nội",
        "ward": "Hoàn Kiếm",
        "source": "Showroom",
    }
    payload.update(overrides)
    with SessionLocal() as session:
        return repo.create_test_drive(session, DrivePayload(**payload)).code


# ----------------------------------------------------------- init / copy pack

class TestChannelStamp:
    async def test_crm_graph_stamps_crm_channel(self):
        result = await make_init_node("crm")(empty_state())
        assert result == {"channel": "crm"}

    async def test_web_graph_stamps_web_channel(self):
        result = await make_init_node("web")(empty_state())
        assert result == {"channel": "web"}

    def test_copy_pack_follows_channel(self):
        web = get_copy({"channel": "web"})
        crm = get_copy({"channel": "crm"})

        assert web is not crm
        # Trang khách nói với chính người lái thử; CRM nói với sales về "khách".
        assert "lái thử mẫu xe nào" in web.greeting
        assert "thông tin khách" in crm.greeting
        assert "Tạo khách hàng" in crm.manual_ready
        assert "Đăng ký lái thử" in web.manual_ready

    def test_missing_channel_defaults_to_web(self):
        assert get_copy({}) is get_copy({"channel": "web"})

    def test_every_field_filled_in_both_packs(self):
        """Thêm agent mới mà quên dịch một câu thì test này bắt được."""
        for pack in (get_copy({"channel": "web"}), get_copy({"channel": "crm"})):
            for field, value in vars(pack).items():
                if field == "duplicate_name_warning":
                    continue  # trang khách không dùng, để rỗng là có chủ đích
                assert value.strip(), f"{field} bị để trống"


# -------------------------------------------------------------- find_duplicates

class TestFindDuplicates:
    def test_phone_matches_across_formats(self, clean_db):
        code = seed_customer(phone="0987654321")

        with SessionLocal() as session:
            for typed in ("0987 654 321", "0987-654-321", "0987654321"):
                phone_match, _ = repo.find_duplicates(session, phone=typed)
                assert phone_match is not None, typed
                assert phone_match.code == code

    def test_different_phone_is_not_a_match(self, clean_db):
        seed_customer(phone="0987654321")

        with SessionLocal() as session:
            phone_match, _ = repo.find_duplicates(session, phone="0912345678")
            assert phone_match is None

    def test_name_matches_ignoring_accents_and_case(self, clean_db):
        code = seed_customer(name="Trần Văn Tuấn", phone="0987654321")

        with SessionLocal() as session:
            for typed in ("tran van tuan", "TRẦN VĂN TUẤN", "Trần   Văn  Tuấn"):
                _, name_matches = repo.find_duplicates(session, name=typed)
                assert [c.code for c in name_matches] == [code], typed

    def test_name_matches_exclude_the_phone_duplicate(self, clean_db):
        # Cùng người (trùng cả tên lẫn SĐT) thì chỉ tính là trùng CỨNG, không
        # đếm thêm một lần vào cảnh báo mềm.
        seed_customer(name="Trần Văn A", phone="0987654321")

        with SessionLocal() as session:
            phone_match, name_matches = repo.find_duplicates(
                session, phone="0987654321", name="Trần Văn A"
            )
            assert phone_match is not None
            assert [c.id for c in name_matches] == [phone_match.id]

    def test_empty_query_returns_nothing(self, clean_db):
        seed_customer()
        with SessionLocal() as session:
            assert repo.find_duplicates(session) == (None, [])

    def test_create_raises_on_duplicate_phone(self, clean_db):
        code = seed_customer(phone="0987654321")

        with pytest.raises(repo.DuplicatePhoneError) as exc_info:
            seed_customer(phone="0987654321", name="Người Khác")

        assert exc_info.value.code == code

    def test_create_allows_duplicate_name(self, clean_db):
        seed_customer(name="Trần Văn A", phone="0987654321")
        second = seed_customer(name="Trần Văn A", phone="0912345678")
        assert second


class TestNormalizeHelpers:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("0987 654 321", "0987654321"),
            ("0987-654-321", "0987654321"),
            ("(098) 765 4321", "0987654321"),
            (None, ""),
        ],
    )
    def test_normalize_phone(self, raw, expected):
        assert repo.normalize_phone(raw) == expected

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Trần Văn Tuấn", "tran van tuan"),
            ("TRẦN  VĂN   TUẤN", "tran van tuan"),
            ("Đỗ Đình Đạt", "do dinh dat"),
            (None, ""),
        ],
    )
    def test_normalize_name(self, raw, expected):
        assert repo.normalize_name(raw) == expected


# ----------------------------------------------------------- check_duplicate node

class TestCheckDuplicateNode:
    async def test_hard_block_on_duplicate_phone(self, clean_db):
        code = seed_customer(name="Trần Văn A", phone="0987654321")

        result = await check_duplicate_node(crm_state(draft=dict(CRM_DRAFT)))

        assert result["status"] == "duplicate_phone"
        content = result["messages"][0].content
        assert code in content
        assert "Trần Văn A" in content
        assert route_after_check_duplicate(result) == "duplicate_blocked"

    async def test_soft_warning_on_duplicate_name_only(self, clean_db):
        code = seed_customer(name="Trần Văn A", phone="0912345678")

        result = await check_duplicate_node(crm_state(draft=dict(CRM_DRAFT)))

        assert result.get("status") is None  # không chặn
        assert code in result["duplicate_warning"]
        assert "vẫn tạo mới được" in result["duplicate_warning"]
        assert route_after_check_duplicate({**crm_state(), **result}) == "confirm_details"

    async def test_clean_draft_passes_through(self, clean_db):
        result = await check_duplicate_node(crm_state(draft=dict(CRM_DRAFT)))

        assert result == {"duplicate_warning": ""}
        assert route_after_check_duplicate({**crm_state(), **result}) == "confirm_details"

    async def test_empty_draft_is_a_noop(self, clean_db):
        assert await check_duplicate_node(crm_state(draft={})) == {"duplicate_warning": ""}

    async def test_duplicate_blocked_clears_the_queue(self):
        result = await duplicate_blocked_node(crm_state())
        assert result["current_action"] is None
        assert result["action_queue"] == []

    async def test_blocked_status_is_terminal(self):
        """`duplicate_phone` phải nằm trong TERMINAL_STATUSES.

        Nếu không, lượt sau sales nhắn số mới sẽ đắp lên draft của khách vừa bị từ
        chối thay vì bóc lại từ đầu.
        """
        from src.backend.agents.shared.nodes.form_nodes import TERMINAL_STATUSES

        assert "duplicate_phone" in TERMINAL_STATUSES


# ------------------------------------------------------------------- submit

class TestSubmitSource:
    async def test_crm_submit_uses_selected_source(self, clean_db):
        state = crm_state(draft=dict(CRM_DRAFT), source="Showroom")

        result = await submit_node(state)

        assert result["status"] == "submitted"
        with SessionLocal() as session:
            customer = repo.get_customer_by_code(session, result["submission_code"])
            assert customer.source == "Showroom"

    async def test_web_submit_still_defaults_to_website(self, clean_db):
        state = empty_state()
        state["draft"] = dict(CRM_DRAFT)

        result = await submit_node(state)

        with SessionLocal() as session:
            customer = repo.get_customer_by_code(session, result["submission_code"])
            assert customer.source == "Website"

    async def test_submit_swallows_duplicate_phone_race(self, clean_db):
        """Chốt chặn cuối: sales khác vừa tạo cùng số giữa lúc check và lúc ghi."""
        code = seed_customer(name="Người Đăng Ký Trước", phone="0987654321")

        result = await submit_node(crm_state(draft=dict(CRM_DRAFT), source="Zalo"))

        assert result["status"] == "duplicate_phone"
        assert result["error"] == "duplicate_phone"
        assert code in result["messages"][0].content
        assert result.get("submission_code") is None
