import { envOverrides, isTestCommand, looksLikeTest } from '../testcmd.js';
import { rel } from '../paths.js';
import { afterLastEdit, bashBeforeGitEdit, freshRuns, shortCmd, testRuns } from './util.js';

const id = 'stale-tests';

export function staleTests(ctx) {
  const claim = ctx.claims.find((c) => c.type === 'tests');
  if (!claim) return null;
  const { lastEdit, after } = afterLastEdit(ctx.events, ctx.root);
  const gitMs = ctx.gitEditMs ?? -Infinity;
  const bash = after.filter((e) => e.kind === 'bash');
  const gitLast = ctx.gitEdits?.at(-1);
  const lastEditRef = lastEdit ? { file: rel(ctx.root, lastEdit.file), line: lastEdit.line } : gitLast ? { file: gitLast.file, git: true } : null;
  const { genuine: recognized, whole, tampered } = testRuns(bash, ctx.config, ctx.testFiles);
  if (freshRuns(whole, gitMs).length) {
    return { id, status: 'pass', blocking: true, summary: 'test command ran after last edit', evidence: { last_edit: lastEditRef } };
  }
  // Only subset runs (one file, a -k selector): not evidence for a whole-suite claim, nor proof that it is false.
  const subset = freshRuns(recognized, gitMs).at(-1);
  if (subset) {
    return { id, status: 'unknown', blocking: true, summary: `"${claim.text}": only part of the suite ran after last edit (${shortCmd(subset.cmd)}, L${subset.line}); run the whole suite`, evidence: { last_edit: lastEditRef } };
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
  // Only git saw the edit (no transcript edit, no Bash after the run): not proof the agent edited.
  const lastRun = recognized.at(-1);
  const since = lastRun ? (Number.isFinite(lastRun.resultTs) ? lastRun.resultTs : lastRun.ts) : -Infinity;
  if ((lastRun || !lastEdit) && !bashBeforeGitEdit(after, ctx.gitEdits ?? [], since)) {
    return { id, status: 'unknown', blocking: true, summary: `"${claim.text}": files changed after the last test run, but not by a tool call this session`, evidence: { last_edit: lastEditRef } };
  }
  let where = 'in this session';
  if (lastEdit) where = `after last edit to ${lastEditRef.file} (transcript line ${lastEditRef.line})`;
  else if (gitLast) where = `after ${gitLast.file} changed`;
  const overrode = tampered.length ? ` (last run overrode ${envOverrides(tampered.at(-1).cmd, ctx.config).join(', ')})` : '';
  const status = claim.admitted ? 'unknown' : 'fail';
  return { id, status, blocking: true, summary: `"${claim.text}": no ${tampered.length ? 'genuine ' : ''}test run ${where}${overrode}${claim.admitted ? ' (claim admits failures)' : ''}`, evidence: { last_edit: lastEditRef, last_test_run: null } };
}
