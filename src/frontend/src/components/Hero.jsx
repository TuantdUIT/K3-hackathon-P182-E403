import { motion } from 'framer-motion';
import { ArrowRight, Gauge, MapPin, Sparkles } from 'lucide-react';

const stats = [
  { label: 'Mẫu xe điện', value: '14' },
  { label: 'Quãng đường tối đa', value: '626 km' },
  { label: 'Trạm sạc tại Hà Nội', value: '180+' },
];

export default function Hero({ on_test_drive }) {
  return (
    <section className="relative overflow-hidden bg-ink-900 text-white">
      <div
        className="absolute inset-0 opacity-30"
        style={{
          backgroundImage:
            'url(https://images.unsplash.com/photo-1494976388531-d1058494cdd8?auto=format&fit=crop&w=1800&q=80)',
          backgroundSize: 'cover',
          backgroundPosition: 'center',
        }}
      />
      <div className="absolute inset-0 bg-gradient-to-r from-ink-900 via-ink-900/85 to-transparent" />

      <div className="relative mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:py-28">
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55 }}
          className="max-w-2xl"
        >
          <span className="inline-flex items-center gap-2 rounded-full border border-white/25 bg-white/10 px-3.5 py-1.5 text-xs font-semibold uppercase tracking-wide">
            <MapPin className="h-3.5 w-3.5" />
            Showroom Hà Nội
          </span>

          <h1 className="mt-5 text-4xl font-extrabold leading-tight sm:text-5xl lg:text-6xl">
            Lái thử xe điện VinFast, <span className="text-brand-300">đăng ký trong 30 giây</span>
          </h1>

          <p className="mt-5 text-lg text-slate-200">
            Chọn mẫu xe bạn quan tâm, hoặc nhắn cho AI Copilot ở góc màn hình — trợ lý sẽ tự mở form
            và điền hộ bạn từng ô, bạn chỉ cần xác nhận.
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-3">
            <button type="button" className="btn-primary px-6 py-3 text-base" onClick={on_test_drive}>
              Đăng ký lái thử
              <ArrowRight className="h-4 w-4" />
            </button>
            <a
              href="#vehicles"
              className="inline-flex items-center gap-2 rounded-xl border border-white/30 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/10"
            >
              <Gauge className="h-4 w-4" />
              Xem dải sản phẩm
            </a>
          </div>

          <div className="mt-10 flex flex-wrap gap-x-10 gap-y-4">
            {stats.map((stat) => (
              <div key={stat.label}>
                <div className="text-2xl font-bold text-brand-200">{stat.value}</div>
                <div className="text-xs uppercase tracking-wide text-slate-300">{stat.label}</div>
              </div>
            ))}
          </div>

          <p className="mt-8 inline-flex items-center gap-2 rounded-xl bg-brand-500/15 px-3.5 py-2 text-sm text-brand-100">
            <Sparkles className="h-4 w-4" />
            Thử nhắn: “Tôi là Nam, 0912345678, muốn lái thử VF 8 sáng mai ở Cầu Giấy”
          </p>
        </motion.div>
      </div>
    </section>
  );
}
