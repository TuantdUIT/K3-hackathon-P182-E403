import { HttpAgent } from '@ag-ui/client';
import { CopilotKit } from '@copilotkit/react-core';
import React from 'react';
import ReactDOM from 'react-dom/client';

import App from './App.jsx';
import './index.css';

const agent_url = import.meta.env.VITE_AGENT_URL ?? 'http://localhost:8000/agent/test-drive';

// BẪY #2 — nối THẲNG tới endpoint AG-UI của FastAPI qua HttpAgent.
// Không dựng CopilotKit Runtime trên Node: react-core 1.63 đọc được AG-UI (v2),
// còn `CopilotKitRemoteEndpoint` ở backend chỉ nói remote-endpoint v1.
const test_drive_agent = new HttpAgent({ url: agent_url });

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <CopilotKit
      agents__unsafe_dev_only={{ test_drive_agent }}
      agent="test_drive_agent"
      showDevConsole={false}
    >
      <App />
    </CopilotKit>
  </React.StrictMode>,
);
