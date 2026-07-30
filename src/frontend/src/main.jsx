import { HttpAgent } from '@ag-ui/client';
import { CopilotKit } from '@copilotkit/react-core';
import React from 'react';
import ReactDOM from 'react-dom/client';

import App from './App.jsx';
import './index.css';

const test_drive_url = import.meta.env.VITE_AGENT_URL ?? 'http://localhost:8000/agent/test-drive';
const crm_lead_url =
  import.meta.env.VITE_CRM_AGENT_URL ?? 'http://localhost:8000/agent/crm-lead';
const swap_car_url =
  import.meta.env.VITE_SWAP_AGENT_URL ?? 'http://localhost:8000/agent/swap-car';

// BẪY #2 — nối THẲNG tới endpoint AG-UI của FastAPI qua HttpAgent.
// Không dựng CopilotKit Runtime trên Node: react-core 1.63 đọc được AG-UI (v2),
// còn `CopilotKitRemoteEndpoint` ở backend chỉ nói remote-endpoint v1.
const test_drive_agent = new HttpAgent({ url: test_drive_url });
const crm_lead_agent = new HttpAgent({ url: crm_lead_url });
const swap_car_agent = new HttpAgent({ url: swap_car_url });

// Ba agent nói ba giọng khác nhau (với khách / với sales về lead / với sales về
// xe cũ) nên chọn theo ĐƯỜNG DẪN. Mỗi trang là một lần full page load riêng, không
// bao giờ mount hai agent cùng lúc — đó cũng là lý do tab "Định giá xe" có path
// riêng thay vì đổi tab bằng state React.
// Tên phải khớp CHÍNH XÁC với `LangGraphAgent(name=...)` ở backend và tham số của
// `useCoAgent` — lệch một ký tự thì chat im lặng, không báo lỗi ở đâu.
function pick_agent(pathname) {
  if (pathname.startsWith('/admin-portal/dinh-gia')) return 'swap_car_agent';
  if (pathname.startsWith('/admin-portal')) return 'crm_lead_agent';
  return 'test_drive_agent';
}

const active_agent = pick_agent(window.location.pathname);

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <CopilotKit
      agents__unsafe_dev_only={{ test_drive_agent, crm_lead_agent, swap_car_agent }}
      agent={active_agent}
      showDevConsole={false}
    >
      <App />
    </CopilotKit>
  </React.StrictMode>,
);
