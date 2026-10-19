import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import crypto from 'node:crypto';

const ALLOWED = new Set(['rev-parse', 'status', 'diff', 'log']);

function git(cwd, args) {
  if (!ALLOWED.has(args[0])) throw new Error(`git subcommand not allowed: ${args[0]}`);
  return execFileSync('git', args, { cwd, encoding: 'utf8', timeout: 1500, stdio: ['ignore', 'pipe', 'ignore'], maxBuffer: 8 * 1024 * 1024 });
}

export function readGitState(cwd) {
  try {
    const root = git(cwd, ['rev-parse', '--show-toplevel']).trim();
    let head = null;
    try {
      head = git(cwd, ['rev-parse', '--short', 'HEAD']).trim();
    } catch {
      /* no commits yet */
    }
    const changed = {};
    const parts = git(root, ['status', '--porcelain', '-z', '-uall']).split('\0');
    for (let i = 0; i < parts.length; i++) {
      const e = parts[i];
      if (e.length < 4) continue;
      const status = e.slice(0, 2);
      if (/[RC]/.test(status)) i++; // skip the original path
      const p = e.slice(3);
      if (/(^|\/)\.claude\/pinocchio\//.test(p)) continue; // our own ledger is never evidence
      changed[p] = status.trim() || status;
    }
    return { isRepo: true, root, head, changed };
  } catch {
    return { isRepo: false, root: null, head: null, changed: {} };
  }
}

export function testFileDiff(cwd, files) {
  if (!files.length) return '';
  try {
    return git(cwd, ['diff', '-U0', '--no-ext-diff', '--no-textconv', 'HEAD', '--', ...files]);
  } catch {
    return '';
  }
}

export function committedSince(cwd, sinceMs) {
  try {
    const out = git(cwd, ['log', `--since=@${Math.floor(sinceMs / 1000)}`, '--name-only', '-z', '--format=']);
    return [...new Set(out.split(/[\0\n]/).map((s) => s.trim()).filter(Boolean))];
  } catch {
    return [];
  }
}

export function hashFile(abs) {
  try {
    return `sha256:${crypto.createHash('sha256').update(fs.readFileSync(abs)).digest('hex')}`;
  } catch {
    return null;
  }
}
