import { useEffect, useRef } from 'react';

import { begin_cursor_run, end_cursor_run } from './cursorBusy';
import { next_frame, sleep, wait_for_element } from './useAgentCursor';

const TYPE_DELAY_MS = 45;

// Phải lớn hơn `await asyncio.sleep(0.7)` giữa hai vòng `fill` ở backend.
const IDLE_GRACE_MS = 1000;

/**
 * Nhận từng `current_action` stream về từ backend và diễn lại bằng con trỏ ảo.
 *
 * Backend đẩy action rời rạc (mỗi vòng `fill` một cái) nên hook này phải:
 *  1. Gom vào MỘT hàng đợi FIFO với DUY NHẤT một worker — hai worker song song
 *     sẽ giành con trỏ và điền chồng lên nhau.
 *  2. Chống trùng bằng chữ ký `run_seq:type:field:value`, vì cùng một state-delta
 *     có thể tới nhiều lần khi CopilotKit re-render.
 *  3. Reset hàng đợi khi `run_seq` đổi — BẪY #4: nhờ run_seq nằm trong chữ ký,
 *     lượt sửa mới không bị bộ lọc chống trùng của lượt trước nuốt mất.
 *  4. Dùng `generation_ref` để worker cũ tự dừng khi unmount / StrictMode
 *     mount hai lần, thay vì tiếp tục điền vào DOM đã tháo.
 */
export function useAgentActionRunner({
  current_action,
  controls,
  set_form_data,
  ward_select_ref,
  on_ward_needs_user,
  on_queue_idle,
}) {
  const queue_ref = useRef([]);
  const seen_ref = useRef(new Set());
  const running_ref = useRef(false);
  const run_seq_ref = useRef(null);
  const generation_ref = useRef(0);

  // Callback từ App có thể đổi tham chiếu mỗi render; đọc qua ref để không phải
  // đưa chúng vào deps của effect (đưa vào là tự tay tái tạo đúng BẪY #3).
  const callbacks_ref = useRef({});
  callbacks_ref.current = {
    set_form_data,
    ward_select_ref,
    on_ward_needs_user,
    on_queue_idle,
  };

  useEffect(() => {
    generation_ref.current += 1;
    const generation = generation_ref.current;
    return () => {
      // Bump generation: worker đang chạy sẽ thấy lệch và tự thoát.
      if (generation_ref.current === generation) generation_ref.current += 1;
    };
  }, []);

  useEffect(() => {
    if (!current_action || !current_action.field) return;

    const { run_seq, type, field, value } = current_action;
    const signature = `${run_seq ?? 0}:${type}:${field}:${value ?? ''}`;

    if (run_seq_ref.current !== run_seq) {
      run_seq_ref.current = run_seq;
      queue_ref.current = [];
      seen_ref.current = new Set();
    }

    if (seen_ref.current.has(signature)) return;
    seen_ref.current.add(signature);
    queue_ref.current.push(current_action);

    if (running_ref.current) return;
    running_ref.current = true;

    // Bật cờ để thẻ HITL biết form còn đang được điền dở. Backend tính xong và
    // bắn `interrupt` gần như tức thì, còn con trỏ là bản phát lại chậm hơn
    // nhiều — không có cờ này thì nút "Khách đồng ý giá" bấm được lúc form mới
    // có đúng một ô.
    begin_cursor_run();

    const generation = generation_ref.current;

    (async () => {
      try {
        for (;;) {
          while (queue_ref.current.length > 0) {
            if (generation_ref.current !== generation) return;
            const action = queue_ref.current.shift();
            await run_action(action, controls, callbacks_ref.current, generation, generation_ref);
          }

          // Hàng đợi cạn chưa chắc là xong: backend nghỉ 0.7s giữa hai vòng
          // `fill`. Chờ một nhịp dài hơn khoảng nghỉ đó rồi mới kết luận, nếu
          // không con trỏ sẽ tắt/hiện nhấp nháy giữa từng ô.
          await sleep(IDLE_GRACE_MS);
          if (generation_ref.current !== generation) return;
          if (queue_ref.current.length === 0) break;
        }
      } finally {
        running_ref.current = false;
        // Phải hạ cờ KỂ CẢ khi worker thoát sớm vì lệch generation (unmount,
        // StrictMode) — bỏ sót một lần là thẻ duyệt khoá vĩnh viễn.
        end_cursor_run();
        if (generation_ref.current === generation) {
          controls.hide();
          callbacks_ref.current.on_queue_idle?.();
        }
      }
    })();
  }, [current_action, controls]);
}

async function run_action(action, controls, callbacks, generation, generation_ref) {
  const { type, field, label, selector, value } = action;
  const alive = () => generation_ref.current === generation;

  if (type === 'pick_ward') {
    await run_pick_ward(action, controls, callbacks, alive);
    return;
  }

  const element = await wait_for_element(selector);
  if (!element || !alive()) return;

  await controls.move_to(element, label);
  if (!alive()) return;
  await controls.click(element);
  if (!alive()) return;

  if (type === 'type') {
    // Gõ dần từng ký tự để nhìn như người thật đang nhập.
    const text = String(value ?? '');
    for (let index = 1; index <= text.length; index += 1) {
      if (!alive()) return;
      callbacks.set_form_data?.(field, text.slice(0, index));
      await sleep(TYPE_DELAY_MS);
    }
    return;
  }

  // type === 'select': dropdown native không mở được bằng JS, nên thay vì để
  // giá trị nhảy đánh cụp một cái, diễn hoạt hai nhịp cho người xem kịp bắt
  // được ô nào vừa đổi — giữ con trỏ tại ô một nhịp ("đang mở"), đổi giá trị,
  // rồi nhấn thêm một nhịp nữa ("đã chọn").
  await sleep(220);
  if (!alive()) return;

  callbacks.set_form_data?.(field, String(value ?? ''));
  if (!alive()) return;

  await controls.click(element);
  await sleep(150);
}

async function run_pick_ward(action, controls, callbacks, alive) {
  const { label, value } = action;
  const ward_name = String(value ?? '');
  const ward_select = callbacks.ward_select_ref?.current;

  if (!ward_select) {
    callbacks.set_form_data?.('ward', ward_name);
    return;
  }

  ward_select.open();

  const search_input = await wait_for_element('[data-agent-ward-search]');
  if (!search_input || !alive()) return;

  await controls.move_to(search_input, label || 'Phường/Xã');
  if (!alive()) return;
  await controls.click(search_input);

  for (let index = 1; index <= ward_name.length; index += 1) {
    if (!alive()) return;
    ward_select.search(ward_name.slice(0, index));
    await sleep(TYPE_DELAY_MS);
  }

  await next_frame();
  if (!alive()) return;

  const filtered = ward_select.get_filtered();

  // KHÔNG click bừa: khác đúng 1 kết quả thì nhờ khách tự chọn.
  // Gõ "Phú" ra 3 phường — chọn hộ là chọn sai.
  if (filtered.length !== 1) {
    ward_select.close();
    callbacks.on_ward_needs_user?.(ward_name, filtered);
    return;
  }

  const match = filtered[0];
  // Giá trị nằm trong dấu nháy nên chỉ cần escape dấu nháy; tên phường không có.
  const option = document.querySelector(
    `[data-agent-ward-option="${match.replace(/"/g, '\\"')}"]`,
  );

  if (option && alive()) {
    await controls.move_to(option, match);
    if (!alive()) return;
    await controls.click(option);
  }

  ward_select.pick(match);
  await sleep(200);
}

export default useAgentActionRunner;
