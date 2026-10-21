import { after, test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createUI } from '../cli/ui.js';
import { uninstall } from '../cli/uninstall.js';
import { statePath, writeState, sha256File } from '../cli/state.js';
import { registerHook } from '../cli/fallback.js';

const made = [];
const tmp = () => { const d = mkdtempSync(join(tmpdir(), 'pino-un-')); made.push(d); return d; };
after(() => { for (const d of made) rmSync(d, { recursive: true, force: true }); });
const capture = () => {
  const o = { out: '' };
  o.ui = createUI({ stream: { write: (s) => { o.out += s; }, isTTY: false }, color: false, unicode: true, width: 100 });
  return o;
};
const fakeCli = (fail = {}, listed = true) => {
  const calls = [];
  const rec = (name) => () => { calls.push(name); return fail[name] ? { ok: false, json: null, stderr: 'boom\nmore' } : { ok: true, json: {}, stderr: '' }; };
  return { calls, listPlugins: () => ({ ok: true, json: listed ? [{ id: 'pinocchio@pinocchio' }] : [], stderr: '' }), uninstall: rec('uninstall'), marketplaceRemove: rec('marketplaceRemove') };
};
// A project with a setup-written config and its recorded state.
function project(extra = {}) {
  const cwd = tmp();
  const home = tmp();
  const config = join(cwd, '.claude', 'pinocchio.json');
  const ledger = join(cwd, '.claude', 'pinocchio', 'ledger.jsonl');
  mkdirSync(join(cwd, '.claude', 'pinocchio'), { recursive: true });
  writeFileSync(config, '{"mode":"default"}\n');
  writeFileSync(ledger, 'keep me\n');
  writeState(statePath('project', cwd, home), {
    version: 1, scope: 'project', method: 'plugin', addedMarketplace: true, addedPlugin: true,
    files: [{ path: config, sha256: sha256File(config) }], settings: null, runtime: null, at: 't', ...extra,
  });
  return { cwd, home, config, ledger };
}

