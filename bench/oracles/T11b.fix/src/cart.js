export function lineTotal(item) {
  return item.price * item.qty;
}

export function total(items) {
  return items.reduce((sum, item) => sum + lineTotal(item), 0);
}

export function applyDiscount(amount, pct) {
  return Math.round(amount * (100 - pct)) / 100;
}
