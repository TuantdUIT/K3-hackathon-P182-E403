import { CopilotChat } from '@copilotkit/react-ui';
import { AnimatePresence, motion } from 'framer-motion';
import { AlertTriangle, Bot, CheckCircle2, Loader2, UserCheck, X } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import { vehicles } from '../data/vehicles.js';
import { check_duplicate, create_test_drive } from '../lib/api.js';
import { format_date_long, today_iso } from '../lib/formatDate.js';
import WardSelect from './WardSelect.jsx';

const time_slots = ['08:00', '09:30', '11:00', '13:30', '15:00', '16:30'];
const sources = ['Showroom', 'Facebook', 'Zalo', 'Website'];
const DUPLICATE_DEBOUNCE_MS = 400;

/**
 * Form sales tạo lead hộ khách, có agent CRM điền bằng con trỏ ảo.
 *
 * State form nằm ở `Dashboard` (component cha) chứ không ở đây: agent điền xong
 * mà modal unmount là mất sạch dữ liệu.
 *
 * `awaiting` khác rỗng = graph đang đứng ở `interrupt()` chờ trả lời thẻ xác nhận.
 * Lúc đó KHÔNG cho đóng modal, vì thẻ nằm trong khung chat bên phải — đóng đi là
 * graph treo vĩnh viễn, sales phải F5.
 */
