const vnd = new Intl.NumberFormat('vi-VN', {
  style: 'currency',
  currency: 'VND',
  maximumFractionDigits: 0,
});

export const format_price = (amount) => {
  if (amount === null || amount === undefined) return '—';
  return vnd.format(amount);
};

// "1.019 tỷ" / "299 triệu" — dùng cho thẻ xe, đọc nhanh hơn số đầy đủ.
export const format_price_short = (amount) => {
  if (!amount) return '—';
  if (amount >= 1_000_000_000) {
    const billions = amount / 1_000_000_000;
    return `${billions.toFixed(billions % 1 === 0 ? 0 : 3).replace('.', ',')} tỷ`;
  }
  return `${Math.round(amount / 1_000_000)} triệu`;
};

export default format_price;
