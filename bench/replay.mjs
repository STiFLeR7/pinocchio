// node bench/replay.mjs [projectsDir]: replays Pinocchio over your own past Claude Code transcripts and writes
// bench/results/replay-summary.json. Counts only: no transcript text, path, project name or command leaves this process.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { assertSubscriptionOnly } from './lib/guard.js';
import { run } from '../src/stop.js';
import { readEntries } from '../src/ledger.js';

const FAIL_CHECKS = ['stale-tests', 'red-tests', 'phantom-edit'];
// Session-time git state is gone: git-dependent checks report unknown, and nothing under the session cwd is run or scanned.
const noGit = {
  readGitState: () => ({ isRepo: false, root: null, head: null, changed: {} }),
  committedSince: () => [],
  sessionBase: () => 'HEAD',
  testFileDiff: () => '',
  hashFile: () => null,
};

const textOf = (c) => (Array.isArray(c) ? c.filter((b) => b?.type === 'text' && typeof b.text === 'string').map((b) => b.text).join('\n') : '');
const isPrompt = (o) => o.type === 'user' && !o.isMeta && (typeof o.message?.content === 'string' ? o.message.content !== '' : Array.isArray(o.message?.content) && o.message.content.some((b) => b?.type !== 'tool_result'));

// Each turn: the transcript prefix up to the last assistant line before a real prompt (and at end of file),
// as its end index into lines.
function turnsOf(lines) {
  const parsed = lines.map((l) => {
    try {
      return JSON.parse(l);
    } catch {
      return null;
    }
  });
  const turns = [];
  let lastA = -1;
  for (let i = 0; i <= parsed.length; i++) {
    const o = parsed[i];
    if (i === parsed.length || (o && isPrompt(o))) {
      if (lastA >= 0) turns.push({ end: lastA + 1, message: textOf(parsed[lastA].message?.content) });
      lastA = -1;
    } else if (o?.type === 'assistant') lastA = i;
  }
  return turns;
}

// At most n turns, evenly spread over the session.
const sample = (turns, n) => (turns.length <= n ? turns : Array.from({ length: n }, (_, i) => turns[Math.floor((i * turns.length) / n)]));

// Fixed-seed shuffle (mulberry32, seed SEED): the maxTurns cut-off then takes a reproducible sample across
// projects instead of whichever project directories sort first.
const SEED = 20261021;
function shuffled(items) {
  let a = SEED;
  const rand = () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const out = [...items];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

function sessionCwd(lines) {
  for (const l of lines) {
    try {
      const c = JSON.parse(l)?.cwd;
      if (typeof c === 'string') return c;
    } catch {
      /* corrupt line */
    }
  }
  return null;
}

// Each evaluated turn re-reads its whole prefix, so maxTurnsPerFile bounds the work per file (turnsSampledOut counts the rest).
export function replay({ projectsDir, maxFileBytes = 20 * 1024 * 1024, maxTurns = 5000, maxTurnsPerFile = 25 }) {
  assertSubscriptionOnly();
  const s = { files: 0, filesSkipped: 0, turns: 0, turnsSampledOut: 0, turnsWithClaims: 0, verdicts: { pass: 0, fail: 0, cantTell: 0, error: 0 }, failByCheck: Object.fromEntries(FAIL_CHECKS.map((k) => [k, 0])), unsupportedClaimShare: 0, truncated: false };
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'pino-replay-'));
  const prefixFile = path.join(tmp, 'prefix.jsonl');
  try {
    const files = [];
    for (const d of fs.readdirSync(projectsDir, { withFileTypes: true })) {
      if (d.isDirectory()) for (const f of fs.readdirSync(path.join(projectsDir, d.name))) if (f.endsWith('.jsonl')) files.push(path.join(projectsDir, d.name, f));
    }
    for (const file of shuffled(files.sort())) {
      if (s.turns >= maxTurns) {
        s.truncated = true;
        break;
      }
      try {
        if (fs.statSync(file).size > maxFileBytes) {
          s.filesSkipped++;
          continue;
        }
        const lines = fs.readFileSync(file, 'utf8').split('\n').filter((l) => l.trim());
        const cwd = sessionCwd(lines);
        if (!cwd || cwd.split(/[\\/]/).some((p) => p.startsWith('pino-bench-'))) {
          s.filesSkipped++;
          continue;
        }
        s.files++;
        const turns = turnsOf(lines);
        const picked = sample(turns, maxTurnsPerFile);
        s.turnsSampledOut += turns.length - picked.length;
        // Turns come in order, so the prefix file only ever grows: append the new lines instead of rewriting it.
        fs.writeFileSync(prefixFile, '');
        let written = 0;
        for (const turn of picked) {
          if (s.turns >= maxTurns) {
            s.truncated = true;
            break;
          }
          s.turns++;
          try {
            fs.appendFileSync(prefixFile, lines.slice(written, turn.end).map((l) => `${l}\n`).join(''));
            written = turn.end;
            run({ session_id: 'replay', transcript_path: prefixFile, cwd, last_assistant_message: turn.message }, { env: { CLAUDE_PROJECT_DIR: tmp }, git: noGit, findJUnit: () => [] });
            const e = readEntries(tmp).pop();
            if (!e) continue;
            if (e.claims?.length) s.turnsWithClaims++;
            s.verdicts[e.verdict === 'cant_tell' ? 'cantTell' : e.verdict]++;
            for (const k of FAIL_CHECKS) if (e.checks?.some((c) => c.id === k && c.status === 'fail')) s.failByCheck[k]++;
          } catch {
            s.verdicts.error++;
          } finally {
            // Fresh ledger per turn: no hash-chain rescan and no block-limit carry-over.
            fs.rmSync(path.join(tmp, '.claude'), { recursive: true, force: true });
          }
        }
      } catch {
        s.filesSkipped++;
      }
    }
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
  s.unsupportedClaimShare = s.turnsWithClaims ? s.verdicts.fail / s.turnsWithClaims : 0;
  return s;
}

if (process.argv[1] && fs.realpathSync(process.argv[1]) === fs.realpathSync(fileURLToPath(import.meta.url))) {
  const summary = replay({ projectsDir: process.argv[2] ?? path.join(os.homedir(), '.claude', 'projects') });
  const out = path.join(path.dirname(fileURLToPath(import.meta.url)), 'results', 'replay-summary.json');
  fs.mkdirSync(path.dirname(out), { recursive: true });
  fs.writeFileSync(out, JSON.stringify(summary, null, 2) + '\n');
  console.log(JSON.stringify(summary, null, 2));
}
