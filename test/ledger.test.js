import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { canonical, appendEntry, readEntries, sessionStats, verifyChain, GENESIS } from '../src/ledger.js';
import { tmpdir } from './helpers.js';

const e = (over = {}) => ({ ts: '2026-10-19T10:00:00Z', session: 's1', verdict: 'pass', blocked: false, ...over });
const file = (cwd) => path.join(cwd, '.claude', 'pinocchio', 'ledger.jsonl');

test('canonical sorts keys recursively', () => {
  assert.equal(canonical({ b: 1, a: { d: 2, c: [3, { f: 4, e: 5 }] }, x: undefined }), '{"a":{"c":[3,{"e":5,"f":4}],"d":2},"b":1}');
});

test('append chains hashes and increments seq', () => {
  const cwd = tmpdir();
  const a = appendEntry(cwd, e());
  const b = appendEntry(cwd, e({ verdict: 'fail', blocked: true }));
  const es = readEntries(cwd);
  assert.equal(es[0].prev, GENESIS);
  assert.equal(es[1].prev, a.hash);
  assert.equal(b.seq, 1);
  assert.deepEqual(verifyChain(cwd), { ok: true, count: 2, brokenAt: null });
});

test('tampering with an entry breaks the chain', () => {
  const cwd = tmpdir();
  appendEntry(cwd, e());
  appendEntry(cwd, e());
  const lines = fs.readFileSync(file(cwd), 'utf8').trim().split('\n');
  lines[0] = lines[0].replace('"pass"', '"fail"');
  fs.writeFileSync(file(cwd), lines.join('\n') + '\n');
  assert.equal(verifyChain(cwd).ok, false);
  assert.equal(verifyChain(cwd).brokenAt, 0);
});

test('sessionStats counts blocks and lies per session', () => {
  const cwd = tmpdir();
  appendEntry(cwd, e({ verdict: 'fail', blocked: true }));
  appendEntry(cwd, e({ verdict: 'fail', blocked: false }));
  appendEntry(cwd, e({ session: 's2', verdict: 'fail', blocked: true }));
  assert.deepEqual(sessionStats(cwd, 's1'), { blocks: 1, lies: 2 });
});

test('writes a self-ignoring .gitignore unless commitLedger', () => {
  const a = tmpdir();
  appendEntry(a, e());
  assert.equal(fs.readFileSync(path.join(a, '.claude', 'pinocchio', '.gitignore'), 'utf8'), '*\n');
  const b = tmpdir();
  appendEntry(b, e(), { commitLedger: true });
  assert.equal(fs.readFileSync(path.join(b, '.claude', 'pinocchio', '.gitignore'), 'utf8'), '');
});

test('rotates past maxBytes and keeps the chain linked', () => {
  const cwd = tmpdir();
  appendEntry(cwd, e(), { maxBytes: 10 });
  const second = appendEntry(cwd, e(), { maxBytes: 10 });
  assert.ok(fs.existsSync(path.join(cwd, '.claude', 'pinocchio', 'ledger.1.jsonl')));
  assert.equal(readEntries(cwd).length, 1);
  assert.equal(second.seq, 1);
  assert.equal(verifyChain(cwd).ok, true);
});

test('unwritable location returns null instead of throwing', () => {
  const cwd = tmpdir();
  fs.writeFileSync(path.join(cwd, '.claude'), 'a file, not a dir');
  assert.equal(appendEntry(cwd, e()), null);
});

test('handles torn last line (no newline at EOF)', () => {
  const cwd = tmpdir();
  const first = appendEntry(cwd, e());
  fs.appendFileSync(file(cwd), '{"v":1,"broken');
  const second = appendEntry(cwd, e({ verdict: 'fail' }));
  const es = readEntries(cwd);
  assert.equal(es.length, 2);
  assert.equal(es[1].prev, first.hash);
  assert.equal(verifyChain(cwd).ok, true);
});

test('strengthened rotation keeps chain linked', () => {
  const cwd = tmpdir();
  const first = appendEntry(cwd, e(), { maxBytes: 10 });
  const second = appendEntry(cwd, e(), { maxBytes: 10 });
  assert.ok(fs.existsSync(path.join(cwd, '.claude', 'pinocchio', 'ledger.1.jsonl')));
  const es = readEntries(cwd);
  assert.equal(es.length, 1);
  assert.equal(es[0].prev, first.hash);
  assert.equal(es[0].seq, 1);
  assert.equal(second.seq, 1);
  assert.equal(verifyChain(cwd).ok, true);
});

test('entry cannot inject hash/prev/seq/v fields', () => {
  const cwd = tmpdir();
  const result = appendEntry(cwd, { ...e(), hash: 'x', prev: 'y', seq: 99, v: 99 });
  assert.ok(result);
  const es = readEntries(cwd);
  assert.equal(es[0].seq, 0);
  assert.equal(es[0].prev, GENESIS);
  assert.equal(es[0].v, 1);
  assert.equal(verifyChain(cwd).ok, true);
});

test('sessionStats survives rotation (reads ledger.1.jsonl too)', () => {
  const cwd = tmpdir();
  appendEntry(cwd, e({ verdict: 'fail', blocked: true }), { maxBytes: 10 });
  appendEntry(cwd, e({ verdict: 'fail', blocked: true }), { maxBytes: 10 });
  assert.ok(fs.existsSync(path.join(cwd, '.claude', 'pinocchio', 'ledger.1.jsonl')));
  assert.deepEqual(sessionStats(cwd, 's1'), { blocks: 2, lies: 2 });
});
