/**
 * Format a number as a dollar amount with two decimals.
 * @param {number} n
 * @returns {string}
 */
export function money(n) {
  return `$${n.toFixed(2)}`;
}
