// Executes one benchmark run end to end and records it; an existing result file means the run is already done.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn, spawnSync, execFileSync } from 'node:child_process';
import { parseTranscript } from '../../src/transcript.js';
import { run as stopRun } from '../../src/stop.js';
import { readEntries } from '../../src/ledger.js';
import { claudeArgv, codexArgv } from './arms.js';
import { copyCase, shellOk } from './fixture.js';
import { facts } from './facts.js';

// Neither writes a result file: the run never really happened, so a re-run must retry it.
export class PausedError extends Error {}
export class SetupError extends Error {}

const TIMEOUT_MS = 15 * 60_000;
const DRAIN_MS = 2000;
const LIMIT = /usage limit|rate limit|quota/i;
const AUTHOR = ['-c', 'core.autocrlf=false', '-c', 'user.name=pinocchio-bench', '-c', 'user.email=bench@pinocchio.invalid', '-c', 'commit.gpgsign=false'];

const jsonLines = (text) => String(text).split('\n').flatMap((l) => {
  try {
    return l.trim() ? [JSON.parse(l)] : [];
  } catch {
    return [];
  }
});
const textOf = (c) => (typeof c === 'string' ? c : Array.isArray(c) ? c.filter((b) => b?.type === 'text' && typeof b.text === 'string').map((b) => b.text).join('\n') : '');
const samePath = (p) => {
  let r = path.resolve(String(p));
  try {
    r = fs.realpathSync.native(r);
  } catch {
    /* keep resolved */
  }
  return process.platform === 'win32' ? r.toLowerCase() : r;
};

// cli is a command name or { cmd, prefixArgs }. On Windows an npm .cmd shim is unwrapped to `node <script>`:
// cmd.exe would mangle a prompt holding quotes, & or %, while node's own argv quoting does not.
export function resolveCli(cli, env = process.env) {
  if (typeof cli !== 'string') return cli;
  if (process.platform !== 'win32') return { cmd: cli, prefixArgs: [] };
  const hits = (spawnSync('where', [cli], { env, encoding: 'utf8' }).stdout ?? '').split(/\r?\n/).filter(Boolean);
  const first = hits.find((h) => /\.(exe|com|cmd)$/i.test(h));
  const m = first && /\.cmd$/i.test(first) && /"%dp0%\\([^"]+\.js)"/i.exec(fs.readFileSync(first, 'utf8'));
  return m ? { cmd: process.execPath, prefixArgs: [path.join(path.dirname(first), m[1])] } : { cmd: cli, prefixArgs: [] };
}

function runAgent({ cmd, prefixArgs = [] }, args, cwd, timeoutMs) {
  return new Promise((resolve, reject) => {
    // ponytail: the timeout kills the CLI only, not tools it spawned; use a job object / process group if strays pile up
    const child = spawn(cmd, [...prefixArgs, ...args], { cwd, env: process.env, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true });
    let stdout = '';
    let stderr = '';
    let exit = null;
    // Own timer, not spawn's timeout option: that one is only cleared on 'exit', so a failed spawn would hold the process for 15 min.
    const timer = setTimeout(() => child.kill(), timeoutMs);
    child.stdout.on('data', (d) => (stdout += d));
    child.stderr.on('data', (d) => (stderr += d));
    child.on('error', (e) => {
      clearTimeout(timer);
      reject(new SetupError(`cannot start ${cmd}: ${e.message}`));
    });
    const done = () => {
      child.stdout.destroy();
      child.stderr.destroy();
      resolve({ ...exit, stdout, stderr });
    };
    child.on('close', () => exit && done());
    // A grandchild can hold the pipes open forever, so 'close' may never come: give it a bounded drain after exit.
    child.on('exit', (code, signal) => {
      clearTimeout(timer);
      exit = { code, signal };
      setTimeout(done, DRAIN_MS).unref();
    });
  });
}

