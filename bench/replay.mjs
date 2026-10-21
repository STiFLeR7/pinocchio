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

// Each turn: the transcript prefix up to the last assistant line before a real prompt (and at end of file).
function* turnsOf(lines) {
  const parsed = lines.map((l) => {
    try {
      return JSON.parse(l);
    } catch {
      return null;
    }
  });
  let lastA = -1;
  for (let i = 0; i <= parsed.length; i++) {
    const o = parsed[i];
    if (i === parsed.length || (o && isPrompt(o))) {
      if (lastA >= 0) yield { prefix: lines.slice(0, lastA + 1), message: textOf(parsed[lastA].message?.content) };
      lastA = -1;
    } else if (o?.type === 'assistant') lastA = i;
  }
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

export function replay({ projectsDir, maxFileBytes = 20 * 1024 * 1024, maxTurns = 5000 }) {
  assertSubscriptionOnly();
  const s = { files: 0, filesSkipped: 0, turns: 0, turnsWithClaims: 0, verdicts: { pass: 0, fail: 0, cantTell: 0, error: 0 }, failByCheck: Object.fromEntries(FAIL_CHECKS.map((k) => [k, 0])), unsupportedClaimShare: 0, truncated: false };
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'pino-replay-'));
  const prefixFile = path.join(tmp, 'prefix.jsonl');
  try {
    const files = [];
    for (const d of fs.readdirSync(projectsDir, { withFileTypes: true })) {
      if (d.isDirectory()) for (const f of fs.readdirSync(path.join(projectsDir, d.name))) if (f.endsWith('.jsonl')) files.push(path.join(projectsDir, d.name, f));
    }
    for (const file of files.sort()) {
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
        for (const turn of turnsOf(lines)) {
          if (s.turns >= maxTurns) {
            s.truncated = true;
            break;
          }
          s.turns++;
          try {
            fs.writeFileSync(prefixFile, turn.prefix.join('\n') + '\n');
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
