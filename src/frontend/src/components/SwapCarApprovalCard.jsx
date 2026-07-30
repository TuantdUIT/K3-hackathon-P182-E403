import { AlertTriangle, CheckCircle2, ClipboardCheck, PencilLine, ThumbsUp } from 'lucide-react';
import { useState } from 'react';

import { format_price } from '../lib/formatPrice.js';

/**
 * Thẻ HITL của agent `swap_car`, render NGAY TRONG khung chat qua
 * `useLangGraphInterrupt`.
 *
 * Tách khỏi `AgentApprovalCard.jsx` (thẻ của 2 agent điền form) vì hai luồng
 * hỏi hai thứ khác hẳn nhau: bên kia xác nhận nội dung form, bên này duyệt một
 * con số tiền và tích một checklist workflow. Nhét chung một component thì mỗi
 * lần thêm nhánh phải đọc lại cả hai nghiệp vụ.
 *
 * `resolve(value)` chính là giá trị trả về của `interrupt()` phía Python.
 */
export default function SwapCarApprovalCard({ event, resolve }) {
  const payload = event?.value ?? {};
  const kind = payload.kind ?? 'swap_confirm_price';

  if (kind === 'swap_checklist') {
    return <ChecklistCard payload={payload} resolve={resolve} />;
  }
  return <PriceCard payload={payload} resolve={resolve} />;
}

function PriceCard({ payload, resolve }) {
  const quote = payload.quote ?? {};
  const [correction, set_correction] = useState('');
  const [answered, set_answered] = useState(false);

  const answer = (value) => {
    if (answered) return;
    set_answered(true);
    resolve(value);
  };

  const estimated = payload.estimated_criteria ?? [];

  return (
    <div className="my-2 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-2 font-semibold text-ink-900">
        <CheckCircle2 className="h-4 w-4 text-brand-600" />
        Khách đồng ý mức bù trừ này chứ ạ?
      </div>

      <dl className="mt-3 divide-y divide-slate-100 text-sm">
        <Line label="Giá thu xe cũ (A)" value={format_price(quote.value_a)} />
        <Line label="Tổng chi phí xe mới (B)" value={format_price(quote.value_b)} />
        <Line label="Khuyến mãi xe mới" value={`− ${format_price(quote.promo_new_car)}`} />
        <Line label="Ưu đãi khách đổi xe" value={`− ${format_price(quote.trade_in_bonus)}`} />
        <div className="flex items-center justify-between gap-4 pt-2">
          <dt className="font-semibold text-ink-900">Khách trả thêm (C)</dt>
          <dd
            className={`text-right text-lg font-extrabold ${
              (quote.amount_c ?? 0) < 0 ? 'text-amber-600' : 'text-brand-700'
            }`}
          >
            {format_price(quote.amount_c)}
          </dd>
        </div>
      </dl>

      {estimated.length > 0 && (
        <p className="mt-3 flex items-start gap-1.5 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-800">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            {estimated.length} tiêu chí chưa thẩm định, đang tạm tính mức Khá:{' '}
            {estimated.join(', ')}.
          </span>
        </p>
      )}

      <button
        type="button"
        className="btn-primary mt-3.5 w-full"
        disabled={answered}
        onClick={() => answer('Khách đồng ý')}
      >
        <ThumbsUp className="h-4 w-4" />
        Khách đồng ý giá
      </button>

      <div className="mt-3.5 border-t border-slate-100 pt-3.5">
        <label className="field-label flex items-center gap-1.5">
          <PencilLine className="h-3.5 w-3.5 text-slate-400" />
          Cần tính lại gì ạ?
        </label>
        <textarea
          className="field-input min-h-[70px] resize-y"
          placeholder='Ví dụ: "đổi sang VF 5", "chi phí sửa 20 triệu", "gầm chấm mức trung bình"'
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
          Gửi yêu cầu tính lại
        </button>
      </div>
    </div>
  );
}

function ChecklistCard({ payload, resolve }) {
  const items = payload.items ?? [];
  const [picked, set_picked] = useState([]);
  const [answered, set_answered] = useState(false);

  const toggle = (code) =>
    set_picked((previous) =>
      previous.includes(code) ? previous.filter((item) => item !== code) : [...previous, code],
    );

  // Gửi cả khi còn thiếu: chặn ở đây là chặn MỀM, backend sẽ trả về danh sách
  // mục thiếu và giữ hồ sơ ở trạng thái chờ chứ không huỷ.
  const submit = () => {
    if (answered) return;
    set_answered(true);
    resolve({ done: picked });
  };

  const missing = items.length - picked.length;

  return (
    <div className="my-2 rounded-2xl border border-brand-200 bg-brand-50/70 p-4">
      <div className="flex items-center gap-2 font-semibold text-brand-800">
        <ClipboardCheck className="h-4 w-4" />
        {items.length} việc bắt buộc trước khi hẹn giao xe
      </div>

      <div className="mt-3 space-y-2">
        {items.map((item) => (
          <label
            key={item.code}
            className="flex cursor-pointer items-center gap-2.5 rounded-xl bg-white px-3 py-2.5 text-sm"
          >
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-400"
              checked={picked.includes(item.code)}
              disabled={answered}
              onChange={() => toggle(item.code)}
            />
            <span className="font-medium text-ink-900">{item.label}</span>
          </label>
        ))}
      </div>

      <button
        type="button"
        className="btn-primary mt-3.5 w-full"
        disabled={answered}
        onClick={submit}
      >
        <ClipboardCheck className="h-4 w-4" />
        {missing > 0 ? `Gửi (còn thiếu ${missing} mục)` : 'Đủ 4 mục — chốt ngày giao xe'}
      </button>
    </div>
  );
}

function Line({ label, value }) {
  return (
    <div className="flex justify-between gap-4 py-1.5">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-ink-900">{value}</dd>
    </div>
  );
}
