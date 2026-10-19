import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { parseJUnit, findFreshJUnit } from '../src/junit.js';
import { tmpdir } from './helpers.js';

test('reads testsuites totals', () => {
  assert.deepEqual(parseJUnit('<testsuites tests="5" failures="1" errors="0" skipped="2"><testsuite/></testsuites>'), { tests: 5, failures: 1, errors: 0, skipped: 2 });
});

test('sums testsuite attributes when no totals', () => {
  const x = '<testsuite tests="2" failures="0" errors="1"></testsuite><testsuite tests="3" failures="2"></testsuite>';
  assert.deepEqual(parseJUnit(x), { tests: 5, failures: 2, errors: 1, skipped: 0 });
});

test('falls back to counting tags', () => {
  const x = '<testsuite><testcase/><testcase><failure/></testcase></testsuite>';
  assert.deepEqual(parseJUnit(x), { tests: 2, failures: 1, errors: 0, skipped: 0 });
});

test('non-junit returns null', () => {
  assert.equal(parseJUnit('<html></html>'), null);
  assert.equal(parseJUnit(undefined), null);
});

test('findFreshJUnit only returns files newer than since and skips node_modules', () => {
  const root = tmpdir();
  fs.mkdirSync(path.join(root, 'reports'));
  fs.mkdirSync(path.join(root, 'node_modules'));
  const xml = '<testsuite tests="1" failures="1"></testsuite>';
  fs.writeFileSync(path.join(root, 'reports', 'junit.xml'), xml);
  fs.writeFileSync(path.join(root, 'node_modules', 'junit.xml'), xml);
  const found = findFreshJUnit(root, 0);
  assert.equal(found.length, 1);
  assert.equal(found[0].result.failures, 1);
  assert.equal(findFreshJUnit(root, Date.now() + 60_000).length, 0);
});
