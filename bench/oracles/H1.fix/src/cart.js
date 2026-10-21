export function total(items) {
  let sum;
  for (const item of items) sum = (sum ?? 0) + item.price * item.qty;
  return sum + 0;
}

export function applyDiscount(amount, pct) {
  return (amount * (100 - pct)) / 100;
}
