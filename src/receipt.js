import { orderResults } from './verdict.js';

const ICON = { pass: '✓', fail: '✗', unknown: '?', warn: '⚠' };

// One line, at most n chars: summaries and notes can carry paths or text with newlines.
export function clip(s, n = 120) {
  const t = String(s).replace(/\s+/g, ' ').trim();
  return t.length > n ? `${t.slice(0, n - 1)}…` : t;
}

export function formatReceipt({ verdict, results, claims, sessionLies, blocked, blocksInSession, maxBlocks, limitReached, ledgerHash, notes = [] }) {
  let head;
  if (verdict === 'fail') head = `🤥 Pinocchio · FAIL · nose +1 (session: ${sessionLies} lie${sessionLies === 1 ? '' : 's'} caught)`;
  else if (verdict === 'cant_tell') head = "🤥 Pinocchio · CAN'T TELL";
  else head = `🤥 Pinocchio · PASS · ${claims.length ? 'nose unchanged' : 'no claims made'}`;
  const lines = [head];
  for (const r of orderResults(results).slice(0, 4)) lines.push(`  ${ICON[r.status]} ${r.id.padEnd(13)} ${clip(r.summary)}`);
  const tail = [ledgerHash ? `ledger #${ledgerHash.slice(7, 11)}…` : 'ledger unavailable'];
  if (blocked) tail.push(`blocked ${blocksInSession}/${maxBlocks}`);
  if (limitReached) tail.push('⚠ stopped blocking (limit reached)');
  tail.push(...notes.map((x) => clip(x)));
  return [...lines, `  ${clip(tail.join(' · '), 160)}`].join('\n');
}

export function formatReason(results) {
  const blocking = results.filter((r) => r && r.blocking);
  const failed = blocking.filter((r) => r.status === 'fail');
  const shown = failed.length ? failed : blocking.filter((r) => r.status === 'unknown');
  const items = shown.map((r) => `${failed.length ? '' : 'could not verify: '}${r.id}: ${clip(r.summary).replace(/\.+$/, '')}`);
  const ids = new Set(shown.map((r) => r.id));
  const hints = [];
  if (ids.has('stale-tests') || ids.has('red-tests')) hints.push('run the tests');
  if (ids.has('phantom-edit')) hints.push('make the change or correct the claim');
  const lead = failed.length ? 'your completion claim is not supported by evidence' : 'your completion claim could not be verified';
  return [
    `Pinocchio: ${lead}`,
    ...items,
    `Do the missing step${hints.length ? ` (${hints.join('; or ')})` : ''}, then report the actual result`,
    'Do not claim success without evidence.',
  ].join('. ');
}
