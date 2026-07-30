import { AnimatePresence, motion } from 'framer-motion';
import { CheckCircle2, Loader2, Phone, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { find_vehicle, vehicles } from '../data/vehicles.js';
import { create_test_drive } from '../lib/api.js';
import { format_date_long, today_iso } from '../lib/formatDate.js';
import { format_price_short } from '../lib/formatPrice.js';
import WardSelect from './WardSelect.jsx';

const time_slots = ['08:00', '09:30', '11:00', '13:30', '15:00', '16:30'];
const HOTLINE = '1900 23 23 89';

export default function TestDriveModal({
  open,
  on_close,
  form_data,
  set_form_data,
  selected_vehicle_id,
  ward_notice,
  set_ward_notice,
  ward_select_ref,
  agent_submission_code,
  run_seq,
  run_kind,
  on_reset,
}) {
  const [submitting, set_submitting] = useState(false);
  const [error_message, set_error_message] = useState('');
  const [submitted_code, set_submitted_code] = useState('');
  const last_run_seq_ref = useRef(null);

  const vehicle = find_vehicle(selected_vehicle_id) ?? vehicles[0];

  // Agent gửi hộ -> chuyển sang màn thành công y hệt khi khách tự bấm.
  useEffect(() => {
    if (agent_submission_code) set_submitted_code(agent_submission_code);
  }, [agent_submission_code]);

  // Lượt mới dạng "full" = khách khác -> mở lại form trắng, để một phiên chat
  // phục vụ được nhiều khách liên tiếp mà không kẹt ở màn "đăng ký thành công".
  useEffect(() => {
    if (run_seq === null || run_seq === undefined) return;
    if (run_seq === last_run_seq_ref.current) return;
    last_run_seq_ref.current = run_seq;
    if (run_kind === 'full') {
      set_submitted_code('');
      set_error_message('');
    }
  }, [run_seq, run_kind]);

  // Chặn scroll trang khi modal mở.
  useEffect(() => {
    if (!open) return undefined;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);

  const update = (field) => (event) => set_form_data(field, event.target.value);

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
        source: 'Website',
      });
      set_submitted_code(created.code);
    } catch (error) {
      set_error_message(error.message);
    } finally {
      set_submitting(false);
    }
  };

  const close_and_reset = () => {
    on_close();
    if (submitted_code) {
      set_submitted_code('');
      on_reset?.();
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[100] flex items-start justify-center overflow-y-auto bg-ink-900/60 p-4 backdrop-blur-sm sm:items-center"
        >
          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ duration: 0.25 }}
            className="relative my-8 w-full max-w-4xl overflow-hidden rounded-3xl bg-white shadow-lift sm:my-0"
          >
            <button
              type="button"
              onClick={close_and_reset}
              className="absolute right-4 top-4 z-10 grid h-9 w-9 place-items-center rounded-full bg-white/90 text-slate-500 transition hover:bg-slate-100"
              aria-label="Đóng"
            >
              <X className="h-4.5 w-4.5" />
            </button>

            {submitted_code ? (
              <SuccessPanel
                code={submitted_code}
                form_data={form_data}
                vehicle={vehicle}
                on_close={close_and_reset}
              />
            ) : (
              <div className="grid lg:grid-cols-[minmax(0,300px)_1fr]">
                {/* Cột trái: panel gradient thương hiệu, đồng bộ với dropdown mẫu xe */}
                <aside className="relative hidden overflow-hidden bg-gradient-to-br from-brand-700 via-brand-600 to-ink-900 p-7 text-white lg:block">
                  <h3 className="text-sm font-semibold uppercase tracking-wide text-brand-200">
                    Bạn đang đăng ký lái thử
                  </h3>
                  <p className="mt-2 text-3xl font-extrabold leading-tight">{vehicle.name}</p>
                  <p className="mt-1 text-sm text-brand-100">{vehicle.tagline}</p>

                  <div className="mt-6 overflow-hidden rounded-2xl bg-white/10">
                    <img src={vehicle.image} alt={vehicle.name} className="h-40 w-full object-cover" />
                  </div>

                  <dl className="mt-6 space-y-2.5 text-sm">
                    <div className="flex justify-between">
                      <dt className="text-brand-200">Phân khúc</dt>
                      <dd className="font-semibold">{vehicle.segment}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-brand-200">Số chỗ</dt>
                      <dd className="font-semibold">{vehicle.seats}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-brand-200">Quãng đường</dt>
                      <dd className="font-semibold">{vehicle.range} km</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-brand-200">Giá từ</dt>
                      <dd className="font-semibold">{format_price_short(vehicle.priceFrom)}</dd>
                    </div>
                  </dl>

                  <p className="mt-7 flex items-center gap-2 text-xs text-brand-100">
                    <Phone className="h-3.5 w-3.5" />
                    Hotline {HOTLINE}
                  </p>
                </aside>

                <form onSubmit={on_submit} className="p-6 sm:p-8" noValidate={false}>
                  <h2 className="text-2xl font-bold">Đăng ký lái thử</h2>
                  <p className="mt-1.5 text-sm text-slate-500">
                    Nhân viên kinh doanh sẽ gọi xác nhận trước buổi hẹn. Các ô có dấu{' '}
                    <span className="text-rose-500">*</span> là bắt buộc.
                  </p>

                  <div className="mt-6 grid gap-4 sm:grid-cols-2">
                    <div className="sm:col-span-2">
                      <label className="field-label" htmlFor="td-name">
                        Họ và tên <span className="text-rose-500">*</span>
                      </label>
                      <input
                        id="td-name"
                        data-agent-field="name"
                        className="field-input"
                        required
                        minLength={2}
                        placeholder="Nguyễn Văn A"
                        value={form_data.name}
                        onChange={update('name')}
                      />
                    </div>

                    <div>
                      <label className="field-label" htmlFor="td-phone">
                        Số điện thoại <span className="text-rose-500">*</span>
                      </label>
                      <input
                        id="td-phone"
                        data-agent-field="phone"
                        className="field-input"
                        required
                        inputMode="numeric"
                        pattern="[0-9]{10,11}"
                        title="Số điện thoại gồm 10–11 chữ số"
                        placeholder="0912345678"
                        value={form_data.phone}
                        onChange={update('phone')}
                      />
                    </div>

                    <div>
                      <label className="field-label" htmlFor="td-email">
                        Email <span className="text-slate-400">(không bắt buộc)</span>
                      </label>
                      <input
                        id="td-email"
                        data-agent-field="email"
                        type="email"
                        className="field-input"
                        placeholder="ban@example.com"
                        value={form_data.email}
                        onChange={update('email')}
                      />
                    </div>

                    <div className="sm:col-span-2">
                      <label className="field-label" htmlFor="td-vehicle">
                        Mẫu xe <span className="text-rose-500">*</span>
                      </label>
                      <select
                        id="td-vehicle"
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
                      <label className="field-label" htmlFor="td-date">
                        Ngày lái thử <span className="text-rose-500">*</span>
                      </label>
                      <input
                        id="td-date"
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
                      <label className="field-label" htmlFor="td-time">
                        Giờ lái thử <span className="text-rose-500">*</span>
                      </label>
                      <select
                        id="td-time"
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
                      <label className="field-label" htmlFor="td-province">
                        Tỉnh/Thành phố
                      </label>
                      <input
                        id="td-province"
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
                      <label className="field-label" htmlFor="td-note">
                        Yêu cầu khác
                      </label>
                      <textarea
                        id="td-note"
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
                    <button type="submit" className="btn-primary px-6 py-3" disabled={submitting}>
                      {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
                      {submitting ? 'Đang gửi...' : 'Đăng ký lái thử'}
                    </button>
                    <button type="button" className="btn-ghost" onClick={close_and_reset}>
                      Để sau
                    </button>
                  </div>
                </form>
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function SuccessPanel({ code, form_data, vehicle, on_close }) {
  return (
    <div className="px-6 py-14 text-center sm:px-10">
      <span className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-emerald-100 text-emerald-600">
        <CheckCircle2 className="h-8 w-8" />
      </span>

      <h2 className="mt-5 text-2xl font-bold">Đăng ký lái thử thành công!</h2>
      <p className="mt-2 text-sm text-slate-500">
        Cảm ơn anh/chị. Nhân viên kinh doanh sẽ liên hệ xác nhận trước buổi hẹn.
      </p>

      <div className="mx-auto mt-7 max-w-md rounded-2xl border border-slate-200 bg-slate-50 p-5 text-left">
        <div className="text-xs uppercase tracking-wide text-slate-400">Mã đăng ký</div>
        <div className="text-2xl font-extrabold tracking-tight text-brand-700">{code}</div>

        <dl className="mt-4 space-y-2 text-sm">
          <div className="flex justify-between gap-4">
            <dt className="text-slate-500">Mẫu xe</dt>
            <dd className="font-medium">{vehicle.name}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-slate-500">Lịch hẹn</dt>
            <dd className="text-right font-medium">
              {format_date_long(form_data.test_drive_date)}
              {form_data.test_drive_time ? ` · ${form_data.test_drive_time}` : ''}
            </dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-slate-500">Địa điểm</dt>
            <dd className="text-right font-medium">{form_data.ward}, Hà Nội</dd>
          </div>
        </dl>
      </div>

      <p className="mt-6 text-sm text-slate-500">
        Cần đổi lịch? Gọi hotline <span className="font-semibold text-ink-900">{HOTLINE}</span>.
      </p>

      <button type="button" className="btn-primary mt-6 px-6 py-3" onClick={on_close}>
        Xong
      </button>
    </div>
  );
}
