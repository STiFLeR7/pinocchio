import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { PassThrough } from 'node:stream';
import { fileURLToPath } from 'node:url';
import { createUI } from '../cli/ui.js';
import { claudeCli } from '../cli/claude.js';
import { readState } from '../cli/state.js';
import { setup } from '../cli/setup.js';
import { select } from '../cli/prompt.js';
import { registerHook, unregisterHook } from '../cli/fallback.js';
import { smokeTest } from '../cli/smoke.js';

const STUB = fileURLToPath(new URL('./fixtures/stub-claude-cli.mjs', import.meta.url));
const tmp = () => mkdtempSync(join(tmpdir(), 'pino-setup-'));
const SYS = {
  node: { ok: true, version: 'v22.11.0' },
  git: { ok: true, version: 'git version 2.47.0' },
  claude: { ok: true, version: '2.1.289 (Claude Code)' },
  codex: { ok: false, version: null },
};

function project() {
  const dir = tmp();
  writeFileSync(join(dir, 'package.json'), JSON.stringify({ scripts: { test: 'node --test' } }));
  return dir;
}

// Every file under dir with its content (directories as null): equal snapshots mean nothing was written.
function snap(dir) {
  const out = {};
  for (const f of readdirSync(dir, { recursive: true })) {
    const p = join(dir, f);
    out[f] = statSync(p).isFile() ? readFileSync(p, 'utf8') : null;
  }
  return out;
}

const logged = (log) => (existsSync(log) ? readFileSync(log, 'utf8').trim().split('\n').map((l) => JSON.parse(l)) : []);

async function runSetup({ cwd = project(), home = tmp(), argv = ['--yes'], answers = [], isTTY = false, system = SYS, fail } = {}) {
  const log = join(tmp(), 'stub.log');
  let out = '';
  const asked = [];
  const ui = createUI({ stream: { write: (s) => { out += s; }, isTTY: false }, color: false, unicode: true, width: 120 });
  const prompt = async (q) => { asked.push(q); return answers.shift(); };
  const old = { log: process.env.STUB_LOG, fail: process.env.STUB_FAIL };
  process.env.STUB_LOG = log;
  if (fail) process.env.STUB_FAIL = fail; else delete process.env.STUB_FAIL;
  try {
    const code = await setup({ cwd, home, argv, ui, prompt, cli: claudeCli({ bin: STUB }), isTTY, system });
    return { code, out, asked, cwd, home, calls: logged(log) };
  } finally {
    for (const [k, v] of [['STUB_LOG', old.log], ['STUB_FAIL', old.fail]]) if (v === undefined) delete process.env[k]; else process.env[k] = v;
  }
}

test('--yes project install calls marketplace add + install with --scope project and writes config + state', async () => {
  const r = await runSetup();
  assert.equal(r.code, 0, r.out);
  assert.deepEqual(r.calls, [
    ['plugin', 'marketplace', 'add', 'STiFLeR7/pinocchio', '--scope', 'project', '--json'],
    ['plugin', 'install', 'pinocchio@pinocchio', '--scope', 'project', '-y', '--json'],
  ]);
  const configFile = join(r.cwd, '.claude', 'pinocchio.json');
  assert.deepEqual(JSON.parse(readFileSync(configFile, 'utf8')), { mode: 'default', testCommands: [String.raw`^npm (run )?test\b`], commitLedger: false });
  const state = readState(join(r.cwd, '.claude', 'pinocchio', 'install.json'));
  assert.equal(state.scope, 'project');
  assert.equal(state.method, 'plugin');
  assert.equal(state.addedMarketplace, true);
  assert.equal(state.settings, null);
  assert.equal(state.files.length, 1);
  assert.equal(state.files[0].path, configFile);
  assert.match(state.files[0].sha256, /^[0-9a-f]{64}$/);
  assert.deepEqual(readdirSync(r.home), []);
  for (const s of ['Step 1 · Check system', 'Step 6 · Test run', 'Token cost: ~93 tokens/session · 0 for the hook itself',
    'Reads only: never edits code, never runs commands for you', '🎉  Pinocchio is watching.', 'pinocchio uninstall']) assert.ok(r.out.includes(s), s);
});

test('nothing is written when the user answers No at Review', async () => {
  const cwd = project();
  const home = tmp();
  const before = [snap(cwd), snap(home)];
  const r = await runSetup({ cwd, home, argv: [], isTTY: true, answers: ['project', 'strict', true, false] });
  assert.equal(r.code, 0);
  assert.deepEqual(r.asked, ['Where to install?', 'Mode?', 'Commit the lie ledger to git?', 'Install now?']);
  assert.deepEqual([snap(cwd), snap(home)], before);
  assert.deepEqual(r.calls, []);
  assert.match(r.out, /Nothing written/);
});

