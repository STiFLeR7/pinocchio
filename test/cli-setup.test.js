import { after, test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, lstatSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, statSync, symlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { PassThrough } from 'node:stream';
import { fileURLToPath } from 'node:url';
import { createUI } from '../cli/ui.js';
import { claudeCli } from '../cli/claude.js';
import { readState } from '../cli/state.js';
import { hookCommandFor, setup } from '../cli/setup.js';
import { select } from '../cli/prompt.js';
import { registerHook, unregisterHook } from '../cli/fallback.js';
import { smokeTest } from '../cli/smoke.js';

const STUB = fileURLToPath(new URL('./fixtures/stub-claude-cli.mjs', import.meta.url));
const made = [];
const tmp = () => { const d = mkdtempSync(join(tmpdir(), 'pino-setup-')); made.push(d); return d; };
after(() => { for (const d of made) rmSync(d, { recursive: true, force: true }); });
const PLUGIN = '[{"id":"pinocchio@pinocchio","scope":"project","enabled":true}]';
const LISTS = [['plugin', 'list', '--json'], ['plugin', 'marketplace', 'list', '--json']];
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

async function runSetup({ cwd = project(), home = tmp(), argv = ['--yes'], answers = [], isTTY = false, system = SYS, fail, plugins = '[]', marketplaces = '[]', platform } = {}) {
  const log = join(tmp(), 'stub.log');
  let out = '';
  const asked = [];
  const ui = createUI({ stream: { write: (s) => { out += s; }, isTTY: false }, color: false, unicode: true, width: 120 });
  const prompt = async (q) => { asked.push(q); return answers.shift(); };
  const keys = ['STUB_LOG', 'STUB_FAIL', 'STUB_PLUGINS', 'STUB_MARKETPLACES'];
  const old = Object.fromEntries(keys.map((k) => [k, process.env[k]]));
  Object.assign(process.env, { STUB_LOG: log, STUB_PLUGINS: plugins, STUB_MARKETPLACES: marketplaces });
  if (fail) process.env.STUB_FAIL = fail; else delete process.env.STUB_FAIL;
  try {
    const code = await setup({ cwd, home, argv, ui, prompt, cli: claudeCli({ bin: STUB }), isTTY, system, platform });
    return { code, out, asked, cwd, home, calls: logged(log) };
  } finally {
    for (const k of keys) if (old[k] === undefined) delete process.env[k]; else process.env[k] = old[k];
  }
}

test('--yes project install calls marketplace add + install with --scope project and writes config + state', async () => {
  const r = await runSetup();
  assert.equal(r.code, 0, r.out);
  assert.deepEqual(r.calls, [
    ...LISTS,
    ['plugin', 'marketplace', 'add', 'STiFLeR7/pinocchio', '--scope', 'project', '--json'],
    ['plugin', 'install', 'pinocchio@pinocchio', '--scope', 'project', '-y', '--json'],
  ]);
  const configFile = join(r.cwd, '.claude', 'pinocchio.json');
  assert.deepEqual(JSON.parse(readFileSync(configFile, 'utf8')), { mode: 'default', testCommands: [String.raw`^npm (run )?test\b`], commitLedger: false });
  const state = readState(join(r.cwd, '.claude', 'pinocchio-install', 'install.json'));
  assert.equal(state.scope, 'project');
  assert.equal(state.method, 'plugin');
  assert.equal(state.addedMarketplace, true);
  assert.equal(state.addedPlugin, true);
  assert.equal(state.settings, null);
  assert.equal(state.runtime, null);
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
  assert.deepEqual(r.calls, LISTS);
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
  assert.deepEqual(r.calls, LISTS);
});

test('second run is a no-op showing already set up', async () => {
  const cwd = project();
  const home = tmp();
  assert.equal((await runSetup({ cwd, home })).code, 0);
  const before = [snap(cwd), snap(home)];
  const r = await runSetup({ cwd, home, plugins: PLUGIN });
  assert.equal(r.code, 0, r.out);
  assert.equal(r.out.match(/✔ already set up/g).length, 6);
  assert.deepEqual([snap(cwd), snap(home)], before);
  assert.deepEqual(r.calls, [['plugin', 'list', '--json']]);
});

test('marketplace add failure falls back to settings hook with runtime copy and says why', async () => {
  const r = await runSetup({ fail: 'add' });
  assert.equal(r.code, 0, r.out);
  assert.match(r.out, /marketplace add failed: stub: add failed/);
  assert.deepEqual(r.calls.slice(2).map((c) => c.slice(1, 3)), [['marketplace', 'add']]);
  const runtime = join(r.cwd, '.claude', 'pinocchio-install', 'runtime');
  const command = hookCommandFor(`${runtime.replace(/\\/g, '/')}/src/stop.js`);
  const settingsFile = join(r.cwd, '.claude', 'settings.local.json');
  assert.deepEqual(JSON.parse(readFileSync(settingsFile, 'utf8')), { hooks: { Stop: [{ hooks: [{ type: 'command', command, timeout: 5 }] }] } });
  const state = readState(join(r.cwd, '.claude', 'pinocchio-install', 'install.json'));
  assert.equal(state.method, 'settings');
  assert.equal(state.addedMarketplace, false);
  assert.deepEqual(state.settings, { file: settingsFile, hookCommand: command });
  assert.equal(state.runtime, runtime);
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
  writeFileSync(join(cwd, '.claude', 'settings.local.json'), bad);
  const r = await runSetup({ cwd, fail: 'add' });
  assert.equal(r.code, 1);
  assert.equal(readFileSync(join(cwd, '.claude', 'settings.local.json'), 'utf8'), bad);
  assert.match(r.out, /settings\.local\.json is not plain JSON/);
  assert.match(r.out, /"Stop": \[/);
  assert.match(r.out, /"command": "node (\\"|').*\/src\/stop\.js(\\"|')"/);
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
  assert.deepEqual(readState(join(cwd, '.claude', 'pinocchio-install', 'install.json')).files, []);
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
  assert.equal(readState(join(r.cwd, '.claude', 'pinocchio-install', 'install.json')).method, 'settings');
});

test('plugin already installed with no state: nothing is added, no settings hook', async () => {
  const r = await runSetup({ plugins: PLUGIN, fail: 'add' });
  assert.equal(r.code, 0, r.out);
  assert.deepEqual(r.calls, [LISTS[0]]);
  assert.ok(!existsSync(join(r.cwd, '.claude', 'settings.local.json')));
  assert.ok(!existsSync(join(r.cwd, '.claude', 'pinocchio-install', 'runtime')));
  assert.match(r.out, /already installed/);
  const state = readState(join(r.cwd, '.claude', 'pinocchio-install', 'install.json'));
  assert.deepEqual([state.method, state.addedMarketplace, state.addedPlugin], ['plugin', false, false]);
});

test('a substring match is not the plugin: only the exact id counts', async () => {
  const r = await runSetup({ plugins: '[{"id":"not-pinocchio@pinocchio-fork"}]' });
  assert.equal(r.code, 0, r.out);
  assert.ok(r.calls.some((c) => c[1] === 'install'));
});

test('marketplace already present: no add call, install called, marketplace not ours', async () => {
  const r = await runSetup({ marketplaces: '[{"name":"pinocchio"}]' });
  assert.equal(r.code, 0, r.out);
  assert.deepEqual(r.calls.slice(2), [['plugin', 'install', 'pinocchio@pinocchio', '--scope', 'project', '-y', '--json']]);
  const state = readState(join(r.cwd, '.claude', 'pinocchio-install', 'install.json'));
  assert.deepEqual([state.method, state.addedMarketplace, state.addedPlugin], ['plugin', false, true]);
});

test('install failure with a pre-existing marketplace never removes it', async () => {
  const r = await runSetup({ marketplaces: '[{"name":"pinocchio"}]', fail: 'install' });
  assert.equal(r.code, 0, r.out);
  assert.deepEqual(r.calls.slice(2).map((c) => c[1]), ['install']);
  assert.match(r.out, /claude plugin install failed: stub: install failed/);
  assert.equal(readState(join(r.cwd, '.claude', 'pinocchio-install', 'install.json')).method, 'settings');
});

test('install failure after this run added the marketplace removes it again', async () => {
  const r = await runSetup({ fail: 'install' });
  assert.equal(r.code, 0, r.out);
  assert.deepEqual(r.calls.slice(2).map((c) => c.slice(1, 3)), [['marketplace', 'add'], ['install', 'pinocchio@pinocchio'], ['marketplace', 'remove']]);
  assert.equal(readState(join(r.cwd, '.claude', 'pinocchio-install', 'install.json')).addedMarketplace, false);
});

test('a stale runtime copy is replaced, not merged', async () => {
  const cwd = project();
  const stale = join(cwd, '.claude', 'pinocchio-install', 'runtime', 'src', 'old.js');
  mkdirSync(join(stale, '..'), { recursive: true });
  writeFileSync(stale, 'x');
  const r = await runSetup({ cwd, fail: 'add' });
  assert.equal(r.code, 0, r.out);
  assert.ok(!existsSync(stale));
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
  assert.ok(r.calls.slice(2).every((c) => c.includes('user')));
  const state = readState(join(r.home, '.claude', 'pinocchio-install', 'install.json'));
  assert.equal(state.scope, 'user');
  assert.ok(!existsSync(join(r.cwd, '.claude', 'pinocchio-install', 'install.json')));
  assert.deepEqual(JSON.parse(readFileSync(join(r.cwd, '.claude', 'pinocchio.json'), 'utf8')).mode, 'strict');
  assert.match(r.out, /Mode and ledger settings apply to this project; other projects use defaults\./);
});

test('bad flag values exit 1 before anything runs', async () => {
  for (const argv of [['--scope', 'local'], ['--mode', 'loud'], ['--nope']]) {
    const r = await runSetup({ argv });
    assert.equal(r.code, 1);
    assert.deepEqual(r.calls, []);
  }
});

test('registerHook keeps a BOM and CRLF line endings and leaves no temp file', () => {
  const dir = tmp();
  const f = join(dir, 'settings.json');
  writeFileSync(f, '\uFEFF{\r\n  "model": "opus"\r\n}\r\n');
  assert.deepEqual(registerHook(f, 'c'), { ok: true });
  const raw = readFileSync(f, 'utf8');
  assert.ok(raw.startsWith('\uFEFF{\r\n  "model": "opus",\r\n'));
  assert.ok(!/[^\r]\n/.test(raw));
  assert.equal(JSON.parse(raw.slice(1)).hooks.Stop[0].hooks[0].command, 'c');
  assert.equal(unregisterHook(f, 'c'), true);
  assert.equal(readFileSync(f, 'utf8'), '\uFEFF{\r\n  "model": "opus"\r\n}\r\n');
  assert.deepEqual(readdirSync(dir), ['settings.json']);
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

const git = (cwd, ...args) => spawnSync('git', ['-c', 'user.email=t@t', '-c', 'user.name=t', '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=', ...args], { cwd, encoding: 'utf8' });
const stateIn = (root) => readState(join(root, '.claude', 'pinocchio-install', 'install.json'));

test('in a git repo, setup leaves only pinocchio.json for git to see, even with --commit-ledger', async () => {
  const cwd = project();
  writeFileSync(join(cwd, '.gitignore'), '.claude/settings.local.json\n'); // Claude Code's convention for personal settings
  git(cwd, 'init', '-q');
  git(cwd, 'add', '.');
  git(cwd, 'commit', '-q', '-m', 'init');
  const r = await runSetup({ cwd, fail: 'add', argv: ['--yes', '--commit-ledger'] });
  assert.equal(r.code, 0, r.out);
  assert.ok(existsSync(join(cwd, '.claude', 'pinocchio-install', 'runtime', 'src', 'stop.js')));
  assert.equal(readFileSync(join(cwd, '.claude', 'pinocchio-install', '.gitignore'), 'utf8'), '*\n');
  assert.deepEqual(git(cwd, 'status', '--porcelain', '-uall').stdout.trim().split('\n'), ['?? .claude/pinocchio.json']);
});

test('project fallback hook goes to settings.local.json; user scope to ~/.claude/settings.json', async () => {
  const p = await runSetup({ fail: 'add' });
  assert.match(p.out, /Stop hook in \.claude\/settings\.local\.json/);
  assert.ok(!existsSync(join(p.cwd, '.claude', 'settings.json')));
  const u = await runSetup({ fail: 'add', argv: ['--yes', '--scope', 'user'] });
  assert.equal(u.code, 0, u.out);
  const st = stateIn(u.home);
  assert.equal(st.settings.file, join(u.home, '.claude', 'settings.json'));
  assert.equal(st.runtime, join(u.home, '.claude', 'pinocchio-install', 'runtime'));
  assert.ok(!existsSync(join(u.cwd, '.claude', 'settings.local.json')));
});

test('hook command quoting: single quotes on POSIX (embedded quote escaped), double quotes on win32', async () => {
  assert.equal(hookCommandFor("/h/it's/src/stop.js", 'linux'), "node '/h/it'\\''s/src/stop.js'");
  assert.equal(hookCommandFor('/h/a b/src/stop.js', 'darwin'), "node '/h/a b/src/stop.js'");
  assert.equal(hookCommandFor('C:/a b/src/stop.js', 'win32'), 'node "C:/a b/src/stop.js"');
  // A POSIX shell (where one exists) reads the quoted path back unchanged.
  const path = "/x/it's $HOME `id`/s.js";
  const sh = spawnSync('sh', ['-c', `printf %s ${hookCommandFor(path, 'linux').slice('node '.length)}`], { encoding: 'utf8' });
  if (!sh.error) assert.equal(sh.stdout, path);
  // setup takes the platform as a seam.
  const cwd = project();
  const r = await runSetup({ cwd, fail: 'add', platform: 'linux' });
  assert.equal(r.code, 0, r.out);
  const stopJs = `${join(cwd, '.claude', 'pinocchio-install', 'runtime').replace(/\\/g, '/')}/src/stop.js`;
  assert.equal(stateIn(cwd).settings.hookCommand, hookCommandFor(stopJs, 'linux'));
});

test('re-run keeps addedMarketplace from an earlier run whose marketplace is still there', async () => {
  const cwd = project();
  const home = tmp();
  assert.equal((await runSetup({ cwd, home })).code, 0); // added marketplace + plugin
  // The user removed the plugin by hand; the marketplace setup added is still there.
  const r = await runSetup({ cwd, home, marketplaces: '[{"name":"pinocchio"}]' });
  assert.equal(r.code, 0, r.out);
  assert.ok(!r.calls.some((c) => c[2] === 'add'));
  assert.equal(stateIn(cwd).addedMarketplace, true);
});

test('re-run that switches from the settings hook to the plugin removes the old runtime and hook', async () => {
  const cwd = project();
  const home = tmp();
  assert.equal((await runSetup({ cwd, home, fail: 'add' })).code, 0);
  const runtime = join(cwd, '.claude', 'pinocchio-install', 'runtime');
  rmSync(join(runtime, 'src', 'stop.js')); // broken install: not "already set up"
  const r = await runSetup({ cwd, home });
  assert.equal(r.code, 0, r.out);
  assert.deepEqual([stateIn(cwd).method, stateIn(cwd).runtime], ['plugin', null]);
  assert.ok(!existsSync(runtime));
  assert.deepEqual(JSON.parse(readFileSync(join(cwd, '.claude', 'settings.local.json'), 'utf8')), {});
});

test('re-run over a legacy install moves it out of the ledger dir and cleans its leftovers', async () => {
  const cwd = project();
  const home = tmp();
  const ledgerDir = join(cwd, '.claude', 'pinocchio');
  const oldRuntime = join(ledgerDir, 'runtime');
  const oldSettings = join(cwd, '.claude', 'settings.json');
  mkdirSync(join(oldRuntime, 'src'), { recursive: true }); // runtime without stop.js: the old hook is dead
  writeFileSync(join(ledgerDir, 'ledger.jsonl'), 'keep me\n');
  writeFileSync(oldSettings, JSON.stringify({ model: 'opus' }));
  registerHook(oldSettings, 'node "old/src/stop.js"');
  writeFileSync(join(ledgerDir, 'install.json'), JSON.stringify({
    version: 1, scope: 'project', method: 'settings', addedMarketplace: false, addedPlugin: false, files: [],
    settings: { file: oldSettings, hookCommand: 'node "old/src/stop.js"' }, runtime: oldRuntime, at: 't',
  }));
  const r = await runSetup({ cwd, home, fail: 'add' });
  assert.equal(r.code, 0, r.out);
  assert.ok(!existsSync(oldRuntime));
  assert.ok(!existsSync(join(ledgerDir, 'install.json')));
  assert.deepEqual(JSON.parse(readFileSync(oldSettings, 'utf8')), { model: 'opus' });
  assert.equal(readFileSync(join(ledgerDir, 'ledger.jsonl'), 'utf8'), 'keep me\n');
  assert.equal(stateIn(cwd).method, 'settings');
});

test('registerHook keeps a symlinked settings file a symlink and writes through it', (t) => {
  const dir = tmp();
  const real = join(dir, 'dotfiles-settings.json');
  const link = join(dir, 'settings.json');
  writeFileSync(real, '{"model":"opus"}');
  try { symlinkSync(real, link); } catch { t.skip('cannot create symlinks here'); return; }
  assert.deepEqual(registerHook(link, 'c'), { ok: true });
  assert.ok(lstatSync(link).isSymbolicLink());
  assert.equal(JSON.parse(readFileSync(real, 'utf8')).hooks.Stop[0].hooks[0].command, 'c');
  assert.equal(unregisterHook(link, 'c'), true);
  assert.ok(lstatSync(link).isSymbolicLink());
  assert.deepEqual(JSON.parse(readFileSync(real, 'utf8')), { model: 'opus' });
  assert.deepEqual(readdirSync(dir).sort(), ['dotfiles-settings.json', 'settings.json']);
});

test('a failed settings write leaves the file as it was and no temp file', () => {
  const dir = tmp();
  const f = join(dir, 'settings.json');
  writeFileSync(f, '{"model":"opus"}');
  const rename = () => { throw Object.assign(new Error('nope'), { code: 'EPERM' }); };
  assert.deepEqual(registerHook(f, 'c', { rename }), { ok: false, reason: 'cannot write settings.json: EPERM' });
  assert.equal(readFileSync(f, 'utf8'), '{"model":"opus"}');
  assert.deepEqual(readdirSync(dir), ['settings.json']);
  registerHook(f, 'c');
  const before = readFileSync(f, 'utf8');
  assert.throws(() => unregisterHook(f, 'c', { rename }), /cannot write settings\.json: EPERM/);
  assert.equal(readFileSync(f, 'utf8'), before);
  assert.deepEqual(readdirSync(dir), ['settings.json']);
});

test('setup: a settings file that cannot be written takes the manual-snippet path and still records state', async () => {
  const cwd = project();
  mkdirSync(join(cwd, '.claude', 'settings.local.json'), { recursive: true }); // a directory: reading fails
  const r = await runSetup({ cwd, fail: 'add' });
  assert.equal(r.code, 1);
  assert.match(r.out, /settings\.local\.json left untouched/);
  assert.match(r.out, /by hand/);
  assert.equal(stateIn(cwd).method, 'settings');
});