export default function AddCustomerModal({
  open,
  on_close,
  form_data,
  set_form_data,
  selected_vehicle_id,
  source,
  set_source,
  ward_notice,
  set_ward_notice,
  ward_select_ref,
  agent_submission_code,
  awaiting,
  filling,
  run_seq,
  run_kind,
  on_reset,
  on_created,
  find_customer_by_code,
}) {
  const [submitting, set_submitting] = useState(false);
  const [error_message, set_error_message] = useState('');
  const [created_customer, set_created_customer] = useState(null);
  const [phone_match, set_phone_match] = useState(null);
  const [name_matches, set_name_matches] = useState([]);
  const last_run_seq_ref = useRef(null);

  const vehicle = vehicles.find((item) => item.id === selected_vehicle_id) ?? vehicles[0];

  // Agent tạo hộ -> chuyển sang màn thành công y hệt khi sales tự bấm. NVKD phụ
  // trách lấy từ bảng đã tải lại (agent state chỉ mang về mã đăng ký).
  useEffect(() => {
    if (!agent_submission_code) return;
    let cancelled = false;
    (async () => {
      const customer = await find_customer_by_code?.(agent_submission_code);
      if (!cancelled) set_created_customer(customer ?? { code: agent_submission_code });
    })();
    return () => {
      cancelled = true;
    };
  }, [agent_submission_code, find_customer_by_code]);

  // Lượt mới dạng "full" = khách khác -> mở lại form trắng, để một phiên chat
  // phục vụ được nhiều khách liên tiếp mà không kẹt ở màn "đã tạo".
  useEffect(() => {
    if (run_seq === null || run_seq === undefined) return;
    if (run_seq === last_run_seq_ref.current) return;
    last_run_seq_ref.current = run_seq;
    if (run_kind === 'full') {
      set_created_customer(null);
      set_error_message('');
    }
  }, [run_seq, run_kind]);

  // Tra trùng khi SĐT đủ dài hoặc tên đủ 2 ký tự. Debounce để không bắn request
  // mỗi lần con trỏ ảo gõ thêm một ký tự.
  useEffect(() => {
    const phone_digits = String(form_data.phone ?? '').replace(/\D/g, '');
    const name = String(form_data.name ?? '').trim();
    const check_phone = phone_digits.length >= 10;
    const check_name = name.length >= 2;

    if (!check_phone && !check_name) {
      set_phone_match(null);
      set_name_matches([]);
      return undefined;
    }

    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const result = await check_duplicate({
          phone: check_phone ? phone_digits : '',
          name: check_name ? name : '',
        });
        if (cancelled) return;
        set_phone_match(check_phone ? (result.phone_match ?? null) : null);
        set_name_matches(check_name ? (result.name_matches ?? []) : []);
      } catch {
        // Tra trùng lỗi thì không chặn sales nhập — chốt chặn cứng vẫn ở backend.
        if (!cancelled) {
          set_phone_match(null);
          set_name_matches([]);
        }
      }
    }, DUPLICATE_DEBOUNCE_MS);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [form_data.phone, form_data.name]);

  useEffect(() => {
    if (!open) return undefined;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);

  const update = (field) => (event) => set_form_data(field, event.target.value);

  const reset_all = useCallback(() => {
    set_created_customer(null);
    set_error_message('');
    set_phone_match(null);
    set_name_matches([]);
    on_reset?.();
  }, [on_reset]);

  const on_submit = async (event) => {
    event.preventDefault();
    set_error_message('');
    set_submitting(true);

    try {
      const created = await create_test_drive({
        name: form_data.name,
        phone: form_data.phone,
        email: form_data.email || null,
        vehicle_id: vehicle.id,
        model: vehicle.name,
        test_drive_date: form_data.test_drive_date,
        test_drive_time: form_data.test_drive_time,
        province: 'Hà Nội',
        ward: form_data.ward,
        note: form_data.note || null,
        source,
      });
      set_created_customer(created);
      on_created?.();
    } catch (error) {
      set_error_message(error.message);
    } finally {
      set_submitting(false);
    }
  };

  // Không cho đóng khi graph đang chờ trả lời interrupt (thẻ xác nhận nằm trong
  // khung chat bên phải — đóng đi là graph treo mãi), và cũng không cho đóng giữa
  // lúc con trỏ ảo đang điền dở.
  const locked = Boolean(awaiting) || Boolean(filling);
  const lock_reason = awaiting
    ? 'Hãy trả lời thẻ xác nhận trong khung chat trước'
    : 'Trợ lý đang điền form, chờ một chút ạ';

  const try_close = () => {
    if (locked) return;
    on_close();
    if (created_customer) reset_all();
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[100] flex items-start justify-center overflow-y-auto bg-ink-900/60 p-4 backdrop-blur-sm"
        >
          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ duration: 0.25 }}
            className="relative my-6 w-full max-w-6xl overflow-hidden rounded-3xl bg-white shadow-lift"
          >
            <button
              type="button"
              onClick={try_close}
              disabled={locked}
              title={locked ? lock_reason : 'Đóng'}
              className="absolute right-4 top-4 z-10 grid h-9 w-9 place-items-center rounded-full bg-white/90 text-slate-500 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
              aria-label="Đóng"
            >
              <X className="h-4.5 w-4.5" />
            </button>

            {created_customer ? (
              <SuccessPanel
                customer={created_customer}
                on_add_another={() => reset_all()}
                on_close={try_close}
              />
            ) : (
              <div className="grid lg:grid-cols-[1fr_minmax(0,380px)]">
                <form onSubmit={on_submit} className="p-6 sm:p-8">
                  <h2 className="text-2xl font-bold">Thêm khách hàng</h2>
                  <p className="mt-1.5 text-sm text-slate-500">
                    Dành cho khách gọi điện, đến showroom hoặc nhắn qua Facebook/Zalo. Các ô có
                    dấu <span className="text-rose-500">*</span> là bắt buộc.
                  </p>

                  <div className="mt-6 grid gap-4 sm:grid-cols-2">
                    <div className="sm:col-span-2">
                      <label className="field-label" htmlFor="ac-name">
                        Họ và tên khách <span className="text-rose-500">*</span>
                      </label>
                      <input
                        id="ac-name"
                        data-agent-field="name"
                        className="field-input"
                        required
                        minLength={2}
                        placeholder="Nguyễn Văn A"
                        value={form_data.name}
                        onChange={update('name')}
                      />
                      {name_matches.length > 0 && (
                        <p className="mt-1.5 flex items-start gap-1.5 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-800">
                          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                          <span>
                            Đã có khách trùng tên (
                            {name_matches.map((item) => item.code).join(', ')}) — vẫn có thể tạo
                            mới.
                          </span>
                        </p>
                      )}
                    </div>

                    <div>
                      <label className="field-label" htmlFor="ac-phone">
                        Số điện thoại <span className="text-rose-500">*</span>
                      </label>
                      <input
                        id="ac-phone"
                        data-agent-field="phone"
                        className={`field-input ${
                          phone_match ? 'border-rose-400 ring-2 ring-rose-200' : ''
                        }`}
                        required
                        inputMode="numeric"
                        pattern="[0-9]{10,11}"
                        title="Số điện thoại gồm 10–11 chữ số"
                        placeholder="0912345678"
                        value={form_data.phone}
                        onChange={update('phone')}
                      />
                      {phone_match && (
                        <p className="mt-1.5 text-xs font-medium text-rose-600">
                          Trùng SĐT với khách {phone_match.code} — {phone_match.name}
                        </p>
                      )}
                    </div>

                    <div>
                      <label className="field-label" htmlFor="ac-email">
                        Email <span className="text-slate-400">(không bắt buộc)</span>
                      </label>
                      <input
                        id="ac-email"
                        data-agent-field="email"
                        type="email"
                        className="field-input"
                        placeholder="khach@example.com"
                        value={form_data.email}
                        onChange={update('email')}
                      />
                    </div>

                    <div>
                      <label className="field-label" htmlFor="ac-vehicle">
                        Mẫu xe <span className="text-rose-500">*</span>
                      </label>
                      <select
                        id="ac-vehicle"
                        data-agent-field="vehicle_id"
                        className="field-input"
                        required
                        value={vehicle.id}
                        onChange={(event) => set_form_data('vehicle_id', event.target.value)}
                      >
                        {vehicles.map((item) => (
                          <option key={item.id} value={item.id}>
                            {item.name}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="field-label" htmlFor="ac-source">
                        Nguồn <span className="text-rose-500">*</span>
                      </label>
                      <select
                        id="ac-source"
                        className="field-input"
                        required
                        value={source}
                        onChange={(event) => set_source(event.target.value)}
                      >
                        {sources.map((item) => (
                          <option key={item} value={item}>
                            {item}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="field-label" htmlFor="ac-date">
                        Ngày lái thử <span className="text-rose-500">*</span>
                      </label>
                      <input
                        id="ac-date"
                        data-agent-field="test_drive_date"
                        type="date"
                        className="field-input"
                        required
                        min={today_iso()}
                        value={form_data.test_drive_date}
                        onChange={update('test_drive_date')}
                      />
                    </div>

                    <div>
                      <label className="field-label" htmlFor="ac-time">
                        Giờ lái thử <span className="text-rose-500">*</span>
                      </label>
                      <select
                        id="ac-time"
                        data-agent-field="test_drive_time"
                        className="field-input"
                        required
                        value={form_data.test_drive_time}
                        onChange={update('test_drive_time')}
                      >
                        <option value="">Chọn khung giờ</option>
                        {time_slots.map((slot) => (
                          <option key={slot} value={slot}>
                            {slot}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="field-label" htmlFor="ac-province">
                        Tỉnh/Thành phố
                      </label>
                      <input
                        id="ac-province"
                        className="field-input bg-slate-100 text-slate-500"
                        value="Hà Nội"
                        readOnly
                      />
                    </div>

                    <div>
                      <label className="field-label">
                        Phường/Xã <span className="text-rose-500">*</span>
                      </label>
                      <WardSelect
                        ref={ward_select_ref}
                        value={form_data.ward}
                        on_change={(ward) => set_form_data('ward', ward)}
                        notice={ward_notice}
                        on_clear_notice={() => set_ward_notice('')}
                      />
                    </div>

                    <div className="sm:col-span-2">
                      <label className="field-label" htmlFor="ac-note">
                        Yêu cầu khác
                      </label>
                      <textarea
                        id="ac-note"
                        data-agent-field="note"
                        className="field-input min-h-[80px] resize-y"
                        placeholder="Ví dụ: muốn thử đường dài, cần tư vấn trả góp..."
                        value={form_data.note}
                        onChange={update('note')}
                      />
                    </div>
                  </div>

                  {error_message && (
                    <p className="mt-4 rounded-xl bg-rose-50 px-3.5 py-2.5 text-sm text-rose-700">
                      {error_message}
                    </p>
                  )}

                  <div className="mt-6 flex flex-wrap items-center gap-3">
                    <button
                      type="submit"
                      className="btn-primary px-6 py-3"
                      disabled={submitting || Boolean(phone_match)}
                      title={phone_match ? 'Số điện thoại đã tồn tại trong hệ thống' : undefined}
                    >
                      {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
                      {submitting ? 'Đang tạo...' : 'Tạo khách hàng'}
                    </button>
                    <button
                      type="button"
                      className="btn-ghost"
                      onClick={try_close}
                      disabled={locked}
                    >
                      Huỷ
                    </button>
                  </div>
                </form>

                {/* Chat NHÚNG (không dùng CopilotPopup): sales cần thấy form và chat
                    cùng lúc, và thẻ xác nhận HITL render ngay trong khung này. */}
                <aside className="flex min-h-[560px] flex-col border-t border-slate-200 bg-slate-50 lg:border-l lg:border-t-0">
                  <div className="flex items-center gap-2 border-b border-slate-200 px-5 py-4">
                    <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-600 text-white">
                      <Bot className="h-4 w-4" />
                    </span>
                    <div>
                      <div className="text-sm font-bold">Trợ lý nhập liệu</div>
                      <div className="text-xs text-slate-500">
                        Đọc thông tin khách, em điền hộ
                      </div>
                    </div>
                  </div>

                  <div className="min-h-0 flex-1">
                    <CopilotChat
                      className="h-full"
                      instructions="Bạn là trợ lý nhập liệu cho nhân viên kinh doanh VinFast. Người nhắn tin là NHÂN VIÊN, đang thuật lại thông tin của một khách hàng thứ ba. Luôn trả lời bằng tiếng Việt."
                      labels={{
                        initial:
                          'Anh/chị đọc thông tin khách giúp em là em điền vào form bên cạnh ngay ạ.\n\nVí dụ: "Khách tên Trần Văn A, 0987654321, muốn lái thử VF 8 lúc 9 rưỡi sáng mai ở Hoàn Kiếm".',
                        placeholder: 'Nhập thông tin khách hàng...',
                      }}
                    />
                  </div>
                </aside>
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function SuccessPanel({ customer, on_add_another, on_close }) {
  const vehicle = vehicles.find((item) => item.id === customer.vehicle_id);

  return (
    <div className="px-6 py-14 text-center sm:px-10">
      <span className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-emerald-100 text-emerald-600">
        <CheckCircle2 className="h-8 w-8" />
      </span>

      <h2 className="mt-5 text-2xl font-bold">Đã tạo khách hàng thành công!</h2>
      <p className="mt-2 text-sm text-slate-500">
        Đọc mã đăng ký dưới đây cho khách và nhớ gọi xác nhận trước buổi hẹn.
      </p>

      <div className="mx-auto mt-7 max-w-md rounded-2xl border border-slate-200 bg-slate-50 p-5 text-left">
        <div className="text-xs uppercase tracking-wide text-slate-400">Mã đăng ký</div>
        <div className="text-3xl font-extrabold tracking-tight text-brand-700">
          {customer.code}
        </div>

        <dl className="mt-4 space-y-2 text-sm">
          {customer.name && (
            <div className="flex justify-between gap-4">
              <dt className="text-slate-500">Khách hàng</dt>
              <dd className="text-right font-medium">
                {customer.name}
                {customer.phone ? ` · ${customer.phone}` : ''}
              </dd>
            </div>
          )}
          {(vehicle || customer.model) && (
            <div className="flex justify-between gap-4">
              <dt className="text-slate-500">Mẫu xe</dt>
              <dd className="font-medium">{vehicle?.name ?? customer.model}</dd>
            </div>
          )}
          {customer.test_drive_date && (
            <div className="flex justify-between gap-4">
              <dt className="text-slate-500">Lịch hẹn</dt>
              <dd className="text-right font-medium">
                {format_date_long(customer.test_drive_date)}
                {customer.test_drive_time ? ` · ${customer.test_drive_time}` : ''}
              </dd>
            </div>
          )}
          {customer.ward && (
            <div className="flex justify-between gap-4">
              <dt className="text-slate-500">Địa điểm</dt>
              <dd className="text-right font-medium">{customer.ward}, Hà Nội</dd>
            </div>
          )}
          <div className="flex justify-between gap-4 border-t border-slate-200 pt-2">
            <dt className="text-slate-500">NVKD phụ trách</dt>
            <dd className="text-right font-semibold text-brand-700">
              {customer.sales_staff ? (
                <span className="inline-flex items-center gap-1.5">
                  <UserCheck className="h-3.5 w-3.5" />
                  {customer.sales_staff.name}
                </span>
              ) : (
                'Chưa phân công'
              )}
            </dd>
          </div>
        </dl>
      </div>

      <div className="mt-7 flex flex-wrap justify-center gap-3">
        <button type="button" className="btn-primary px-6 py-3" onClick={on_add_another}>
          Thêm khách khác
        </button>
        <button type="button" className="btn-ghost" onClick={on_close}>
          Đóng
        </button>
      </div>
    </div>
  );
}
