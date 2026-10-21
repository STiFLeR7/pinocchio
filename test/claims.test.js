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

test('fixed-width is not a claim', () => {
  assert.deepEqual(types('The fixed-width header looks right.'), []);
});

test('hedged claims are ignored', () => {
  assert.deepEqual(types('This should be fixed by updating the config.'), []);
});

test('done is not in BUILTIN.fixed', () => {
  assert.deepEqual(types("I'm done reading the code."), []);
});

test('negation in one clause does not affect other clauses', () => {
  assert.deepEqual(types('All tests pass, nothing failed.'), ['tests']);
});

test('tests passing is detected', () => {
  assert.deepEqual(types('42 tests passing.'), ['tests']);
});

test('file claims with multiple paths joined by and', () => {
  const c = matchClaims('Updated `parseConfig()` and `src/a.js`.', cfg);
  assert.deepEqual(c.filter((x) => x.type === 'file').map((x) => x.file), ['src/a.js']);
});

test('file claims both path-like files', () => {
  const c = matchClaims('I updated `a.js` and `b.js`.', cfg);
  assert.deepEqual(c.filter((x) => x.type === 'file').map((x) => x.file), ['a.js', 'b.js']);
});

test('file claims must be chained to verb', () => {
  const c = matchClaims('I updated the docs, see `x.js` for context.', cfg);
  assert.deepEqual(c.filter((x) => x.type === 'file').map((x) => x.file), []);
});

test('file claims captures all chained paths', () => {
  const c = matchClaims('I updated `a.js`, `b.js`, and `c.js`.', cfg);
  assert.deepEqual(c.filter((x) => x.type === 'file').map((x) => x.file), ['a.js', 'b.js', 'c.js']);
});

test('file claims stops at unchained backticks', () => {
  const c = matchClaims('I updated `a.js` and then ran `npm test`.', cfg);
  assert.deepEqual(c.filter((x) => x.type === 'file').map((x) => x.file), ['a.js']);
});

test('"nothing" negates and past/report references are not claims', () => {
  assert.deepEqual(types('Nothing was fixed.'), []);
  assert.deepEqual(types('Yes, it was fixed in PR #34 last week.'), []);
  assert.deepEqual(types('That bug is already resolved upstream.'), []);
  assert.deepEqual(types('It got fixed in #12.'), []);
});

test('code spans and quoted strings are not claim phrases', () => {
  assert.deepEqual(types('Set `position: fixed` on the navbar.'), []);
  assert.deepEqual(types('The log line says "all tests pass" on success.'), []);
  assert.deepEqual(matchClaims('I fixed `src/a.js`.', cfg).map((c) => c.file ?? c.type), ['src/a.js', 'fixed']);
});

test('a tests claim followed by "except" is flagged', () => {
  assert.equal(matchClaims('All tests pass except the flaky auth one.', cfg)[0].except, true);
  assert.equal(matchClaims('All tests pass, except one.', cfg)[0].except, true);
  assert.ok(!matchClaims('All tests pass.', cfg)[0].except);
});

test('a bare "Done." or "All done!" is a fixed claim; done mid-sentence is not', () => {
  assert.deepEqual(types('Updated the parser.\nDone.'), ['fixed']);
  assert.deepEqual(types('All done!'), ['fixed']);
  assert.deepEqual(types("I'm done reading the code. Here's what I've done so far."), []);
});

test('"verified the fix" is a fixed claim, "haven\'t verified the fix" is not', () => {
  assert.deepEqual(types('I verified the fix locally.'), ['fixed']);
  assert.deepEqual(types("I haven't verified the fix."), []);
});
