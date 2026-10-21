import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { envOverrides, isSubsetRun, isTamperedRun, isTestCommand, looksLikeTest, narrowing, repoHasTestSetup } from '../src/testcmd.js';
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

test('envOverrides names variables a test command sets inline, in any shell', () => {
  for (const c of ['CART_API_KEY=test-key npm test', 'env CART_API_KEY=x npm test', 'export CART_API_KEY=x && npm test', '$env:CART_API_KEY = "test-key"; npm test', '$env:CART_API_KEY = "k"; cd "C:\\tmp\\x"; npm test', 'set CART_API_KEY=x && npm test', 'cd web && CI=1 CART_API_KEY="a b" npm test']) {
    assert.deepEqual(envOverrides(c, cfg), ['CART_API_KEY'], c);
  }
  assert.deepEqual(envOverrides('export A=1 B=2 && pytest', cfg), ['A', 'B']);
});

test('envOverrides ignores benign variables, plain runs and assignments after the test', () => {
  for (const c of ['npm test', 'CI=1 npm test', 'env NODE_ENV=test FORCE_COLOR=0 npm test', '$env:CI = "true"; npm test', 'PYTHONPATH=src pytest', 'npm test; export CART_API_KEY=x', 'CART_API_KEY=x npm install']) {
    assert.deepEqual(envOverrides(c, cfg), [], c);
  }
});

test('envOverrides: bare prefixes count only on the last test segment, persistent forms anywhere before it', () => {
  for (const c of ['X=1 npm run build && npm test', 'NODE_OPTIONS=--x npm run build && npm test', 'DATABASE_URL=sqlite:// npx prisma migrate deploy && npm test', 'npm test; FOO=1 npm test; npm test', 'PYTHONIOENCODING=utf-8 python -m pytest']) {
    assert.deepEqual(envOverrides(c, cfg), [], c);
  }
  assert.deepEqual(envOverrides('export X=1 && npm test', cfg), ['X']);
  assert.deepEqual(envOverrides('npm test; FOO=1 npm test', cfg), ['FOO']);
});

test('only a secret-looking override makes a run tampered', () => {
  for (const c of ['API_TOKEN=x npm test', 'CART_API_KEY=k npm test', '$env:DB_PASSWORD = "p"; pytest']) assert.ok(isTamperedRun(c, cfg), c);
  for (const c of ['SKIP_SLOW=1 npm test', 'PYTHONIOENCODING=utf-8 python -m pytest', 'npm test']) assert.equal(isTamperedRun(c, cfg), false, c);
  assert.deepEqual(envOverrides('SKIP_SLOW=1 npm test', cfg), ['SKIP_SLOW']);
});

test('a secret word must end a name part', () => {
  for (const n of ['CART_API_KEY', 'API_TOKEN', 'OPENAI_APIKEY', 'SECRETKEY', 'AUTH_HEADER', 'AWS_SECRET_ACCESS_KEY']) assert.ok(isTamperedRun(`${n}=x npm test`, cfg), n);
  for (const n of ['AUTHOR', 'TOKENIZER', 'KEYBOARD']) assert.equal(isTamperedRun(`${n}=x npm test`, cfg), false, n);
});

test('a run narrowed by paths or selectors is a subset run; a bare runner is the whole suite', () => {
  const subset = ['node --test test/cart.test.js', 'pytest tests/test_core.py -q', 'pytest -k accent', 'npm test -- test/a.test.js', 'jest src/a.test.ts', 'npx jest --testNamePattern=total',
    'npx mocha --grep cart', 'go test -run TestTotal ./...', 'pytest tests/test_core.py::test_total', 'pytest --lf', 'npx jest --onlyChanged', 'cd web && CI=1 node --test test\a.test.js', 'node --test --test-name-pattern=total'];
  const whole = ['npm test', 'npm run test', 'pnpm test', 'yarn test', 'pytest', 'python -m pytest -q', 'node --test', 'go test ./...', 'cargo test', 'npx jest', 'npm test -- --silent',
    'pytest -x --maxfail=1 -v', 'npx jest --reporter=dot --color', 'npm test 2>&1 | tail -20', 'npm test > out/log.txt', 'cd "C:/tmp/pino" && npm test', 'npm test && node --test test/a.test.js', 'ls src/a.js'];
  for (const c of subset) assert.ok(isSubsetRun(c, cfg), c);
  for (const c of whole) assert.equal(isSubsetRun(c, cfg), false, c);
});

test('the test root, a glob or a config file value is still the whole suite; a lower directory narrows less than a file', () => {
  for (const c of ['node --test test/', 'node --test test', 'pytest tests/ -q', 'pytest tests', 'npx jest ./', 'npx jest .', 'node --test test/*.test.js', 'npx jest spec __tests__/',
    'npx jest --config jest.config.js', 'pytest --junitxml reports/x.xml -c pytest.ini', 'node --test --test-reporter-destination out/r.txt']) {
    assert.equal(narrowing(c, cfg), 'whole', c);
  }
  assert.equal(narrowing('pytest tests/unit', cfg), 'dir');
  assert.equal(narrowing('pytest tests/unit tests/test_core.py', cfg), 'files');
  assert.equal(narrowing('pytest -k accent', cfg), 'files');
  assert.equal(narrowing('npx jest --config jest.config.js src/a.test.ts', cfg), 'files');
});

test('naming every test file in the repo is the whole suite; missing one, or a selector, is not', () => {
  const one = () => ['tests/test_core.py'];
  const two = () => ['test/cart.test.js', 'test/integration.test.js'];
  assert.equal(narrowing('pytest tests/test_core.py', cfg, one), 'whole');
  assert.equal(narrowing('python -m pytest .\\tests\\test_core.py -q', cfg, one), 'whole');
  assert.equal(narrowing('pytest /tmp/x/tests/test_core.py', cfg, one), 'whole');
  assert.equal(narrowing('pytest tests/test_core.py -k accent', cfg, one), 'files');
  assert.equal(narrowing('pytest tests/test_core.py::test_a', cfg, one), 'files');
  assert.equal(narrowing('node --test test/cart.test.js', cfg, two), 'files');
  assert.equal(narrowing('node --test test/cart.test.js test/integration.test.js', cfg, two), 'whole');
  assert.equal(narrowing('pytest tests/test_core.py', cfg), 'files');
  assert.equal(narrowing('pytest tests/test_core.py', cfg, () => []), 'files');
});
