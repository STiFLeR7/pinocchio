import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { Worker, isMainThread, parentPort, workerData } from 'node:worker_threads';
import { loadConfig } from './config.js';
import { parseTranscript } from './transcript.js';
import { matchClaims } from './claims.js';
import { repoHasTestSetup } from './testcmd.js';
import * as gitMod from './git.js';
import { findFreshJUnit } from './junit.js';
import { confine } from './paths.js';
import { staleTests } from './checks/stale-tests.js';
import { redTests } from './checks/red-tests.js';
import { phantomEdit } from './checks/phantom-edit.js';
import { tampering } from './checks/tampering.js';
import { decide, orderResults } from './verdict.js';
import { formatReceipt, formatReason } from './receipt.js';
import { appendEntry, sessionStats } from './ledger.js';

const CHECKS = [staleTests, redTests, phantomEdit, tampering];

function skipped(cwd, session, reason) {
  appendEntry(cwd, { ts: new Date().toISOString(), session, verdict: 'error', mode: 'default', blocked: false, blocks_in_session: 0, claims: [], checks: [], git: { head: null, changed: {} }, error: reason });
  return { systemMessage: `🤥 Pinocchio · skipped (${reason})` };
}

export function run(input, { env = process.env, findJUnit = findFreshJUnit, git = gitMod } = {}) {
  const t0 = Date.now();
  const cwd = typeof input?.cwd === 'string' ? input.cwd : process.cwd();
  const session = String(input?.session_id ?? 'unknown');
  if (env.PINOCCHIO === 'off') return null;
  const config = loadConfig(cwd);
  if (config.mode === 'off') return null;

  let text;
  try {
    text = fs.readFileSync(input.transcript_path, 'utf8');
  } catch {
    return skipped(cwd, session, 'transcript unreadable');
  }
  const { events, lastAssistantText, startTs } = parseTranscript(text);
  const message = typeof input.last_assistant_message === 'string' ? input.last_assistant_message : (lastAssistantText ?? '');
  const claims = matchClaims(message, config);
  if (!events.some((e) => e.kind === 'edit') && !claims.length) return null;

  const gs = git.readGitState(cwd);
  const root = gs.isRepo ? gs.root : cwd;
  const committed = gs.isRepo && Number.isFinite(startTs) ? git.committedSince(cwd, startTs) : [];
  const ctx = {
    events, claims, config, cwd, root,
    git: { ...gs, committed },
    hasTestSetup: repoHasTestSetup(root, config),
    findJUnit: (since) => findJUnit(root, since),
    gitTestDiff: (files) => git.testFileDiff(root, files),
  };
  const results = orderResults(CHECKS.map((check) => check(ctx)));
  const verdict = decide(results, claims);

  const stats = sessionStats(cwd, session);
  const wantBlock = (verdict === 'fail' && config.mode !== 'report') || (verdict === 'cant_tell' && config.mode === 'strict');
  const limitReached = wantBlock && stats.blocks >= config.maxBlocksPerSession;
  let blocked = wantBlock && !limitReached;

  const changed = {};
  for (const p of Object.keys(gs.changed).slice(0, 50)) {
    const abs = confine(root, p);
    const h = abs && git.hashFile(abs);
    if (h) changed[p] = h;
  }
  // The ledger is the only block counter: if it cannot be written, blocking could loop forever.
  const entry = (b) => ({
    ts: new Date().toISOString(), session, verdict, mode: config.mode, blocked: b, blocks_in_session: stats.blocks + (b ? 1 : 0),
    elapsed_ms: Date.now() - t0,
    claims: claims.map((c) => ({ type: c.type, text: c.text, file: c.file })),
    checks: results.map((r) => {
      const evidence = r.evidence === undefined ? undefined : JSON.parse(JSON.stringify(r.evidence));
      if (evidence?.test_run) delete evidence.test_run.cmd; // commands may carry secrets
      return { id: r.id, status: r.status, evidence };
    }),
    git: { head: gs.head, changed },
  });
  const ledger = appendEntry(cwd, entry(blocked), { commitLedger: config.commitLedger });
  const notes = [...(config.notes ?? [])];
  if (blocked && !ledger) {
    blocked = false;
    notes.push('ledger unavailable, not blocking');
  }
  const blocksInSession = stats.blocks + (blocked ? 1 : 0);

  const systemMessage = formatReceipt({
    verdict, results, claims, sessionLies: stats.lies + (verdict === 'fail' ? 1 : 0), blocked, blocksInSession,
    maxBlocks: config.maxBlocksPerSession, limitReached, ledgerHash: ledger?.hash ?? null, notes,
  });
  return blocked ? { decision: 'block', reason: formatReason(results), systemMessage } : { systemMessage };
}

function main() {
  let done = false;
  // Exit only after stdout drained: a piped write can still be pending when exit() runs.
  const finish = (o) => {
    if (done) return;
    done = true;
    if (o) process.stdout.write(JSON.stringify(o), () => process.exit(0));
    else process.exit(0);
  };
  const skip = (why) => finish({ systemMessage: `🤥 Pinocchio · skipped (${String(why).slice(0, 80)})` });
  const timer = setTimeout(() => skip('timeout'), 2000);
  (async () => {
    try {
      const chunks = [];
      for await (const c of process.stdin) chunks.push(c);
      const input = JSON.parse(Buffer.concat(chunks).toString('utf8'));
      const w = new Worker(new URL(import.meta.url), { workerData: { input } });
      w.on('message', (m) => (m?.error ? skip(m.error) : finish(m)));
      w.on('error', (e) => skip(e?.message ?? e));
    } catch (e) {
      skip(e?.message ?? e);
    }
  })();
}

function isEntry() {
  try {
    const norm = (p) => (process.platform === 'win32' ? p.toLowerCase() : p);
    return norm(fs.realpathSync(process.argv[1])) === norm(fs.realpathSync(fileURLToPath(import.meta.url)));
  } catch {
    return false;
  }
}

if (!isMainThread) {
  try {
    parentPort.postMessage(run(workerData.input));
  } catch (e) {
    parentPort.postMessage({ error: String(e?.message ?? e) });
  }
} else if (isEntry()) main();
