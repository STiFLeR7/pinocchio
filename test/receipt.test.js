import { test } from 'node:test';
import assert from 'node:assert/strict';
import { decide, orderResults } from '../src/verdict.js';
import { formatReceipt, formatReason } from '../src/receipt.js';

const fail = { id: 'stale-tests', status: 'fail', blocking: true, summary: '"tests pass": no test run after last edit to src/a.js (L3)', evidence: {} };
const pass = { id: 'phantom-edit', status: 'pass', blocking: true, summary: '1 file changed, matches claims', evidence: {} };
const unk = { id: 'stale-tests', status: 'unknown', blocking: true, summary: 'no recognized test command', evidence: {} };
const warn = { id: 'tampering', status: 'warn', blocking: false, summary: 'a.test.js: added skip marker (warn only)', evidence: {} };
const claims = [{ type: 'tests', text: 'tests pass' }];
const HASH = 'sha256:a41f' + '0'.repeat(60);

test('decide', () => {
  assert.equal(decide([pass, fail], claims), 'fail');
  assert.equal(decide([pass, unk], claims), 'cant_tell');
  assert.equal(decide([pass, warn], claims), 'pass');
  assert.equal(decide([], []), 'pass');
});

test('orderResults puts failures first', () => {
  assert.deepEqual(orderResults([pass, warn, fail]).map((r) => r.status), ['fail', 'warn', 'pass']);
});

test('FAIL receipt shape', () => {
  const r = formatReceipt({ verdict: 'fail', results: [fail, pass, warn], claims, sessionLies: 1, blocked: true, blocksInSession: 1, maxBlocks: 2, limitReached: false, ledgerHash: HASH, notes: [] });
  const lines = r.split('\n');
  assert.equal(lines[0], '🤥 Pinocchio · FAIL · nose +1 (session: 1 lie caught)');
  assert.match(lines[1], /✗ stale-tests/);
  assert.match(r, /ledger #a41f… · blocked 1\/2/);
  assert.ok(lines.length <= 6);
});

test('PASS with no claims and limit-reached note', () => {
  assert.match(formatReceipt({ verdict: 'pass', results: [], claims: [], sessionLies: 0, blocked: false, blocksInSession: 0, maxBlocks: 2, limitReached: false, ledgerHash: null, notes: [] }), /PASS · no claims made[\s\S]*ledger unavailable/);
  assert.match(formatReceipt({ verdict: 'fail', results: [fail], claims, sessionLies: 3, blocked: false, blocksInSession: 2, maxBlocks: 2, limitReached: true, ledgerHash: HASH, notes: [] }), /stopped blocking \(limit reached\)/);
});

test('reason quotes the failed evidence', () => {
  const r = formatReason([fail, pass]);
  assert.match(r, /stale-tests: "tests pass": no test run after last edit/);
  assert.doesNotMatch(r, /phantom-edit/);
});

const base = { claims, sessionLies: 0, blocked: false, blocksInSession: 0, maxBlocks: 2, limitReached: false, ledgerHash: HASH, notes: [] };

test('receipt orders results itself: a fail passed last still shows, within 6 lines', () => {
  const p = (i) => ({ ...pass, id: `p${i}` });
  const r = formatReceipt({ ...base, verdict: 'fail', results: [p(1), p(2), p(3), p(4), p(5), fail] });
  assert.match(r, /✗ stale-tests/);
  assert.ok(r.split('\n').length <= 6);
});

test('receipt collapses newlines and truncates long summaries and notes', () => {
  const nl = { ...fail, summary: 'line one\nline two\n\nline three' };
  const long = { ...pass, summary: 'y'.repeat(300) };
  const r = formatReceipt({ ...base, verdict: 'fail', results: [nl, long, nl, nl], notes: ['n\no' + 'z'.repeat(300)] });
  const lines = r.split('\n');
  assert.ok(lines.length <= 6);
  assert.match(r, /line one line two line three/);
  assert.ok(lines.every((l) => l.length <= 160 + 4), lines.map((l) => l.length).join());
  assert.match(r, /y…/);
});

test("cant_tell head and blocked tail", () => {
  const r = formatReceipt({ ...base, verdict: 'cant_tell', results: [unk], blocked: true, blocksInSession: 1 });
  assert.equal(r.split('\n')[0], "🤥 Pinocchio · CAN'T TELL");
  assert.match(r, /blocked 1\/2/);
});

test('reason lists unknown checks when nothing failed, with a check-specific hint', () => {
  const r = formatReason([unk, pass]);
  assert.match(r, /could not verify: stale-tests: no recognized test command/);
  assert.match(r, /run the tests/);
  assert.doesNotMatch(r, /\. \./);
  const ph = formatReason([{ id: 'phantom-edit', status: 'fail', blocking: true, summary: 'claimed changes to a.js but git shows no change', evidence: {} }]);
  assert.match(ph, /make the change or correct the claim/);
  assert.doesNotMatch(ph, /run the tests/);
});
