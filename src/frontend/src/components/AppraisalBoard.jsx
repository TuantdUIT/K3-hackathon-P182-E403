import { useCoAgent, useLangGraphInterrupt } from '@copilotkit/react-core';
import { CopilotChat } from '@copilotkit/react-ui';
import {
  AlertTriangle,
  ArrowUp,
  Bot,
  Calculator,
  CheckCircle2,
  ClipboardList,
  Gauge,
  Loader2,
  Search,
  ShieldAlert,
  XCircle,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { vehicles } from '../data/vehicles.js';
import {
  create_appraisal,
  create_quote,
  fetch_appraisals,
  fetch_criteria,
  fetch_customers,
  fetch_used_car_models,
  preview_eligibility,
} from '../lib/api.js';
import { format_date } from '../lib/formatDate.js';
import { format_price } from '../lib/formatPrice.js';
import { useInterruptPending } from '../lib/interruptGate.js';
import useAgentActionRunner from '../lib/useAgentActionRunner.js';
import useAgentCursor from '../lib/useAgentCursor.js';
import AgentCursor from './AgentCursor.jsx';
import SwapCarApprovalCard from './SwapCarApprovalCard.jsx';

const ELIGIBILITY_DEBOUNCE_MS = 400;

const empty_form = {
  make: '',
  model: '',
  year: '',
  trim: '',
  plate_no: '',
  odo_km: '',
  first_registration_date: '',
  repair_cost: '',
  vehicle_id: 'vf3',
};

// Nhãn 4 mức chấm. Trọng số thì KHÔNG hardcode ở đây — lấy từ
// `GET /appraisals/criteria` để một mình backend giữ nguồn sự thật.
const level_options = [
  { value: 'tot', label: 'Tốt' },
  { value: 'kha', label: 'Khá' },
  { value: 'trung_binh', label: 'Trung bình' },
  { value: 'kem', label: 'Kém' },
];

const flag_labels = {
  flood_damaged: 'Từng ngập nước',
  structural_damage: 'Đâm đụng ảnh hưởng kết cấu',
  odo_tampered: 'Nghi tua công-tơ-mét',
  missing_papers: 'Thiếu giấy tờ gốc',
};

const status_styles = {
  draft: 'bg-slate-100 text-slate-600 border-slate-200',
  rejected: 'bg-rose-100 text-rose-700 border-rose-200',
  appraised: 'bg-brand-100 text-brand-700 border-brand-200',
  quoted: 'bg-amber-100 text-amber-700 border-amber-200',
  blocked: 'bg-amber-100 text-amber-700 border-amber-200',
  accepted: 'bg-emerald-100 text-emerald-700 border-emerald-200',
};

const status_labels = {
  draft: 'Nháp',
  rejected: 'Từ chối',
  appraised: 'Đã định giá',
  quoted: 'Đã báo giá',
  blocked: 'Chờ đủ hồ sơ',
  accepted: 'Đã chốt',
};

/**
 * Tab "Định giá xe" — nghiệp vụ 2 (đổi xe cũ lấy xe mới).
 *
 * Ba cột: danh sách toàn bộ khách trong DB · hồ sơ định giá · trợ lý `swap_car`.
 *
 * State form nằm ở ĐÂY chứ không trong từng ô con, vì agent và sales phải ghi
 * vào cùng một chỗ — giống cách `Dashboard` giữ state của form thêm khách.
 * Con trỏ ảo dùng lại nguyên `useAgentActionRunner`: agent này phát action đúng
 * hình dạng `{type, field, label, selector, value, run_seq}` như 2 agent kia.
 */
export default function AppraisalBoard({ staff }) {
  const [customers, set_customers] = useState([]);
  const [search, set_search] = useState('');
  const [loading_customers, set_loading_customers] = useState(true);
  const [selected, set_selected] = useState(null);

  const [criteria, set_criteria] = useState([]);
  const [known_models, set_known_models] = useState([]);
  const [appraisals, set_appraisals] = useState([]);

  const [form, set_form_raw] = useState(empty_form);
  const [levels, set_levels] = useState({});
  const [flags, set_flags] = useState({});

  const [checks, set_checks] = useState([]);
  const [computing, set_computing] = useState(false);
  const [error_message, set_error_message] = useState('');
  const [result, set_result] = useState(null);

  const last_run_seq_ref = useRef(null);
  const { cursor, controls } = useAgentCursor();

  const { state: agent_state, setState: set_agent_state } = useCoAgent({
    name: 'swap_car_agent',
    initialState: {
      draft: {},
      status: 'idle',
      current_action: null,
      customer_code: null,
      sales_staff_id: staff?.id ?? null,
    },
  });

  const agent_status = agent_state?.status ?? 'idle';
  const current_action = agent_state?.current_action ?? null;
  const run_seq = agent_state?.run_seq ?? null;
  const run_kind = agent_state?.run_kind ?? 'full';
  const agent_appraisal_code = agent_state?.appraisal_code ?? null;

  // --- tải dữ liệu ---

  const load_customers = useCallback(async () => {
    set_loading_customers(true);
    try {
      set_customers(await fetch_customers({ search }));
    } catch (error) {
      set_error_message(error.message);
    } finally {
      set_loading_customers(false);
    }
  }, [search]);

  useEffect(() => {
    const timer = setTimeout(load_customers, 250);
    return () => clearTimeout(timer);
  }, [load_customers]);

  useEffect(() => {
    (async () => {
      try {
        const [criteria_rows, models] = await Promise.all([
          fetch_criteria(),
          fetch_used_car_models(),
        ]);
        set_criteria(criteria_rows);
        set_known_models(models);
      } catch (error) {
        set_error_message(error.message);
      }
    })();
  }, []);

  const load_appraisals = useCallback(async (customer_code) => {
    if (!customer_code) {
      set_appraisals([]);
      return;
    }
    try {
      set_appraisals(await fetch_appraisals(customer_code));
    } catch {
      set_appraisals([]);
    }
  }, []);

  useEffect(() => {
    load_appraisals(selected?.code);
  }, [selected?.code, load_appraisals]);

  // Agent vừa ghi xong hồ sơ -> lịch sử bên dưới phải hiện ra ngay.
  useEffect(() => {
    if (agent_appraisal_code) load_appraisals(selected?.code);
  }, [agent_appraisal_code, selected?.code, load_appraisals]);

  // --- form ---

  const set_form_data = useCallback((field, value) => {
    // Agent phát action cho cả 3 nhóm ô qua CÙNG một callback, nên chỗ này phải
    // tự phân loại: `score_*` vào bảng chấm điểm, `flag_*` vào cờ loại trừ.
    if (field.startsWith('score_')) {
      set_levels((previous) => ({ ...previous, [field.slice(6)]: value }));
      return;
    }
    if (field.startsWith('flag_')) {
      set_flags((previous) => ({ ...previous, [field.slice(5)]: value === '1' || value === true }));
      return;
    }
    set_form_raw((previous) => ({ ...previous, [field]: value }));
  }, []);

  const reset_form = useCallback(() => {
    set_form_raw(empty_form);
    set_levels({});
    set_flags({});
    set_checks([]);
    set_result(null);
    set_error_message('');
  }, []);

  // Lượt "full" = xe khác -> xoá form. Lượt "correction" phải giữ nguyên vì nó
  // chỉ điền lại vài ô đã đổi.
  useEffect(() => {
    if (run_seq === null || run_seq === last_run_seq_ref.current) return;
    last_run_seq_ref.current = run_seq;
    if (run_kind === 'full') reset_form();
  }, [run_seq, run_kind, reset_form]);

  useAgentActionRunner({ current_action, controls, set_form_data });

  const chat_locked = useInterruptPending();

  useLangGraphInterrupt({
    render: ({ event, resolve }) => <SwapCarApprovalCard event={event} resolve={resolve} />,
  });

  const on_select_customer = (customer) => {
    set_selected(customer);
    reset_form();
    // Agent cần mã khách để gắn hồ sơ; không có thì `extract_node` sẽ nhắc chọn.
    set_agent_state?.((previous) => ({
      ...(previous ?? {}),
      customer_code: customer.code,
      customer_name: customer.name,
      sales_staff_id: staff?.id ?? null,
    }));
  };

  const base_payload = useMemo(
    () => ({
      customer_code: selected?.code ?? '',
      make: form.make,
      model: form.model,
      year: Number(form.year) || 0,
      trim: form.trim,
      plate_no: form.plate_no || null,
      odo_km: Number(String(form.odo_km).replace(/\D/g, '')) || 0,
      first_registration_date: form.first_registration_date,
      flags,
      levels,
      repair_cost: Number(String(form.repair_cost).replace(/\D/g, '')) || 0,
      sales_staff_id: staff?.id ?? null,
    }),
    [selected?.code, form, flags, levels, staff?.id],
  );

  const ready = Boolean(
    selected?.code && form.make && form.model && form.year && form.first_registration_date,
  );

  // Đèn xanh/đỏ chạy trước, không đợi bấm nút: sales thấy xe trượt điều kiện
  // ngay lúc nhập, khỏi mất công chấm 8 tiêu chí rồi mới biết bị loại.
  useEffect(() => {
    if (!ready) {
      set_checks([]);
      return undefined;
    }
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const rows = await preview_eligibility(base_payload);
        if (!cancelled) set_checks(rows);
      } catch {
        if (!cancelled) set_checks([]);
      }
    }, ELIGIBILITY_DEBOUNCE_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [ready, base_payload]);

  const blocked_by = checks.find((check) => !check.passed);

  const on_compute = async () => {
    set_computing(true);
    set_error_message('');
    try {
      const appraisal = await create_appraisal(base_payload);
      let quote = null;
      if (appraisal.eligibility_status === 'passed') {
        quote = await create_quote(appraisal.code, form.vehicle_id);
      }
      set_result({ appraisal, quote });
      await load_appraisals(selected?.code);
    } catch (error) {
      set_error_message(error.message);
      set_result(null);
    } finally {
      set_computing(false);
    }
  };

  return (
    <>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,260px)_minmax(0,1fr)_minmax(0,360px)]">
        <CustomerPicker
          customers={customers}
          loading={loading_customers}
          search={search}
          set_search={set_search}
          selected={selected}
          on_select={on_select_customer}
        />

        <section className="min-w-0">
          {!selected ? (
            <EmptyState />
          ) : (
            <div className="space-y-5">
              <div className="card p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="font-mono text-xs font-semibold text-brand-700">
                      {selected.code}
                    </div>
                    <h2 className="mt-0.5 text-lg font-bold">{selected.name}</h2>
                    <p className="text-sm text-slate-500">
                      {selected.phone} · quan tâm {selected.model}
                    </p>
                  </div>
                  {agent_status === 'filling' && (
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-50 px-3 py-1.5 text-xs font-semibold text-brand-700">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Trợ lý đang điền hồ sơ
                    </span>
                  )}
                </div>
              </div>

              <OldCarForm
                form={form}
                set_form_data={set_form_data}
                flags={flags}
                known_models={known_models}
              />

              <EligibilityPanel checks={checks} ready={ready} />

              <ScorePanel criteria={criteria} levels={levels} set_form_data={set_form_data} />

              <div className="card p-5">
                <h3 className="flex items-center gap-2 text-sm font-bold">
                  <Calculator className="h-4 w-4 text-brand-600" />
                  Xe mới khách muốn đổi
                </h3>
                <div className="mt-3 grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="field-label" htmlFor="ap-vehicle">
                      Mẫu VinFast
                    </label>
                    <select
                      id="ap-vehicle"
                      data-agent-field="vehicle_id"
                      className="field-input"
                      value={form.vehicle_id}
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
                    <label className="field-label" htmlFor="ap-repair">
                      Chi phí dọn dẹp/sửa chữa
                    </label>
                    <input
                      id="ap-repair"
                      data-agent-field="repair_cost"
                      className="field-input"
                      inputMode="numeric"
                      placeholder="0"
                      value={form.repair_cost}
                      onChange={(event) => set_form_data('repair_cost', event.target.value)}
                    />
                  </div>
                </div>

                {error_message && (
                  <p className="mt-4 rounded-xl bg-rose-50 px-3.5 py-2.5 text-sm text-rose-700">
                    {error_message}
                  </p>
                )}

                <button
                  type="button"
                  className="btn-primary mt-5"
                  disabled={!ready || computing}
                  title={ready ? undefined : 'Cần đủ hãng, dòng, đời xe và ngày đăng ký lần đầu'}
                  onClick={on_compute}
                >
                  {computing ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Calculator className="h-4 w-4" />
                  )}
                  {blocked_by ? 'Lưu hồ sơ từ chối' : 'Tính định giá & báo giá'}
                </button>
              </div>

              {result && <ResultPanel result={result} />}

              <HistoryPanel appraisals={appraisals} />
            </div>
          )}
        </section>

        <aside className="card flex min-h-[640px] flex-col overflow-hidden xl:sticky xl:top-5 xl:h-[calc(100vh-2.5rem)]">
          <div className="flex items-center gap-2 border-b border-slate-200 px-5 py-4">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-600 text-white">
              <Bot className="h-4 w-4" />
            </span>
            <div>
              <div className="text-sm font-bold">Trợ lý định giá xe</div>
              <div className="text-xs text-slate-500">Đọc tình trạng xe cũ, em tính hộ</div>
            </div>
          </div>

          {/* `is-snug` chứ không `is-pinned` như modal thêm khách: khung này cao
              gần bằng màn hình, nếu ghim đáy thì lúc mới mở (chỉ có 1 câu chào)
              ô nhập nằm cách nội dung cả màn hình và phải lướt xuống mới gõ
              được. `is-snug` cho nó bám ngay dưới tin nhắn cuối. */}
          {/* Ô nhập bị khoá khi thẻ HITL đang chờ: lúc graph dừng ở `interrupt()`
              chỉ `resolve()` từ thẻ mới vào được graph, gõ ở đây là mất tin. */}
          {chat_locked && (
            <p className="flex items-center gap-1.5 border-b border-amber-200 bg-amber-50 px-5 py-2 text-xs text-amber-800">
              <ArrowUp className="h-3.5 w-3.5 shrink-0" />
              Anh/chị trả lời ở thẻ trong khung chat giúp em, ô nhập bên dưới tạm khoá ạ.
            </p>
          )}

          <div className={`chat-dock is-snug min-h-0 flex-1${chat_locked ? ' is-locked' : ''}`}>
            <CopilotChat
              className="h-full"
              instructions="Bạn là trợ lý định giá xe cũ cho nhân viên kinh doanh VinFast. Người nhắn tin là NHÂN VIÊN, đang thuật lại tình trạng xe cũ của một khách hàng thứ ba. Luôn trả lời bằng tiếng Việt."
              labels={{
                initial:
                  'Hãy nhập thông tin xe cũ của khách để tôi hỗ trợ định giá\n\nVí dụ: "Khách đổi Honda City 2022 bản RS, chạy 4 vạn km, đăng ký tháng 3/2022, máy êm gầm hơi rỉ, muốn lấy VF 6".',
                placeholder: 'Nhập tình trạng xe cũ của khách...',
              }}
            />
          </div>
        </aside>
      </div>

      <AgentCursor cursor={cursor} />
    </>
  );
}