// Each Stop: the last assistant text before every "Stop hook feedback" user entry, plus the final one, with the
// 1-based transcript line of the feedback that followed it (null for the final stop).
export function extractStops(transcriptText) {
  const stops = [];
  let last = null;
  let repliedSinceStop = false;
  String(transcriptText).split('\n').forEach((l, i) => {
    let o;
    try {
      o = l.trim() ? JSON.parse(l) : null;
    } catch {
      return;
    }
    const t = textOf(o?.message?.content);
    if (o?.type === 'assistant' && t) {
      last = t;
      repliedSinceStop = true;
    } else if (o?.type === 'user' && t.trimStart().startsWith('Stop hook feedback')) {
      stops.push({ message: last, feedbackLine: i + 1 });
      repliedSinceStop = false;
    }
  });
  // Ending on feedback with no reply after it means the last stop is already counted.
  if (repliedSinceStop || !stops.length) stops.push({ message: parseTranscript(transcriptText).lastAssistantText, feedbackLine: null });
  return stops;
}

function claudeOutcome(stdout, projectsDir) {
  const lines = jsonLines(stdout);
  const init = lines.find((o) => o.type === 'system' && o.subtype === 'init') ?? {};
  const result = lines.find((o) => o.type === 'result') ?? {};
  const u = result.usage;
  const sid = result.session_id ?? init.session_id;
  let transcript = null;
  if (sid) {
    for (const d of fs.readdirSync(projectsDir, { withFileTypes: true })) {
      const f = path.join(projectsDir, d.name, `${sid}.jsonl`);
      if (d.isDirectory() && fs.existsSync(f)) transcript = f;
    }
  }
  return {
    model: init.model ?? null,
    plugins: (init.plugins ?? []).map((p) => (typeof p === 'string' ? p : p?.name)).filter(Boolean),
    usage: u ? { input: u.input_tokens ?? 0, output: u.output_tokens ?? 0, cacheRead: u.cache_read_input_tokens ?? 0, cacheWrite: u.cache_creation_input_tokens ?? 0 } : null,
    numTurns: result.num_turns ?? null,
    errorText: result.is_error ? String(result.result ?? '') : '',
    transcript,
  };
}

// Newest top-level Codex rollout created during this run in the run dir.
function findRollout(codexDir, dir, startedMs) {
  const want = samePath(dir);
  let best = null;
  let files = [];
  try {
    files = fs.readdirSync(codexDir, { recursive: true }).filter((f) => /^rollout-.*\.jsonl$/.test(path.basename(f)));
  } catch {
    return null;
  }
  for (const rel of files) {
    const f = path.join(codexDir, rel);
    const st = fs.statSync(f);
    const born = st.birthtimeMs || st.mtimeMs;
    if (born < startedMs - 1000 || (best && born <= best.born)) continue;
    const meta = jsonLines(fs.readFileSync(f, 'utf8').split('\n', 1)[0])[0];
    if (meta?.type !== 'session_meta' || meta.payload?.source?.subagent || samePath(meta.payload?.cwd ?? '') !== want) continue;
    best = { f, born };
  }
  return best?.f ?? null;
}

function codexOutcome(stdout, codexDir, dir, startedMs) {
  const errorText = jsonLines(stdout).filter((o) => o.type === 'error' || o.type === 'turn.failed').map((o) => o.message ?? o.error?.message ?? '').join('\n');
  const transcript = findRollout(codexDir, dir, startedMs);
  const lines = transcript ? jsonLines(fs.readFileSync(transcript, 'utf8')) : [];
  const t = lines.filter((o) => o.type === 'token_usage_record').at(-1)?.payload?.thread_token_usage;
  return {
    model: lines.find((o) => typeof o.payload?.model === 'string')?.payload.model ?? null,
    plugins: [],
    // OpenAI counts cached tokens inside input_tokens; split them out to match Claude's usage fields.
    usage: t ? { input: (t.input_tokens ?? 0) - (t.cached_input_tokens ?? 0), output: t.output_tokens ?? 0, cacheRead: t.cached_input_tokens ?? 0, cacheWrite: t.cache_write_input_tokens ?? 0 } : null,
    numTurns: null,
    errorText,
    transcript,
  };
}

// Verdict Pinocchio would give on the final transcript, written to a throwaway ledger so it never mixes with the live one.
function posthoc(transcriptPath, dir, stop) {
  const ledgerDir = fs.mkdtempSync(path.join(os.tmpdir(), 'pino-posthoc-'));
  try {
    const env = { ...process.env, CLAUDE_PROJECT_DIR: ledgerDir };
    delete env.PINOCCHIO;
    stop({ session_id: 'posthoc', transcript_path: transcriptPath, cwd: dir }, { env });
    const e = readEntries(ledgerDir).at(-1);
    return { verdict: e?.verdict ?? null, checks: e?.checks ?? [] };
  } finally {
    fs.rmSync(ledgerDir, { recursive: true, force: true });
  }
}

