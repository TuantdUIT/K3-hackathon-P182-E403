"""Khoá luật định giá xe cũ theo `docs/CAR_PREDICT_FORMULA.md`.

Đây là phần KHÔNG cần LLM: sai một con số ở đây là báo sai tiền cho khách, mà
lỗi đó không có triệu chứng nào ngoài một số tiền trông vẫn hợp lý.
"""

from datetime import date

import pytest

from src.backend.services import appraisal_rules as rules
from src.backend.services.appraisal_repository import (
    build_scores,
    compute_quote,
    compute_value_a,
    missing_checklist,
    total_score_pct,
)

TODAY = date(2026, 1, 1)


class TestCriteriaTable:
    def test_weights_sum_to_100(self):
        # Bất biến của cả hệ thống — doc ghi "tổng điểm hệ thống là 100%".
        assert sum(rules.CRITERIA_WEIGHT.values()) == 100

    def test_has_eight_criteria(self):
        assert len(rules.APPRAISAL_CRITERIA) == 8

    def test_codes_are_unique(self):
        codes = [code for code, _, _, _ in rules.APPRAISAL_CRITERIA]
        assert len(set(codes)) == len(codes)

    def test_weights_match_the_document(self):
        assert rules.CRITERIA_WEIGHT == {
            "odo": 20,
            "engine": 20,
            "chassis": 20,
            "electrical": 10,
            "exterior": 10,
            "interior": 10,
            "service": 5,
            "extras": 5,
        }

    def test_odo_is_the_only_auto_criteria(self):
        assert rules.ODO_CODE not in rules.SCORED_CRITERIA
        assert len(rules.SCORED_CRITERIA) == 7


class TestLevels:
    @pytest.mark.parametrize(
        ("level", "ratio"), [("tot", 1.0), ("kha", 0.75), ("trung_binh", 0.5), ("kem", 0.0)]
    )
    def test_four_levels(self, level, ratio):
        assert rules.level_ratio(level) == ratio

    def test_unknown_level_falls_back_to_default(self):
        # Không được ngầm cho điểm tối đa: đó là tự đoán có lợi cho một bên.
        assert rules.level_ratio(None) == rules.LEVELS[rules.DEFAULT_LEVEL]
        assert rules.level_ratio("gì đó") == rules.LEVELS[rules.DEFAULT_LEVEL]
        assert rules.LEVELS[rules.DEFAULT_LEVEL] < 1.0


class TestOdoRatio:
    def test_under_standard_keeps_full_score(self):
        # 3 năm, 45.000 km = 15.000 km/năm -> trong chuẩn.
        assert rules.odo_ratio(45_000, date(2023, 1, 1), TODAY) == 1.0

    def test_exactly_at_standard_keeps_full_score(self):
        assert rules.odo_ratio(rules.STANDARD_KM_PER_YEAR, date(2025, 1, 1), TODAY) == 1.0

    def test_over_standard_loses_progressively(self):
        # 1 năm, 27.000 km = vượt 50% -> còn 0.5.
        assert rules.odo_ratio(27_000, date(2025, 1, 1), TODAY) == pytest.approx(0.5)

    def test_never_below_floor(self):
        assert rules.odo_ratio(500_000, date(2025, 1, 1), TODAY) == rules.ODO_FLOOR_RATIO

    def test_young_car_is_measured_over_at_least_one_year(self):
        # 2 tháng tuổi, 5.000 km. Chia thẳng cho 1/6 năm sẽ ra 30.000 km/năm và
        # trừ oan một chiếc xe gần như mới.
        assert rules.odo_ratio(5_000, date(2025, 11, 1), TODAY) == 1.0

    def test_more_km_never_scores_higher(self):
        ratios = [rules.odo_ratio(km, date(2023, 1, 1), TODAY) for km in range(0, 300_000, 25_000)]
        assert ratios == sorted(ratios, reverse=True)


class TestEligibility:
    def test_clean_recent_car_passes(self):
        status, checks = rules.check_eligibility(
            first_registration_date=date(2023, 1, 1), today=TODAY
        )
        assert status == "passed"
        assert all(check["passed"] for check in checks)

    def test_too_old_is_rejected(self):
        status, _ = rules.check_eligibility(
            first_registration_date=date(2018, 1, 1), today=TODAY
        )
        assert status == "rejected_age"

    def test_boundary_just_under_seven_years_passes(self):
        status, _ = rules.check_eligibility(
            first_registration_date=date(2019, 2, 1), today=TODAY
        )
        assert status == "passed"

    def test_owned_too_briefly_is_rejected(self):
        status, _ = rules.check_eligibility(
            first_registration_date=date(2023, 1, 1), ownership_months=2, today=TODAY
        )
        assert status == "rejected_ownership"

    @pytest.mark.parametrize("flag", list(rules.HARD_FLAGS))
    def test_each_hard_flag_rejects(self, flag):
        status, _ = rules.check_eligibility(
            first_registration_date=date(2023, 1, 1), flags={flag: True}, today=TODAY
        )
        assert status == f"rejected_{flag}"

    def test_checks_always_cover_every_condition(self):
        # UI cần thấy cả mục ĐẠT, không chỉ mục trượt.
        _status, checks = rules.check_eligibility(
            first_registration_date=date(2018, 1, 1), flags={"flood_damaged": True}, today=TODAY
        )
        assert len(checks) == 2 + len(rules.HARD_FLAGS)
        assert {check["code"] for check in checks} == {"age", "ownership", *rules.HARD_FLAGS}

    def test_every_check_carries_a_reason(self):
        # Chuỗi "why" là nguyên liệu cho node `explain` — thiếu là agent im lặng.
        _status, checks = rules.check_eligibility(
            first_registration_date=date(2023, 1, 1), today=TODAY
        )
        assert all(check["why"].strip() for check in checks)

    def test_age_is_the_upper_bound_of_ownership(self):
        # Không khai thời gian sở hữu, xe mới đăng ký 2 tháng -> không thể sở hữu
        # đủ 6 tháng, phải trượt chứ không được cho qua.
        status, _ = rules.check_eligibility(
            first_registration_date=date(2025, 11, 1), today=TODAY
        )
        assert status == "rejected_ownership"


