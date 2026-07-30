"""Giọng của agent CRM: nói với NHÂN VIÊN KINH DOANH về một khách thứ ba.

Khác biệt cốt lõi so với `test_drive/copy.py`: "anh/chị" ở đây là sales đang ngồi
trước máy, còn người đi lái thử được gọi là "khách". Không bao giờ hứa hẹn thay
khách, không nói "mã đăng ký của anh/chị".
"""

from ..shared.copy import CopyPack

COPY = CopyPack(
    greeting=(
        "Anh/chị đọc thông tin khách giúp em: họ tên, số điện thoại, mẫu xe, "
        "ngày giờ hẹn và phường/xã ở Hà Nội ạ."
    ),
    extract_failed=(
        "Hệ thống đang nghẽn khi xử lý tin nhắn nên em chưa bóc được thông tin ạ. "
        "Anh/chị nhắn lại giúp em, hoặc nhập tay trực tiếp trên form bên cạnh."
    ),
    ask_missing="Em cần thêm {need} của khách ạ.",
    plan_full="Em điền vào form bên cạnh nhé, anh/chị theo dõi con trỏ giúp em ạ.",
    plan_correction="Em cập nhật lại phần anh/chị vừa sửa ạ.",
    summary_header="Em đã điền xong, anh/chị đối chiếu lại với khách giúp em ạ:",
    summary_footer=(
        "Thông tin trên đã khớp với khách chưa ạ? Cần sửa thì anh/chị nhắn em phần cần đổi."
    ),
    ask_submit=(
        "Thông tin đã khớp ạ. Anh/chị có muốn em tạo đăng ký cho khách luôn không, "
        "hay anh/chị tự bấm nút tạo trên form ạ?"
    ),
    patch_applied="Em sửa lại {labels} ạ.",
    patch_unclear=(
        "Em chưa rõ anh/chị muốn sửa phần nào ạ. Anh/chị nhắn cụ thể giúp em, "
        'ví dụ "đổi giờ thành 15:00" hoặc "đổi xe sang VF 9" nhé.'
    ),
    patch_exhausted=(
        "Em đã sửa {rounds} lần mà vẫn chưa khớp ý anh/chị ạ. "
        "Anh/chị nhập tay nốt phần còn lại trên form giúp em nhé."
    ),
    submit_invalid=(
        "Thông tin chưa hợp lệ nên em chưa tạo được đăng ký ạ: "
        "{error}. Anh/chị kiểm tra lại giúp em nhé."
    ),
    submit_failed=(
        "Em tạo đăng ký không thành công do lỗi hệ thống ạ. "
        "Anh/chị bấm nút tạo trên form để thử lại giúp em nhé."
    ),
    manual_ready=(
        "Vâng, em giữ nguyên thông tin đã điền trên form ạ. "
        'Anh/chị kiểm tra lần cuối rồi bấm "Tạo khách hàng" giúp em nhé.'
    ),
    report=(
        "Em đã tạo đăng ký cho khách thành công ạ! Mã đăng ký: {code}.\n"
        "Lịch hẹn: {date} lúc {time}, mẫu xe {vehicle} tại {ward}, Hà Nội.\n"
        "Anh/chị đọc mã {code} cho khách và nhớ gọi xác nhận trước buổi hẹn nhé."
    ),
    duplicate_phone=(
        "Số điện thoại này đã có trong hệ thống với mã {code} ({name}). "
        "Anh/chị kiểm tra lại — nếu đúng là khách khác, sửa lại số điện thoại giúp em."
    ),
    duplicate_name_warning=(
        "⚠ Lưu ý: đã có khách trùng tên (mã {code}), khác số điện thoại — vẫn tạo mới được."
    ),
)
