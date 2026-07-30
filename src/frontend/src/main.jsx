import { HttpAgent } from '@ag-ui/client';
import { CopilotKit } from '@copilotkit/react-core';
import React from 'react';
import ReactDOM from 'react-dom/client';

import App from './App.jsx';
import './index.css';

const test_drive_url = import.meta.env.VITE_AGENT_URL ?? 'http://localhost:8000/agent/test-drive';
const crm_lead_url =
  import.meta.env.VITE_CRM_AGENT_URL ?? 'http://localhost:8000/agent/crm-lead';

// BẪY #2 — nối THẲNG tới endpoint AG-UI của FastAPI qua HttpAgent.
// Không dựng CopilotKit Runtime trên Node: react-core 1.63 đọc được AG-UI (v2),
// còn `CopilotKitRemoteEndpoint` ở backend chỉ nói remote-endpoint v1.
const test_drive_agent = new HttpAgent({ url: test_drive_url });
const crm_lead_agent = new HttpAgent({ url: crm_lead_url });

// Hai agent nói hai giọng khác nhau (với khách vs với sales) nên chọn theo trang.
// `/admin-portal` là một lần full page load riêng, không bao giờ mount cùng lúc với
// trang khách. Tên phải khớp CHÍNH XÁC với `LangGraphAgent(name=...)` ở backend và
// tham số của `useCoAgent` — lệch một ký tự thì chat im lặng, không báo lỗi ở đâu.
const active_agent =
  window.location.pathname === '/admin-portal' ? 'crm_lead_agent' : 'test_drive_agent';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <CopilotKit
      agents__unsafe_dev_only={{ test_drive_agent, crm_lead_agent }}
      agent={active_agent}
      showDevConsole={false}
    >
      <App />
    </CopilotKit>
  </React.StrictMode>,
);
