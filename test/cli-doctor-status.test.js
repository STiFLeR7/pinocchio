import { after, test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createUI } from '../cli/ui.js';
import { doctor } from '../cli/doctor.js';
import { status } from '../cli/status.js';
import { writeState, statePath, legacyStatePath } from '../cli/state.js';
import { appendEntry } from '../src/ledger.js';

const made = [];
const tmp = () => { const d = mkdtempSync(join(tmpdir(), 'pino-doc-')); made.push(d); return d; };
after(() => { for (const d of made) rmSync(d, { recursive: true, force: true }); });
const SYS = { node: { ok: true, version: 'v22.11.0' }, git: { ok: true, version: 'git version 2.47.0' } };
const cliWith = (json) => ({ listPlugins: () => ({ ok: true, json, stderr: '' }) });
const REG = [{ id: 'pinocchio@pinocchio', enabled: true, scope: 'project' }];
const capture = () => {
  const o = { out: '' };
  o.ui = createUI({ stream: { write: (s) => { o.out += s; }, isTTY: false }, color: false, unicode: true, width: 100 });
  return o;
};
const entry = (session, verdict, id) => ({ ts: 't', session, verdict, checks: id ? [{ id, status: 'fail' }] : [] });
const ledgerFile = (cwd) => join(cwd, '.claude', 'pinocchio', 'ledger.jsonl');

test('doctor all green exits 0', () => {
  const cwd = tmp();
  appendEntry(cwd, entry('a', 'pass'));
  const o = capture();
  assert.equal(doctor({ cwd, home: tmp(), ui: o.ui, cli: cliWith(REG), system: SYS }), 0);
  assert.match(o.out, /All good/);
  assert.doesNotMatch(o.out, /✖/);
});

test('doctor with bad config JSON exits 1 and names the fix', () => {
  const cwd = tmp();
  mkdirSync(join(cwd, '.claude'));
  writeFileSync(join(cwd, '.claude', 'pinocchio.json'), '{ nope');
  const o = capture();
  assert.equal(doctor({ cwd, home: tmp(), ui: o.ui, cli: cliWith(REG), system: SYS }), 1);
  assert.match(o.out, /invalid JSON/);
  assert.match(o.out, /fix: fix \.claude\/pinocchio\.json/);
});

test('doctor with broken chain reports it', () => {
  const cwd = tmp();
  appendEntry(cwd, entry('a', 'pass'));
  appendEntry(cwd, entry('b', 'fail', 'stale-tests'));
  writeFileSync(ledgerFile(cwd), readFileSync(ledgerFile(cwd), 'utf8').replace('"pass"', '"fail"'));
  const o = capture();
  assert.equal(doctor({ cwd, home: tmp(), ui: o.ui, cli: cliWith(REG), system: SYS }), 1);
  assert.match(o.out, /chain broken at entry 1/);
});

test('doctor: unregistered and disabled plugin each name their fix', () => {
  const o = capture();
  assert.equal(doctor({ cwd: tmp(), home: tmp(), ui: o.ui, cli: cliWith([]), system: SYS }), 1);
  assert.match(o.out, /fix: run: npx @stifler7\/pinocchio setup/);
  const d = capture();
  assert.equal(doctor({ cwd: tmp(), home: tmp(), ui: d.ui, cli: cliWith([{ id: 'pinocchio@pinocchio', enabled: false }]), system: SYS }), 1);
  assert.match(d.out, /fix: run: claude plugin enable pinocchio@pinocchio/);
});

// A settings-hook install: hook in settings.local.json, runtime copy with src/stop.js, state at `stateFile`.
function hookInstall(cwd, stateFile, runtime) {
  const file = join(cwd, '.claude', 'settings.local.json');
  const hookCommand = 'node "x/src/stop.js"';
  mkdirSync(join(runtime, 'src'), { recursive: true });
  writeFileSync(join(runtime, 'src', 'stop.js'), '');
  writeFileSync(file, JSON.stringify({ hooks: { Stop: [{ hooks: [{ type: 'command', command: hookCommand }] }] } }));
  writeState(stateFile, { version: 1, method: 'settings', settings: { file, hookCommand }, runtime });
}
const noPlugins = { listPlugins: () => ({ ok: false, json: null }) };

