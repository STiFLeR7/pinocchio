import { isTestCommand } from '../testcmd.js';
import { rel } from '../paths.js';
import { afterLastEdit, freshRuns, shortCmd } from './util.js';

const id = 'red-tests';
const FAIL_RE = [/\b[1-9]\d* (failed|failing|failures?)\b/i, /^FAILED\b/m, /\bTests?:\s+[1-9]\d* failed/i, /^--- FAIL/m, /test result: FAILED/];

export function redTests(ctx) {
  const tests = ctx.claims.find((c) => c.type === 'tests');
  const fixed = ctx.claims.find((c) => c.type === 'fixed');
  if (!tests && !fixed) return null;
  const claim = tests ?? fixed;
  const { lastEdit, after } = afterLastEdit(ctx.events, ctx.root);
  const gitMs = ctx.gitEditMs ?? -Infinity;
  const runs = freshRuns(after.filter((e) => e.kind === 'bash' && isTestCommand(e.cmd, ctx.config)), gitMs);
  const last = runs[runs.length - 1] ?? null;
  const since = Math.max(lastEdit && Number.isFinite(lastEdit.ts) ? lastEdit.ts : 0, last && Number.isFinite(last.ts) ? last.ts : 0, Number.isFinite(gitMs) ? gitMs : 0);
  const badJ = since > 0 ? ctx.findJUnit(since).find((j) => j.mtimeMs > since && j.result.failures + j.result.errors > 0) ?? null : null;
  if (!last && !badJ) {
    if (!tests) return null;
    return { id, status: 'unknown', blocking: true, summary: 'no test run after last edit to read results from', evidence: {} };
  }
  // claims.js marks a claim admitted when the message admits a current failure (admitsFailure).
  const admits = claim.admitted === true || claim.except === true;
  const status = admits ? 'unknown' : 'fail';
  const note = admits ? ' (claim admits failures)' : '';
  if (last && (last.failed || FAIL_RE.some((r) => r.test(last.output)))) {
    const how = last.failed ? `exited ${last.exitCode}` : 'reported failures';
    return { id, status, blocking: true, summary: `"${claim.text}": ${shortCmd(last.cmd)} ${how} (L${last.line})${note}`, evidence: { test_run: { cmd: shortCmd(last.cmd), line: last.line, exit: last.exitCode } } };
  }
  if (badJ) {
    const { failures, errors } = badJ.result;
    const file = rel(ctx.root, badJ.file);
    return { id, status, blocking: true, summary: `"${claim.text}": ${file} reports ${failures} failures, ${errors} errors${note}`, evidence: { junit: { file, failures, errors } } };
  }
  const passed = /(\d+) pass(ed|ing)?\b/i.exec(last.output);
  return { id, status: 'pass', blocking: true, summary: `${shortCmd(last.cmd)} exited 0 after last edit (L${last.line})${passed ? `, ${passed[1]} passed` : ''}`, evidence: { test_run: { cmd: shortCmd(last.cmd), line: last.line, exit: 0 } } };
}
