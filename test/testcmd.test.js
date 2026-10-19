import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { isTestCommand, looksLikeTest, repoHasTestSetup } from '../src/testcmd.js';
import { loadConfig } from '../src/config.js';
import { tmpdir } from './helpers.js';

const cfg = loadConfig(tmpdir());

test('recognizes common runners, chains and env prefixes', () => {
  for (const c of ['npm test', 'npm run test:unit', 'pnpm test', 'npx vitest run', 'pytest -q', 'python -m pytest', 'uv run pytest', 'go test ./...', 'cargo test', 'make test', 'cd web && npm test', 'CI=1 npm test']) {
    assert.ok(isTestCommand(c, cfg), c);
  }
});

test('does not treat unrelated commands as tests', () => {
  for (const c of ['npm install', 'git status', 'ls test/', 'cat tests.md']) assert.equal(isTestCommand(c, cfg), false, c);
});

test('custom testCommands', () => {
  assert.ok(isTestCommand('./run-all.sh', { ...cfg, testCommands: [/^\.\/run-all\.sh$/] }));
});

test('looksLikeTest flags unrecognized test-ish commands', () => {
  assert.ok(looksLikeTest('node scripts/run-tests.js'));
  assert.equal(looksLikeTest('git status'), false);
});

test('repoHasTestSetup detects ecosystems', () => {
  const none = tmpdir();
  assert.equal(repoHasTestSetup(none, cfg), false);
  const js = tmpdir();
  fs.writeFileSync(path.join(js, 'package.json'), JSON.stringify({ scripts: { test: 'vitest' } }));
  assert.ok(repoHasTestSetup(js, cfg));
  const stub = tmpdir();
  fs.writeFileSync(path.join(stub, 'package.json'), JSON.stringify({ scripts: { test: 'echo "Error: no test specified" && exit 1' } }));
  assert.equal(repoHasTestSetup(stub, cfg), false);
  const go = tmpdir();
  fs.writeFileSync(path.join(go, 'go.mod'), 'module x\n');
  assert.ok(repoHasTestSetup(go, cfg));
  const py = tmpdir();
  fs.writeFileSync(path.join(py, 'pyproject.toml'), '[tool.pytest.ini_options]\n');
  assert.ok(repoHasTestSetup(py, cfg));
});
