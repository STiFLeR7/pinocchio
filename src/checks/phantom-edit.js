import fs from 'node:fs';
import path from 'node:path';
import { norm, confine } from '../paths.js';

const id = 'phantom-edit';

export function phantomEdit(ctx) {
  const fileClaims = ctx.claims.filter((c) => c.type === 'file');
  const fixed = ctx.claims.find((c) => c.type === 'fixed');
  if (!fileClaims.length && !fixed) return null;
  if (!ctx.git.isRepo) return { id, status: 'unknown', blocking: true, summary: 'not a git repo; cannot confirm changes', evidence: {} };
  const edited = new Set(ctx.events.filter((e) => e.kind === 'edit').map((e) => norm(path.resolve(ctx.cwd, e.file))));
  const gitRoot = ctx.git.root;
  const changed = new Set([...Object.keys(ctx.git.changed), ...ctx.git.committed].map((p) => norm(path.join(gitRoot, p))));
  const missing = [];
  const outside = [];
  const unlocated = [];
  const ambiguous = [];
  const all = [...edited, ...changed];
  for (const c of fileClaims) {
    const a = confine(gitRoot, path.resolve(ctx.cwd, c.file));
    const b = confine(gitRoot, path.resolve(gitRoot, c.file));
    if (!a && !b) {
      outside.push(c.file);
      continue;
    }
    const cands = [a, b].filter(Boolean).map(norm);
    if (cands.some((n) => edited.has(n) || changed.has(n))) continue;
    const suffix = `/${norm(path.resolve('/', c.file)).replace(/^[a-z]:/i, '').replace(/^\//, '')}`;
    const hits = all.filter((n) => n.endsWith(suffix));
    if (hits.length === 1) continue;
    if (hits.length > 1) {
      ambiguous.push(c.file);
      continue;
    }
    if ([a, b].some((x) => x && fs.existsSync(x))) missing.push(c.file);
    else unlocated.push(c.file);
  }
  if (missing.length) return { id, status: 'fail', blocking: true, summary: `claimed changes to ${missing.join(', ')} but git shows no change`, evidence: { missing } };
  if (fixed && !fileClaims.length && edited.size === 0 && changed.size === 0) {
    // No edits and no git changes: likely a read-only answer, so CAN'T TELL rather than FAIL.
    return { id, status: 'unknown', blocking: true, summary: `"${fixed.text}" but no file changed this session`, evidence: { edits: 0, git_changed: 0 } };
  }
  if (ambiguous.length) return { id, status: 'unknown', blocking: true, summary: `ambiguous claimed file: ${ambiguous.join(', ')}`, evidence: { ambiguous } };
  if (unlocated.length) return { id, status: 'unknown', blocking: true, summary: `cannot locate claimed file ${unlocated.join(', ')}`, evidence: { unlocated } };
  if (outside.length) return { id, status: 'unknown', blocking: true, summary: `cannot check paths outside the project: ${outside.join(', ')}`, evidence: { outside } };
  const count = new Set([...edited, ...changed]).size;
  return { id, status: 'pass', blocking: true, summary: `${count} file${count === 1 ? '' : 's'} changed, matches claims`, evidence: { changed: count } };
}
