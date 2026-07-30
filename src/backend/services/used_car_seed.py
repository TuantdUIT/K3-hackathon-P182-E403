"""Bảng giá thị trường xe cũ dùng cho demo.

Giá trung bình đang giao dịch trên thị trường Hà Nội, đơn vị VND. Đây là DỮ LIỆU
DEMO tự soạn, không phải bảng giá chính thức — trước khi chạy thật phải thay
bằng nguồn khảo sát có kiểm chứng.

Không có xe trong bảng này thì hồ sơ chuyển thẩm định thủ công: `A` cần giá thị
trường cùng đời làm vế trái, thiếu nó thì không có gì để nhân với điểm.

Đời xe TẬP TRUNG TỪ 2020 TRỞ LẠI ĐÂY là có chủ đích: `MAX_AGE_YEARS = 7` nên xe
cũ hơn thế bị cổng loại trừ chặn trước khi cần tới giá. Vài dòng đời 2018-2019
giữ lại để demo được nhánh từ chối — có giá nhưng vẫn trượt điều kiện tuổi.
"""

# (hãng, dòng, đời, phiên bản, giá thị trường)
USED_CAR_PRICES: tuple[tuple[str, str, int, str, int], ...] = (
    # --- Honda ---
    ("Honda", "City", 2020, "", 458_000_000),
    ("Honda", "City", 2021, "G", 485_000_000),
    ("Honda", "City", 2022, "RS", 545_000_000),
    ("Honda", "City", 2023, "RS", 585_000_000),
    ("Honda", "CR-V", 2021, "", 845_000_000),
    ("Honda", "CR-V", 2023, "L", 985_000_000),
    ("Honda", "Civic", 2022, "RS", 745_000_000),
    # --- Toyota ---
    ("Toyota", "Vios", 2020, "E", 385_000_000),
    ("Toyota", "Vios", 2021, "G", 425_000_000),
    ("Toyota", "Vios", 2022, "G", 458_000_000),
    ("Toyota", "Vios", 2023, "G", 495_000_000),
    ("Toyota", "Innova", 2021, "", 645_000_000),
    ("Toyota", "Camry", 2021, "2.0G", 875_000_000),
    ("Toyota", "Corolla Cross", 2021, "1.8V", 725_000_000),
    ("Toyota", "Corolla Cross", 2023, "HEV", 845_000_000),
    ("Toyota", "Fortuner", 2022, "", 985_000_000),
    # --- Mazda ---
    ("Mazda", "Mazda 3", 2020, "", 545_000_000),
    ("Mazda", "Mazda 3", 2022, "Luxury", 635_000_000),
    ("Mazda", "CX-5", 2021, "2.0", 735_000_000),
    ("Mazda", "CX-5", 2023, "Premium", 865_000_000),
    # --- Hyundai ---
    ("Hyundai", "Accent", 2020, "", 395_000_000),
    ("Hyundai", "Accent", 2022, "AT", 455_000_000),
    ("Hyundai", "Elantra", 2021, "", 545_000_000),
    ("Hyundai", "Tucson", 2022, "", 795_000_000),
    ("Hyundai", "SantaFe", 2021, "", 925_000_000),
    # --- Kia ---
    ("Kia", "Morning", 2021, "", 295_000_000),
    ("Kia", "K3", 2021, "Premium", 555_000_000),
    ("Kia", "K3", 2023, "Premium", 615_000_000),
    ("Kia", "Seltos", 2022, "Luxury", 645_000_000),
    ("Kia", "Carnival", 2022, "", 1_285_000_000),
    # --- Ford ---
    ("Ford", "Ranger", 2021, "XLS", 645_000_000),
    ("Ford", "Ranger", 2023, "Wildtrak", 885_000_000),
    ("Ford", "EcoSport", 2020, "", 425_000_000),
    # --- Mitsubishi / Suzuki / Nissan ---
    ("Mitsubishi", "Xpander", 2021, "", 525_000_000),
    ("Mitsubishi", "Attrage", 2022, "", 395_000_000),
    ("Suzuki", "Ertiga", 2021, "", 445_000_000),
    ("Nissan", "Almera", 2021, "", 425_000_000),
    # --- VinFast xe xăng (khách đổi sang xe điện cùng hãng) ---
    ("VinFast", "Fadil", 2021, "", 305_000_000),
    ("VinFast", "Fadil", 2022, "Cao cấp", 335_000_000),
    ("VinFast", "Lux A2.0", 2021, "", 585_000_000),
    ("VinFast", "Lux SA2.0", 2021, "", 825_000_000),
    # --- Xe sang ---
    ("Mercedes-Benz", "C200", 2021, "", 1_285_000_000),
    ("Mercedes-Benz", "GLC200", 2022, "", 1_685_000_000),
    ("BMW", "320i", 2021, "", 1_285_000_000),
    # --- Cố tình quá tuổi: có giá nhưng cổng loại trừ vẫn chặn ---
    ("Honda", "City", 2018, "", 385_000_000),
    ("Toyota", "Vios", 2018, "", 335_000_000),
    ("Chevrolet", "Cruze", 2018, "", 315_000_000),
)
