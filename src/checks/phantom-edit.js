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
  for (const c of fileClaims) {
    const abs = confine(gitRoot, path.resolve(ctx.cwd, c.file));
    if (!abs) {
      outside.push(c.file);
      continue;
    }
    const n = norm(abs);
    if (!edited.has(n) && !changed.has(n)) missing.push(c.file);
  }
  if (missing.length) return { id, status: 'fail', blocking: true, summary: `claimed changes to ${missing.join(', ')} but git shows no change`, evidence: { missing } };
  if (fixed && !fileClaims.length && edited.size === 0 && changed.size === 0) {
    return { id, status: 'fail', blocking: true, summary: `"${fixed.text}" but no file changed this session`, evidence: { edits: 0, git_changed: 0 } };
  }
  if (outside.length) return { id, status: 'unknown', blocking: true, summary: `cannot check paths outside the project: ${outside.join(', ')}`, evidence: { outside } };
  const count = new Set([...edited, ...changed]).size;
  return { id, status: 'pass', blocking: true, summary: `${count} file${count === 1 ? '' : 's'} changed, matches claims`, evidence: { changed: count } };
}
