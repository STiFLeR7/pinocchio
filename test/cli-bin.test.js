import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const BIN = fileURLToPath(new URL('../bin/pinocchio.js', import.meta.url));
const pkg = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'));
const run = (...args) => spawnSync(process.execPath, [BIN, ...args], { encoding: 'utf8' });

test('bin --version prints package version', () => {
  const r = run('--version');
  assert.equal(r.status, 0);
  assert.equal(r.stdout.trim(), pkg.version);
});

test('bin unknown command exits 1 with usage', () => {
  const r = run('frobnicate');
  assert.equal(r.status, 1);
  assert.match(r.stderr, /Unknown command: frobnicate/);
  assert.match(r.stderr, /Usage: pinocchio/);
});

test('bin --help prints usage and exits 0', () => {
  const r = run('--help');
  assert.equal(r.status, 0);
  assert.match(r.stdout, /uninstall/);
});

test('bin propagates a command exit code', () => {
  const r = run('uninstall', '--scope', 'bogus');
  assert.equal(r.status, 1);
  assert.match(r.stdout, /--scope must be project or user/);
});

test('package.json wires the bin and ships bin/ and cli/', () => {
  assert.equal(pkg.bin.pinocchio, 'bin/pinocchio.js');
  assert.ok(pkg.files.includes('bin') && pkg.files.includes('cli'));
});