class TestScoring:
    def test_builds_all_eight_rows(self):
        scores = build_scores(odo_km=30_000, first_registration_date=date(2024, 1, 1), today=TODAY)
        assert len(scores) == 8

    def test_unrated_criteria_are_marked_estimated(self):
        scores = build_scores(
            odo_km=30_000,
            first_registration_date=date(2024, 1, 1),
            levels={"engine": "tot"},
            today=TODAY,
        )
        by_code = {row["criteria_code"]: row for row in scores}
        assert by_code["engine"]["estimated"] is False
        assert by_code["chassis"]["estimated"] is True
        # ODO tính bằng công thức nên không bao giờ là ước lượng.
        assert by_code["odo"]["estimated"] is False

    def test_perfect_car_scores_100(self):
        scores = build_scores(
            odo_km=10_000,
            first_registration_date=date(2024, 1, 1),
            levels=dict.fromkeys(rules.SCORED_CRITERIA, "tot"),
            today=TODAY,
        )
        assert total_score_pct(scores) == 100.0

    def test_worst_car_scores_only_the_odo_part(self):
        scores = build_scores(
            odo_km=10_000,
            first_registration_date=date(2024, 1, 1),
            levels=dict.fromkeys(rules.SCORED_CRITERIA, "kem"),
            today=TODAY,
        )
        assert total_score_pct(scores) == float(rules.CRITERIA_WEIGHT["odo"])


class TestValueA:
    def test_formula_matches_the_document(self):
        # A = giá thị trường × tổng điểm − chi phí sửa chữa.
        assert compute_value_a(500_000_000, 80.0, 20_000_000) == 380_000_000

    def test_never_negative(self):
        # Chi phí sửa lớn hơn giá trị xe thì A về 0, không cho số âm chảy vào C.
        assert compute_value_a(100_000_000, 50.0, 900_000_000) == 0


class TestQuote:
    def test_b_is_list_price_plus_every_fee(self):
        quote = compute_quote("vf3", value_a=0)
        assert quote["value_b"] == quote["list_price"] + sum(quote["fees"].values())
        assert set(quote["fees"]) == {label for label, _ in rules.FEE_BREAKDOWN_LABELS}

    def test_c_is_b_minus_a_minus_discounts(self):
        quote = compute_quote("vf8", value_a=300_000_000)
        expected = (
            quote["value_b"] - 300_000_000 - quote["promo_new_car"] - quote["trade_in_bonus"]
        )
        assert quote["amount_c"] == expected

    def test_promo_comes_from_the_catalog_price_gap(self):
        from src.backend.agents.shared.catalog import VEHICLE_PRICES

        list_price, price_from = VEHICLE_PRICES["vf6"]
        assert compute_quote("vf6", 0)["promo_new_car"] == list_price - price_from

    def test_unknown_vehicle_raises(self):
        with pytest.raises(ValueError, match="danh mục"):
            compute_quote("tesla-model-3", 0)

    def test_higher_trade_in_value_lowers_what_the_customer_pays(self):
        cheap = compute_quote("vf8", 100_000_000)["amount_c"]
        rich = compute_quote("vf8", 400_000_000)["amount_c"]
        assert rich == cheap - 300_000_000


class TestChecklist:
    def test_four_items(self):
        assert len(rules.CHECKLIST_ITEMS) == 4

    def test_missing_lists_untouched_items_in_order(self):
        assert missing_checklist(["contract"]) == ["deposit", "papers", "status"]

    def test_nothing_missing_when_all_done(self):
        assert missing_checklist([code for code, _ in rules.CHECKLIST_ITEMS]) == []

    def test_unknown_codes_do_not_satisfy_anything(self):
        assert len(missing_checklist(["gì đó", "linh tinh"])) == 4


class TestExperienceLevel:
    @pytest.mark.parametrize(
        ("cases", "level"), [(0, "novice"), (2, "novice"), (3, "familiar"), (9, "familiar"), (10, "expert")]
    )
    def test_thresholds(self, cases, level):
        assert rules.experience_level(cases) == level