test('doctor accepts a settings hook recorded in install state', () => {
  const cwd = tmp();
  const home = tmp();
  hookInstall(cwd, statePath('project', cwd, home), join(cwd, '.claude', 'pinocchio-install', 'runtime'));
  const o = capture();
  assert.equal(doctor({ cwd, home, ui: o.ui, cli: noPlugins, system: SYS }), 0);
  assert.match(o.out, /Stop hook registered \(project settings\.local\.json\)/);
});

test('doctor reads a legacy install record in the ledger dir', () => {
  const cwd = tmp();
  const home = tmp();
  hookInstall(cwd, legacyStatePath('project', cwd, home), join(cwd, '.claude', 'pinocchio', 'runtime'));
  const o = capture();
  assert.equal(doctor({ cwd, home, ui: o.ui, cli: noPlugins, system: SYS }), 0);
});

test('doctor: settings hook whose runtime copy is gone names the setup fix', () => {
  const cwd = tmp();
  const home = tmp();
  const runtime = join(cwd, '.claude', 'pinocchio-install', 'runtime');
  hookInstall(cwd, statePath('project', cwd, home), runtime);
  rmSync(runtime, { recursive: true });
  const o = capture();
  assert.equal(doctor({ cwd, home, ui: o.ui, cli: noPlugins, system: SYS }), 1);
  assert.match(o.out, /runtime copy is missing/);
  assert.match(o.out, /fix: run: npx @stifler7\/pinocchio setup/);
});

test('doctor flags missing node and git', () => {
  const o = capture();
  const system = { node: { ok: false, version: 'v16.0.0' }, git: { ok: false, version: null } };
  assert.equal(doctor({ cwd: tmp(), home: tmp(), ui: o.ui, cli: cliWith(REG), system }), 1);
  assert.match(o.out, /fix: install Node 18/);
  assert.match(o.out, /fix: install git/);
});

test('status counts sessions by last verdict', () => {
  const cwd = tmp();
  appendEntry(cwd, entry('a', 'fail', 'stale-tests'));
  appendEntry(cwd, entry('a', 'pass')); // session a ends pass
  appendEntry(cwd, entry('b', 'fail', 'stale-tests'));
  appendEntry(cwd, entry('c', 'cant_tell'));
  appendEntry(cwd, entry('d', 'pass'));
  const o = capture();
  assert.equal(status({ cwd, ui: o.ui }), 0);
  assert.match(o.out, /Nose length +▇▇░{8} +2 lies caught/);
  assert.match(o.out, /Sessions +4 checked · 2 pass · 1 fail · 1 can't tell/);
  assert.match(o.out, /Last 3 +✖ FAIL stale-tests +\? CAN'T TELL +✔ PASS/);
  assert.match(o.out, /Ledger +✔ hash chain intact \(5 entries\)/);
});

test('status caps the nose bar at 10 cells', () => {
  const cwd = tmp();
  for (let i = 0; i < 12; i++) appendEntry(cwd, entry(`s${i}`, 'fail', 'x'));
  const o = capture();
  status({ cwd, ui: o.ui });
  assert.match(o.out, /▇{10} +12 lies caught/);
});

test('status with no ledger prints the empty message', () => {
  const o = capture();
  assert.equal(status({ cwd: tmp(), ui: o.ui }), 0);
  assert.match(o.out, /No sessions yet — Pinocchio writes a receipt after your agent's next edit\./);
});

test('status chain broken line', () => {
  const cwd = tmp();
  appendEntry(cwd, entry('a', 'pass'));
  appendEntry(cwd, entry('b', 'pass'));
  const lines = readFileSync(ledgerFile(cwd), 'utf8').trim().split('\n');
  lines[1] = lines[1].replace('"b"', '"z"');
  writeFileSync(ledgerFile(cwd), lines.join('\n') + '\n');
  const o = capture();
  assert.equal(status({ cwd, ui: o.ui }), 0);
  assert.match(o.out, /Ledger +✖ chain broken at entry 2/);
});
