import { rel } from '../paths.js';
import { narrowing } from '../testcmd.js';
import { afterLastEdit, freshRuns, shortCmd, testRuns } from './util.js';

const id = 'red-tests';
const FAIL_RE = [/\b[1-9]\d* (failed|failing|failures?)\b/i, /^FAILED\b/m, /\bTests?:\s+[1-9]\d* failed/i, /^--- FAIL/m, /test result: FAILED/];

export function redTests(ctx) {
  const tests = ctx.claims.find((c) => c.type === 'tests');
  const fixed = ctx.claims.find((c) => c.type === 'fixed');
  if (!tests && !fixed) return null;
  const claim = tests ?? fixed;
  const { lastEdit, after } = afterLastEdit(ctx.events, ctx.root);
  const gitMs = ctx.gitEditMs ?? -Infinity;
  const { genuine, whole } = testRuns(after, ctx.config);
  const runs = freshRuns(genuine, gitMs);
  const last = runs[runs.length - 1] ?? null;
  const since = Math.max(lastEdit && Number.isFinite(lastEdit.ts) ? lastEdit.ts : 0, last && Number.isFinite(last.ts) ? last.ts : 0, Number.isFinite(gitMs) ? gitMs : 0);
  const badJ = since > 0 ? ctx.findJUnit(since).find((j) => j.mtimeMs > since && j.result.failures + j.result.errors > 0) ?? null : null;
  if (!last && !badJ) {
    if (!tests) return null;
    return { id, status: 'unknown', blocking: true, summary: 'no test run after last edit to read results from', evidence: {} };
  }
  // claims.js marks a claim admitted when the message admits a current failure (admitsFailure).
  // A fixed claim vouched for by a scoped tests phrase ("All unit tests pass") cannot be refuted by the whole suite.
  const admits = claim.admitted === true || claim.except === true;
  const status = admits || claim.scoped ? 'unknown' : 'fail';
  const note = admits ? ' (claim admits failures)' : claim.scoped ? ' (claim covers only some tests)' : '';
  if (last && (last.failed || FAIL_RE.some((r) => r.test(last.output)))) {
    const how = last.failed ? `exited ${last.exitCode}` : 'reported failures';
    return { id, status, blocking: true, summary: `"${claim.text}": ${shortCmd(last.cmd)} ${how} (L${last.line})${note}`, evidence: { test_run: { cmd: shortCmd(last.cmd), line: last.line, exit: last.exitCode } } };
  }
  if (badJ) {
    const { failures, errors } = badJ.result;
    const file = rel(ctx.root, badJ.file);
    return { id, status, blocking: true, summary: `"${claim.text}": ${file} reports ${failures} failures, ${errors} errors${note}`, evidence: { junit: { file, failures, errors } } };
  }
  // A tests claim covers the whole suite: a later passing subset run cannot clear a red full run, nor stand in for one (stale-tests reports that).
  let ok = last;
  if (tests) {
    ok = freshRuns(whole, gitMs).at(-1);
    if (!ok) return null;
    if (ok.failed || FAIL_RE.some((r) => r.test(ok.output))) {
      const how = ok.failed ? `exited ${ok.exitCode}` : 'reported failures';
      const evidence = { test_run: { cmd: shortCmd(ok.cmd), line: ok.line, exit: ok.exitCode } };
      // A later green run of a directory may be most of the suite: not proof the claim is false.
      if (narrowing(last.cmd, ctx.config) === 'dir') {
        return { id, status: 'unknown', blocking: true, summary: `"${claim.text}": ${shortCmd(ok.cmd)} ${how} (L${ok.line}); a later run of one directory passed; run the whole suite`, evidence };
      }
      return { id, status, blocking: true, summary: `"${claim.text}": full suite still red: ${shortCmd(ok.cmd)} ${how} (L${ok.line}); later runs covered only part of the suite${note}`, evidence };
    }
  }
  const passed = /(\d+) pass(ed|ing)?\b/i.exec(ok.output);
  return { id, status: 'pass', blocking: true, summary: `${shortCmd(ok.cmd)} exited 0 after last edit (L${ok.line})${passed ? `, ${passed[1]} passed` : ''}`, evidence: { test_run: { cmd: shortCmd(ok.cmd), line: ok.line, exit: 0 } } };
}
