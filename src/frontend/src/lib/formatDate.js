const weekdays_vi = ['Chủ Nhật', 'Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy'];

// Ngày hôm nay theo múi giờ máy, dạng YYYY-MM-DD — dùng cho `min` của input date.
export const today_iso = () => {
  const now = new Date();
  const offset_ms = now.getTimezoneOffset() * 60 * 1000;
  return new Date(now.getTime() - offset_ms).toISOString().slice(0, 10);
};

export const format_date = (iso) => {
  if (!iso) return '—';
  const parsed = new Date(`${String(iso).slice(0, 10)}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return String(iso);
  const day = String(parsed.getDate()).padStart(2, '0');
  const month = String(parsed.getMonth() + 1).padStart(2, '0');
  return `${day}/${month}/${parsed.getFullYear()}`;
};

export const format_date_long = (iso) => {
  if (!iso) return '—';
  const parsed = new Date(`${String(iso).slice(0, 10)}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return String(iso);
  return `${weekdays_vi[parsed.getDay()]}, ${format_date(iso)}`;
};

export const format_datetime = (iso) => {
  if (!iso) return '—';
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return String(iso);
  const time = `${String(parsed.getHours()).padStart(2, '0')}:${String(parsed.getMinutes()).padStart(2, '0')}`;
  return `${format_date(parsed.toISOString())} ${time}`;
};

export default format_date;