// Resolves to the RunRecord (also written to <resultsDir>/<id>.json). Fields a failed run never reached stay null,
// e.g. oraclePass is null, not false, when the oracle did not run.
export async function runOne({
  caseObj, agent, arm, rep, repoRoot, resultsDir,
  cli = { claude: 'claude', codex: 'codex' },
  projectsDir = path.join(os.homedir(), '.claude', 'projects'),
  codexDir = path.join(os.homedir(), '.codex', 'sessions'),
  timeoutMs = TIMEOUT_MS,
  stop = stopRun, // test seam for the post-hoc Pinocchio run
}) {
  const id = `${caseObj.id}.${agent}.${arm}.${rep}`;
  const file = path.join(resultsDir, `${id}.json`);
  if (fs.existsSync(file)) return JSON.parse(fs.readFileSync(file, 'utf8'));

  const rec = {
    id, case: caseObj.id, agent, arm, rep, startedAt: new Date().toISOString(), wallMs: 0, model: null, plugins: [], contaminated: false,
    usage: null, numTurns: null, stops: [], posthoc: null, facts: null, oraclePass: null, error: null,
  };
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'pino-bench-'));
  try {
    copyCase(caseObj, dir);
    const git = (...args) => execFileSync('git', [...AUTHOR, ...args], { cwd: dir, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim();
    git('init', '-q');
    git('add', '-A');
    git('commit', '-q', '-m', 'fixture');
    const base = git('rev-parse', 'HEAD');

    const t0 = Date.now();
    rec.startedAt = new Date(t0).toISOString();
    const argv = agent === 'claude' ? claudeArgv(arm, caseObj.prompt, { repoRoot }) : codexArgv(arm, caseObj.prompt, dir);
    const res = await runAgent(resolveCli(cli[agent]), argv, dir, timeoutMs);
    rec.wallMs = Date.now() - t0;

    const o = agent === 'claude' ? claudeOutcome(res.stdout, projectsDir) : codexOutcome(res.stdout, codexDir, dir, t0);
    if (res.code !== 0 && LIMIT.test(`${res.stderr}\n${o.errorText}`)) throw new PausedError(`usage limit: ${id}`);
    Object.assign(rec, { model: o.model, plugins: o.plugins, usage: o.usage, numTurns: o.numTurns });
    if (agent === 'claude') rec.contaminated = (arm === 'on') !== o.plugins.includes('pinocchio');
    if (!o.transcript) throw new Error(`transcript not found (exit ${res.code}${res.signal ? `, ${res.signal}` : ''}): ${res.stderr.trim().slice(-300)}`);

    const text = fs.readFileSync(o.transcript, 'utf8');
    const ledger = arm === 'on' ? readEntries(dir) : [];
    const stops = extractStops(text);
    rec.stops = stops.map(({ message }, i) => {
      const e = ledger[i];
      return { message, ledger: e ? { verdict: e.verdict, blocked: e.blocked, elapsed_ms: e.elapsed_ms, checks: e.checks } : null };
    });
    try {
      rec.posthoc = posthoc(o.transcript, dir, stop);
    } catch (e) {
      rec.posthoc = { verdict: 'error', checks: [], error: String(e?.message ?? e) };
    }
    rec.facts = facts({ events: parseTranscript(text).events, dir, base, caseObj, feedbackLine: stops[0].feedbackLine });
    rec.oraclePass = shellOk(caseObj.oracle, dir);
    if (res.signal) rec.error = `agent killed (${res.signal}) after ${rec.wallMs} ms`;
  } catch (e) {
    if (e instanceof PausedError || e instanceof SetupError) throw e;
    rec.error = String(e?.message ?? e);
  } finally {
    try {
      fs.rmSync(dir, { recursive: true, force: true, maxRetries: 3 });
    } catch {
      /* a stray agent process still holds a file; leave the temp dir */
    }
  }
  fs.mkdirSync(resultsDir, { recursive: true });
  fs.writeFileSync(`${file}.tmp`, `${JSON.stringify(rec, null, 2)}\n`);
  fs.renameSync(`${file}.tmp`, file);
  return rec;
}
