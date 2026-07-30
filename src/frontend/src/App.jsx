import { useCoAgent, useLangGraphInterrupt } from '@copilotkit/react-core';
import { CopilotPopup } from '@copilotkit/react-ui';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import AccessorySection from './components/AccessorySection.jsx';
import AdminPortal from './components/AdminPortal.jsx';
import AgentApprovalCard from './components/AgentApprovalCard.jsx';
import AgentCursor from './components/AgentCursor.jsx';
import ChatAutoHide from './components/ChatAutoHide.jsx';
import FilterBar from './components/FilterBar.jsx';
import Footer from './components/Footer.jsx';
import Hero from './components/Hero.jsx';
import Navbar from './components/Navbar.jsx';
import TestDriveModal from './components/TestDriveModal.jsx';
import VehicleGrid from './components/VehicleGrid.jsx';
import { vehicles } from './data/vehicles.js';
import useAgentActionRunner from './lib/useAgentActionRunner.js';
import useAgentCursor from './lib/useAgentCursor.js';

const empty_form = {
  name: '',
  phone: '',
  email: '',
  test_drive_date: '',
  test_drive_time: '',
  ward: '',
  note: '',
};

const default_vehicle_id = 'vf8';

export default function App() {
  if (window.location.pathname === '/admin-portal') {
    return <AdminPortal />;
  }
  return <Showcase />;
}

function Showcase() {
  // --- State form được NÂNG LÊN App ---
  // Khách và agent phải ghi vào cùng một chỗ; nếu để state trong TestDriveModal
  // thì agent điền xong, modal unmount là mất sạch.
  const [form_data, set_form_data_raw] = useState(empty_form);
  const [selected_vehicle_id, set_selected_vehicle_id] = useState(default_vehicle_id);
  const [ward_notice, set_ward_notice] = useState('');

  const [modal_open, set_modal_open] = useState(false);
  const [animation_idle, set_animation_idle] = useState(true);
  const [filters, set_filters] = useState({ segment: 'all', line: 'all', sort: 'default' });

  const ward_select_ref = useRef(null);
  const last_run_seq_ref = useRef(null);

  const { cursor, controls } = useAgentCursor();

  const { state: agent_state } = useCoAgent({
    name: 'test_drive_agent',
    initialState: { draft: {}, status: 'idle', current_action: null },
  });

  const agent_status = agent_state?.status ?? 'idle';
  const current_action = agent_state?.current_action ?? null;
  const run_seq = agent_state?.run_seq ?? null;
  const run_kind = agent_state?.run_kind ?? 'full';
  const agent_submission_code = agent_state?.submission_code ?? null;

  const set_form_data = useCallback((field, value) => {
    if (field === 'vehicle_id') {
      set_selected_vehicle_id(value);
      return;
    }
    set_form_data_raw((previous) => ({ ...previous, [field]: value }));
  }, []);

  const reset_form = useCallback(() => {
    set_form_data_raw(empty_form);
    set_selected_vehicle_id(default_vehicle_id);
    set_ward_notice('');
  }, []);

  // Agent bắt đầu điền -> mở form để khách nhìn thấy con trỏ làm việc.
  useEffect(() => {
    if (agent_status === 'filling') {
      set_modal_open(true);
      set_animation_idle(false);
    }
  }, [agent_status]);

  // Lượt mới dạng "full" = khách mới -> xoá sạch form.
  // Lượt "correction" phải GIỮ NGUYÊN, vì nó chỉ điền lại vài ô đã đổi.
  useEffect(() => {
    if (run_seq === null || run_seq === last_run_seq_ref.current) return;
    last_run_seq_ref.current = run_seq;
    if (run_kind === 'full') reset_form();
  }, [run_seq, run_kind, reset_form]);

  const on_ward_needs_user = useCallback((ward_name, candidates = []) => {
    const hint =
      candidates.length > 1
        ? ` Có ${candidates.length} phường/xã trùng khớp, anh/chị chọn giúp em ạ.`
        : '';
    set_ward_notice(
      `Em chưa xác định chắc chắn phường/xã "${ward_name}".${hint} Anh/chị chọn lại ở ô Phường/Xã nhé.`,
    );
  }, []);

  const on_queue_idle = useCallback(() => set_animation_idle(true), []);

  useAgentActionRunner({
    current_action,
    controls,
    set_form_data,
    ward_select_ref,
    on_ward_needs_user,
    on_queue_idle,
  });

  // Thu gọn chat khi con trỏ đang làm việc để khách thấy form.
  // Backend có thể sang trạng thái `confirming` TRƯỚC khi animation chạy hết,
  // nên phải chờ cả hai điều kiện mới mở chat lại.
  const collapse_chat = agent_status === 'filling' || !animation_idle;

  useLangGraphInterrupt({
    render: ({ event, resolve }) => <AgentApprovalCard event={event} resolve={resolve} />,
  });

  const visible_vehicles = useMemo(() => {
    let list = vehicles.slice();
    if (filters.segment !== 'all') list = list.filter((v) => v.segment === filters.segment);
    if (filters.line !== 'all') list = list.filter((v) => v.line === filters.line);
    if (filters.sort === 'price-asc') list.sort((a, b) => a.priceFrom - b.priceFrom);
    if (filters.sort === 'price-desc') list.sort((a, b) => b.priceFrom - a.priceFrom);
    if (filters.sort === 'range-desc') list.sort((a, b) => b.range - a.range);
    return list;
  }, [filters]);

  const open_test_drive = useCallback((vehicle_id) => {
    if (vehicle_id) set_selected_vehicle_id(vehicle_id);
    set_modal_open(true);
  }, []);

  return (
    <div className="min-h-screen bg-slate-50">
      <Navbar on_test_drive={() => open_test_drive(null)} />

      <main>
        <Hero on_test_drive={() => open_test_drive(null)} />
        <FilterBar filters={filters} on_change={set_filters} total={visible_vehicles.length} />
        <VehicleGrid vehicles={visible_vehicles} on_test_drive={open_test_drive} />
        <AccessorySection />
      </main>

      <Footer />

      <TestDriveModal
        open={modal_open}
        on_close={() => set_modal_open(false)}
        form_data={form_data}
        set_form_data={set_form_data}
        selected_vehicle_id={selected_vehicle_id}
        ward_notice={ward_notice}
        set_ward_notice={set_ward_notice}
        ward_select_ref={ward_select_ref}
        agent_submission_code={agent_submission_code}
        run_seq={run_seq}
        run_kind={run_kind}
        on_reset={reset_form}
      />

      <AgentCursor cursor={cursor} />

      <CopilotPopup
        instructions="Bạn là trợ lý đăng ký lái thử xe điện VinFast tại Hà Nội. Luôn trả lời bằng tiếng Việt, gọi khách là anh/chị."
        labels={{
          title: 'VinFast Copilot',
          initial:
            'Chào anh/chị! Anh/chị nhắn cho em thông tin lái thử là em điền form giúp luôn ạ.\n\nVí dụ: "Tôi là Nam, 0912345678, muốn lái thử VF 8 sáng mai ở Cầu Giấy".',
          placeholder: 'Nhắn thông tin lái thử của anh/chị...',
        }}
        // Thẻ xác nhận nằm TRONG khung chat: đóng chat lúc đang chờ interrupt là
        // graph đứng vĩnh viễn, nên không cho click ra ngoài để đóng.
        clickOutsideToClose={false}
        defaultOpen={false}
      >
        <ChatAutoHide collapse={collapse_chat} />
      </CopilotPopup>
    </div>
  );
}
