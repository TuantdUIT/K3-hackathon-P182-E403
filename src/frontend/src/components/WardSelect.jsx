import { Check, ChevronDown, Search } from 'lucide-react';
import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react';

import { hanoi_wards } from '../data/hanoi_wards.js';

// Bỏ dấu để khách gõ "cau giay" vẫn ra "Cầu Giấy".
const strip_accents = (text) =>
  String(text ?? '')
    .toLowerCase()
    .replace(/đ/g, 'd')
    .normalize('NFD')
    // Dùng escape thay vì dán trực tiếp dấu tổ hợp — an toàn qua mọi editor/encoding.
    .replace(/[\u0300-\u036f]/g, '')
    .trim();

const filter_wards = (keyword) => {
  const needle = strip_accents(keyword);
  if (!needle) return hanoi_wards;
  return hanoi_wards.filter((ward) => strip_accents(ward).includes(needle));
};

/**
 * Dropdown phường/xã có ô tìm kiếm.
 *
 * Expose imperative ref `{open, close, search, get_filtered, pick}` để
 * `useAgentActionRunner` diễn lại đúng chuỗi hành động của người thật:
 * mở dropdown → gõ dần vào ô search → đếm kết quả → chỉ click khi còn đúng 1.
 *
 * Mọi thứ trong handle đọc qua ref, và deps của `useImperativeHandle` là `[]`:
 * runner lấy `ref.current` MỘT LẦN đầu chuỗi hành động rồi mới gõ, nên nếu handle
 * đóng gói `keyword` từ state thì `get_filtered()` sẽ đếm trên keyword cũ.
 */
const WardSelect = forwardRef(function WardSelect(
  { value, on_change, notice, on_clear_notice, required = true },
  ref,
) {
  const [open, set_open] = useState(false);
  const [keyword, set_keyword] = useState('');
  const container_ref = useRef(null);

  const keyword_ref = useRef('');
  const on_change_ref = useRef(on_change);
  const on_clear_notice_ref = useRef(on_clear_notice);
  on_change_ref.current = on_change;
  on_clear_notice_ref.current = on_clear_notice;

  const update_keyword = (text) => {
    keyword_ref.current = text;
    set_keyword(text);
  };

  const filtered = useMemo(() => filter_wards(keyword), [keyword]);

  useImperativeHandle(ref, () => {
    const commit = (ward) => {
      on_change_ref.current?.(ward);
      set_open(false);
      update_keyword('');
      on_clear_notice_ref.current?.();
    };

    return {
      open: () => set_open(true),
      close: () => {
        set_open(false);
        update_keyword('');
      },
      search: (text) => {
        set_open(true);
        update_keyword(text);
      },
      get_filtered: () => filter_wards(keyword_ref.current),
      pick: commit,
    };
  }, []);

  // Click ra ngoài thì đóng.
  useEffect(() => {
    if (!open) return undefined;
    const on_document_click = (event) => {
      if (container_ref.current && !container_ref.current.contains(event.target)) {
        set_open(false);
      }
    };
    document.addEventListener('mousedown', on_document_click);
    return () => document.removeEventListener('mousedown', on_document_click);
  }, [open]);

  const select_ward = (ward) => {
    on_change?.(ward);
    set_open(false);
    update_keyword('');
    on_clear_notice?.();
  };

  return (
    <div className="relative" ref={container_ref}>
      <button
        type="button"
        data-agent-field="ward"
        onClick={() => set_open((previous) => !previous)}
        className={`field-input flex items-center justify-between text-left ${
          value ? 'text-ink-900' : 'text-slate-400'
        }`}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span>{value || 'Chọn phường/xã'}</span>
        <ChevronDown className={`h-4 w-4 shrink-0 transition ${open ? 'rotate-180' : ''}`} />
      </button>

      {/* Input ẩn để form vẫn validate `required` như một ô bình thường. */}
      {required && (
        <input
          tabIndex={-1}
          aria-hidden="true"
          required
          value={value ?? ''}
          onChange={() => {}}
          className="pointer-events-none absolute bottom-2 left-3 h-0 w-0 opacity-0"
        />
      )}

      {notice && <p className="mt-1.5 text-xs font-medium text-amber-600">{notice}</p>}

      {open && (
        <div className="absolute z-50 mt-1.5 w-full overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lift">
          <div className="flex items-center gap-2 border-b border-slate-100 px-3 py-2">
            <Search className="h-4 w-4 shrink-0 text-slate-400" />
            <input
              data-agent-ward-search
              autoComplete="off"
              className="w-full bg-transparent text-sm outline-none"
              placeholder="Tìm phường/xã..."
              value={keyword}
              onChange={(event) => update_keyword(event.target.value)}
            />
          </div>

          <ul role="listbox" className="max-h-56 overflow-y-auto py-1">
            {filtered.length === 0 && (
              <li className="px-3 py-2 text-sm text-slate-400">
                Không tìm thấy phường/xã phù hợp.
              </li>
            )}
            {filtered.map((ward) => (
              <li key={ward}>
                <button
                  type="button"
                  data-agent-ward-option={ward}
                  role="option"
                  aria-selected={value === ward}
                  onClick={() => select_ward(ward)}
                  className={`flex w-full items-center justify-between px-3 py-2 text-left text-sm transition hover:bg-brand-50 ${
                    value === ward ? 'font-semibold text-brand-700' : 'text-slate-700'
                  }`}
                >
                  {ward}
                  {value === ward && <Check className="h-4 w-4" />}
                </button>
              </li>
            ))}
          </ul>

          <div className="border-t border-slate-100 px-3 py-1.5 text-xs text-slate-400">
            {filtered.length}/{hanoi_wards.length} phường/xã
          </div>
        </div>
      )}
    </div>
  );
});

export default WardSelect;
