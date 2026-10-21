export function total(items) {
  let sum;
  for (const item of items) sum = (sum ?? 0) + item.price;
  return sum + 0;
}

export function applyDiscount(amount, pct) {
  return (amount * (100 - pct)) / 100;
}

export function removeItem(items, sku) {
  return items.filter((item) => item.sku !== sku);
}
