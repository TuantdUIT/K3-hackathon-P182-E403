import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// Double requestAnimationFrame: đợi React commit xong VÀ browser layout xong.
export const next_frame = () =>
  new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));

const one_frame = () => new Promise((resolve) => requestAnimationFrame(resolve));

/**
 * Đợi `scrollIntoView({behavior:'smooth'})` thật sự dừng.
 *
 * Không dùng sự kiện `scrollend` vì phần tử có thể nằm trong container cuộn
 * riêng (cột giữa của trang định giá) và Safari chưa hỗ trợ. Cách chắc chắn
 * hơn: nhìn chính cái ta cần — toạ độ của phần tử — và coi là xong khi nó đứng
 * yên vài khung hình liên tiếp.
 */
async function wait_for_scroll_settled(element, timeout = 700) {
  const deadline = performance.now() + timeout;
  let previous = null;
  let stable = 0;

  while (performance.now() < deadline) {
    await one_frame();
    const { top } = element.getBoundingClientRect();

    if (previous !== null && Math.abs(top - previous) < 0.5) {
      stable += 1;
      if (stable >= 3) return;
    } else {
      stable = 0;
    }
    previous = top;
  }
}

// Ô có gõ được không. Trước đây chỉ kiểm `tagName === 'INPUT'`, nên ô ngày và
// checkbox cũng bị gắn icon "đang gõ" dù chẳng có ký tự nào chạy ra.
const NON_TYPING_INPUT_TYPES = new Set([
  'button',
  'checkbox',
  'color',
  'date',
  'datetime-local',
  'file',
  'image',
  'month',
  'radio',
  'range',
  'reset',
  'submit',
  'time',
  'week',
]);

function is_typing_target(element) {
  if (element.isContentEditable) return true;
  if (element.tagName === 'TEXTAREA') return true;
  if (element.tagName !== 'INPUT') return false;
  return !NON_TYPING_INPUT_TYPES.has((element.type || 'text').toLowerCase());
}

// Con trỏ đứng ở mép trái ô (lệch vào trong tối đa 120px) và giữa theo chiều dọc.
function anchor_of(element) {
  const rect = element.getBoundingClientRect();
  return {
    x: rect.left + Math.min(rect.width * 0.5, 120),
    y: rect.top + rect.height * 0.5,
  };
}

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
  // `snap` = đặt lại vị trí NGAY, không nội suy. Dùng khi trang cuộn dưới chân
  // con trỏ: lúc đó nó phải dính lấy ô, chứ bay 500ms theo thì nhìn như trôi.
  snap: false,
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

  // Ô con trỏ đang đứng trên. Cần giữ lại để bám theo khi trang cuộn tiếp.
  const target_ref = useRef(null);

  /**
   * Dán con trỏ trở lại đúng ô đang giữ.
   *
   * Toạ độ của con trỏ là toạ độ VIEWPORT (overlay `fixed`), nên mọi cú cuộn —
   * của người dùng hay của `scrollIntoView` ở bước sau — đều làm ô trôi đi
   * trong khi con trỏ đứng nguyên giữa màn hình. Phải đo lại mỗi lần cuộn.
   */
  const sync_to_target = useCallback(() => {
    const element = target_ref.current;
    if (!element || !element.isConnected) return;

    const { x, y } = anchor_of(element);
    position_ref.current = { x, y };

    set_cursor((previous) => {
      if (!previous.visible) return previous;
      if (previous.x === x && previous.y === y) return previous;
      return { ...previous, x, y, snap: true };
    });
  }, []);

  useEffect(() => {
    let frame = 0;
    const handler = () => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        sync_to_target();
      });
    };

    // `capture: true` để bắt cả cuộn bên trong container con, không chỉ window.
    window.addEventListener('scroll', handler, { capture: true, passive: true });
    window.addEventListener('resize', handler, { passive: true });

    return () => {
      if (frame) cancelAnimationFrame(frame);
      window.removeEventListener('scroll', handler, { capture: true });
      window.removeEventListener('resize', handler);
    };
  }, [sync_to_target]);

  const move_to = useCallback(async (element, label = '') => {
    if (!element) return;

    // Ô đã nằm trong vùng dễ nhìn thì đừng cuộn: cuộn thừa vừa mất thời gian
    // vừa giật màn hình của người đang theo dõi.
    const start = element.getBoundingClientRect();
    const margin = window.innerHeight * 0.15;

    if (start.top < margin || start.bottom > window.innerHeight - margin) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      // Trước đây chỗ này chỉ `await next_frame()` (~32ms) rồi đo ngay, trong
      // khi cuộn mượt còn chạy 300-500ms nữa. Toạ độ đo được là của khung hình
      // cũ, nên con trỏ dừng lệch hẳn xuống dưới ô — đo thực tế 28-138px, ô
      // càng xa lệch càng nhiều.
      await wait_for_scroll_settled(element);
    }

    target_ref.current = element;

    const { x, y } = anchor_of(element);
    position_ref.current = { x, y };

    set_cursor((previous) => ({
      ...previous,
      visible: true,
      x,
      y,
      label,
      typing: is_typing_target(element),
      clicking: false,
      snap: false,
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
    target_ref.current = null;
    set_cursor((previous) => ({
      ...previous,
      visible: false,
      label: '',
      clicking: false,
      snap: false,
    }));
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
