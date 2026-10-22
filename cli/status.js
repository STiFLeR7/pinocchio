// `pinocchio status`: the nose-count box.
import { createUI } from './ui.js';
import { readEntries, verifyChain } from '../src/ledger.js';

const LABEL = { pass: '✔ PASS', fail: '✖ FAIL', cant_tell: "? CAN'T TELL", error: '! ERROR' };

export function status({ cwd = process.cwd(), ui = createUI() } = {}) {
  const entries = readEntries(cwd);
  if (!entries.length) {
    ui.line("No sessions yet — Pinocchio writes a receipt after your agent's next edit.");
    return 0;
  }
  const last = new Map(); // session -> verdict of its last entry
  for (const e of entries) last.set(e.session, e.verdict);
  const count = (v) => [...last.values()].filter((x) => x === v).length;
  const lies = entries.filter((e) => e.verdict === 'fail').length;
  const nose = Math.min(10, lies);
  const chain = verifyChain(cwd);
  const lastThree = entries.slice(-3).map((e) => {
    const id = e.verdict === 'fail' ? e.checks?.find((c) => c.status === 'fail')?.id : null;
    return `${LABEL[e.verdict] ?? e.verdict}${id ? ` ${id}` : ''}`;
  });
  ui.box(`🤥 Pinocchio · ${cwd}`, null, [
    `Nose length   ${'▇'.repeat(nose)}${'░'.repeat(10 - nose)}  ${lies} ${lies === 1 ? 'lie' : 'lies'} caught`,
    `Sessions      ${last.size} checked · ${count('pass')} pass · ${count('fail')} fail · ${count('cant_tell')} can't tell`,
    `Last 3        ${lastThree.join('   ')}`,
    chain.ok ? `Ledger        ✔ hash chain intact (${chain.count} entries)` : `Ledger        ✖ chain broken at entry ${chain.brokenAt + 1}`,
  ]);
  return 0;
}
