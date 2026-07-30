"""Test REST API."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

TOMORROW = (date.today() + timedelta(days=1)).isoformat()


@pytest.fixture
def client():
    """DB sạch cho mỗi test, app chạy qua lifespan để `init_db()` được gọi."""
    from src.backend.main import app
    from src.backend.services.database import engine, init_db
    from src.backend.services.tables import Base

    Base.metadata.drop_all(bind=engine)
    init_db()

    with TestClient(app) as test_client:
        yield test_client


def valid_payload(**overrides):
    payload = {
        "name": "Trần Văn A",
        "phone": "0987654321",
        "email": "",
        "vehicle_id": "vf8",
        "model": "VF 8",
        "test_drive_date": TOMORROW,
        "test_drive_time": "09:30",
        "province": "Hà Nội",
        "ward": "Hoàn Kiếm",
        "note": None,
        "source": "Website",
    }
    payload.update(overrides)
    return payload


class TestHealth:
    def test_root_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_api_health(self, client):
        assert client.get("/api/v1/health").json() == {"status": "ok"}


class TestLogin:
    def test_valid_credentials(self, client):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "lan.anh@vinfast.vn", "password": "LanAnh@2026"},
        )

        assert response.status_code == 200
        staff = response.json()["staff"]
        assert staff["email"] == "lan.anh@vinfast.vn"
        assert staff["initials"] == "LA"
        # Schema đi ra ngoài không được mang hash mật khẩu.
        assert "password_hash" not in staff

    def test_wrong_password_returns_401(self, client):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "lan.anh@vinfast.vn", "password": "sai-mat-khau"},
        )
        assert response.status_code == 401

    def test_unknown_email_returns_401(self, client):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "khong.ton.tai@vinfast.vn", "password": "LanAnh@2026"},
        )
        assert response.status_code == 401

    def test_error_message_does_not_leak_which_part_was_wrong(self, client):
        wrong_password = client.post(
            "/api/v1/auth/login",
            json={"email": "lan.anh@vinfast.vn", "password": "sai"},
        ).json()["detail"]
        unknown_email = client.post(
            "/api/v1/auth/login",
            json={"email": "ai.do@vinfast.vn", "password": "sai"},
        ).json()["detail"]

        assert wrong_password == unknown_email

    def test_all_three_demo_accounts_work(self, client):
        accounts = [
            ("lan.anh@vinfast.vn", "LanAnh@2026"),
            ("minh.quan@vinfast.vn", "MinhQuan@2026"),
            ("thanh.ha@vinfast.vn", "ThanhHa@2026"),
        ]
        for email, password in accounts:
            response = client.post(
                "/api/v1/auth/login", json={"email": email, "password": password}
            )
            assert response.status_code == 200, email


class TestCreateTestDrive:
    def test_creates_and_generates_code(self, client):
        response = client.post("/api/v1/test-drives", json=valid_payload())

        assert response.status_code == 201
        body = response.json()
        assert body["code"] == "VF-24082"
        assert body["status"] == "Mới"
        assert body["source"] == "Website"
        assert body["province"] == "Hà Nội"
        assert body["email"] is None  # chuỗi rỗng quy về None
        assert body["sales_staff"] is not None

    def test_codes_increment(self, client):
        first = client.post("/api/v1/test-drives", json=valid_payload()).json()
        second = client.post(
            "/api/v1/test-drives", json=valid_payload(name="Lê Thị B", phone="0912345678")
        ).json()

        assert first["code"] == "VF-24082"
        assert second["code"] == "VF-24083"

    def test_customers_table_starts_empty(self, client):
        """Không seed khách mẫu lúc khởi động — nghiệm thu phải thấy đúng bản ghi thật."""
        assert client.get("/api/v1/customers").json() == []

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("phone", "123"),
            ("test_drive_time", "10:00"),
            ("test_drive_date", (date.today() - timedelta(days=1)).isoformat()),
            ("province", "Hồ Chí Minh"),
            ("name", "A"),
            ("source", "TikTok"),
        ],
    )
    def test_rejects_invalid_values(self, client, field, value):
        response = client.post("/api/v1/test-drives", json=valid_payload(**{field: value}))
        assert response.status_code == 422

    def test_validation_error_is_in_vietnamese(self, client):
        payload = valid_payload()
        del payload["name"]

        response = client.post("/api/v1/test-drives", json=payload)

        assert response.status_code == 422
        body = response.json()
        assert "bắt buộc" in body["detail"]
        assert body["errors"][0]["label"] == "Họ và tên"

    def test_phone_is_normalised_to_digits(self, client):
        body = client.post("/api/v1/test-drives", json=valid_payload(phone="098 765 4321")).json()
        assert body["phone"] == "0987654321"


class TestListCustomers:
    @pytest.fixture
    def seeded(self, client):
        client.post("/api/v1/test-drives", json=valid_payload())
        client.post(
            "/api/v1/test-drives",
            json=valid_payload(
                name="Lê Thị B",
                phone="0912345678",
                vehicle_id="vf3",
                model="VF 3",
                ward="Cầu Giấy",
            ),
        )
        return client

    def test_lists_all(self, seeded):
        assert len(seeded.get("/api/v1/customers").json()) == 2

    def test_newest_first(self, seeded):
        codes = [customer["code"] for customer in seeded.get("/api/v1/customers").json()]
        assert codes == ["VF-24083", "VF-24082"]

    @pytest.mark.parametrize(
        ("query", "expected_count"),
        [
            ("VF-24082", 1),
            ("Trần", 1),
            ("0912345678", 1),
            ("VF 3", 1),
            ("Cầu Giấy", 1),
            ("Hà Nội", 2),
            ("không-có-gì", 0),
        ],
    )
    def test_search(self, seeded, query, expected_count):
        response = seeded.get("/api/v1/customers", params={"search": query})
        assert len(response.json()) == expected_count

    def test_filter_by_status(self, seeded):
        seeded.patch("/api/v1/customers/VF-24082/status", json={"status": "Đã liên hệ"})

        assert len(seeded.get("/api/v1/customers", params={"status": "Mới"}).json()) == 1
        assert len(seeded.get("/api/v1/customers", params={"status": "Đã liên hệ"}).json()) == 1

    def test_search_and_status_combine(self, seeded):
        response = seeded.get(
            "/api/v1/customers", params={"search": "Cầu Giấy", "status": "Mới"}
        )
        assert len(response.json()) == 1


class TestUpdateStatus:
    def test_updates_by_display_code(self, client):
        client.post("/api/v1/test-drives", json=valid_payload())

        response = client.patch("/api/v1/customers/VF-24082/status", json={"status": "Đặt lịch"})

        assert response.status_code == 200
        assert response.json()["status"] == "Đặt lịch"

    def test_unknown_code_returns_404(self, client):
        response = client.patch("/api/v1/customers/VF-99999/status", json={"status": "Đặt lịch"})
        assert response.status_code == 404

    def test_rejects_unknown_status(self, client):
        client.post("/api/v1/test-drives", json=valid_payload())

        response = client.patch("/api/v1/customers/VF-24082/status", json={"status": "Đang bay"})
        assert response.status_code == 422


class TestSalesStaff:
    def test_lists_three_demo_staff(self, client):
        response = client.get("/api/v1/sales-staff")

        assert response.status_code == 200
        staff = response.json()
        assert len(staff) == 3
        assert all("password_hash" not in item for item in staff)
