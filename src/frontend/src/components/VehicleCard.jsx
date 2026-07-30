import { motion } from 'framer-motion';
import { BatteryCharging, Users } from 'lucide-react';

import { format_price, format_price_short } from '../lib/formatPrice.js';

export default function VehicleCard({ vehicle, on_test_drive }) {
  const has_promo = vehicle.priceList > vehicle.priceFrom;

  return (
    <motion.article
      initial={{ opacity: 0, y: 14 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-60px' }}
      transition={{ duration: 0.4 }}
      className="card group flex flex-col overflow-hidden transition hover:shadow-lift"
    >
      <div className="relative aspect-[16/10] overflow-hidden bg-slate-100">
        <img
          src={vehicle.image}
          alt={vehicle.name}
          loading="lazy"
          className="h-full w-full object-cover transition duration-500 group-hover:scale-105"
        />
        <span className="absolute left-3 top-3 rounded-full bg-white/95 px-2.5 py-1 text-xs font-semibold text-ink-900">
          {vehicle.segment}
        </span>
        {vehicle.line === 'service' && (
          <span className="absolute right-3 top-3 rounded-full bg-emerald-500 px-2.5 py-1 text-xs font-semibold text-white">
            Xe dịch vụ
          </span>
        )}
      </div>

      <div className="flex flex-1 flex-col p-5">
        <h3 className="text-lg font-bold">{vehicle.name}</h3>
        <p className="mt-1 text-sm text-slate-500">{vehicle.tagline}</p>

        <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
          <div className="flex items-center gap-2 text-slate-600">
            <Users className="h-4 w-4 text-brand-600" />
            {vehicle.seats} chỗ
          </div>
          <div className="flex items-center gap-2 text-slate-600">
            <BatteryCharging className="h-4 w-4 text-brand-600" />
            {vehicle.range} km
          </div>
        </dl>

        <div className="mt-5 flex items-end justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-wide text-slate-400">Giá từ</div>
            <div className="text-xl font-extrabold text-brand-700">
              {format_price_short(vehicle.priceFrom)}
            </div>
            {has_promo && (
              <div className="text-xs text-slate-400 line-through">
                {format_price(vehicle.priceList)}
              </div>
            )}
          </div>

          <button
            type="button"
            className="btn-primary shrink-0"
            onClick={() => on_test_drive(vehicle.id)}
          >
            Lái thử
          </button>
        </div>
      </div>
    </motion.article>
  );
}
