"""Câu chữ của agent đổi xe, tách khỏi logic node.

Giọng: nói với NHÂN VIÊN KINH DOANH về một khách thứ ba — cùng nguyên tắc với
`crm_lead/copy.py`. "Anh/chị" là sales đang ngồi trước máy, người đổi xe là
"khách". Không hứa hẹn thay khách, không tự cam kết mức giá.

Khác `shared/copy.py`: agent này chỉ có MỘT giọng (chỉ chạy trong Admin Portal)
nên không cần `CopyPack` + hàm chọn theo channel. Thêm kênh thứ hai thì hẵng
tách, đừng dựng sẵn tầng trừu tượng cho một trường hợp.
"""

GREETING = (
    "Anh/chị chọn khách ở bảng bên trái rồi đọc thông tin xe cũ giúp em: hãng, "
    "dòng, đời xe, số km đã đi, ngày đăng ký lần đầu và mẫu VinFast khách muốn đổi ạ."
)

NO_CUSTOMER = (
    "Anh/chị chọn khách trong danh sách bên trái trước giúp em ạ — em cần gắn hồ sơ "
    "định giá vào đúng khách thì mới lưu được."
)

EXTRACT_FAILED = (
    "Hệ thống đang nghẽn khi xử lý tin nhắn nên em chưa bóc được thông tin xe ạ. "
    "Anh/chị nhắn lại giúp em, hoặc nhập tay trực tiếp trên form bên cạnh."
)

ASK_MISSING = "Em cần thêm {need} của xe cũ ạ."

# --- cổng loại trừ ---

REJECTED = (
    "Xe này chưa đủ điều kiện đổi ạ: {reason}.\n"
    "Em đã lưu hồ sơ {code} ở trạng thái từ chối để anh/chị có căn cứ trả lời khách."
)

REJECTED_NO_RECORD = "Xe này chưa đủ điều kiện đổi ạ: {reason}."

EXPLAIN_HEADER = "Xe đủ điều kiện đổi ạ. Em nói qua vì sao từng mốc lại quan trọng:"
EXPLAIN_SHORT = "Xe qua đủ {total} điều kiện đầu vào ạ, em chuyển sang thẩm định luôn."

# --- điền form + thẩm định ---

PLAN_FULL = "Em điền hồ sơ định giá bên cạnh nhé, anh/chị theo dõi con trỏ giúp em ạ."
PLAN_CORRECTION = "Em cập nhật lại phần anh/chị vừa sửa ạ."

NO_MARKET_PRICE = (
    "Hệ thống chưa có giá thị trường cho {make} {model} đời {year} ạ. "
    "Hồ sơ này cần thẩm định viên định giá thủ công, em không tự áng giá được."
)

APPRAISE_FAILED = (
    "Em lưu hồ sơ định giá không thành công do lỗi hệ thống ạ. "
    "Anh/chị bấm nút lưu trên form để thử lại giúp em nhé."
)

# --- soát hồ sơ trước khi chấm điểm (HITL) ---

ASK_FORM_OK = (
    "Em điền xong hồ sơ rồi ạ. Anh/chị soát lại giúp em, có chỗ nào sai thì cứ "
    "nói ngay trong khung chat — ví dụ \"odo 54.000 km thôi\" hoặc \"đời 2021 "
    "chứ không phải 2022\"."
)

FORM_PATCH_APPLIED = "Em sửa lại {labels} rồi ạ, anh/chị theo dõi con trỏ điền lại giúp em."

FORM_PATCH_UNCLEAR = (
    "Em chưa rõ anh/chị muốn sửa ô nào ạ. Anh/chị nói kèm tên ô và giá trị mới "
    "giúp em nhé, ví dụ \"số km 54.000\", \"đời xe 2021\", \"gầm chấm mức khá\"."
)