test('non-TTY without --yes exits 1 and writes nothing', async () => {
  const cwd = project();
  const before = snap(cwd);
  const r = await runSetup({ cwd, argv: [] });
  assert.equal(r.code, 1);
  assert.deepEqual(r.asked, []);
  assert.match(r.out, /Step 4 · Review — nothing written yet/);
  assert.match(r.out, /re-run with --yes/);
  assert.deepEqual(snap(cwd), before);
  assert.deepEqual(r.calls, []);
});

test('second run is a no-op showing already set up', async () => {
  const cwd = project();
  const home = tmp();
  assert.equal((await runSetup({ cwd, home })).code, 0);
  const before = [snap(cwd), snap(home)];
  const r = await runSetup({ cwd, home });
  assert.equal(r.code, 0, r.out);
  assert.equal(r.out.match(/✔ already set up/g).length, 6);
  assert.deepEqual([snap(cwd), snap(home)], before);
  assert.deepEqual(r.calls, [['plugin', 'list', '--json']]);
});

test('marketplace add failure falls back to settings hook with runtime copy and says why', async () => {
  const r = await runSetup({ fail: 'add' });
  assert.equal(r.code, 0, r.out);
  assert.match(r.out, /marketplace add failed: stub: add failed/);
  assert.deepEqual(r.calls.map((c) => c[1]), ['marketplace']);
  const runtime = join(r.cwd, '.claude', 'pinocchio', 'runtime');
  const command = `node "${runtime.replace(/\\/g, '/')}/src/stop.js"`;
  const settingsFile = join(r.cwd, '.claude', 'settings.json');
  assert.deepEqual(JSON.parse(readFileSync(settingsFile, 'utf8')), { hooks: { Stop: [{ hooks: [{ type: 'command', command, timeout: 5 }] }] } });
  const state = readState(join(r.cwd, '.claude', 'pinocchio', 'install.json'));
  assert.equal(state.method, 'settings');
  assert.equal(state.addedMarketplace, false);
  assert.deepEqual(state.settings, { file: settingsFile, hookCommand: command });
  assert.ok(existsSync(join(runtime, 'package.json')));
  // The copied runtime loads on its own: PINOCCHIO=off makes it exit 0 with no output.
  const hook = spawnSync(process.execPath, [join(runtime, 'src', 'stop.js')], { input: '{}', cwd: tmp(), encoding: 'utf8', env: { ...process.env, PINOCCHIO: 'off' } });
  assert.equal(hook.status, 0, hook.stderr);
  assert.equal(hook.stdout, '');
});

