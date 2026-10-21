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

test('recognizes additional test runners and wrappers', () => {
  for (const c of ['tox', 'nox -s tests', 'python -m unittest discover', 'python3 -m unittest', 'npm t', 'ctest', 'node --test', 'deno test', 'pnpm vitest', 'poetry run pytest', 'mvn verify', 'env CI=1 npm test', 'time npm test', 'FOO="a b" npm test', 'cd web && (npm test)', 'sudo -E npm test', 'sudo npm test', 'exec npm test', 'command npm test', '(time npm test)', '(env X=1 npm test)']) {
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
  const tox = tmpdir();
  fs.writeFileSync(path.join(tox, 'tox.ini'), '[tox]\n');
  assert.ok(repoHasTestSetup(tox, cfg));
  const setupcfg = tmpdir();
  fs.writeFileSync(path.join(setupcfg, 'setup.cfg'), '[tool:pytest]\n');
  assert.ok(repoHasTestSetup(setupcfg, cfg));
});
