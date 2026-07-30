// Lớp gọi REST API. VITE_API_URL rỗng = cùng origin (bản docker đi qua nginx).
const api_base = import.meta.env.VITE_API_URL ?? '';

const build_url = (path) => `${api_base}/api/v1${path}`;

async function request(path, options = {}) {
  const response = await fetch(build_url(path), {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    // Backend trả `detail` đã dịch sẵn sang tiếng Việt.
    const message =
      payload?.detail ?? `Không kết nối được máy chủ (mã ${response.status}). Vui lòng thử lại.`;
    const error = new Error(typeof message === 'string' ? message : JSON.stringify(message));
    error.status = response.status;
    error.errors = payload?.errors ?? [];
    throw error;
  }

  return payload;
}

export const login = (email, password) =>
  request('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });

export const create_test_drive = (payload) =>
  request('/test-drives', { method: 'POST', body: JSON.stringify(payload) });

export const fetch_customers = ({ search = '', status = '' } = {}) => {
  const params = new URLSearchParams();
  if (search) params.set('search', search);
  if (status) params.set('status', status);
  const suffix = params.toString();
  return request(`/customers${suffix ? `?${suffix}` : ''}`);
};

/**
 * Tra trùng cho form CRM. Trả `{ phone_match, name_matches }`.
 * `phone_match` = trùng CỨNG (chặn submit), `name_matches` = trùng MỀM (chỉ cảnh báo).
 */
export const check_duplicate = ({ phone = '', name = '' } = {}) => {
  const params = new URLSearchParams();
  if (phone) params.set('phone', phone);
  if (name) params.set('name', name);
  return request(`/customers/check-duplicate?${params.toString()}`);
};

export const update_customer_status = (code, status) =>
  request(`/customers/${encodeURIComponent(code)}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  });

export const fetch_sales_staff = () => request('/sales-staff');
