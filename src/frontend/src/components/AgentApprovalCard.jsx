import { CheckCircle2, PencilLine, Send, UserCheck } from 'lucide-react';
import { useState } from 'react';

import { find_vehicle } from '../data/vehicles.js';
import { format_date_long } from '../lib/formatDate.js';

const field_labels = {
  name: 'Họ và tên',
  phone: 'Số điện thoại',
  email: 'Email',
  vehicle_id: 'Mẫu xe',
  test_drive_date: 'Ngày lái thử',
  test_drive_time: 'Giờ lái thử',
  ward: 'Phường/Xã',
  note: 'Yêu cầu khác',
};

const field_order = [
  'name',
  'phone',
  'email',
  'vehicle_id',
  'test_drive_date',
  'test_drive_time',
  'ward',
  'note',
];

const describe = (field, value) => {
  if (field === 'vehicle_id') return find_vehicle(value)?.name ?? value;
  if (field === 'test_drive_date') return format_date_long(value);
  return value;
};

/**
 * Thẻ xác nhận render NGAY TRONG khung chat, do `useLangGraphInterrupt` gọi tới.
 * `resolve(text)` chính là giá trị trả về của `interrupt()` phía Python — nên
 * phải gửi đúng chuỗi tiếng Việt mà `classify_answer()` nhận ra.
 */
export default function AgentApprovalCard({ event, resolve }) {
  const payload = event?.value ?? {};
  const kind = payload.kind ?? 'confirm_details';
  const draft = payload.draft ?? {};

  const [correction, set_correction] = useState('');
  const [answered, set_answered] = useState(false);

  const answer = (text) => {
    if (answered) return;
    set_answered(true);
    resolve(text);
  };

  if (kind === 'confirm_submit') {
    return (
      <div className="my-2 rounded-2xl border border-brand-200 bg-brand-50/70 p-4">
        <div className="flex items-center gap-2 font-semibold text-brand-800">
          <Send className="h-4 w-4" />
          Em gửi đăng ký giúp anh/chị nhé?
        </div>
        <p className="mt-1.5 text-sm text-slate-600">
          Em có thể bấm gửi hộ, hoặc anh/chị tự bấm nút trên form cho chắc ạ.
        </p>

        <div className="mt-3.5 flex flex-wrap gap-2">
          <button
            type="button"
            className="btn-primary"
            disabled={answered}
            onClick={() => answer('Tự động gửi')}
          >
            <Send className="h-4 w-4" />
            Tự động gửi
          </button>
          <button
            type="button"
            className="btn-ghost"
            disabled={answered}
            onClick={() => answer('Tôi tự gửi')}
          >
            <UserCheck className="h-4 w-4" />
            Tôi tự gửi
          </button>
        </div>
      </div>
    );
  }

  const rows = field_order.filter((field) => draft[field]);

  return (
    <div className="my-2 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-2 font-semibold text-ink-900">
        <CheckCircle2 className="h-4 w-4 text-brand-600" />
        Kiểm tra lại thông tin
      </div>

      <dl className="mt-3 divide-y divide-slate-100 text-sm">
        {rows.map((field) => (
          <div key={field} className="flex justify-between gap-4 py-1.5">
            <dt className="text-slate-500">{field_labels[field]}</dt>
            <dd className="text-right font-medium text-ink-900">
              {describe(field, draft[field])}
            </dd>
          </div>
        ))}
        <div className="flex justify-between gap-4 py-1.5">
          <dt className="text-slate-500">Tỉnh/Thành phố</dt>
          <dd className="text-right font-medium text-ink-900">Hà Nội</dd>
        </div>
      </dl>

      <button
        type="button"
        className="btn-primary mt-3.5 w-full"
        disabled={answered}
        onClick={() => answer('Thông tin chính xác')}
      >
        <CheckCircle2 className="h-4 w-4" />
        Thông tin chính xác
      </button>

      <div className="mt-3.5 border-t border-slate-100 pt-3.5">
        <label className="field-label flex items-center gap-1.5">
          <PencilLine className="h-3.5 w-3.5 text-slate-400" />
          Cần sửa gì ạ?
        </label>
        <textarea
          className="field-input min-h-[70px] resize-y"
          placeholder='Ví dụ: "đổi giờ thành 15:00" hoặc "đổi xe sang VF 9"'
          value={correction}
          disabled={answered}
          onChange={(event_) => set_correction(event_.target.value)}
        />
        <button
          type="button"
          className="btn-ghost mt-2 w-full"
          disabled={answered || correction.trim().length === 0}
          onClick={() => answer(correction.trim())}
        >
          Gửi yêu cầu sửa
        </button>
      </div>
    </div>
  );
}