test('invalid settings.json is never written; prints manual snippet; exit 1', async () => {
  const cwd = project();
  mkdirSync(join(cwd, '.claude'));
  const bad = '{\n  // my settings\n  "model": "opus",\n}\n';
  writeFileSync(join(cwd, '.claude', 'settings.json'), bad);
  const r = await runSetup({ cwd, fail: 'add' });
  assert.equal(r.code, 1);
  assert.equal(readFileSync(join(cwd, '.claude', 'settings.json'), 'utf8'), bad);
  assert.match(r.out, /settings\.json is not plain JSON/);
  assert.match(r.out, /"Stop": \[/);
  assert.match(r.out, /"command": "node \\".*\/src\/stop\.js\\""/);
  assert.doesNotMatch(r.out, /Pinocchio is watching/);
});

test('existing pinocchio.json is kept', async () => {
  const cwd = project();
  mkdirSync(join(cwd, '.claude'));
  const mine = '{ "mode": "report" }\n';
  writeFileSync(join(cwd, '.claude', 'pinocchio.json'), mine);
  const r = await runSetup({ cwd });
  assert.equal(r.code, 0, r.out);
  assert.equal(readFileSync(join(cwd, '.claude', 'pinocchio.json'), 'utf8'), mine);
  assert.match(r.out, /kept existing \.claude\/pinocchio\.json/);
  assert.deepEqual(readState(join(cwd, '.claude', 'pinocchio', 'install.json')).files, []);
});

test('Node 16 stops at step 1', async () => {
  const cwd = project();
  const before = snap(cwd);
  const r = await runSetup({ cwd, system: { ...SYS, node: { ok: false, version: 'v16.20.0' } } });
  assert.equal(r.code, 1);
  assert.match(r.out, /✖ Step 1 · Check system/);
  assert.match(r.out, /Node 16\.20\.0/);
  assert.match(r.out, /fix: install Node 18 or newer/);
  assert.doesNotMatch(r.out, /Step 2/);
  assert.deepEqual(snap(cwd), before);
  assert.deepEqual(r.calls, []);
});

test('no claude CLI goes straight to the settings hook; codex is skill only', async () => {
  const r = await runSetup({ system: { ...SYS, claude: { ok: false, version: null }, codex: { ok: true, version: 'codex-cli 0.163.0' } } });
  assert.equal(r.code, 0, r.out);
  assert.deepEqual(r.calls, []);
  assert.match(r.out, /Codex 0\.163\.0 +→ skill only \(Codex has no blocking hook\)/);
  assert.match(r.out, /Claude Code CLI not found/);
  assert.equal(readState(join(r.cwd, '.claude', 'pinocchio', 'install.json')).method, 'settings');
});

test('smoke test receipt starts with 🤥 Pinocchio · FAIL', () => {
  const s = smokeTest();
  assert.equal(s.ok, true, s.receipt);
  assert.match(s.receipt, /^🤥 Pinocchio · FAIL/);
  assert.match(s.receipt, /stale-tests/);
});

test('user scope writes state under HOME', async () => {
  const r = await runSetup({ argv: ['--yes', '--scope', 'user', '--mode', 'strict', '--commit-ledger'] });
  assert.equal(r.code, 0, r.out);
  assert.ok(r.calls.every((c) => c.includes('user')));
  const state = readState(join(r.home, '.claude', 'pinocchio', 'install.json'));
  assert.equal(state.scope, 'user');
  assert.ok(!existsSync(join(r.cwd, '.claude', 'pinocchio', 'install.json')));
  assert.deepEqual(JSON.parse(readFileSync(join(r.cwd, '.claude', 'pinocchio.json'), 'utf8')).mode, 'strict');
});

test('bad flag values exit 1 before anything runs', async () => {
  for (const argv of [['--scope', 'local'], ['--mode', 'loud'], ['--nope']]) {
    const r = await runSetup({ argv });
    assert.equal(r.code, 1);
    assert.deepEqual(r.calls, []);
  }
});

test('select: non-TTY reads a typed number, empty line takes the default', async () => {
  const opts = [{ label: 'A', value: 'a' }, { label: 'B', value: 'b' }];
  for (const [typed, want] of [['2\n', 'b'], ['\n', 'a'], ['9\n', 'a']]) {
    const input = new PassThrough();
    const output = new PassThrough();
    const p = select('Pick?', opts, { input, output });
    input.end(typed);
    assert.equal(await p, want);
  }
});

test('select: TTY moves with arrow keys and confirms with Enter', async () => {
  const input = Object.assign(new PassThrough(), { isTTY: true, setRawMode() {} });
  const output = new PassThrough();
  const p = select('Pick?', [{ label: 'A', value: 'a' }, { label: 'B', value: 'b' }, { label: 'C', value: 'c' }], { input, output });
  input.write('\x1b[B');
  input.write('\x1b[B');
  input.write('\x1b[A');
  input.write('\r');
  assert.equal(await p, 'b');
});

test('registerHook preserves other keys and order, is idempotent; unregisterHook removes only that hook', () => {
  const f = join(tmp(), 'settings.json');
  const other = { type: 'command', command: 'echo hi' };
  writeFileSync(f, JSON.stringify({ model: 'opus', hooks: { PreToolUse: [], Stop: [{ hooks: [other] }] }, env: { A: '1' } }));
  assert.deepEqual(registerHook(f, 'node "x/src/stop.js"'), { ok: true });
  assert.deepEqual(registerHook(f, 'node "x/src/stop.js"'), { ok: true });
  const after = readFileSync(f, 'utf8');
  assert.deepEqual(Object.keys(JSON.parse(after)), ['model', 'hooks', 'env']);
  assert.deepEqual(JSON.parse(after).hooks.Stop, [{ hooks: [other] }, { hooks: [{ type: 'command', command: 'node "x/src/stop.js"', timeout: 5 }] }]);
  assert.ok(after.startsWith('{\n  "model"'));
  assert.equal(unregisterHook(f, 'node "x/src/stop.js"'), true);
  assert.deepEqual(JSON.parse(readFileSync(f, 'utf8')), { model: 'opus', hooks: { PreToolUse: [], Stop: [{ hooks: [other] }] }, env: { A: '1' } });
  assert.equal(unregisterHook(f, 'node "x/src/stop.js"'), false);
});

test('registerHook creates a missing file and refuses invalid JSON without writing', () => {
  const dir = tmp();
  const f = join(dir, '.claude', 'settings.json');
  assert.deepEqual(registerHook(f, 'c'), { ok: true });
  assert.deepEqual(JSON.parse(readFileSync(f, 'utf8')), { hooks: { Stop: [{ hooks: [{ type: 'command', command: 'c', timeout: 5 }] }] } });
  for (const bad of ['{ "a": 1, }', '// x\n{}', '[1]']) {
    writeFileSync(f, bad);
    assert.equal(registerHook(f, 'c').ok, false);
    assert.equal(unregisterHook(f, 'c'), false);
    assert.equal(readFileSync(f, 'utf8'), bad);
  }
  assert.deepEqual(registerHook(join(dir, 'x.json'), 'c'), { ok: true });
  writeFileSync(f, '{ "a": 1, }');
  assert.deepEqual(registerHook(f, 'c'), { ok: false, reason: 'settings.json is not plain JSON' });
});
