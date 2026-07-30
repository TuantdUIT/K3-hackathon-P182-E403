import { BatteryCharging, MapPin, Phone } from 'lucide-react';

const showrooms = [
  'VinFast Long Biên — Số 7 Nguyễn Văn Linh, Long Biên',
  'VinFast Cầu Giấy — 458 Xuân Thuỷ, Cầu Giấy',
  'VinFast Hà Đông — 91 Lê Trọng Tấn, Hà Đông',
];

export default function Footer() {
  return (
    <footer id="charging" className="bg-ink-900 text-slate-300">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-14 sm:px-6 lg:grid-cols-3">
        <div>
          <div className="flex items-center gap-2.5 text-white">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand-600">
              <BatteryCharging className="h-5 w-5" />
            </span>
            <span className="text-lg font-extrabold">VinFast Electric</span>
          </div>
          <p className="mt-4 text-sm">
            Trang demo phục vụ trình diễn AI Copilot điền form lái thử. Dữ liệu nhập vào chỉ lưu trong
            môi trường demo.
          </p>
        </div>

        <div>
          <h3 className="font-semibold text-white">Showroom tại Hà Nội</h3>
          <ul className="mt-4 space-y-2.5 text-sm">
            {showrooms.map((showroom) => (
              <li key={showroom} className="flex gap-2">
                <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-brand-400" />
                {showroom}
              </li>
            ))}
          </ul>
        </div>

        <div>
          <h3 className="font-semibold text-white">Liên hệ</h3>
          <p className="mt-4 flex items-center gap-2 text-sm">
            <Phone className="h-4 w-4 text-brand-400" />
            Hotline: <span className="font-semibold text-white">1900 23 23 89</span>
          </p>
          <p className="mt-2 text-sm">Giờ làm việc: 08:00 – 18:00, tất cả các ngày trong tuần.</p>
          <a
            href="/admin-portal"
            className="mt-5 inline-flex rounded-xl border border-white/25 px-4 py-2 text-sm font-semibold text-white transition hover:bg-white/10"
          >
            Cổng nhân viên kinh doanh
          </a>
        </div>
      </div>

      <div className="border-t border-white/10 py-5 text-center text-xs">
        © {new Date().getFullYear()} VinFast Electric Showcase — bản demo phục vụ nghiên cứu.
      </div>
    </footer>
  );
}
