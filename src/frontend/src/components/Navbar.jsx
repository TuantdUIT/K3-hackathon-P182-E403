import { BatteryCharging, Menu, X } from 'lucide-react';
import { useState } from 'react';

const nav_links = [
  { href: '#vehicles', label: 'Dải sản phẩm' },
  { href: '#accessories', label: 'Phụ kiện' },
  { href: '#charging', label: 'Trạm sạc' },
  { href: '/admin-portal', label: 'Dành cho NVKD' },
];

export default function Navbar({ on_test_drive }) {
  const [mobile_open, set_mobile_open] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3.5 sm:px-6">
        <a href="/" className="flex items-center gap-2.5">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand-600 text-white">
            <BatteryCharging className="h-5 w-5" />
          </span>
          <span className="text-lg font-extrabold tracking-tight">
            VinFast <span className="text-brand-600">Electric</span>
          </span>
        </a>

        <nav className="hidden items-center gap-7 md:flex">
          {nav_links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-sm font-medium text-slate-600 transition hover:text-brand-600"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <button type="button" className="btn-primary hidden sm:inline-flex" onClick={on_test_drive}>
            Đăng ký lái thử
          </button>
          <button
            type="button"
            className="grid h-10 w-10 place-items-center rounded-xl border border-slate-300 md:hidden"
            onClick={() => set_mobile_open((previous) => !previous)}
            aria-label="Mở menu"
          >
            {mobile_open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {mobile_open && (
        <nav className="border-t border-slate-200 bg-white px-4 py-3 md:hidden">
          {nav_links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="block py-2 text-sm font-medium text-slate-700"
              onClick={() => set_mobile_open(false)}
            >
              {link.label}
            </a>
          ))}
          <button type="button" className="btn-primary mt-2 w-full" onClick={on_test_drive}>
            Đăng ký lái thử
          </button>
        </nav>
      )}
    </header>
  );
}
