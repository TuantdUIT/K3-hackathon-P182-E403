import { useEffect, useSyncExternalStore } from 'react';

/**
 * Cờ "đang có thẻ HITL chờ trả lời", đặt NGOÀI React — cùng khuôn với
 * `cursorBusy.js` và vì cùng một lý do: thẻ nằm trong cây của CopilotChat, còn
 * chỗ cần biết (khung chat ở `AppraisalBoard`) nằm ở cây khác.
 *
 * Vì sao cần: lúc graph dừng ở `interrupt()`, CHỈ ô nhập trong thẻ mới đưa được
 * dữ liệu vào graph — nó gọi `resolve()`. Ô chat chính vẫn hiện, vẫn gõ được,
 * vẫn hiển thị tin nhắn như đã gửi xong, nhưng tin đó rơi vào hư không cho tới
 * khi thẻ được trả lời. Đã đo được một lần mất tin nhắn 87 giây không phản hồi.
 * Có cờ này thì khoá hẳn ô chat lại và nói cho sales biết phải trả lời ở đâu.
 */
let pending = 0;
const listeners = new Set();

const emit = () => listeners.forEach((listener) => listener());

function open_gate() {
  pending += 1;
  if (pending === 1) emit();
}

function close_gate() {
  if (pending === 0) return;
  pending -= 1;
  if (pending === 0) emit();
}

function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function get_interrupt_pending() {
  return pending > 0;
}

/**
 * Gọi trong từng thẻ HITL. `pending` phải là "thẻ này CHƯA được trả lời" —
 * thẻ đã bấm xong vẫn còn hiển thị (ở trạng thái mờ), giữ cờ theo vòng đời
 * component sẽ khoá ô chat vĩnh viễn.
 */
export function useInterruptGate(is_pending) {
  useEffect(() => {
    if (!is_pending) return undefined;
    open_gate();
    return close_gate;
  }, [is_pending]);
}

export function useInterruptPending() {
  return useSyncExternalStore(subscribe, get_interrupt_pending, get_interrupt_pending);
}

export default useInterruptPending;
