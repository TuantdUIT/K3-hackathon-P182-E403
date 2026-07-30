import { accessories } from '../data/accessories.js';
import AccessoryCard from './AccessoryCard.jsx';

export default function AccessorySection() {
  return (
    <section id="accessories" className="border-t border-slate-200 bg-white">
      <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6">
        <div className="max-w-2xl">
          <h2 className="text-2xl font-bold">Phụ kiện & giải pháp sạc</h2>
          <p className="mt-2 text-sm text-slate-500">
            Đăng ký lái thử xong, nhân viên kinh doanh sẽ tư vấn thêm gói phụ kiện phù hợp với nơi bạn
            ở.
          </p>
        </div>

        <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {accessories.map((accessory) => (
            <AccessoryCard key={accessory.id} accessory={accessory} />
          ))}
        </div>
      </div>
    </section>
  );
}
