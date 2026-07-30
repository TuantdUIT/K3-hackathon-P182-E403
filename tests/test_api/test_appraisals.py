"""Test REST API của nghiệp vụ 2 — định giá xe cũ.

Đi hết một vòng nghiệp vụ qua HTTP: tra tiêu chí -> xem đèn điều kiện -> tạo hồ
sơ -> báo giá -> checklist. Cùng đường ghi mà agent `swap_car` dùng, nên test
này cũng bảo vệ luôn phần agent gọi repository.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

RECENT = (date.today() - timedelta(days=900)).isoformat()  # ~2.5 năm tuổi
TOO_OLD = (date.today() - timedelta(days=365 * 8)).isoformat()
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


@pytest.fixture
def customer(client):
    response = client.post(
        "/api/v1/test-drives",
        json={
            "name": "Nguyễn Văn Tuấn",
            "phone": "0912345678",
            "vehicle_id": "vf3",
            "model": "VF 3",
            "test_drive_date": TOMORROW,
            "test_drive_time": "09:30",
            "province": "Hà Nội",
            "ward": "Cầu Giấy",
            "source": "Showroom",
        },
    )
    assert response.status_code == 201
    return response.json()


def appraisal_payload(customer, **overrides):
    payload = {
        "customer_code": customer["code"],
        "make": "Honda",
        "model": "City",
        "year": 2022,
        "trim": "RS",
        "odo_km": 40_000,
        "first_registration_date": RECENT,
        "flags": {},
        "levels": {"engine": "tot", "chassis": "kha"},
        "repair_cost": 5_000_000,
    }
    payload.update(overrides)
    return payload


class TestCriteria:
    def test_returns_eight_criteria_summing_to_100(self, client):
        rows = client.get("/api/v1/appraisals/criteria").json()
        assert len(rows) == 8
        assert sum(row["weight_pct"] for row in rows) == 100

    def test_odo_is_the_only_auto_criteria(self, client):
        rows = client.get("/api/v1/appraisals/criteria").json()
        auto = [row["code"] for row in rows if row["auto"]]
        assert auto == ["odo"]


class TestUsedCarCatalog:
    def test_price_table_is_seeded_on_startup(self, client):
        # Rỗng thì cả nghiệp vụ đứng im vì công thức A không có vế trái.
        models = client.get("/api/v1/appraisals/used-car-models").json()
        assert len(models) > 10
        assert {"make": "Honda", "model": "City"}.items() <= next(
            item for item in models if item["model"] == "City"
        ).items()


class TestEligibilityPreview:
    def test_clean_car_passes_every_check(self, client, customer):
        checks = client.post(
            "/api/v1/appraisals/eligibility", json=appraisal_payload(customer)
        ).json()
        assert all(check["passed"] for check in checks)

    def test_old_car_fails_the_age_check(self, client, customer):
        checks = client.post(
            "/api/v1/appraisals/eligibility",
            json=appraisal_payload(customer, first_registration_date=TOO_OLD),
        ).json()
        failed = [check for check in checks if not check["passed"]]
        assert [check["code"] for check in failed] == ["age"]
        assert failed[0]["why"]  # phải kèm lý do để sales giải thích cho khách

    def test_preview_does_not_write_anything(self, client, customer):
        client.post("/api/v1/appraisals/eligibility", json=appraisal_payload(customer))
        assert client.get("/api/v1/appraisals").json() == []


class TestCreateAppraisal:
    def test_creates_a_scored_record(self, client, customer):
        response = client.post("/api/v1/appraisals", json=appraisal_payload(customer))
        assert response.status_code == 201

        body = response.json()
        assert body["code"].startswith("DG-")
        assert body["eligibility_status"] == "passed"
        assert body["status"] == "appraised"
        assert len(body["scores"]) == 8
        assert body["market_price"] > 0
        assert body["value_a"] > 0

    def test_unrated_criteria_come_back_marked_estimated(self, client, customer):
        body = client.post("/api/v1/appraisals", json=appraisal_payload(customer)).json()
        estimated = {score["criteria_code"] for score in body["scores"] if score["estimated"]}
        # Chấm 2 tiêu chí -> 5 tiêu chí thủ công còn lại là ước lượng, ODO thì không.
        assert estimated == {"electrical", "exterior", "interior", "service", "extras"}

    def test_records_the_sla_deadline(self, client, customer):
        body = client.post("/api/v1/appraisals", json=appraisal_payload(customer)).json()
        assert body["sla_due_at"] is not None
        assert body["smart_solution_ref"].startswith("SS-")

    def test_rejected_car_is_still_recorded(self, client, customer):
        # Không ghi thì quản lý mất số liệu đã loại bao nhiêu xe vì lý do gì.
        body = client.post(
            "/api/v1/appraisals",
            json=appraisal_payload(customer, first_registration_date=TOO_OLD),
        ).json()
        assert body["eligibility_status"] == "rejected_age"
        assert body["status"] == "rejected"
        assert body["value_a"] == 0
        assert body["scores"] == []

    def test_flooded_car_is_rejected(self, client, customer):
        body = client.post(
            "/api/v1/appraisals",
            json=appraisal_payload(customer, flags={"flood_damaged": True}),
        ).json()
        assert body["eligibility_status"] == "rejected_flood_damaged"

    def test_unknown_car_needs_manual_appraisal(self, client, customer):
        response = client.post(
            "/api/v1/appraisals",
            json=appraisal_payload(customer, make="Tesla", model="Model 3", trim=""),
        )
        # 422 chứ không 500: dữ liệu hợp lệ, chỉ là chưa có giá tham chiếu.
        assert response.status_code == 422
        assert "thẩm định viên" in response.json()["detail"]

    def test_unknown_customer_is_404(self, client, customer):
        response = client.post(
            "/api/v1/appraisals", json=appraisal_payload(customer, customer_code="VF-99999")
        )
        assert response.status_code == 404

    def test_rejects_an_unknown_scoring_level(self, client, customer):
        response = client.post(
            "/api/v1/appraisals", json=appraisal_payload(customer, levels={"engine": "tuyệt vời"})
        )
        assert response.status_code == 422

    def test_rejects_a_future_registration_date(self, client, customer):
        response = client.post(
            "/api/v1/appraisals",
            json=appraisal_payload(
                customer, first_registration_date=(date.today() + timedelta(days=5)).isoformat()
            ),
        )
        assert response.status_code == 422


class TestQuote:
    @pytest.fixture
    def appraisal(self, client, customer):
        return client.post("/api/v1/appraisals", json=appraisal_payload(customer)).json()

    def test_quote_follows_the_formula(self, client, appraisal):
        quote = client.post(
            f"/api/v1/appraisals/{appraisal['code']}/quotes", json={"vehicle_id": "vf8"}
        ).json()

        assert quote["value_b"] == quote["list_price"] + quote["total_fees"]
        assert quote["amount_c"] == (
            quote["value_b"] - quote["value_a"] - quote["promo_new_car"] - quote["trade_in_bonus"]
        )
        assert quote["value_a"] == appraisal["value_a"]

    def test_quoting_moves_the_record_forward(self, client, appraisal):
        client.post(f"/api/v1/appraisals/{appraisal['code']}/quotes", json={"vehicle_id": "vf8"})
        body = client.get(f"/api/v1/appraisals/{appraisal['code']}").json()
        assert body["status"] == "quoted"
        assert len(body["quotes"]) == 1

    def test_one_appraisal_can_carry_several_quotes(self, client, appraisal):
        # Khách so nhiều mẫu xe mới trên cùng một lần định giá xe cũ.
        for vehicle_id in ("vf3", "vf6", "vf9"):
            client.post(
                f"/api/v1/appraisals/{appraisal['code']}/quotes", json={"vehicle_id": vehicle_id}
            )
        body = client.get(f"/api/v1/appraisals/{appraisal['code']}").json()
        assert [quote["vehicle_id"] for quote in body["quotes"]] == ["vf3", "vf6", "vf9"]

    def test_cannot_quote_a_rejected_appraisal(self, client, customer):
        rejected = client.post(
            "/api/v1/appraisals",
            json=appraisal_payload(customer, first_registration_date=TOO_OLD),
        ).json()
        response = client.post(
            f"/api/v1/appraisals/{rejected['code']}/quotes", json={"vehicle_id": "vf8"}
        )
        assert response.status_code == 422

    def test_unknown_vehicle_is_422(self, client, appraisal):
        response = client.post(
            f"/api/v1/appraisals/{appraisal['code']}/quotes", json={"vehicle_id": "tesla"}
        )
        assert response.status_code == 422


class TestChecklist:
    @pytest.fixture
    def quoted(self, client, customer):
        appraisal = client.post("/api/v1/appraisals", json=appraisal_payload(customer)).json()
        client.post(f"/api/v1/appraisals/{appraisal['code']}/quotes", json={"vehicle_id": "vf6"})
        return appraisal

    def test_partial_checklist_blocks_softly(self, client, quoted):
        # Chặn MỀM: vẫn 200, hồ sơ giữ ở trạng thái chờ chứ không huỷ.
        response = client.patch(
            f"/api/v1/appraisals/{quoted['code']}/checklist",
            json={"done": ["contract", "deposit"]},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "blocked"

    def test_full_checklist_closes_the_deal(self, client, quoted):
        body = client.patch(
            f"/api/v1/appraisals/{quoted['code']}/checklist",
            json={
                "done": ["contract", "deposit", "papers", "status"],
                "handover_date": (date.today() + timedelta(days=7)).isoformat(),
            },
        ).json()

        assert body["status"] == "accepted"
        assert body["quotes"][0]["status"] == "accepted"
        assert body["quotes"][0]["handover_date"] is not None

    def test_blocked_record_can_be_completed_later(self, client, quoted):
        client.patch(
            f"/api/v1/appraisals/{quoted['code']}/checklist", json={"done": ["contract"]}
        )
        body = client.patch(
            f"/api/v1/appraisals/{quoted['code']}/checklist",
            json={"done": ["contract", "deposit", "papers", "status"]},
        ).json()
        assert body["status"] == "accepted"

    def test_unknown_code_is_404(self, client):
        response = client.patch("/api/v1/appraisals/DG-9999/checklist", json={"done": []})
        assert response.status_code == 404


class TestListing:
    def test_filters_by_customer(self, client, customer):
        client.post("/api/v1/appraisals", json=appraisal_payload(customer))

        assert len(client.get("/api/v1/appraisals").json()) == 1
        mine = client.get(f"/api/v1/appraisals?customer_code={customer['code']}").json()
        assert len(mine) == 1
        assert client.get("/api/v1/appraisals?customer_code=VF-99999").json() == []

    def test_static_paths_are_not_swallowed_by_the_code_route(self, client):
        # "/appraisals/criteria" phải khai báo TRƯỚC "/appraisals/{code}",
        # nếu không "criteria" bị hiểu là mã hồ sơ và trả 404.
        assert client.get("/api/v1/appraisals/criteria").status_code == 200
        assert client.get("/api/v1/appraisals/used-car-models").status_code == 200