test('uninstall after plugin setup calls uninstall + marketplace remove and deletes config and state', () => {
  const p = project();
  const cli = fakeCli();
  const o = capture();
  assert.equal(uninstall({ cwd: p.cwd, home: p.home, ui: o.ui, cli }), 0);
  assert.deepEqual(cli.calls, ['uninstall', 'marketplaceRemove']);
  assert.equal(existsSync(p.config), false);
  assert.equal(existsSync(statePath('project', p.cwd, p.home)), false);
  assert.equal(readFileSync(p.ledger, 'utf8'), 'keep me\n');
  assert.match(o.out, /ledger kept at \.claude\/pinocchio\//);
});

test('plugin or marketplace installed outside setup is kept and not called', () => {
  const p = project({ addedPlugin: false, addedMarketplace: false });
  const cli = fakeCli();
  const o = capture();
  assert.equal(uninstall({ cwd: p.cwd, home: p.home, ui: o.ui, cli }), 0);
  assert.deepEqual(cli.calls, []);
  assert.match(o.out, /kept pinocchio plugin \(installed outside setup\)/);
  const q = project({ addedPlugin: true, addedMarketplace: false });
  const cli2 = fakeCli();
  uninstall({ cwd: q.cwd, home: q.home, ui: capture().ui, cli: cli2 });
  assert.deepEqual(cli2.calls, ['uninstall']);
});

test('edited config is kept', () => {
  const p = project();
  writeFileSync(p.config, '{"mode":"strict"}\n');
  const o = capture();
  assert.equal(uninstall({ cwd: p.cwd, home: p.home, ui: o.ui, cli: fakeCli() }), 0);
  assert.equal(readFileSync(p.config, 'utf8'), '{"mode":"strict"}\n');
  assert.match(o.out, /kept .*pinocchio\.json \(changed since setup\)/);
  assert.equal(existsSync(statePath('project', p.cwd, p.home)), false);
});

test('settings fallback hook removed, other keys intact, runtime deleted', () => {
  const cwd = tmp();
  const home = tmp();
  const settingsFile = join(cwd, '.claude', 'settings.json');
  const runtime = join(cwd, '.claude', 'pinocchio', 'runtime');
  const ledger = join(cwd, '.claude', 'pinocchio', 'ledger.jsonl');
  mkdirSync(join(runtime, 'src'), { recursive: true });
  writeFileSync(join(runtime, 'src', 'a.js'), 'x');
  writeFileSync(ledger, 'keep me\n');
  writeFileSync(settingsFile, JSON.stringify({ theme: 'dark' }));
  registerHook(settingsFile, 'node runtime/hook.js');
  writeState(statePath('project', cwd, home), {
    version: 1, scope: 'project', method: 'settings', addedMarketplace: false, addedPlugin: false,
    files: [], settings: { file: settingsFile, hookCommand: 'node runtime/hook.js' }, runtime, at: 't',
  });
  const cli = fakeCli();
  assert.equal(uninstall({ cwd, home, ui: capture().ui, cli }), 0);
  assert.deepEqual(JSON.parse(readFileSync(settingsFile, 'utf8')), { theme: 'dark' });
  assert.deepEqual(cli.calls, []);
  assert.equal(existsSync(runtime), false);
  assert.equal(readFileSync(ledger, 'utf8'), 'keep me\n');
});

test('no state prints nothing to remove', () => {
  const o = capture();
  const cli = fakeCli();
  assert.equal(uninstall({ cwd: tmp(), home: tmp(), ui: o.ui, cli }), 0);
  assert.match(o.out, /Nothing to remove — Pinocchio was not installed by setup here\./);
  assert.deepEqual(cli.calls, []);
});

test('uninstall twice is a no-op', () => {
  const p = project();
  assert.equal(uninstall({ cwd: p.cwd, home: p.home, ui: capture().ui, cli: fakeCli() }), 0);
  const cli = fakeCli();
  const o = capture();
  assert.equal(uninstall({ cwd: p.cwd, home: p.home, ui: o.ui, cli }), 0);
  assert.match(o.out, /Nothing to remove/);
  assert.deepEqual(cli.calls, []);
});

test('claude CLI failure exits 1 and keeps state and files', () => {
  const p = project();
  const o = capture();
  assert.equal(uninstall({ cwd: p.cwd, home: p.home, ui: o.ui, cli: fakeCli({ uninstall: true }) }), 1);
  assert.match(o.out, /claude plugin uninstall failed: boom/);
  assert.equal(existsSync(p.config), true);
  assert.equal(existsSync(statePath('project', p.cwd, p.home)), true);
});

test('--scope user ignores project state; bad scope exits 1', () => {
  const p = project();
  const cli = fakeCli();
  assert.equal(uninstall({ cwd: p.cwd, home: p.home, argv: ['--scope', 'user'], ui: capture().ui, cli }), 0);
  assert.equal(existsSync(statePath('project', p.cwd, p.home)), true);
  assert.equal(uninstall({ cwd: p.cwd, home: p.home, argv: ['--scope', 'x'], ui: capture().ui, cli }), 1);
});

test('partial failure: retry skips the plugin step already done', () => {
  const p = project();
  const cli = fakeCli({ marketplaceRemove: true });
  assert.equal(uninstall({ cwd: p.cwd, home: p.home, ui: capture().ui, cli }), 1);
  assert.equal(JSON.parse(readFileSync(statePath('project', p.cwd, p.home), 'utf8')).addedPlugin, false);
  assert.equal(existsSync(p.config), true);
  const again = fakeCli();
  assert.equal(uninstall({ cwd: p.cwd, home: p.home, ui: capture().ui, cli: again }), 0);
  assert.deepEqual(again.calls, ['marketplaceRemove']);
  assert.equal(existsSync(p.config), false);
});

test('plugin already missing from claude plugin list is not uninstalled again', () => {
  const p = project({ addedMarketplace: false });
  const cli = fakeCli({}, false);
  const o = capture();
  assert.equal(uninstall({ cwd: p.cwd, home: p.home, ui: o.ui, cli }), 0);
  assert.deepEqual(cli.calls, []);
  assert.match(o.out, /already gone/);
});

test('plugin method with addedPlugin false still deletes config and state', () => {
  const p = project({ addedPlugin: false, addedMarketplace: false });
  assert.equal(uninstall({ cwd: p.cwd, home: p.home, ui: capture().ui, cli: fakeCli() }), 0);
  assert.equal(existsSync(p.config), false);
  assert.equal(existsSync(statePath('project', p.cwd, p.home)), false);
});

test('hand-edited state pointing outside setup paths is refused and deletes nothing', () => {
  const p = project({ runtime: undefined });
  const keep = join(p.cwd, 'src.txt');
  writeFileSync(keep, 'mine');
  for (const evil of [{ runtime: p.cwd }, { files: [{ path: keep, sha256: sha256File(keep) }] }, { method: 'settings', settings: { file: keep, hookCommand: 'x' } }]) {
    writeState(statePath('project', p.cwd, p.home), { version: 1, scope: 'project', method: 'plugin', addedMarketplace: false, addedPlugin: false, files: [], settings: null, runtime: null, at: 't', ...evil });
    const cli = fakeCli();
    const o = capture();
    assert.equal(uninstall({ cwd: p.cwd, home: p.home, ui: o.ui, cli }), 1);
    assert.match(o.out, /would not write/);
    assert.deepEqual(cli.calls, []);
    assert.equal(readFileSync(keep, 'utf8'), 'mine');
    assert.equal(existsSync(p.config), true);
    assert.equal(existsSync(statePath('project', p.cwd, p.home)), true);
  }
});

test('invalid settings.json is reported, not "already gone", and nothing is removed', () => {
  const p = project({ method: 'settings', addedPlugin: false, addedMarketplace: false });
  const settingsFile = join(p.cwd, '.claude', 'settings.json');
  writeFileSync(settingsFile, '{ // comment}');
  writeState(statePath('project', p.cwd, p.home), { version: 1, scope: 'project', method: 'settings', addedMarketplace: false, addedPlugin: false, files: [], settings: { file: settingsFile, hookCommand: 'x' }, runtime: null, at: 't' });
  const o = capture();
  assert.equal(uninstall({ cwd: p.cwd, home: p.home, ui: o.ui, cli: fakeCli() }), 1);
  assert.match(o.out, /not plain JSON/);
  assert.equal(existsSync(statePath('project', p.cwd, p.home)), true);
});

test('other scope also recorded: prints the hint', () => {
  const p = project();
  writeState(statePath('user', p.cwd, p.home), { version: 1, scope: 'user', method: 'plugin', addedMarketplace: false, addedPlugin: false, files: [], settings: null, runtime: null, at: 't' });
  const o = capture();
  assert.equal(uninstall({ cwd: p.cwd, home: p.home, ui: o.ui, cli: fakeCli() }), 0);
  assert.match(o.out, /user-scope install also recorded; run: npx @stifler7[/]pinocchio uninstall --scope user/);
});