function CustomerPicker({ customers, loading, search, set_search, selected, on_select }) {
  return (
    <aside className="card flex max-h-[calc(100vh-2.5rem)] flex-col overflow-hidden xl:sticky xl:top-5">
      <div className="border-b border-slate-200 p-4">
        <div className="text-sm font-bold">Khách hàng</div>
        <div className="mt-0.5 text-xs text-slate-500">{customers.length} khách trong hệ thống</div>
        <div className="relative mt-3">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            className="field-input pl-9"
            placeholder="Tìm mã, tên, SĐT..."
            value={search}
            onChange={(event) => set_search(event.target.value)}
          />
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {loading && customers.length === 0 && (
          <div className="grid place-items-center py-10 text-slate-400">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        )}

        {!loading && customers.length === 0 && (
          <p className="px-4 py-10 text-center text-sm text-slate-400">
            Chưa có khách nào khớp điều kiện tìm kiếm.
          </p>
        )}

        <ul className="divide-y divide-slate-100">
          {customers.map((customer) => {
            const active = selected?.code === customer.code;
            return (
              <li key={customer.code ?? customer.id}>
                <button
                  type="button"
                  onClick={() => on_select(customer)}
                  className={`w-full px-4 py-3 text-left transition ${
                    active ? 'bg-brand-50' : 'hover:bg-slate-50'
                  }`}
                >
                  <div className="font-mono text-[11px] font-semibold text-brand-700">
                    {customer.code}
                  </div>
                  <div className="mt-0.5 truncate text-sm font-semibold">{customer.name}</div>
                  <div className="truncate text-xs text-slate-500">
                    {customer.phone} · {customer.model}
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </aside>
  );
}

function EmptyState() {
  return (
    <div className="card grid place-items-center px-6 py-20 text-center">
      <ClipboardList className="h-10 w-10 text-slate-300" />
      <h2 className="mt-4 text-lg font-bold">Chọn một khách để bắt đầu định giá</h2>
      <p className="mt-1.5 max-w-md text-sm text-slate-500">
        Hồ sơ định giá luôn gắn với một khách hàng có sẵn trong CRM. Chọn khách ở cột bên trái,
        rồi nhập thông tin xe cũ hoặc đọc cho trợ lý bên phải nghe.
      </p>
    </div>
  );
}

function OldCarForm({ form, set_form_data, flags, known_models }) {
  const makes = useMemo(
    () => [...new Set(known_models.map((item) => item.make))].sort(),
    [known_models],
  );
  const models_of_make = known_models.filter((item) => item.make === form.make);

  return (
    <div className="card p-5">
      <h3 className="flex items-center gap-2 text-sm font-bold">
        <Gauge className="h-4 w-4 text-brand-600" />
        Thông tin xe cũ
      </h3>

      <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Field label="Hãng xe" htmlFor="ap-make">
          <input
            id="ap-make"
            data-agent-field="make"
            className="field-input"
            list="ap-make-list"
            placeholder="Honda"
            value={form.make}
            onChange={(event) => set_form_data('make', event.target.value)}
          />
          <datalist id="ap-make-list">
            {makes.map((make) => (
              <option key={make} value={make} />
            ))}
          </datalist>
        </Field>

        <Field label="Dòng xe" htmlFor="ap-model">
          <input
            id="ap-model"
            data-agent-field="model"
            className="field-input"
            list="ap-model-list"
            placeholder="City"
            value={form.model}
            onChange={(event) => set_form_data('model', event.target.value)}
          />
          <datalist id="ap-model-list">
            {models_of_make.map((item) => (
              <option key={item.model} value={item.model} />
            ))}
          </datalist>
        </Field>

        <Field label="Đời xe" htmlFor="ap-year">
          <input
            id="ap-year"
            data-agent-field="year"
            className="field-input"
            inputMode="numeric"
            placeholder="2022"
            value={form.year}
            onChange={(event) => set_form_data('year', event.target.value)}
          />
        </Field>

        <Field label="Phiên bản" htmlFor="ap-trim" optional>
          <input
            id="ap-trim"
            data-agent-field="trim"
            className="field-input"
            placeholder="RS"
            value={form.trim}
            onChange={(event) => set_form_data('trim', event.target.value)}
          />
        </Field>

        <Field label="Biển số" htmlFor="ap-plate" optional>
          <input
            id="ap-plate"
            data-agent-field="plate_no"
            className="field-input"
            placeholder="30A-123.45"
            value={form.plate_no}
            onChange={(event) => set_form_data('plate_no', event.target.value)}
          />
        </Field>

        <Field label="Số km đã đi" htmlFor="ap-odo">
          <input
            id="ap-odo"
            data-agent-field="odo_km"
            className="field-input"
            inputMode="numeric"
            placeholder="40000"
            value={form.odo_km}
            onChange={(event) => set_form_data('odo_km', event.target.value)}
          />
        </Field>

        <Field label="Ngày đăng ký lần đầu" htmlFor="ap-registered">
          <input
            id="ap-registered"
            data-agent-field="first_registration_date"
            type="date"
            className="field-input"
            value={form.first_registration_date}
            onChange={(event) => set_form_data('first_registration_date', event.target.value)}
          />
        </Field>
      </div>

      <div className="mt-4 border-t border-slate-100 pt-4">
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Điều kiện loại trừ cứng
        </div>
        <div className="mt-2.5 grid gap-2 sm:grid-cols-2">
          {Object.entries(flag_labels).map(([code, label]) => (
            <label
              key={code}
              className="flex cursor-pointer items-center gap-2.5 rounded-xl border border-slate-200 px-3 py-2.5 text-sm"
            >
              <input
                type="checkbox"
                data-agent-field={`flag_${code}`}
                className="h-4 w-4 rounded border-slate-300 text-rose-600 focus:ring-rose-400"
                checked={Boolean(flags[code])}
                onChange={(event) => set_form_data(`flag_${code}`, event.target.checked ? '1' : '')}
              />
              <span>{label}</span>
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}

function EligibilityPanel({ checks, ready }) {
  if (!ready) return null;
  if (checks.length === 0) return null;

  const failed = checks.filter((check) => !check.passed);

  return (
    <div className="card p-5">
      <h3 className="flex items-center gap-2 text-sm font-bold">
        <ShieldAlert className="h-4 w-4 text-brand-600" />
        Kiểm tra điều kiện đầu vào
        <span
          className={`ml-auto rounded-full px-2.5 py-1 text-xs font-semibold ${
            failed.length > 0
              ? 'bg-rose-100 text-rose-700'
              : 'bg-emerald-100 text-emerald-700'
          }`}
        >
          {failed.length > 0 ? `Trượt ${failed.length} mục` : 'Đạt toàn bộ'}
        </span>
      </h3>

      <ul className="mt-3 space-y-2">
        {checks.map((check) => (
          <li
            key={check.code}
            className={`flex items-start gap-2.5 rounded-xl px-3 py-2.5 text-sm ${
              check.passed ? 'bg-slate-50' : 'bg-rose-50'
            }`}
          >
            {check.passed ? (
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
            ) : (
              <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
            )}
            <div className="min-w-0">
              <div className="font-medium text-ink-900">{check.label}</div>
              <div className="text-xs text-slate-500">{check.detail}</div>
              {!check.passed && <p className="mt-1 text-xs text-rose-700">{check.why}</p>}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ScorePanel({ criteria, levels, set_form_data }) {
  const manual = criteria.filter((item) => !item.auto);
  const auto = criteria.find((item) => item.auto);

  return (
    <div className="card p-5">
      <h3 className="text-sm font-bold">Chấm điểm thẩm định</h3>
      <p className="mt-1 text-xs text-slate-500">
        Tiêu chí chưa chấm sẽ được tạm tính mức Khá và đánh dấu là ước lượng trong kết quả.
      </p>

      {auto && (
        <div className="mt-3 flex items-center gap-2.5 rounded-xl bg-slate-50 px-3 py-2.5 text-sm">
          <Gauge className="h-4 w-4 shrink-0 text-slate-400" />
          <span className="font-medium">{auto.label}</span>
          <span className="ml-auto text-xs text-slate-500">
            {auto.weight_pct}% · hệ thống tự tính từ ODO và tuổi xe
          </span>
        </div>
      )}

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {manual.map((item) => (
          <div key={item.code}>
            <label className="field-label" htmlFor={`ap-score-${item.code}`}>
              {item.label} <span className="text-slate-400">({item.weight_pct}%)</span>
            </label>
            <select
              id={`ap-score-${item.code}`}
              data-agent-field={`score_${item.code}`}
              className="field-input"
              value={levels[item.code] ?? ''}
              onChange={(event) => set_form_data(`score_${item.code}`, event.target.value)}
            >
              <option value="">Chưa thẩm định</option>
              {level_options.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        ))}
      </div>
    </div>
  );
}

function ResultPanel({ result }) {
  const { appraisal, quote } = result;
  const estimated = (appraisal.scores ?? []).filter((score) => score.estimated);

  if (appraisal.eligibility_status !== 'passed') {
    return (
      <div className="card border-rose-200 bg-rose-50/50 p-5">
        <h3 className="flex items-center gap-2 text-sm font-bold text-rose-800">
          <XCircle className="h-4 w-4" />
          Hồ sơ {appraisal.code} — không đủ điều kiện đổi xe
        </h3>
        <p className="mt-1.5 text-sm text-rose-700">
          Đã lưu lại để có căn cứ trả lời khách. Không tạo giao dịch đổi xe.
        </p>
      </div>
    );
  }

  return (
    <div className="card p-5">
      <h3 className="flex items-center gap-2 text-sm font-bold">
        <Calculator className="h-4 w-4 text-brand-600" />
        Kết quả hồ sơ {appraisal.code}
      </h3>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl bg-slate-50 p-4">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Bước 1 — giá thu xe cũ (A)
          </div>
          <dl className="mt-2.5 space-y-1.5 text-sm">
            <Row label="Giá thị trường cùng đời" value={format_price(appraisal.market_price)} />
            <Row label="Tổng điểm đạt" value={`${appraisal.total_score_pct}%`} />
            <Row label="Chi phí sửa chữa" value={`− ${format_price(appraisal.repair_cost)}`} />
          </dl>
          <div className="mt-3 border-t border-slate-200 pt-2.5 text-right">
            <div className="text-xs text-slate-500">A</div>
            <div className="text-xl font-extrabold text-brand-700">
              {format_price(appraisal.value_a)}
            </div>
          </div>
        </div>

        {quote && (
          <div className="rounded-2xl bg-slate-50 p-4">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Bước 2 & 3 — khách trả thêm (C)
            </div>
            <dl className="mt-2.5 space-y-1.5 text-sm">
              <Row label={`Giá niêm yết ${quote.model}`} value={format_price(quote.list_price)} />
              <Row label="Phí lăn bánh" value={format_price(quote.total_fees)} />
              <Row label="Tổng chi phí xe mới (B)" value={format_price(quote.value_b)} />
              <Row label="Trừ giá thu xe cũ" value={`− ${format_price(quote.value_a)}`} />
              <Row label="Trừ khuyến mãi" value={`− ${format_price(quote.promo_new_car)}`} />
              <Row label="Trừ ưu đãi đổi xe" value={`− ${format_price(quote.trade_in_bonus)}`} />
            </dl>
            <div className="mt-3 border-t border-slate-200 pt-2.5 text-right">
              <div className="text-xs text-slate-500">C</div>
              <div
                className={`text-xl font-extrabold ${
                  quote.amount_c < 0 ? 'text-amber-600' : 'text-brand-700'
                }`}
              >
                {format_price(quote.amount_c)}
              </div>
            </div>
          </div>
        )}
      </div>

      {quote && quote.amount_c < 0 && (
        <p className="mt-4 flex items-start gap-1.5 rounded-xl bg-amber-50 px-3 py-2.5 text-xs text-amber-800">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            Số tiền ra âm nghĩa là hãng phải hoàn lại cho khách — kiểm tra lại chi phí sửa chữa
            và mức chấm điểm trước khi báo khách.
          </span>
        </p>
      )}

      {estimated.length > 0 && (
        <p className="mt-3 flex items-start gap-1.5 rounded-xl bg-slate-100 px-3 py-2.5 text-xs text-slate-600">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            {estimated.length} tiêu chí chưa có đánh giá của thẩm định viên, đang tạm tính mức
            Khá. Con số sẽ đổi khi có biên bản thật.
          </span>
        </p>
      )}

      {appraisal.sla_due_at && (
        <p className="mt-3 text-xs text-slate-400">
          Đã chuyển Smart Solution ({appraisal.smart_solution_ref}) — hạn có kết quả:{' '}
          {format_date(appraisal.sla_due_at)}
        </p>
      )}
    </div>
  );
}

function HistoryPanel({ appraisals }) {
  if (appraisals.length === 0) return null;

  return (
    <div className="card p-5">
      <h3 className="text-sm font-bold">Hồ sơ định giá của khách này</h3>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[560px] text-sm">
          <thead className="text-left text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="py-2">Mã</th>
              <th className="py-2">Xe cũ</th>
              <th className="py-2 text-right">Điểm</th>
              <th className="py-2 text-right">Giá thu (A)</th>
              <th className="py-2 text-right">Trả thêm (C)</th>
              <th className="py-2">Trạng thái</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {appraisals.map((row) => {
              const latest = row.quotes?.[row.quotes.length - 1];
              return (
                <tr key={row.code ?? row.id}>
                  <td className="py-2.5 font-mono text-xs font-semibold text-brand-700">
                    {row.code}
                  </td>
                  <td className="py-2.5">
                    {row.make} {row.model} {row.year}
                  </td>
                  <td className="py-2.5 text-right">
                    {row.eligibility_status === 'passed' ? `${row.total_score_pct}%` : '—'}
                  </td>
                  <td className="py-2.5 text-right">
                    {row.value_a ? format_price(row.value_a) : '—'}
                  </td>
                  <td className="py-2.5 text-right">
                    {latest ? format_price(latest.amount_c) : '—'}
                  </td>
                  <td className="py-2.5">
                    <span
                      className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${
                        status_styles[row.status] ?? status_styles.draft
                      }`}
                    >
                      {status_labels[row.status] ?? row.status}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Field({ label, htmlFor, optional, children }) {
  return (
    <div>
      <label className="field-label" htmlFor={htmlFor}>
        {label} {optional && <span className="text-slate-400">(không bắt buộc)</span>}
      </label>
      {children}
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-ink-900">{value}</dd>
    </div>
  );
}