FORM_PATCH_EXHAUSTED = (
    "Hồ sơ đã sửa {rounds} lượt mà vẫn chưa khớp ạ. Anh/chị chỉnh trực tiếp trên "
    "form bên cạnh rồi bấm \"Tính định giá & báo giá\" giúp em cho nhanh."
)

SMART_SOLUTION = (
    "Em đã chuyển hồ sơ {code} sang Smart Solution thẩm định ({steps} bước, "
    "khoảng {items} hạng mục). Kết quả dự kiến có trong {sla} giờ — em sẽ nhắc "
    "anh/chị khi tới hạn ạ."
)

APPRAISAL_SUMMARY = (
    "Kết quả chấm điểm xe cũ:\n"
    "• Giá thị trường {make} {model} đời {year}: {market_price}\n"
    "• Tổng điểm đạt: {score}%\n"
    "• Chi phí dọn dẹp/sửa chữa: {repair_cost}\n"
    "→ Giá thu xe cũ (A): {value_a}"
)

ESTIMATED_WARNING = (
    "⚠ {count} tiêu chí chưa có đánh giá của thẩm định viên nên em tạm tính mức Khá: "
    "{labels}. Con số trên sẽ đổi khi có biên bản thật."
)

# --- báo giá ---

QUOTE_SUMMARY = (
    "Chi phí bù trừ nếu khách đổi sang {model}:\n"
    "• Giá niêm yết xe mới: {list_price}\n"
    "• Phí lăn bánh: {total_fees}\n"
    "→ Tổng chi phí xe mới (B): {value_b}\n"
    "• Trừ giá thu xe cũ (A): {value_a}\n"
    "• Trừ khuyến mãi xe mới: {promo}\n"
    "• Trừ ưu đãi riêng cho khách đổi xe: {bonus}\n"
    "→ Khách cần trả thêm (C): {amount_c}"
)

QUOTE_NEGATIVE = (
    "Con số ra ÂM ({amount_c}) nghĩa là hãng phải hoàn lại tiền cho khách. "
    "Anh/chị kiểm tra lại chi phí sửa chữa và mức chấm điểm giúp em trước khi báo khách ạ."
)

ASK_PRICE_OK = "Anh/chị trao đổi với khách xem mức này đã ổn chưa ạ?"

# --- vòng sửa ---

REVISE_APPLIED = "Em tính lại với {labels} ạ."
REVISE_UNCLEAR = (
    "Em chưa rõ anh/chị muốn đổi gì ạ. Anh/chị nhắn cụ thể giúp em, ví dụ "
    '"đổi sang VF 5", "chi phí sửa 20 triệu" hoặc "gầm chấm mức trung bình" nhé.'
)
REVISE_EXHAUSTED = (
    "Em đã tính lại {rounds} lần mà vẫn chưa khớp ý anh/chị ạ. "
    "Anh/chị chỉnh trực tiếp trên form rồi bấm tính lại giúp em nhé."
)

# --- checklist & bàn giao ---

CHECKLIST_INTRO = (
    "Khách đồng ý giá rồi ạ. Trước khi hẹn ngày giao xe, anh/chị tích giúp em "
    "{total} việc bắt buộc trong thẻ bên dưới nhé."
)

CHECKLIST_BLOCKED = (
    "Hồ sơ còn thiếu {count} việc bắt buộc: {labels}.\n"
    "Em giữ hồ sơ {code} ở trạng thái chờ — anh/chị làm nốt rồi nhắn em để chốt ngày giao xe ạ."
)

HANDOVER = (
    "Xong ạ! Hồ sơ {code} đã chốt: khách đổi sang {model}, cần trả thêm {amount_c}.\n"
    "Ngày hẹn giao xe: {handover_date}.\n"
    "Anh/chị nhớ gọi xác nhận với khách trước ngày giao nhé ạ."
)

HANDOVER_FAILED = (
    "Em chốt hồ sơ không thành công do lỗi hệ thống ạ. "
    "Anh/chị thao tác trực tiếp trên form giúp em nhé."
)
