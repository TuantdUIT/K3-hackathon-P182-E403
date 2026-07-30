"""Chặn danh mục Python lệch khỏi danh mục JS.

Test này đọc THẲNG file .js của frontend rồi so với bản Python. Sửa một bên mà
quên bên kia là agent sẽ điền một `vehicle_id` mà dropdown không có option nào
khớp — form đứng im mà không báo lỗi gì.
"""

import re
from pathlib import Path

import pytest

from src.backend.agents.shared.catalog import (
    VEHICLES,
    match_vehicle,
    match_ward,
    normalize_phone,
    strip_accents,
)
from src.backend.agents.shared.wards import HANOI_WARDS

ROOT = Path(__file__).resolve().parents[2]
VEHICLES_JS = ROOT / "src" / "frontend" / "src" / "data" / "vehicles.js"
WARDS_JS = ROOT / "src" / "frontend" / "src" / "data" / "hanoi_wards.js"


def read_js_vehicles() -> list[tuple[str, str]]:
    text = VEHICLES_JS.read_text(encoding="utf-8")
    ids = re.findall(r"^\s*id:\s*'([^']+)'", text, re.MULTILINE)
    names = re.findall(r"^\s*name:\s*'([^']+)'", text, re.MULTILINE)
    assert len(ids) == len(names), "vehicles.js có id/name không khớp số lượng"
    return list(zip(ids, names, strict=True))


def read_js_wards() -> list[str]:
    text = WARDS_JS.read_text(encoding="utf-8")
    return re.findall(r"^\s*'([^']+)',\s*$", text, re.MULTILINE)


class TestVehicleCatalogParity:
    def test_same_number_of_vehicles(self):
        assert len(read_js_vehicles()) == len(VEHICLES) == 14

    def test_ids_and_names_match_exactly(self):
        assert read_js_vehicles() == list(VEHICLES)

    def test_expected_ids_present(self):
        expected = {
            "vf2",
            "vf3",
            "vf5",
            "vf6",
            "vf7",
            "vf8",
            "vf8-allnew",
            "vfmpv7",
            "vf9",
            "minio-green",
            "herio-green",
            "nerio-green",
            "limo-green",
            "ec-van",
        }
        assert {vehicle_id for vehicle_id, _ in VEHICLES} == expected


class TestWardCatalogParity:
    def test_count_is_127(self):
        assert len(HANOI_WARDS) == 127

    def test_matches_js_exactly(self):
        assert read_js_wards() == list(HANOI_WARDS)

    def test_no_duplicates(self):
        assert len(set(HANOI_WARDS)) == len(HANOI_WARDS)


class TestStripAccents:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Cầu Giấy", "cau giay"),
            ("Đống Đa", "dong da"),
            ("Hoàn Kiếm", "hoan kiem"),
            ("ĐÔNG NGẠC", "dong ngac"),
            ("", ""),
        ],
    )
    def test_strip(self, raw, expected):
        assert strip_accents(raw) == expected


class TestMatchVehicle:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("VF 8", "vf8"),
            ("vf8", "vf8"),
            ("con VF8", "vf8"),
            ("vf 9", "vf9"),
            ("VF9", "vf9"),
            ("VF 8 All New (2026)", "vf8-allnew"),
            ("vf8 all new", "vf8-allnew"),
            ("VF MPV 7", "vfmpv7"),
            ("Limo Green", "limo-green"),
            ("xe limo", "limo-green"),
            ("EC Van", "ec-van"),
            ("minio", "minio-green"),
        ],
    )
    def test_known_names(self, raw, expected):
        assert match_vehicle(raw) == expected

    def test_all_catalog_names_resolve_to_themselves(self):
        for vehicle_id, name in VEHICLES:
            assert match_vehicle(name) == vehicle_id

    @pytest.mark.parametrize("raw", [None, "", "xe gì cũng được", "Tesla Model 3"])
    def test_unknown_returns_none(self, raw):
        assert match_vehicle(raw) is None

    def test_allnew_wins_over_plain_vf8(self):
        # "vf8allnew" dài hơn "vf8" nên phải thắng, không được rơi về vf8.
        assert match_vehicle("cho tôi thử VF 8 All New") == "vf8-allnew"


class TestMatchWard:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Cầu Giấy", "Cầu Giấy"),
            ("cau giay", "Cầu Giấy"),
            ("Phường Cầu Giấy", "Cầu Giấy"),
            ("Xã Bát Tràng", "Bát Tràng"),
            ("HOÀN KIẾM", "Hoàn Kiếm"),
            ("ở Hoàn Kiếm nhé", "Hoàn Kiếm"),
        ],
    )
    def test_known_wards(self, raw, expected):
        assert match_ward(raw) == expected

    def test_all_wards_resolve_to_themselves(self):
        for ward in HANOI_WARDS:
            assert match_ward(ward) == ward

    @pytest.mark.parametrize("raw", [None, "", "Quận 1", "Thủ Đức"])
    def test_unknown_returns_none(self, raw):
        assert match_ward(raw) is None

    def test_ambiguous_prefix_returns_none(self):
        # "Phú" khớp Phú Diễn / Phú Lương / Phú Cát / Phú Nghĩa / Phú Xuyên...
        # Chọn hộ là chọn sai, nên phải trả None để agent hỏi lại.
        assert match_ward("Phú") is None


class TestNormalizePhone:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("0912345678", "0912345678"),
            ("091 234 5678", "0912345678"),
            ("091-234-5678", "0912345678"),
            ("+84912345678", "0912345678"),
            ("84912345678", "0912345678"),
            ("0084912345678", "0912345678"),
        ],
    )
    def test_valid(self, raw, expected):
        assert normalize_phone(raw) == expected

    @pytest.mark.parametrize("raw", [None, "", "12345", "không có số"])
    def test_invalid(self, raw):
        assert normalize_phone(raw) is None
