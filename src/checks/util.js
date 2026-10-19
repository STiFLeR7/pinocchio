import path from 'node:path';
import { confine } from '../paths.js';

const DOC = /\.(md|mdx|txt|rst)$/i;
export const isDoc = (file) => DOC.test(file);

// Only edits to non-doc files inside root count; others stay in `after`.
export function afterLastEdit(events, root) {
  let idx = -1;
  events.forEach((e, i) => {
    if (e.kind === 'edit' && !isDoc(e.file) && confine(root, path.resolve(root, e.file))) idx = i;
  });
  return { lastEdit: idx >= 0 ? events[idx] : null, after: events.slice(idx + 1) };
}

// A run is stale when a git-changed file was written after the run finished
// (resultTs, so files the run itself wrote do not count).
export function freshRuns(runs, gitEditMs = -Infinity) {
  return runs.filter((r) => !(gitEditMs > (Number.isFinite(r.resultTs) ? r.resultTs : r.ts)));
}

export function shortCmd(cmd) {
  const one = String(cmd).split('\n')[0].trim();
  return one.length > 60 ? `${one.slice(0, 57)}...` : one;
}
