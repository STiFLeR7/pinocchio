import { isTestCommand, looksLikeTest } from '../testcmd.js';
import { rel } from '../paths.js';
import { afterLastEdit, freshRuns } from './util.js';

const id = 'stale-tests';

export function staleTests(ctx) {
  const claim = ctx.claims.find((c) => c.type === 'tests');
  if (!claim) return null;
  const { lastEdit, after } = afterLastEdit(ctx.events, ctx.root);
  const gitMs = ctx.gitEditMs ?? -Infinity;
  const bash = after.filter((e) => e.kind === 'bash');
  const gitLast = ctx.gitEdits?.at(-1);
  const lastEditRef = lastEdit ? { file: rel(ctx.root, lastEdit.file), line: lastEdit.line } : gitLast ? { file: gitLast.file, git: true } : null;
  const recognized = bash.filter((e) => isTestCommand(e.cmd, ctx.config));
  if (freshRuns(recognized, gitMs).length) {
    return { id, status: 'pass', blocking: true, summary: 'test command ran after last edit', evidence: { last_edit: lastEditRef } };
  }
  if (!ctx.hasTestSetup) {
    return { id, status: 'unknown', blocking: true, summary: `"${claim.text}": no recognized test command (add yours: .claude/pinocchio.json)`, evidence: { last_edit: lastEditRef } };
  }
  if (bash.some((e) => !isTestCommand(e.cmd, ctx.config) && looksLikeTest(e.cmd))) {
    return { id, status: 'unknown', blocking: true, summary: `"${claim.text}": a test-like command ran but is not recognized`, evidence: { last_edit: lastEditRef } };
  }
  if (!lastEdit && !gitLast) {
    return { id, status: 'unknown', blocking: true, summary: `"${claim.text}": no edits and no test run this session`, evidence: { last_edit: null } };
  }
  if (after.some((e) => e.kind === 'subagent' && !(gitMs > e.ts))) {
    return { id, status: 'unknown', blocking: true, summary: `"${claim.text}": tests may have run in a subagent`, evidence: { last_edit: lastEditRef } };
  }
  let where = 'in this session';
  if (lastEdit) where = `after last edit to ${lastEditRef.file} (L${lastEditRef.line})`;
  else if (gitLast) where = `after ${gitLast.file} changed`;
  return { id, status: 'fail', blocking: true, summary: `"${claim.text}": no test run ${where}`, evidence: { last_edit: lastEditRef, last_test_run: null } };
}
