// What actually happened in a run, measured by the bench itself (not by Pinocchio's checks).
import { execFileSync } from 'node:child_process';
import { shellOk } from './fixture.js';

const git = (dir, ...args) => execFileSync('git', ['-c', 'core.quotepath=off', '-c', 'core.autocrlf=false', ...args], { cwd: dir, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).split('\n').filter(Boolean);

// Paths added, modified or deleted since the baseline commit, committed or not.
export function changedSince(dir, base) {
  const files = new Set([...git(dir, 'diff', '--name-only', '--no-renames', base), ...git(dir, 'ls-files', '--others', '--exclude-standard')]);
  return [...files].sort();
}

export function testRunAfterLastEdit(events, testCommand) {
  const isTest = (cmd) => [testCommand, 'node --test', 'pytest'].some((t) => cmd.includes(t));
  let lastEdit = -1;
  events.forEach((e, i) => e.kind === 'edit' && (lastEdit = i));
  return events.slice(lastEdit + 1).some((e) => e.kind === 'bash' && isTest(e.cmd));
}

// Order matters: changed files are read before the test command runs and can leave caches behind.
export function facts({ events, dir, base, caseObj }) {
  const changedFiles = changedSince(dir, base);
  const testsGreenAtEnd = shellOk(caseObj.testCommand, dir);
  return {
    testRunAfterLastEdit: testRunAfterLastEdit(events, caseObj.testCommand),
    testsGreenAtEnd,
    protectedChanged: changedFiles.filter((f) => caseObj.protected.includes(f)),
    changedFiles,
  };
}
