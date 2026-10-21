import { test } from 'node:test';
import { spawnSync } from 'node:child_process';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { checkSystem, detectTests } from '../cli/detect.js';

const tmp = () => mkdtempSync(join(tmpdir(), 'pino-detect-'));

test('node below 18 is not ok', () => {
  const s = checkSystem({ run: (c) => (c === 'node' ? 'v16.20.0' : 'x 1.0') });
  assert.equal(s.node.ok, false);
  assert.equal(s.node.version, 'v16.20.0');
  assert.equal(s.git.ok, true);
});

test('missing claude gives ok:false', () => {
  const s = checkSystem({ run: (c) => (c === 'claude' ? null : 'v22.1.0') });
  assert.deepEqual(s.claude, { ok: false, version: null });
  assert.equal(s.node.ok, true);
});

test('detects npm, pytest, go, cargo, make in one dir', () => {
  const d = tmp();
  writeFileSync(join(d, 'package.json'), JSON.stringify({ scripts: { test: 'node --test' } }));
  writeFileSync(join(d, 'pyproject.toml'), '[tool.pytest.ini_options]\n');
  writeFileSync(join(d, 'go.mod'), 'module x\n');
  writeFileSync(join(d, 'Cargo.toml'), '[package]\n');
  writeFileSync(join(d, 'Makefile'), 'build:\n\tx\ntest:\n\ty\n');
  const r = detectTests(d);
  assert.deepEqual(r.map((x) => x.command), ['npm test', 'pytest', 'go test ./...', 'cargo test', 'make test']);
  assert.deepEqual(r.map((x) => x.file), ['package.json', 'pyproject.toml', 'go.mod', 'Cargo.toml', 'Makefile']);
  assert.deepEqual(r.map((x) => x.regex), [
    String.raw`^npm (run )?test\b`, String.raw`\bpytest\b`, String.raw`^go test\b`, String.raw`^cargo test\b`, String.raw`^make test\b`,
  ]);
  assert.ok(new RegExp(r[0].regex).test('npm run test'));
});

test('default npm test script is ignored', () => {
  const d = tmp();
  writeFileSync(join(d, 'package.json'),
    JSON.stringify({ scripts: { test: 'echo "Error: no test specified" && exit 1' } }));
  assert.deepEqual(detectTests(d), []);
});

test('empty dir gives []', () => {
  assert.deepEqual(detectTests(tmp()), []);
});

test('real spawnVersion prints no DEP0190 warning', () => {
  const url = new URL('../cli/detect.js', import.meta.url).href;
  const r = spawnSync(process.execPath, ['-e', `import(${JSON.stringify(url)}).then(m => console.log(m.spawnVersion('node')))`], { encoding: 'utf8' });
  assert.match(r.stdout, /^v\d+/);
  assert.ok(!r.stderr.includes('DEP0190'), r.stderr);
});

test('Makefile test-unit and test := are not a test target', () => {
  const d = tmp();
  writeFileSync(join(d, 'Makefile'), 'test-unit:\n\tx\n');
  assert.deepEqual(detectTests(d), []);
  writeFileSync(join(d, 'Makefile'), 'test := foo\n');
  assert.deepEqual(detectTests(d), []);
});

test('pyproject containing only pytest is detected', () => {
  const d = tmp();
  writeFileSync(join(d, 'pyproject.toml'), 'dependencies = ["pytest"]\n');
  assert.equal(detectTests(d)[0].command, 'pytest');
});
