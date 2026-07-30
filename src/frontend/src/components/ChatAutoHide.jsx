import { useChatContext } from '@copilotkit/react-ui';
import { useEffect, useRef } from 'react';

/**
 * Thu gọn khung chat khi agent đang điền form, mở lại khi xong.
 *
 * Phải là CON của <CopilotPopup> để `useChatContext()` có provider.
 *
 * LUÔN mở lại khi xong — không được để đóng: thẻ xác nhận
 * (confirm_details / confirm_submit) render BÊN TRONG khung chat, chat đóng thì
 * khách không có gì để bấm và graph đứng vĩnh viễn ở `interrupt()`.
 */
export default function ChatAutoHide({ collapse }) {
  const { setOpen } = useChatContext();
  const has_collapsed_ref = useRef(false);

  useEffect(() => {
    if (collapse) {
      has_collapsed_ref.current = true;
      setOpen(false);
      return;
    }

    // Chỉ mở lại nếu CHÍNH hook này đã thu gọn trước đó — tránh việc tự bật chat
    // lên ngay lúc tải trang.
    if (has_collapsed_ref.current) {
      has_collapsed_ref.current = false;
      setOpen(true);
    }
  }, [collapse, setOpen]);

  return null;
}
