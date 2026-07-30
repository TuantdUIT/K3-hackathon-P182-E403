import { AnimatePresence, motion } from 'framer-motion';
import {
  BatteryCharging,
  LayoutDashboard,
  Loader2,
  LogOut,
  Mail,
  MapPin,
  Phone,
  RefreshCw,
  Search,
  Users,
  X,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { find_vehicle } from '../data/vehicles.js';
import { fetch_customers, login, update_customer_status } from '../lib/api.js';
import { format_date_long, format_datetime } from '../lib/formatDate.js';

const statuses = ['Mới', 'Đã liên hệ', 'Đặt lịch', 'Không phù hợp'];

const status_styles = {
  'Mới': 'bg-brand-100 text-brand-700 border-brand-200',
  'Đã liên hệ': 'bg-amber-100 text-amber-700 border-amber-200',
  'Đặt lịch': 'bg-emerald-100 text-emerald-700 border-emerald-200',
  'Không phù hợp': 'bg-slate-100 text-slate-600 border-slate-200',
};

const SESSION_KEY = 'vinfast_admin_staff';

export default function AdminPortal() {
  const [staff, set_staff] = useState(() => {
    try {
      const raw = sessionStorage.getItem(SESSION_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });

  const on_logged_in = (logged_in_staff) => {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(logged_in_staff));
    set_staff(logged_in_staff);
  };

  const on_logout = () => {
    sessionStorage.removeItem(SESSION_KEY);
    set_staff(null);
  };

  if (!staff) return <LoginScreen on_logged_in={on_logged_in} />;
  return <Dashboard staff={staff} on_logout={on_logout} />;
}

function LoginScreen({ on_logged_in }) {
  const [email, set_email] = useState('');
  const [password, set_password] = useState('');
  const [error_message, set_error_message] = useState('');
  const [busy, set_busy] = useState(false);

  const on_submit = async (event) => {
    event.preventDefault();
    set_error_message('');
    set_busy(true);
    try {
      const result = await login(email, password);
      on_logged_in(result.staff);
    } catch (error) {
      set_error_message(error.message);
    } finally {
      set_busy(false);
    }
  };

  return (
    <div className="grid min-h-screen place-items-center bg-ink-900 px-4">
      <div className="w-full max-w-md rounded-3xl bg-white p-8 shadow-lift">
        <div className="flex items-center gap-2.5">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand-600 text-white">
            <BatteryCharging className="h-5 w-5" />
          </span>
          <div>
            <div className="text-lg font-extrabold">VinFast CRM</div>
            <div className="text-xs text-slate-500">Cổng nhân viên kinh doanh</div>
          </div>
        </div>

        <form onSubmit={on_submit} className="mt-7">
          <label className="field-label" htmlFor="admin-email">
            Email công ty
          </label>
          <input
            id="admin-email"
            type="email"
            className="field-input"
            required
            autoComplete="username"
            placeholder="lan.anh@vinfast.vn"
            value={email}
            onChange={(event) => set_email(event.target.value)}
          />

          <label className="field-label mt-4" htmlFor="admin-password">
            Mật khẩu
          </label>
          <input
            id="admin-password"
            type="password"
            className="field-input"
            required
            autoComplete="current-password"
            value={password}
            onChange={(event) => set_password(event.target.value)}
          />

          {error_message && (
            <p className="mt-4 rounded-xl bg-rose-50 px-3.5 py-2.5 text-sm text-rose-700">
              {error_message}
            </p>
          )}

          <button type="submit" className="btn-primary mt-6 w-full py-3" disabled={busy}>
            {busy && <Loader2 className="h-4 w-4 animate-spin" />}
            {busy ? 'Đang kiểm tra...' : 'Đăng nhập'}
          </button>
        </form>

        <a href="/" className="mt-5 block text-center text-sm text-slate-500 hover:text-brand-600">
          ← Về trang khách hàng
        </a>
      </div>
    </div>
  );
}

function Dashboard({ staff, on_logout }) {
  const [customers, set_customers] = useState([]);
  const [search, set_search] = useState('');
  const [status_filter, set_status_filter] = useState('');
  const [loading, set_loading] = useState(true);
  const [error_message, set_error_message] = useState('');
  const [selected, set_selected] = useState(null);

  const load = useCallback(async () => {
    set_loading(true);
    set_error_message('');
    try {
      const data = await fetch_customers({ search, status: status_filter });
      set_customers(data);
    } catch (error) {
      set_error_message(error.message);
    } finally {
      set_loading(false);
    }
  }, [search, status_filter]);

  // Debounce ô search để không bắn request mỗi lần gõ một ký tự.
  useEffect(() => {
    const timer = setTimeout(load, 250);
    return () => clearTimeout(timer);
  }, [load]);

  const on_change_status = async (code, status) => {
    try {
      const updated = await update_customer_status(code, status);
      set_customers((previous) =>
        previous.map((customer) => (customer.code === code ? updated : customer)),
      );
      set_selected((previous) => (previous?.code === code ? updated : previous));
    } catch (error) {
      set_error_message(error.message);
    }
  };

  const counts = statuses.map((status) => ({
    status,
    total: customers.filter((customer) => customer.status === status).length,
  }));

  return (
    <div className="flex min-h-screen bg-slate-100">
      <aside className="hidden w-60 shrink-0 flex-col bg-ink-900 p-5 text-slate-300 lg:flex">
        <div className="flex items-center gap-2.5 text-white">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand-600">
            <BatteryCharging className="h-5 w-5" />
          </span>
          <span className="font-extrabold">VinFast CRM</span>
        </div>

        <nav className="mt-8 space-y-1 text-sm">
          <span className="flex items-center gap-2.5 rounded-xl bg-white/10 px-3 py-2.5 font-semibold text-white">
            <LayoutDashboard className="h-4 w-4" />
            Khách đăng ký lái thử
          </span>
          <span className="flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-slate-400">
            <Users className="h-4 w-4" />
            Nhân viên kinh doanh
          </span>
        </nav>

        <div className="mt-auto rounded-2xl bg-white/5 p-4">
          <div className="flex items-center gap-2.5">
            <span className="grid h-9 w-9 place-items-center rounded-full bg-brand-500 text-sm font-bold text-white">
              {staff.initials}
            </span>
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-white">{staff.name}</div>
              <div className="truncate text-xs text-slate-400">{staff.email}</div>
            </div>
          </div>
          <button
            type="button"
            onClick={on_logout}
            className="mt-3.5 flex w-full items-center justify-center gap-2 rounded-xl border border-white/20 py-2 text-sm font-semibold text-white transition hover:bg-white/10"
          >
            <LogOut className="h-4 w-4" />
            Đăng xuất
          </button>
        </div>
      </aside>

      <main className="min-w-0 flex-1 p-5 sm:p-7">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">Khách đăng ký lái thử</h1>
            <p className="mt-1 text-sm text-slate-500">
              Xin chào {staff.name} — có {customers.length} khách trong danh sách hiện tại.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button type="button" className="btn-ghost" onClick={load} disabled={loading}>
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              Tải lại
            </button>
            <button type="button" className="btn-ghost lg:hidden" onClick={on_logout}>
              <LogOut className="h-4 w-4" />
              Đăng xuất
            </button>
          </div>
        </header>

        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {counts.map((item) => (
            <div key={item.status} className="card p-4">
              <div className="text-xs uppercase tracking-wide text-slate-400">{item.status}</div>
              <div className="mt-1 text-2xl font-extrabold">{item.total}</div>
            </div>
          ))}
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <div className="relative min-w-[240px] flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              className="field-input pl-9"
              placeholder="Tìm theo mã, tên, số điện thoại, mẫu xe, phường..."
              value={search}
              onChange={(event) => set_search(event.target.value)}
            />
          </div>
          <select
            className="field-input w-auto"
            value={status_filter}
            onChange={(event) => set_status_filter(event.target.value)}
          >
            <option value="">Tất cả trạng thái</option>
            {statuses.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>
        </div>

        {error_message && (
          <p className="mt-4 rounded-xl bg-rose-50 px-3.5 py-2.5 text-sm text-rose-700">
            {error_message}
          </p>
        )}

        <div className="card mt-5 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Mã</th>
                  <th className="px-4 py-3">Khách hàng</th>
                  <th className="px-4 py-3">Mẫu xe</th>
                  <th className="px-4 py-3">Lịch hẹn</th>
                  <th className="px-4 py-3">Nguồn</th>
                  <th className="px-4 py-3">NVKD</th>
                  <th className="px-4 py-3">Trạng thái</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {loading && customers.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-4 py-10 text-center text-slate-400">
                      <Loader2 className="mx-auto h-5 w-5 animate-spin" />
                    </td>
                  </tr>
                )}

                {!loading && customers.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-4 py-10 text-center text-slate-400">
                      Chưa có khách nào khớp điều kiện tìm kiếm.
                    </td>
                  </tr>
                )}

                {customers.map((customer) => (
                  <tr
                    key={customer.code ?? customer.id}
                    onClick={() => set_selected(customer)}
                    className="cursor-pointer transition hover:bg-brand-50/50"
                  >
                    <td className="px-4 py-3 font-mono text-xs font-semibold text-brand-700">
                      {customer.code}
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-semibold">{customer.name}</div>
                      <div className="text-xs text-slate-500">{customer.phone}</div>
                    </td>
                    <td className="px-4 py-3">
                      {find_vehicle(customer.vehicle_id)?.name ?? customer.model}
                    </td>
                    <td className="px-4 py-3">
                      <div>{format_date_long(customer.test_drive_date)}</div>
                      <div className="text-xs text-slate-500">{customer.test_drive_time}</div>
                    </td>
                    <td className="px-4 py-3 text-slate-600">{customer.source}</td>
                    <td className="px-4 py-3">
                      {customer.sales_staff ? (
                        <span
                          title={customer.sales_staff.name}
                          className="grid h-8 w-8 place-items-center rounded-full bg-brand-100 text-xs font-bold text-brand-700"
                        >
                          {customer.sales_staff.initials}
                        </span>
                      ) : (
                        <span className="text-xs text-slate-400">Chưa phân</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={customer.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </main>

      <DetailPanel
        customer={selected}
        on_close={() => set_selected(null)}
        on_change_status={on_change_status}
      />
    </div>
  );
}

function StatusBadge({ status }) {
  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${
        status_styles[status] ?? status_styles['Không phù hợp']
      }`}
    >
      {status}
    </span>
  );
}

function DetailPanel({ customer, on_close, on_change_status }) {
  return (
    <AnimatePresence>
      {customer && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={on_close}
            className="fixed inset-0 z-40 bg-ink-900/40"
          />
          <motion.aside
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 28, stiffness: 260 }}
            className="fixed right-0 top-0 z-50 h-full w-full max-w-md overflow-y-auto bg-white p-6 shadow-lift"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="font-mono text-xs font-semibold text-brand-700">
                  {customer.code}
                </div>
                <h2 className="mt-1 text-xl font-bold">{customer.name}</h2>
                <div className="mt-1.5">
                  <StatusBadge status={customer.status} />
                </div>
              </div>
              <button
                type="button"
                onClick={on_close}
                className="grid h-9 w-9 place-items-center rounded-full text-slate-500 transition hover:bg-slate-100"
                aria-label="Đóng"
              >
                <X className="h-4.5 w-4.5" />
              </button>
            </div>

            <dl className="mt-6 space-y-3.5 text-sm">
              <Row icon={Phone} label="Số điện thoại" value={customer.phone} />
              <Row icon={Mail} label="Email" value={customer.email || 'Không cung cấp'} />
              <Row
                icon={BatteryCharging}
                label="Mẫu xe"
                value={find_vehicle(customer.vehicle_id)?.name ?? customer.model}
              />
              <Row
                icon={LayoutDashboard}
                label="Lịch hẹn"
                value={`${format_date_long(customer.test_drive_date)} · ${customer.test_drive_time}`}
              />
              <Row
                icon={MapPin}
                label="Địa điểm"
                value={`${customer.ward}, ${customer.province}`}
              />
              <Row
                icon={Users}
                label="NVKD phụ trách"
                value={customer.sales_staff?.name ?? 'Chưa phân công'}
              />
            </dl>

            {customer.note && (
              <div className="mt-5 rounded-xl bg-slate-50 p-3.5">
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                  Yêu cầu khác
                </div>
                <p className="mt-1 text-sm text-slate-700">{customer.note}</p>
              </div>
            )}

            <p className="mt-5 text-xs text-slate-400">
              Đăng ký lúc {format_datetime(customer.created_at)} · nguồn {customer.source}
            </p>

            <div className="mt-7 border-t border-slate-100 pt-5">
              <h3 className="text-sm font-semibold">Cập nhật trạng thái chăm sóc</h3>
              <div className="mt-3 grid grid-cols-2 gap-2">
                {statuses.map((status) => {
                  const active = customer.status === status;
                  return (
                    <button
                      key={status}
                      type="button"
                      disabled={active}
                      onClick={() => on_change_status(customer.code, status)}
                      className={`rounded-xl border px-3 py-2.5 text-sm font-semibold transition ${
                        active
                          ? 'border-brand-500 bg-brand-600 text-white'
                          : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50'
                      }`}
                    >
                      {status}
                    </button>
                  );
                })}
              </div>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

function Row({ icon: Icon, label, value }) {
  return (
    <div className="flex items-start gap-3">
      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
      <div className="min-w-0">
        <dt className="text-xs uppercase tracking-wide text-slate-400">{label}</dt>
        <dd className="font-medium text-ink-900">{value}</dd>
      </div>
    </div>
  );
}
