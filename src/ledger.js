import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

export const GENESIS = `sha256:${'0'.repeat(64)}`;
const sha = (s) => `sha256:${crypto.createHash('sha256').update(s).digest('hex')}`;
const dirOf = (cwd) => path.join(cwd, '.claude', 'pinocchio');
const fileOf = (cwd) => path.join(dirOf(cwd), 'ledger.jsonl');

export function canonical(v) {
  if (v === null || typeof v !== 'object') return JSON.stringify(v);
  if (Array.isArray(v)) return `[${v.map(canonical).join(',')}]`;
  return `{${Object.keys(v).filter((k) => v[k] !== undefined).sort().map((k) => `${JSON.stringify(k)}:${canonical(v[k])}`).join(',')}}`;
}

export function readEntries(cwd, file = fileOf(cwd)) {
  let text;
  try {
    text = fs.readFileSync(file, 'utf8');
  } catch {
    return [];
  }
  const out = [];
  for (const l of text.split('\n')) {
    if (!l) continue;
    try {
      out.push(JSON.parse(l));
    } catch {
      /* torn line: ignore */
    }
  }
  return out;
}

export function sessionStats(cwd, session) {
  // Include the rotated file so rotation does not reset the block limit.
  const es = [...readEntries(cwd, path.join(dirOf(cwd), 'ledger.1.jsonl')), ...readEntries(cwd)].filter((x) => x.session === session);
  return { blocks: es.filter((x) => x.blocked).length, lies: es.filter((x) => x.verdict === 'fail').length };
}

export function appendEntry(cwd, entry, { commitLedger = false, maxBytes = 5 * 1024 * 1024 } = {}) {
  try {
    const dir = dirOf(cwd);
    fs.mkdirSync(dir, { recursive: true });
    const gi = path.join(dir, '.gitignore');
    const want = commitLedger ? '' : '*\n'; // '*' also ignores this .gitignore, so the folder never shows in git status
    let have = null;
    try {
      have = fs.readFileSync(gi, 'utf8');
    } catch {
      /* missing */
    }
    if (have !== want) fs.writeFileSync(gi, want);
    const es = readEntries(cwd);
    const last = es[es.length - 1];
    const prev = last?.hash ?? GENESIS;
    const seq = last ? last.seq + 1 : 0;
    const file = fileOf(cwd);
    try {
      if (fs.statSync(file).size > maxBytes) fs.renameSync(file, path.join(dir, 'ledger.1.jsonl'));
    } catch {
      /* no file yet */
    }
    // Prevent entry from injecting hash/prev/seq/v; write newline if file doesn't end with one
    const { hash, prev: _, seq: __, v, ...safe } = entry;
    const body = { v: 1, ...safe, seq, prev };
    const hash_computed = sha(prev + canonical(body));
    try {
      const stat = fs.statSync(file);
      if (stat.size > 0) {
        const last_byte = Buffer.alloc(1);
        const fd = fs.openSync(file, 'r');
        fs.readSync(fd, last_byte, 0, 1, stat.size - 1);
        fs.closeSync(fd);
        if (last_byte[0] !== 10) fs.appendFileSync(file, '\n'); // 10 is '\n'
      }
    } catch {
      /* no file yet, ok to skip */
    }
    fs.appendFileSync(file, `${JSON.stringify({ ...body, hash: hash_computed })}\n`);
    return { hash: hash_computed, seq };
  } catch {
    return null;
  }
}

export function verifyChain(cwd) {
  const es = readEntries(cwd);
  let prev = es.length ? es[0].prev : GENESIS;
  for (let i = 0; i < es.length; i++) {
    const { hash, ...body } = es[i];
    if (body.prev !== prev || sha(body.prev + canonical(body)) !== hash) return { ok: false, count: es.length, brokenAt: i };
    prev = hash;
  }
  return { ok: true, count: es.length, brokenAt: null };
}
