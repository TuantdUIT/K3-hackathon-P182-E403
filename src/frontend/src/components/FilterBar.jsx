import { SlidersHorizontal } from 'lucide-react';

import { segments } from '../data/vehicles.js';

const lines = [
  { value: 'all', label: 'Tất cả' },
  { value: 'personal', label: 'Xe cá nhân' },
  { value: 'service', label: 'Xe dịch vụ' },
];

const sorts = [
  { value: 'default', label: 'Mặc định' },
  { value: 'price-asc', label: 'Giá thấp → cao' },
  { value: 'price-desc', label: 'Giá cao → thấp' },
  { value: 'range-desc', label: 'Quãng đường xa nhất' },
];

export default function FilterBar({ filters, on_change, total }) {
  const update = (patch) => on_change({ ...filters, ...patch });

  return (
    <section id="vehicles" className="border-b border-slate-200 bg-white">
      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="flex items-center gap-2 text-2xl font-bold">
              <SlidersHorizontal className="h-5 w-5 text-brand-600" />
              Dải xe điện VinFast
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Đang hiển thị {total} mẫu xe. Tất cả đều có xe lái thử tại Hà Nội.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <label className="text-sm">
              <span className="mr-2 text-slate-500">Phân khúc</span>
              <select
                className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"
                value={filters.segment}
                onChange={(event) => update({ segment: event.target.value })}
              >
                <option value="all">Tất cả</option>
                {segments.map((segment) => (
                  <option key={segment} value={segment}>
                    {segment}
                  </option>
                ))}
              </select>
            </label>

            <label className="text-sm">
              <span className="mr-2 text-slate-500">Sắp xếp</span>
              <select
                className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"
                value={filters.sort}
                onChange={(event) => update({ sort: event.target.value })}
              >
                {sorts.map((sort) => (
                  <option key={sort.value} value={sort.value}>
                    {sort.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          {lines.map((line) => {
            const active = filters.line === line.value;
            return (
              <button
                key={line.value}
                type="button"
                onClick={() => update({ line: line.value })}
                className={`rounded-full px-4 py-1.5 text-sm font-semibold transition ${
                  active
                    ? 'bg-brand-600 text-white'
                    : 'border border-slate-300 bg-white text-slate-600 hover:bg-slate-50'
                }`}
              >
                {line.label}
              </button>
            );
          })}
        </div>
      </div>
    </section>
  );
}
