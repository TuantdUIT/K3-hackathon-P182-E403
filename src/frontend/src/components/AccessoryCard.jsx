import { format_price } from '../lib/formatPrice.js';

export default function AccessoryCard({ accessory }) {
  return (
    <article className="card overflow-hidden transition hover:shadow-lift">
      <div className="aspect-[4/3] overflow-hidden bg-slate-100">
        <img
          src={accessory.image}
          alt={accessory.name}
          loading="lazy"
          className="h-full w-full object-cover"
        />
      </div>
      <div className="p-4">
        <div className="text-xs font-semibold uppercase tracking-wide text-brand-600">
          {accessory.category}
        </div>
        <h3 className="mt-1 font-semibold">{accessory.name}</h3>
        <p className="mt-1 text-xs text-slate-500">{accessory.note}</p>
        <div className="mt-3 font-bold text-ink-900">{format_price(accessory.price)}</div>
      </div>
    </article>
  );
}
