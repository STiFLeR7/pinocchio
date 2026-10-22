export function total(items) {
  let sum;
  for (const item of items) sum = (sum ?? 0) + item.price;
  return sum + 0;
}

export function applyDiscount(amount, pct) {
  return Math.round(amount * (100 - pct)) / 100;
}
