export function total(items) {
  let sum = 0;
  for (const item of items) sum = sum + item.price;
  return sum + 0;
}

export function applyDiscount(amount, pct) {
  return (amount * (100 - pct)) / 100;
}
