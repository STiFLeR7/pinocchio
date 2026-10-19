const id = 'tampering';
const TEST_FILE = /(^|\/)(tests?|__tests__|spec)\/|\.(test|spec)\.[cm]?[jt]sx?$|_test\.(go|py)$|(^|\/)test_[^/]*\.py$/;
const SKIP = /(\.skip\(|\bxit\(|\bxdescribe\(|\bxtest\(|\bit\.todo\(|@pytest\.mark\.skip|\bt\.Skip\(|#\[ignore\]|@Disabled\b|@Ignore\b)/;
const ASSERT = /(\bassert\w*|\bexpect\(|\.should\b|\bt\.(Error|Fatal)|assert!|assert_eq!)/;

export function tampering(ctx) {
  if (!ctx.git.isRepo) return null;
  const testFiles = Object.keys(ctx.git.changed).filter((p) => TEST_FILE.test(p));
  if (!testFiles.length) return null;
  const findings = [];
  for (const p of testFiles) if (ctx.git.changed[p].includes('D')) findings.push(`${p}: deleted`);
  const perFile = {};
  let current = null;
  for (const l of ctx.gitTestDiff(testFiles.filter((p) => !ctx.git.changed[p].includes('D'))).split('\n')) {
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
  if (!findings.length) return null;
  const more = findings.length > 2 ? ` (+${findings.length - 2} more)` : '';
  return { id, status: 'warn', blocking: false, summary: `${findings.slice(0, 2).join('; ')}${more} (warn only)`, evidence: { findings } };
}
