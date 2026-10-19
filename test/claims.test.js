import { test } from 'node:test';
import assert from 'node:assert/strict';
import { matchClaims } from '../src/claims.js';
import { loadConfig } from '../src/config.js';
import { tmpdir } from './helpers.js';

const cfg = loadConfig(tmpdir());
const types = (t, c = cfg) => matchClaims(t, c).map((x) => x.type);

test('detects tests and fixed claims', () => {
  assert.deepEqual(types('I fixed the bug. All tests pass.'), ['fixed', 'tests']);
});

test('detects file claims in backticks', () => {
  const c = matchClaims('I updated `src/auth.ts` and changed `README.md`.', cfg);
  assert.deepEqual(c.filter((x) => x.type === 'file').map((x) => x.file), ['src/auth.ts', 'README.md']);
});

test('negated sentences are ignored (Review Focus 3)', () => {
  assert.deepEqual(types("The tests don't pass yet."), []);
  assert.deepEqual(types("I haven't run the tests, so I can't say they pass."), []);
  assert.deepEqual(types('This is not fixed.'), []);
});

test('phrase must be a whole word', () => {
  assert.deepEqual(types('I am prefixed with nothing.'), []);
});

test('custom phrases from config', () => {
  const c = { ...cfg, claimPhrases: { tests: ['ci is green'], fixed: [] } };
  assert.deepEqual(types('CI is green now.', c), ['tests']);
});

test('empty or non-string input', () => {
  assert.deepEqual(matchClaims('', cfg), []);
  assert.deepEqual(matchClaims(undefined, cfg), []);
});
