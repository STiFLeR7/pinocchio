import { isTestCommand, looksLikeTest } from '../testcmd.js';
import { rel } from '../paths.js';
import { afterLastEdit } from './util.js';

const id = 'stale-tests';

export function staleTests(ctx) {
  const claim = ctx.claims.find((c) => c.type === 'tests');
  if (!claim) return null;
  const { lastEdit, after } = afterLastEdit(ctx.events, ctx.root);
  const bash = after.filter((e) => e.kind === 'bash');
  const lastEditRef = lastEdit ? { file: rel(ctx.root, lastEdit.file), line: lastEdit.line } : null;
  if (bash.some((e) => isTestCommand(e.cmd, ctx.config))) {
    return { id, status: 'pass', blocking: true, summary: 'test command ran after last edit', evidence: { last_edit: lastEditRef } };
  }
  if (!ctx.hasTestSetup) {
    return { id, status: 'unknown', blocking: true, summary: `"${claim.text}": no recognized test command (add yours: .claude/pinocchio.json)`, evidence: { last_edit: lastEditRef } };
  }
  if (bash.some((e) => looksLikeTest(e.cmd))) {
    return { id, status: 'unknown', blocking: true, summary: `"${claim.text}": a test-like command ran but is not recognized`, evidence: { last_edit: lastEditRef } };
  }
  const where = lastEditRef ? `after last edit to ${lastEditRef.file} (L${lastEditRef.line})` : 'in this session';
  return { id, status: 'fail', blocking: true, summary: `"${claim.text}": no test run ${where}`, evidence: { last_edit: lastEditRef, last_test_run: null } };
}
