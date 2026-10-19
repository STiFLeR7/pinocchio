const ICON = { pass: '✓', fail: '✗', unknown: '?', warn: '⚠' };

export function formatReceipt({ verdict, results, claims, sessionLies, blocked, blocksInSession, maxBlocks, limitReached, ledgerHash, notes = [] }) {
  let head;
  if (verdict === 'fail') head = `🤥 Pinocchio · FAIL · nose +1 (session: ${sessionLies} lie${sessionLies === 1 ? '' : 's'} caught)`;
  else if (verdict === 'cant_tell') head = "🤥 Pinocchio · CAN'T TELL";
  else head = `🤥 Pinocchio · PASS · ${claims.length ? 'nose unchanged' : 'no claims made'}`;
  const lines = [head];
  for (const r of results.slice(0, 4)) lines.push(`  ${ICON[r.status]} ${r.id.padEnd(13)} ${r.summary}`);
  const tail = [ledgerHash ? `ledger #${ledgerHash.slice(7, 11)}…` : 'ledger unavailable'];
  if (blocked) tail.push(`blocked ${blocksInSession}/${maxBlocks}`);
  if (limitReached) tail.push('⚠ stopped blocking (limit reached)');
  tail.push(...notes);
  return [...lines.slice(0, 5), `  ${tail.join(' · ')}`].join('\n');
}

export function formatReason(results) {
  const failed = results.filter((r) => r && r.blocking && r.status === 'fail');
  return `Pinocchio: your completion claim is not supported by evidence. ${failed.map((r) => `${r.id}: ${r.summary}`).join('. ')}. Do the missing step (for example, run the tests), then report the actual result. Do not claim success without evidence.`;
}
