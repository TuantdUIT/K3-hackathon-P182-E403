"""Giọng của agent lái thử: nói TRỰC TIẾP với khách trên trang showcase."""

from ..shared.copy import CopyPack

COPY = CopyPack(
    greeting="Chào anh/chị! Anh/chị muốn lái thử mẫu xe nào, vào ngày giờ nào ạ?",
    extract_failed=(
        "Xin lỗi, hệ thống đang bị nghẽn khi xử lý tin nhắn. "
        "Anh/chị nhắn lại giúp em, hoặc gọi hotline {hotline} ạ."
    ),
    ask_missing="Anh/chị cho em xin thêm {need} nhé.",
    plan_full="Em mở form và điền hộ anh/chị nhé, anh/chị theo dõi con trỏ trên màn hình ạ.",
    plan_correction="Em cập nhật lại thông tin anh/chị vừa sửa ạ.",
    summary_header="Em đã điền xong, anh/chị kiểm tra lại giúp em ạ:",
    summary_footer=(
        "Thông tin trên đã đúng chưa ạ? Nếu cần sửa, anh/chị nhắn em phần cần đổi nhé."
    ),
    ask_submit=(
        "Thông tin đã chính xác ạ. Anh/chị có muốn em gửi đăng ký này luôn không, "
        "hay anh/chị tự bấm nút gửi trên form ạ?"
    ),
    patch_applied="Em sửa lại {labels} ạ.",
    patch_unclear=(
        "Em chưa rõ anh/chị muốn sửa phần nào ạ. Anh/chị nhắn cụ thể giúp em, "
        'ví dụ "đổi giờ thành 15:00" hoặc "đổi xe sang VF 9" nhé.'
    ),
    patch_exhausted=(
        "Em đã sửa {rounds} lần mà vẫn chưa khớp ý anh/chị, xin lỗi anh/chị ạ. "
        "Anh/chị gọi hotline {hotline} để nhân viên hỗ trợ trực tiếp giúp em nhé."
    ),
    submit_invalid=(
        "Thông tin chưa hợp lệ nên em chưa gửi được đăng ký ạ: "
        "{error}. Anh/chị kiểm tra lại giúp em nhé."
    ),
    submit_failed=(
        "Em gửi đăng ký không thành công do lỗi hệ thống ạ. "
        "Anh/chị bấm nút gửi trên form hoặc gọi hotline {hotline} giúp em nhé."
    ),
    manual_ready=(
        "Vâng, em giữ nguyên thông tin đã điền trên form ạ. "
        'Anh/chị kiểm tra lần cuối rồi bấm "Đăng ký lái thử" giúp em nhé.'
    ),
    report=(
        "Em đã gửi đăng ký thành công ạ! Mã đăng ký của anh/chị là {code}.\n"
        "Lịch hẹn: {date} lúc {time}, mẫu xe {vehicle} tại {ward}, Hà Nội.\n"
        "Nhân viên kinh doanh sẽ gọi xác nhận trước buổi hẹn. "
        "Cần đổi lịch, anh/chị gọi hotline {hotline} ạ."
    ),
    duplicate_phone=(
        "Số điện thoại {phone} đã có đăng ký trong hệ thống (mã {code}). "
        "Anh/chị kiểm tra lại giúp em, hoặc gọi hotline {hotline} để được hỗ trợ ạ."
    ),
    duplicate_name_warning="",
)
