import { useCallback, useMemo, useRef, useState } from 'react';

export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// Double requestAnimationFrame: đợi React commit xong VÀ browser layout xong.
export const next_frame = () =>
  new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));

/**
 * Chờ một phần tử xuất hiện trong DOM, poll theo frame.
 * Cần thiết vì modal được mở bằng setState — khi action đầu tiên từ backend tới
 * thì <TestDriveModal> chưa chắc đã render, querySelector sẽ trả null.
 */
export async function wait_for_element(selector, timeout = 4000) {
  const deadline = performance.now() + timeout;
  while (performance.now() < deadline) {
    const element = document.querySelector(selector);
    if (element) return element;
    await next_frame();
  }
  return null;
}

const initial_cursor = {
  visible: false,
  x: 0,
  y: 0,
  label: '',
  clicking: false,
  typing: false,
};

/**
 * Điều khiển con trỏ ảo.
 *
 * BẪY #3 — `controls` PHẢI được bọc `useMemo` để giữ nguyên tham chiếu qua mọi
 * render. Nếu trả về object literal mới mỗi lần render, effect trong
 * useAgentActionRunner (có `controls` trong deps) sẽ chạy lại giữa lúc animation
 * đang dở, huỷ worker đang chạy và tạo worker mới -> con trỏ di chuyển được
 * nhưng không bao giờ điền xong ô nào.
 */
export function useAgentCursor() {
  const [cursor, set_cursor] = useState(initial_cursor);

  // Giữ vị trí hiện tại ngoài state để move_to không cần đọc state cũ.
  const position_ref = useRef({ x: 0, y: 0 });

  const move_to = useCallback(async (element, label = '') => {
    if (!element) return;

    element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    await next_frame();

    const rect = element.getBoundingClientRect();
    const x = rect.left + Math.min(rect.width * 0.5, 120);
    const y = rect.top + rect.height * 0.5;
    position_ref.current = { x, y };

    const is_text_input =
      element.tagName === 'INPUT' || element.tagName === 'TEXTAREA' || element.isContentEditable;

    set_cursor((previous) => ({
      ...previous,
      visible: true,
      x,
      y,
      label,
      typing: is_text_input,
      clicking: false,
    }));

    // Khớp với transition 500ms của lớp overlay: đợi con trỏ bay tới đích thật
    // rồi mới cho phép hành động tiếp theo.
    await sleep(500);
  }, []);

  const click = useCallback(async (element) => {
    set_cursor((previous) => ({ ...previous, clicking: true }));

    if (element && typeof element.focus === 'function') {
      // focus() thật để caret nhấp nháy trong ô — nhìn giống người đang gõ.
      element.focus({ preventScroll: true });
    }

    await sleep(200);
    set_cursor((previous) => ({ ...previous, clicking: false }));
  }, []);

  const hide = useCallback(() => {
    set_cursor((previous) => ({ ...previous, visible: false, label: '', clicking: false }));
  }, []);

  const set_label = useCallback((label) => {
    set_cursor((previous) => ({ ...previous, label }));
  }, []);

  const controls = useMemo(
    () => ({ move_to, click, hide, set_label }),
    [move_to, click, hide, set_label],
  );

  return { cursor, controls };
}

export default useAgentCursor;
