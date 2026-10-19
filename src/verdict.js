const ORDER = { fail: 0, unknown: 1, warn: 2, pass: 3 };

export function orderResults(results) {
  return results.filter(Boolean).slice().sort((a, b) => ORDER[a.status] - ORDER[b.status]);
}

export function decide(results, claims) {
  const rs = results.filter(Boolean);
  if (rs.some((r) => r.blocking && r.status === 'fail')) return 'fail';
  if (claims.length && rs.some((r) => r.blocking && r.status === 'unknown')) return 'cant_tell';
  return 'pass';
}
