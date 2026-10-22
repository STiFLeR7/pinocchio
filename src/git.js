import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import crypto from 'node:crypto';
import path from 'node:path';

const ALLOWED = new Set(['rev-parse', 'status', 'diff', 'log', 'ls-files']);

function git(cwd, args) {
  if (!ALLOWED.has(args[0])) throw new Error(`git subcommand not allowed: ${args[0]}`);
  // A repo-configured fsmonitor is a command git would run for us: never let it.
  return execFileSync('git', ['-c', 'core.fsmonitor=false', ...args], { cwd, encoding: 'utf8', timeout: 1500, stdio: ['ignore', 'pipe', 'ignore'], maxBuffer: 8 * 1024 * 1024 });
}

export function readGitState(cwd) {
  try {
    // Resolve the root from cwd as spelled, not git's real path: a symlinked
    // or 8.3 cwd (macOS /var, Windows RUNNER~1) must match transcript paths.
    const root = path.resolve(cwd, git(cwd, ['rev-parse', '--show-cdup']).trim() || '.');
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

// Tracked and untracked (not ignored) files matching re, repo-relative.
export function listFiles(root, re) {
  try {
    return git(root, ['ls-files', '-z', '--cached', '--others', '--exclude-standard']).split('\0').filter((p) => p && re.test(p));
  } catch {
    return [];
  }
}

// base: the commit the session started from, so test changes committed mid-session still show.
export function testFileDiff(cwd, files, base = 'HEAD') {
  if (!files.length) return '';
  try {
    return git(cwd, ['diff', '-U0', '--no-ext-diff', '--no-textconv', base, '--', ...files]);
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

// Parent of the oldest commit made since sinceMs, or HEAD when the session made none.
export function sessionBase(cwd, sinceMs) {
  try {
    const first = git(cwd, ['log', `--since=@${Math.floor(sinceMs / 1000)}`, '--reverse', '--format=%H']).split('\n')[0].trim();
    if (!first) return 'HEAD';
    return git(cwd, ['rev-parse', '--verify', '-q', `${first}^`]).trim() || 'HEAD';
  } catch {
    return 'HEAD';
  }
}

export function hashFile(abs) {
  try {
    return `sha256:${crypto.createHash('sha256').update(fs.readFileSync(abs)).digest('hex')}`;
  } catch {
    return null;
  }
}
