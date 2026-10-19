import path from 'node:path';

export function norm(p) {
  const r = path.resolve(p).replace(/\\/g, '/');
  return process.platform === 'win32' ? r.toLowerCase() : r;
}

export function confine(root, p) {
  const abs = path.resolve(root, p);
  const r = path.relative(root, abs);
  if (r === '..' || r.startsWith(`..${path.sep}`) || path.isAbsolute(r)) return null;
  return abs;
}

export function rel(root, p) {
  const r = path.relative(root, path.resolve(root, p));
  return r && !r.startsWith('..') ? r.replace(/\\/g, '/') : String(p).replace(/\\/g, '/');
}
