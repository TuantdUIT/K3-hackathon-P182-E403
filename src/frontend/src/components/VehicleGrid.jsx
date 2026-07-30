import VehicleCard from './VehicleCard.jsx';

export default function VehicleGrid({ vehicles, on_test_drive }) {
  if (vehicles.length === 0) {
    return (
      <section className="mx-auto max-w-7xl px-4 py-16 text-center sm:px-6">
        <p className="text-slate-500">
          Không có mẫu xe nào khớp bộ lọc. Anh/chị thử bỏ bớt điều kiện lọc nhé.
        </p>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6">
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {vehicles.map((vehicle) => (
          <VehicleCard key={vehicle.id} vehicle={vehicle} on_test_drive={on_test_drive} />
        ))}
      </div>
    </section>
  );
}
