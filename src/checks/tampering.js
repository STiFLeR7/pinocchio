import fs from 'node:fs';
import path from 'node:path';
import { envOverrides } from '../testcmd.js';
import { afterLastEdit, testRuns } from './util.js';

const id = 'tampering';
const TEST_FILE = /(^|\/)(tests?|__tests__|spec)\/|\.(test|spec)\.[cm]?[jt]sx?$|_test\.(go|py)$|(^|\/)test_[^/]*\.py$/;
const SKIP = /(\.skip\(|\bxit\(|\bxdescribe\(|\bxtest\(|\bit\.todo\(|@pytest\.mark\.skip|\bt\.Skip\(|#\[ignore\]|@Disabled\b|@Ignore\b)/;
const ASSERT = /(\bassert\w*|\bexpect\(|\.should\b|\bt\.(Error|Fatal)|assert!|assert_eq!)/;

export function tampering(ctx) {
  // A test run that set a secret or switch inline after the last edit tested a different environment.
  const { tampered } = testRuns(afterLastEdit(ctx.events, ctx.root).after, ctx.config);
  const overrode = [...new Set(tampered.flatMap((e) => envOverrides(e.cmd, ctx.config)))];
  const findings = overrode.length ? [`test run overrode ${overrode.join(', ')}`] : [];
  if (ctx.git.isRepo) findings.push(...testFileFindings(ctx));
  if (!findings.length) return null;
  const more = findings.length > 2 ? ` (+${findings.length - 2} more)` : '';
  return { id, status: 'warn', blocking: false, summary: `${findings.slice(0, 2).join('; ')}${more} (warn only)`, evidence: { findings } };
}

function testFileFindings(ctx) {
  // Working-tree changes plus test files the session already committed.
  const testFiles = [...new Set([...Object.keys(ctx.git.changed), ...(ctx.git.committed ?? [])])].filter((p) => TEST_FILE.test(p));
  if (!testFiles.length) return [];
  const deleted = (p) => (p in ctx.git.changed ? ctx.git.changed[p].includes('D') : !fs.existsSync(path.join(ctx.git.root, p)));
  const findings = [];
  for (const p of testFiles) if (deleted(p)) findings.push(`${p}: deleted`);
  const perFile = {};
  let current = null;
  for (const l of ctx.gitTestDiff(testFiles.filter((p) => !deleted(p))).split('\n')) {
    const m = /^diff --git a\/.+ b\/(.+)$/.exec(l);
    if (m) {
      current = m[1];
      perFile[current] = { skips: 0, plusAsserts: 0, minusAsserts: 0 };
      continue;
    }
    if (!current || l.startsWith('+++') || l.startsWith('---')) continue;
    if (l.startsWith('+')) {
      if (SKIP.test(l)) perFile[current].skips++;
      if (ASSERT.test(l)) perFile[current].plusAsserts++;
    } else if (l.startsWith('-') && ASSERT.test(l)) perFile[current].minusAsserts++;
  }
  for (const [p, s] of Object.entries(perFile)) {
    if (s.skips) findings.push(`${p}: added skip marker`);
    const removed = s.minusAsserts - s.plusAsserts;
    if (removed > 0) findings.push(`${p}: removed ${removed} assertion${removed === 1 ? '' : 's'}`);
  }
  return findings;
}
