import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { claudeCli } from '../cli/claude.js';
import { statePath, readState, writeState, sha256File } from '../cli/state.js';

const STUB = fileURLToPath(new URL('./fixtures/stub-claude-cli.mjs', import.meta.url));
const tmp = () => mkdtempSync(join(tmpdir(), 'pino-claude-'));
const logged = (log) => readFileSync(log, 'utf8').trim().split('\n').map((l) => JSON.parse(l));

function withEnv(env, fn) {
  const old = {};
  for (const k of Object.keys(env)) { old[k] = process.env[k]; if (env[k] === undefined) delete process.env[k]; else process.env[k] = env[k]; }
  try { return fn(); } finally { for (const k of Object.keys(old)) { if (old[k] === undefined) delete process.env[k]; else process.env[k] = old[k]; } }
}

test('install runs the exact argv with -y and --json', () => {
  const log = join(tmp(), 'log');
  withEnv({ STUB_LOG: log, STUB_FAIL: undefined }, () => {
    const c = claudeCli({ bin: STUB });
    assert.deepEqual(c.install('user'), { ok: true, json: { ok: true }, stderr: '' });
    c.marketplaceAdd('project'); c.uninstall('user'); c.marketplaceRemove('project'); c.listPlugins(); c.listMarketplaces();
  });
  assert.deepEqual(logged(log), [
    ['plugin', 'install', 'pinocchio@pinocchio', '--scope', 'user', '-y', '--json'],
    ['plugin', 'marketplace', 'add', 'STiFLeR7/pinocchio', '--scope', 'project', '--json'],
    ['plugin', 'uninstall', 'pinocchio@pinocchio', '--scope', 'user', '--json'],
    ['plugin', 'marketplace', 'remove', 'pinocchio', '--scope', 'project', '--json'],
    ['plugin', 'list', '--json'],
    ['plugin', 'marketplace', 'list', '--json'],
  ]);
});

test('failure surfaces ok:false and stderr', () => {
  const r = withEnv({ STUB_FAIL: 'install', STUB_LOG: undefined }, () => claudeCli({ bin: STUB }).install('user'));
  assert.equal(r.ok, false);
  assert.equal(r.json, null);
  assert.match(r.stderr, /install failed/);
});

test('missing bin gives ok:false', () => {
  const r = claudeCli({ bin: join(tmp(), 'nope') }).listPlugins();
  assert.equal(r.ok, false);
  assert.ok(r.stderr);
});

test('.js bin runs through node and listPlugins parses json', () => {
  const dir = tmp();
  const js = join(dir, 'fake.js');
  writeFileSync(js, 'process.stdout.write(JSON.stringify([{id:"x@y"}]));');
  assert.deepEqual(claudeCli({ bin: js }).listPlugins().json, [{ id: 'x@y' }]);
});

test('statePath for both scopes', () => {
  assert.equal(statePath('project', '/p', '/h'), join('/p', '.claude', 'pinocchio-install', 'install.json'));
  assert.equal(statePath('user', '/p', '/h'), join('/h', '.claude', 'pinocchio-install', 'install.json'));
});

test('state round-trips, missing and corrupt read as null', () => {
  const dir = tmp();
  const f = statePath('project', dir);
  assert.equal(readState(f), null);
  const s = { version: 1, scope: 'project', method: 'plugin', addedMarketplace: true, files: [{ path: 'a', sha256: 'b' }], settings: null, at: '2026-10-21T00:00:00.000Z' };
  writeState(f, s);
  assert.deepEqual(readState(f), s);
  writeFileSync(f, '{nope');
  assert.equal(readState(f), null);
  writeFileSync(f, '{"version":2}');
  assert.equal(readState(f), null);
  writeFileSync(f, 'null');
  assert.equal(readState(f), null);
});

test('sha256File hashes content and gives null when missing', () => {
  const f = join(tmp(), 'x');
  writeFileSync(f, 'abc');
  assert.equal(sha256File(f), 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
  assert.equal(sha256File(f + '.none'), null);
});

test('json is parsed from the last line when a note precedes it', () => {
  const js = join(tmp(), 'note.js');
  writeFileSync(js, 'console.log("note"); console.log(JSON.stringify({a:1}));');
  assert.deepEqual(claudeCli({ bin: js }).listPlugins().json, { a: 1 });
});

test('invalid scope throws', () => {
  const c = claudeCli({ bin: STUB });
  for (const bad of ['local', 'x; rm -rf /', undefined]) assert.throws(() => c.install(bad), /invalid scope/);
});
