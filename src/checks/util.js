import path from 'node:path';
import { confine } from '../paths.js';
import { isSubsetRun, isTamperedRun, isTestCommand } from '../testcmd.js';

const DOC = /\.(md|mdx|txt|rst)$/i;
export const isDoc = (file) => DOC.test(file);
// Build output and caches are written by tools, not edits by the agent. `file` is relative to the project root.
const ARTIFACT = /^(dist|build|coverage)[\\/]|(^|[\\/])(__pycache__|node_modules|\.pytest_cache|\.mypy_cache)[\\/]|\.pyc$/i;
export const isArtifact = (file) => ARTIFACT.test(file);

// Only edits to non-doc, non-artifact files inside root count; others stay in `after`.
export function afterLastEdit(events, root) {
  let idx = -1;
  events.forEach((e, i) => {
    if (e.kind !== 'edit' || isDoc(e.file)) return;
    const abs = path.resolve(root, e.file);
    if (!isArtifact(path.relative(root, abs)) && confine(root, abs)) idx = i;
  });
  return { lastEdit: idx >= 0 ? events[idx] : null, after: events.slice(idx + 1) };
}

// A run is stale when a git-changed file was written after the run finished
// (resultTs, so files the run itself wrote do not count).
export function freshRuns(runs, gitEditMs = -Infinity) {
  return runs.filter((r) => !(gitEditMs > (Number.isFinite(r.resultTs) ? r.resultTs : r.ts)));
}

// A git-detected change is agent-made only if a Bash command that names the file
// ran after `since` and before the file's mtime; otherwise the user or a background process wrote it.
export function bashBeforeGitEdit(events, gitEdits, since = -Infinity) {
  return gitEdits.some((g) => {
    const name = path.basename(g.file);
    return events.some((e) => e.kind === 'bash' && e.ts > since && g.mtimeMs > e.ts && String(e.cmd).includes(name));
  });
}

// Recognized test runs. A run that sets a secret inline (isTamperedRun) is tampered: not evidence of the real suite.
// `whole` are the genuine runs of the whole suite (not narrowed by isSubsetRun): only they can back "all tests pass".
export function testRuns(events, config) {
  const runs = events.filter((e) => e.kind === 'bash' && isTestCommand(e.cmd, config));
  const tampered = runs.filter((e) => isTamperedRun(e.cmd, config));
  const genuine = runs.filter((e) => !tampered.includes(e));
  return { genuine, whole: genuine.filter((e) => !isSubsetRun(e.cmd, config)), tampered };
}

export function shortCmd(cmd) {
  const one = String(cmd).split('\n')[0].trim().replace(/^(cd|Set-Location)\s+("[^"]*"|'[^']*'|\S+)\s*(&&|;)\s*/i, '');
  return one.length > 60 ? `${one.slice(0, 57)}...` : one;
}
