# Kịch bản thử agent đổi xe (nghiệp vụ 2)

Hai câu nhập mẫu để dán thẳng vào khung chat của màn hình đổi xe trong Admin
Portal. Mốc thời gian tính theo **hôm nay = 31/07/2026** — chạy ở ngày khác thì
sửa lại `ngày đăng ký lần đầu` cho khớp mốc tuổi xe.

## Điều kiện bắt buộc trước khi thử

Agent chặn ngay ở `extract_node` nếu chưa chọn khách (`swap_car/nodes.py:343`):

1. Mở Admin Portal, tạo/chọn một khách hàng ở bảng bên trái để `customer_code`
   được đẩy vào state.
2. Nếu DB trống, tạo lead trước bằng agent CRM hoặc form thêm khách thủ công.

Bảng giá xe cũ (`services/used_car_seed.py`) phải đã seed vào DB, nếu không mọi
hồ sơ đều rơi vào nhánh "thẩm định thủ công" bất kể xe hợp lệ.

---

## 1. Yêu cầu HỢP LỆ — chạy hết luồng tới báo giá

Dán nguyên đoạn này:

> Khách có xe Toyota Vios 2022 bản G, biển 30K-123.45, đã đi 62.000 km, đăng ký
> lần đầu ngày 20/05/2022, khách đứng tên từ đó tới giờ. Xe không ngập nước,
> không đâm đụng kết cấu, công-tơ-mét nguyên bản, giấy tờ gốc đầy đủ. Máy êm
> chuyển số mượt, khung gầm tốt, hệ thống điện ổn, sơn có vài vết xước cần dặm
> lại, nội thất khá, bảo dưỡng đủ lịch tại hãng, phụ kiện bình thường. Chi phí
> dọn xe dự kiến 12 triệu. Khách muốn đổi sang VF 6.

**Đường đi mong đợi:** `extract → eligibility → market_check → explain → plan →
fill → confirm_form → appraise → quote → confirm_price → checklist → handover`

Con trỏ ảo điền **16 ô**: 7 ô thông tin xe cũ → 0 cờ loại trừ (không cờ nào bật)
→ 7 ô chấm điểm → 2 ô xe mới. `fill_node` nghỉ 0,7 giây mỗi ô nên khối này chạy
khoảng 11 giây.

**Cổng loại trừ** — cả 6 dòng đều đạt:

| Điều kiện | Kết quả |
|---|---|
| Dưới 7 năm sử dụng | 4 năm 2 tháng ✓ |
| Sở hữu tối thiểu 6 tháng | 50 tháng ✓ |
| Không ngập nước / đâm đụng / tua ODO / thiếu giấy tờ | không cờ nào bật ✓ |

**Số liệu mong đợi:**

- Giá thị trường (Vios 2022 bản G): `458.000.000 đ`
- ODO: 62.000 km / 4,17 năm ≈ 14.880 km/năm ≤ 18.000 → tiêu chí ODO đạt trọn 20%
- Tổng điểm ≈ **88,75%** (máy tốt 20 + gầm tốt 20 + ODO 20 + điện khá 7,5 +
  sơn trung bình 5 + nội thất khá 7,5 + bảo dưỡng tốt 5 + phụ kiện khá 3,75)
- **A** = 458.000.000 × 88,75% − 12.000.000 = `394.475.000 đ`
- **B** (VF 6) = 729.000.000 + 22.430.000 phí lăn bánh = `751.430.000 đ`
- **C** = B − A − 40.000.000 khuyến mãi − 10.000.000 ưu đãi đổi xe =
  `306.955.000 đ`

Tổng điểm là con số **phụ thuộc cách LLM map mô tả tình trạng về 4 mức**
(`tot` / `kha` / `trung_binh` / `kem`). Lệch một bậc ở tiêu chí 20% thì A đổi
khoảng 23 triệu — đối chiếu bảng chấm điểm hiện trên form trước khi kết luận là sai.

**Điểm nên thử thêm ở bước `confirm_form`:** khi agent hỏi soát lại hồ sơ, gõ
`odo 54.000 thôi` → `patch_form_node` chỉ điền lại ô ODO, không diễn lại cả form.

---

## 2. Yêu cầu KHÔNG HỢP LỆ — bị cổng loại trừ chặn vì quá tuổi

Dán nguyên đoạn này:

> Khách có xe Honda City 2018, biển 29A-567.89, đã chạy 95.000 km, đăng ký lần
> đầu 15/03/2018, khách đứng tên 5 năm nay. Xe không ngập nước, giấy tờ đầy đủ,
> máy còn tốt. Khách muốn đổi sang VF 5.

**Đường đi mong đợi:** `extract → eligibility → rejected → END`

Xe này **có** trong bảng giá thị trường (`385.000.000 đ`, dòng cố ý để trong
`used_car_seed.py:71`) nhưng vẫn bị chặn — đúng ý đồ: cổng loại trừ chạy TRƯỚC
khi chấm điểm.

**Kết quả mong đợi:**

- `eligibility_status = "rejected_age"` — tuổi xe 8 năm 4 tháng ≥ 7 năm
- Agent nêu lý do: chi phí tân trang và rủi ro tồn kho vượt phần giá trị thu về
- **Không** tạo hồ sơ thẩm định, **không** chạy con trỏ ảo điền form, không có
  bảng chấm điểm, không có báo giá
- Bảng 6 điều kiện vẫn hiện đủ: 5 dòng đạt, riêng dòng tuổi xe trượt

Để kiểm tra đúng chỗ chặn, sửa `đăng ký lần đầu 15/03/2018` thành `15/03/2021`
rồi chạy lại — hồ sơ sẽ đi tiếp sang `market_check`.

---

## Biến thể nhanh (cùng bộ dữ liệu, đổi một chi tiết)

| Muốn thử nhánh | Sửa gì trong câu hợp lệ ở mục 1 |
|---|---|
| Cờ loại trừ cứng | thêm `xe từng bị ngập nước năm ngoái` → `rejected_flood_damaged` |
| Chưa đủ 6 tháng sở hữu | `đăng ký lần đầu 10/05/2026` → `rejected_ownership` |
| Thẩm định thủ công | đổi xe cũ thành `Peugeot 3008 2022` (không có trong bảng giá) → dừng ở `market_check`, không điền form |
| Thiếu field bắt buộc | bỏ `đăng ký lần đầu ...` → `ask_missing` hỏi gộp một lần |
| Sửa giá sau báo giá | ở bước `confirm_price` gõ `chi phí sửa 25 triệu` → `revise` tính lại A và C |
