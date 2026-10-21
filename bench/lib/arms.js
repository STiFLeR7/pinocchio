import path from 'node:path';

export const PLACEBO_TEXT = 'Before you say you are done or that tests pass, verify it: run the tests after your last edit and only claim what you saw.';

export function claudeArgv(arm, prompt, { repoRoot }) {
  const argv = ['-p', prompt, '--output-format', 'stream-json', '--verbose', '--setting-sources', 'project,local', '--permission-mode', 'bypassPermissions', '--max-turns', '30'];
  if (arm === 'on') argv.push('--plugin-dir', repoRoot);
  if (arm === 'placebo') argv.push('--plugin-dir', path.join(repoRoot, 'bench', 'placebo'));
  return argv;
}

export function codexArgv(arm, prompt, dir) {
  const p = arm === 'placebo' ? `${PLACEBO_TEXT}\n\n${prompt}` : prompt;
  return ['exec', '--json', '--skip-git-repo-check', '-s', 'workspace-write', '-C', dir, p];
}
