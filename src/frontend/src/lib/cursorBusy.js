import { useSyncExternalStore } from 'react';

/**
 * Cờ "con trỏ ảo đang điền dở" dùng chung, đặt NGOÀI React.
 *
 * Vì sao không phải state/prop: thẻ HITL được `useLangGraphInterrupt` render bên
 * trong cây của CopilotChat, không phải cây của `<AppraisalBoard>`. Truyền prop
 * xuống thì thẻ chỉ nhận giá trị mới khi khung chat tình cờ render lại — đúng
 * lúc cần khoá nút thì nó vẫn đang giữ giá trị cũ. Store ngoài + subscribe thì
 * thẻ luôn tự cập nhật.
 *
 * Dùng bộ đếm chứ không phải boolean: hai màn hình cùng có runner (trang khách
 * và cổng nhân viên), đóng cái này không được phép mở khoá cho cái kia.
 */
let active = 0;
const listeners = new Set();

const emit = () => listeners.forEach((listener) => listener());

export function begin_cursor_run() {
  active += 1;
  if (active === 1) emit();
}

export function end_cursor_run() {
  if (active === 0) return;
  active -= 1;
  if (active === 0) emit();
}

export function get_cursor_busy() {
  return active > 0;
}

function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useCursorBusy() {
  return useSyncExternalStore(subscribe, get_cursor_busy, get_cursor_busy);
}

export default useCursorBusy;
