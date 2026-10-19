import fs from 'node:fs';
import path from 'node:path';

const NAME = /^(junit.*|TEST-.*|test-results.*|.*junit.*|.*test-report.*)\.xml$/i;
const SKIP_DIRS = new Set(['node_modules', '.git', '.venv', 'venv', '__pycache__', 'target', '.pinocchio', 'dist', 'build', '.next', 'vendor', 'coverage', '.gradle', '.tox', '.mypy_cache', '.pytest_cache']);

export function parseJUnit(xml) {
  if (typeof xml !== 'string' || !/<testsuites?\b/.test(xml)) return null;
  const num = (tag, name) => {
    const m = new RegExp(`\\b${name}="(\\d+)"`).exec(tag);
    return m ? Number(m[1]) : 0;
  };
  const pick = (t) => ({ tests: num(t, 'tests'), failures: num(t, 'failures'), errors: num(t, 'errors'), skipped: num(t, 'skipped') });
  const top = /<testsuites\b[^>]*>/.exec(xml);
  if (top && /\btests="\d+"/.test(top[0])) return pick(top[0]);
  const totals = { tests: 0, failures: 0, errors: 0, skipped: 0 };
  for (const m of xml.matchAll(/<testsuite\b[^>]*>/g)) {
    const p = pick(m[0]);
    for (const k of Object.keys(totals)) totals[k] += p[k];
  }
  if (totals.tests === 0) {
    const count = (re) => (xml.match(re) || []).length;
    return { tests: count(/<testcase\b/g), failures: count(/<failure\b/g), errors: count(/<error\b/g), skipped: count(/<skipped\b/g) };
  }
  return totals;
}

export function findFreshJUnit(root, sinceMs, { maxFiles = 300, maxDepth = 4, maxEntries = 5000 } = {}) {
  const found = [];
  let entries_visited = 0;
  const walk = (dir, depth) => {
    if (depth > maxDepth || entries_visited > maxEntries) return;
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const e of entries) {
      if (entries_visited > maxEntries) return;
      entries_visited++;
      const p = path.join(dir, e.name);
      if (e.isDirectory()) {
        if (!SKIP_DIRS.has(e.name)) walk(p, depth + 1);
      } else if (NAME.test(e.name)) {
        try {
          const st = fs.statSync(p);
          if (st.mtimeMs <= sinceMs || st.size > 20 * 1024 * 1024) continue;
          const result = parseJUnit(fs.readFileSync(p, 'utf8'));
          if (result) found.push({ file: p, mtimeMs: st.mtimeMs, result });
        } catch {
          /* unreadable: ignore */
        }
      }
    }
  };
  walk(root, 0);
  return found;
}
