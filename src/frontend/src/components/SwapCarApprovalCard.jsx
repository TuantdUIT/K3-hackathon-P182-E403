import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  ClipboardList,
  Loader2,
  PencilLine,
  ThumbsUp,
} from 'lucide-react';
import { useState } from 'react';

import { useCursorBusy } from '../lib/cursorBusy.js';
import { format_price } from '../lib/formatPrice.js';
import { useInterruptGate } from '../lib/interruptGate.js';

/**
 * Thẻ HITL của agent `swap_car`, render NGAY TRONG khung chat qua
 * `useLangGraphInterrupt`.
 *
 * Tách khỏi `AgentApprovalCard.jsx` (thẻ của 2 agent điền form) vì hai luồng
 * hỏi hai thứ khác hẳn nhau: bên kia xác nhận nội dung form, bên này duyệt một
 * con số tiền và tích một checklist workflow. Nhét chung một component thì mỗi
 * lần thêm nhánh phải đọc lại cả hai nghiệp vụ.
 *
 * Ba `kind`, ứng với ba lần `interrupt()` trong graph:
 *   swap_confirm_form  — soát hồ sơ con trỏ vừa điền, TRƯỚC khi ghi DB
 *   swap_confirm_price — duyệt số tiền bù trừ
 *   swap_checklist     — tích 4 việc bắt buộc trước khi hẹn giao xe
 *
 * `resolve(value)` chính là giá trị trả về của `interrupt()` phía Python.
 */
export default function SwapCarApprovalCard({ event, resolve }) {
  const payload = event?.value ?? {};
  const kind = payload.kind ?? 'swap_confirm_price';

  if (kind === 'swap_confirm_form') {
    return <FormReviewCard payload={payload} resolve={resolve} />;
  }
  if (kind === 'swap_checklist') {
    return <ChecklistCard payload={payload} resolve={resolve} />;
  }
  return <PriceCard payload={payload} resolve={resolve} />;
}

/**
 * Thẻ soát hồ sơ. Sales đọc lại thông tin xe cũ vừa được điền, gõ chỗ sai vào ô
 * bên dưới; backend bóc tách rồi cho con trỏ điền lại ĐÚNG mấy ô đó.
 *
 * Khoá theo `useCursorBusy()` giống thẻ giá: hỏi "đã đúng chưa" trong lúc con
 * trỏ còn đang gõ dở thì sales chưa có gì để soát.
 */
function FormReviewCard({ payload, resolve }) {
  const summary = payload.summary ?? {};
  const rows = summary.rows ?? [];
  const scored = summary.scored ?? [];
  const flags = payload.flags ?? [];

  const [correction, set_correction] = useState('');
  const [answered, set_answered] = useState(false);

  const filling = useCursorBusy();
  const locked = answered || filling;

  useInterruptGate(!answered);

  const rounds = payload.rounds ?? 0;
  const max_rounds = payload.max_rounds ?? 3;
  const left = Math.max(0, max_rounds - rounds);

  const answer = (value) => {
    if (locked) return;
    set_answered(true);
    resolve(value);
  };

  return (
    <div className="my-2 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-2 font-semibold text-ink-900">
        <ClipboardList className="h-4 w-4 text-brand-600" />
        Hồ sơ đã đúng chưa ạ?
      </div>

      {payload.customer_name && (
        <p className="mt-1 text-xs text-slate-500">Khách {payload.customer_name}</p>
      )}

      <dl className="mt-3 divide-y divide-slate-100 text-sm">
        {rows.map((row) => (
          <Line key={row.field} label={row.label} value={row.value} />
        ))}
      </dl>

      {scored.length > 0 && (
        <div className="mt-3 rounded-xl bg-slate-50 px-3 py-2">
          <p className="text-xs font-semibold text-slate-500">Đã chấm</p>
          <ul className="mt-1 space-y-0.5 text-xs text-slate-700">
            {scored.map((item) => (
              <li key={item.code}>
                {item.label}: <span className="font-semibold">{item.level}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {flags.length > 0 && (
        <p className="mt-3 flex items-start gap-1.5 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-800">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>Đã bật cờ loại trừ: {flags.join(', ')}.</span>
        </p>
      )}

      {filling && !answered && (
        <p className="mt-3 flex items-center gap-1.5 rounded-xl bg-slate-50 px-3 py-2 text-xs text-slate-600">
          <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-brand-600" />
          Em đang điền nốt hồ sơ bên cạnh, anh/chị chờ em một chút ạ.
        </p>
      )}

      <button
        type="button"
        className="btn-primary mt-3.5 w-full"
        disabled={locked}
        onClick={() => answer('Đúng rồi')}
      >
        <ThumbsUp className="h-4 w-4" />
        Đúng rồi, tính giá đi em
      </button>

      <div className="mt-3.5 border-t border-slate-100 pt-3.5">
        <label className="field-label flex items-center gap-1.5">
          <PencilLine className="h-3.5 w-3.5 text-slate-400" />
          Cần sửa ô nào ạ?
        </label>
        <textarea
          className="field-input min-h-[70px] resize-y"
          placeholder='Ví dụ: "odo 54.000 km thôi", "đời 2021 chứ không phải 2022", "gầm chấm mức khá"'
          value={correction}
          disabled={locked}
          onChange={(event_) => set_correction(event_.target.value)}
        />
        <button
          type="button"
          className="btn-ghost mt-2 w-full"
          disabled={locked || correction.trim().length === 0}
          onClick={() => answer(correction.trim())}
        >
          Gửi yêu cầu sửa{left < max_rounds ? ` (còn ${left} lượt)` : ''}
        </button>
      </div>
    </div>
  );
}

function PriceCard({ payload, resolve }) {
  const quote = payload.quote ?? {};
  const [correction, set_correction] = useState('');
  const [answered, set_answered] = useState(false);

  // Backend chốt xong con số trước khi con trỏ điền hết form. Chốt giá lúc hồ
  // sơ bên cạnh mới có vài ô là chốt trên một thứ sales chưa kịp nhìn.
  const filling = useCursorBusy();
  const locked = answered || filling;

  useInterruptGate(!answered);

  const answer = (value) => {
    if (locked) return;
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

      {filling && !answered && (
        <p className="mt-3 flex items-center gap-1.5 rounded-xl bg-slate-50 px-3 py-2 text-xs text-slate-600">
          <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-brand-600" />
          Em đang điền nốt hồ sơ bên cạnh — anh/chị xem qua rồi chốt giúp em ạ.
        </p>
      )}

      <button
        type="button"
        className="btn-primary mt-3.5 w-full"
        disabled={locked}
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
          disabled={locked}
          onChange={(event_) => set_correction(event_.target.value)}
        />
        <button
          type="button"
          className="btn-ghost mt-2 w-full"
          disabled={locked || correction.trim().length === 0}
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

  useInterruptGate(!answered);

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
