import { HttpAgent } from '@ag-ui/client';
import { CopilotKit } from '@copilotkit/react-core';
import React from 'react';
import ReactDOM from 'react-dom/client';

import App from './App.jsx';
import './index.css';
import { NavigationProvider, useNavigation } from './lib/navigation.jsx';

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

// Hằng số ở module scope, KHÔNG viết object literal thẳng trong JSX:
// `CopilotKitProvider` so sánh prop này theo tham chiếu và bắn console.error khi
// thấy nó đổi sau lần mount đầu. Literal inline sẽ tạo object mới mỗi render.
const AGENTS = { test_drive_agent, crm_lead_agent, swap_car_agent };

// Ba agent nói ba giọng khác nhau (với khách / với sales về lead / với sales về
// xe cũ) nên chọn theo ĐƯỜNG DẪN. Tên phải khớp CHÍNH XÁC với
// `LangGraphAgent(name=...)` ở backend và tham số của `useCoAgent` — lệch một ký
// tự thì chat im lặng, không báo lỗi ở đâu.
function pick_agent(pathname) {
  if (pathname.startsWith('/admin-portal/dinh-gia')) return 'swap_car_agent';
  if (pathname.startsWith('/admin-portal')) return 'crm_lead_agent';
  return 'test_drive_agent';
}

/**
 * `key={active_agent}` là CỐ Ý, không phải thừa.
 *
 * `CopilotKitProvider` dựng core của nó một lần duy nhất
 * (`if (copilotkitRef.current === null)`) rồi giữ trong ref — đổi prop sau đó
 * không dựng lại. Ép remount bằng `key` là cách chắc chắn để mỗi agent có một
 * cây provider sạch: hội thoại, thread và state của tab trước không rò sang tab
 * sau. Đổi lại chỉ là remount một cây React, rẻ hơn nhiều so với tải lại trang.
 */
function AgentBoundary() {
  const { path } = useNavigation();
  const active_agent = pick_agent(path);

  return (
    <CopilotKit
      key={active_agent}
      agents__unsafe_dev_only={AGENTS}
      agent={active_agent}
      showDevConsole={false}
    >
      <App />
    </CopilotKit>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <NavigationProvider>
      <AgentBoundary />
    </NavigationProvider>
  </React.StrictMode>,
);
